from abc import ABC, abstractmethod

from llama_index.core import QueryBundle

_SELF_RAG_DEBUG = True  # set to False to disable Self-RAG evaluation logging


def _clean_answer(text) -> str:
    return str(text).strip().replace('\n', ' ').replace(';', ',')


def _generate_hypothetical(question: str, llm) -> str:
    return str(llm.complete(
        f"Write a short, factual answer to the following question based on your knowledge:"
        f"\n\nQuestion: {question}\n\nAnswer:"
    )).strip()


class _CRAGResponse:
    """Minimal response wrapper so CRAG output is compatible with _write_xai_trace."""
    def __init__(self, nodes):
        self.source_nodes = nodes


class QueryStrategy(ABC):
    @abstractmethod
    def build_query(self, question: str, llm) -> object:
        """Returns a str (naive) or QueryBundle (HyDE) for the retriever."""

    def execute(self, query_engine, question: str, llm, synthesis_question: str = None) -> tuple:
        synthesis_question = synthesis_question or question
        query = self.build_query(question, llm)
        if isinstance(query, QueryBundle):
            query = QueryBundle(query_str=synthesis_question, custom_embedding_strs=query.custom_embedding_strs)
        else:
            query = synthesis_question
        response = query_engine.query(query)
        answer = _clean_answer(response)
        return answer, response


class NaiveStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> str:
        return question


class HyDEAnswerStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> QueryBundle:
        hypothetical = _generate_hypothetical(question, llm)
        return QueryBundle(query_str=question, custom_embedding_strs=[hypothetical])


class HyDECombinedStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> QueryBundle:
        hypothetical = _generate_hypothetical(question, llm)
        return QueryBundle(query_str=question, custom_embedding_strs=[question, hypothetical])


class CRAGStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> str:
        return question  # unused — execute() is fully overridden

    def execute(self, query_engine, question: str, llm, synthesis_question: str = None) -> tuple:
        synthesis_question = synthesis_question or question

        nodes = query_engine.retriever.retrieve(question)

        relevant = [n for n in nodes if self._grade(n.text, question, llm) != 'IRRELEVANT']
        if not relevant:
            relevant = nodes  # fallback: use everything if nothing passed

        chunks = "\n---\n".join(n.text for n in relevant)
        prompt = f"Context:\n{chunks}\n\nQuestion: {synthesis_question}\n\nAnswer:"
        answer = _clean_answer(llm.complete(prompt))
        return answer, _CRAGResponse(relevant)

    def _grade(self, chunk: str, question: str, llm) -> str:
        prompt = (
            f"Is the following text relevant to answer the question?\n\n"
            f"Question: {question}\n\nText: {chunk}\n\n"
            f"Reply with exactly one word: RELEVANT, AMBIGUOUS, or IRRELEVANT."
        )
        grade = str(llm.complete(prompt)).strip().upper()
        if 'IRRELEVANT' in grade:
            return 'IRRELEVANT'
        if 'RELEVANT' in grade:
            return 'RELEVANT'
        return 'AMBIGUOUS'


class SelfRAGStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> str:
        return question  # unused — execute() is fully overridden

    def execute(self, query_engine, question: str, llm, synthesis_question: str = None) -> tuple:
        synthesis_question = synthesis_question or question

        response = query_engine.query(synthesis_question)
        answer = _clean_answer(response)

        if llm:
            evaluation = self._evaluate(question, response.source_nodes, answer, llm)
            if not evaluation['supported']:
                chunks = "\n---\n".join(n.text for n in response.source_nodes)
                critique = ""
                if evaluation['issues']:
                    critique += "Issues to fix:\n" + "\n".join(f"- {i}" for i in evaluation['issues']) + "\n"
                if evaluation['missing_info']:
                    critique += f"Missing information: {evaluation['missing_info']}\n"
                prompt = (
                    f"The previous answer had the following problems:\n{critique}\n"
                    f"Context fragments (use ONLY these):\n{chunks}\n\n"
                    f"Question: {question}\n\n"
                    f"Rewrite the answer fixing the problems above using only the fragments provided."
                )
                answer = _clean_answer(llm.complete(prompt))

        return answer, response

    def _evaluate(self, question: str, nodes: list, answer: str, llm) -> dict:
        import json, re
        chunks = "\n---\n".join(n.text[:200] for n in nodes)
        prompt = (
            f"Question: {question}\n\n"
            f"Retrieved context:\n{chunks}\n\n"
            f"Answer: {answer}\n\n"
            f"Evaluate this answer. Reply with ONLY a JSON object with these fields:\n"
            f"- supported (bool): true if the answer is grounded in the context and relevant\n"
            f"- missing_info (str): what important information is missing or wrong, empty string if none\n"
            f"- issues (list of str): specific problems found, empty list if none\n\n"
            f"Reply with ONLY the JSON object, no other text."
        )
        raw = str(llm.complete(prompt)).strip()
        try:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            result = json.loads(match.group() if match else raw)
            supported = bool(result.get('supported', True))
            missing_info = str(result.get('missing_info', ''))
            issues = [str(i) for i in result.get('issues', [])]
            verdict = 'PASS' if supported else 'FAIL'
            if _SELF_RAG_DEBUG:
                print(f"[Self-RAG] Evaluation: {verdict} | issues: {issues} | missing: {missing_info}")
            return {'supported': supported, 'missing_info': missing_info, 'issues': issues}
        except Exception:
            verdict = 'FAIL' if ('FALSE' in raw.upper() or 'FAIL' in raw.upper()) else 'PASS'
            if _SELF_RAG_DEBUG:
                print(f"[Self-RAG] Evaluation (fallback): {verdict} (raw: {raw[:80]})")
            return {'supported': verdict == 'PASS', 'missing_info': '', 'issues': []}


_STRATEGIES = {
    'naive':         NaiveStrategy,
    'hyde_answer':   HyDEAnswerStrategy,
    'hyde_combined': HyDECombinedStrategy,
    'crag':          CRAGStrategy,
    'self_rag':      SelfRAGStrategy,
}


def get_query_strategy(mode: str) -> QueryStrategy:
    return _STRATEGIES.get(mode, NaiveStrategy)()
