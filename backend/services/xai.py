import re

from services.query_strategies import StrategyDecorator, _clean_answer

_TRACE_SEP = "=" * 80


# Appended to the question so the model cites verbatim fragments that can be verified afterwards.
CITATION_INSTRUCTION = (
    "\n\nIMPORTANT: For each statement, cite the exact source fragment "
    "like this: [Source: <verbatim text copied from context>]"
)


def _citation_in_chunks(citation: str, source_texts: list, threshold: float = 0.6) -> bool:
    '''
        Returns True if ≥threshold fraction of citation words appear in any chunk.
        Punctuation is stripped before comparison to avoid false mismatches (e.g. commas vs semicolons).
    '''
    clean = lambda text: re.sub(r'[^\w\s]', '', text.lower())
    citation_words = set(clean(citation).split())
    if not citation_words:
        return False
    for chunk in source_texts:
        chunk_words = set(clean(chunk).split())
        overlap = len(citation_words & chunk_words) / len(citation_words)
        if overlap >= threshold:
            return True
    return False


def _check_citations(rag_answer: str, source_texts: list):
    '''
        Centralised citation check used by the feedback loop.
        Returns (all_citations, bad_citations, hallucinations_count).
        hallucinations=-2 when model produced no [Source:] tags at all.
    '''
    citations = re.findall(r'\[Source:(.*?)\]', rag_answer)
    real = [c for c in citations if "verbatim text copied from context" not in c]
    if not real:
        return [], [], -2
    bad = [c for c in real if not _citation_in_chunks(c, source_texts)]
    return real, bad, len(bad)


def _refine_answer(llm, question: str, source_texts: list) -> str:
    '''Re-prompts the LLM with raw chunks when citations fail verification (Phase 6).'''
    chunks_str    = "\n---\n".join(source_texts)
    refine_prompt = (
        f"Question: {question}\n\n"
        f"Context fragments:\n{chunks_str}\n\n"
        f"Answer the question using ONLY these fragments. "
        f"Cite each one like [Source: <verbatim text copied from context>]."
    )
    return _clean_answer(llm.complete(refine_prompt))


def _xai_feedback_loop(rag_answer: str, source_texts: list, llm, question: str,
                        max_refine: int = 2):
    '''
        Implements the Phase 5→6 check→refine loop.
        Returns (final_answer, citations, hallucinations_count, process_log).
        process_log records every intermediate attempt for the XAI trace.
    '''
    citations    = []
    hallucinations = -1
    process_log  = []

    for attempt in range(max_refine + 1):
        # ─── FASE 5: Feedback on Clarity ─────────────────────────────────
        citations, bad_citations, hallucinations = _check_citations(rag_answer, source_texts)

        needs_refine = hallucinations != 0  # -2 = no citations; >0 = bad citations

        if not needs_refine:
            process_log.append({
                "attempt":       attempt,
                "hallucinations": hallucinations,
                "bad_citations": bad_citations,
                "action":        "accepted"
            })
            break

        if attempt == max_refine or not llm:
            action = "exhausted" if attempt == max_refine else "no_llm"
            process_log.append({
                "attempt":        attempt,
                "hallucinations": hallucinations,
                "bad_citations":  bad_citations,
                "action":         action
            })
            break

        # ─── FASE 6: Refine Explainability ───────────────────────────────
        process_log.append({
            "attempt":        attempt,
            "hallucinations": hallucinations,
            "bad_citations":  bad_citations,
            "action":         "refined"
        })
        rag_answer = _refine_answer(llm, question, source_texts)

    return rag_answer, citations, hallucinations, process_log


_ACTION_LABELS = {
    "accepted":  "→ answer accepted ✅",
    "refined":   "→ REFINEMENT triggered 🔄",
    "exhausted": "→ max refinements reached ⛔",
    "no_llm":    "→ no LLM available ⛔",
}


def _format_process_entry(entry: dict) -> str:
    """Formats a single process log entry as a human-readable string."""
    attempt, h, action = entry["attempt"], entry["hallucinations"], entry["action"]
    if h == -2:
        status = f"  Attempt {attempt}: no citations found"
    elif h == 0:
        status = f"  Attempt {attempt}: 0 unverified citations"
    else:
        status = f"  Attempt {attempt}: {h} unverified citation(s) detected"
    return f"{status} {_ACTION_LABELS.get(action, '')}"


def _write_process_log(log, process_log: list):
    """Writes the Phase 5-6 process log section to the XAI trace file."""
    log.write("\nPROCESS LOG (Phases 5 & 6):\n")
    for entry in process_log:
        log.write(f"{_format_process_entry(entry)}\n")
        for bc in entry["bad_citations"]:
            log.write(f"    ⚠️  HALLUCINATION: [Source:{bc.strip()}]\n")

    intermediate_hallucinations = sum(
        e["hallucinations"] for e in process_log
        if e["hallucinations"] > 0
    )
    if intermediate_hallucinations > 0:
        fixed = process_log[-1]["hallucinations"] == 0
        status = "fixed by refinement ✅" if fixed else "NOT fixed ❌"
        log.write(f"\n  ⚠️  {intermediate_hallucinations} intermediate hallucination(s) detected — {status}\n")


def _write_citations_section(log, citations: list, source_texts: list):
    """Writes the citations verification summary to the XAI trace file."""
    log.write("\nCITATIONS FOUND IN ANSWER:\n")
    if citations:
        for citation in citations:
            found  = _citation_in_chunks(citation, source_texts)
            status = "✅ FOUND IN CHUNKS" if found else "❌ NOT FOUND — HALLUCINATION"
            log.write(f"  [{status}] {citation.strip()}\n")
    else:
        log.write("  No citations found — COMPLIANCE FAILURE\n")


def _write_xai_trace(log_path: str, exec_num: int, q_idx: int, question: str,
                     rag_answer: str, hallucinations: int,
                     response, source_texts: list, citations: list,
                     process_log: list):
    """Appends a full XAI trace entry for one question to the log file."""
    mode = 'w' if (exec_num == 1 and q_idx == 0) else 'a'
    with open(log_path, mode, encoding='utf-8') as log:
        log.write(f"\n{_TRACE_SEP}\n")
        log.write(f"EXEC {exec_num} | QUESTION {q_idx + 1}: {question}\n")
        log.write(f"{_TRACE_SEP}\n")

        _write_process_log(log, process_log)

        log.write(f"\nFINAL ANSWER:\n{rag_answer}\n")
        if hallucinations == -2:
            log.write("\nHALLUCINATIONS DETECTED (final): INDETERMINATE (model did not cite)\n")
        else:
            log.write(f"\nHALLUCINATIONS DETECTED (final): {hallucinations}\n")

        log.write(f"\nRETRIEVED CHUNKS ({len(source_texts)} total):\n")
        for j, (node, text) in enumerate(zip(response.source_nodes, source_texts)):
            log.write(f"\n  --- CHUNK {j + 1} | Score: {node.score:.3f} ---\n")
            log.write(f"  {text}\n")

        _write_citations_section(log, citations, source_texts)


class XAIResponse:
    """Response of an XAI-decorated strategy: the inner response plus the verification report."""
    def __init__(self, inner, citations: list, hallucinations: int, process_log: list):
        self.inner          = inner
        self.source_nodes   = inner.source_nodes
        self.citations      = citations
        self.hallucinations = hallucinations
        self.process_log    = process_log


class XAIDecorator(StrategyDecorator):
    """Explainable RAG (phases 3-6): asks for citations, verifies them against the retrieved chunks and
    re-prompts up to max_refine times if any is not found. Wraps any QueryStrategy. Evaluation only:
    the answer is flattened (_clean_answer) before the citations are checked."""

    def __init__(self, inner, max_refine: int = 2):
        super().__init__(inner)
        self.max_refine = max_refine

    def execute(self, query_engine, question: str, llm, synthesis_question: str = None,
                answer_instruction: str = '') -> tuple:
        # The citation request goes to the model that writes the answer, never into the retrieval query
        answer, response = self.inner.execute(query_engine, question, llm, synthesis_question=synthesis_question,
                                              answer_instruction=answer_instruction + CITATION_INSTRUCTION)
        source_texts = [node.text for node in response.source_nodes]
        answer, citations, hallucinations, process_log = _xai_feedback_loop(
            _clean_answer(answer), source_texts, llm, question, self.max_refine
        )
        return answer, XAIResponse(response, citations, hallucinations, process_log)
