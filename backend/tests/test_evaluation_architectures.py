"""Does every architecture really behave differently when run by Evaluation?

Runs the REAL evaluation path (`setup_rag` builds the index and the engine, `run_rag` answers) for each
retrieval mode, with scripted models, and checks each architecture's observable signature: which model calls it
makes, which chunks reach the answer prompt and how the final answer is produced. If two architectures were
silently running the same engine, these signatures would collapse into one."""
import collections
import re

import pytest
from llama_index.core.schema import QueryBundle

import config
from services.rag_engine import run_rag, setup_rag
from services.xai import CITATION_INSTRUCTION
from tests.fakes import FakeProvider, ScriptedLLM

QUESTION = 'Who designed the Eiffel Tower?'
TOP_K = 3
DOCS = {
    'paris.txt': 'The Eiffel Tower is in Paris. It was designed by Gustave Eiffel and finished in 1889. '
                 'It is 330 metres tall. Paris is the capital of France. The Louvre museum holds the Mona Lisa. '
                 'The Seine river crosses Paris. Paris has many bridges over the Seine. '
                 'The tower attracts millions of visitors every year.',
    'volcano.txt': 'Mount Etna is a volcano in Sicily. Volcano eruptions release lava and ash. '
                   'Magma rises through the crater during an eruption. Vesuvius destroyed Pompeii in 79 AD. '
                   'Iceland has many active volcanoes and geysers. Lava flows can reach several kilometres.',
    'cooking.txt': 'To bake bread you need flour, water, yeast and salt. Knead the dough for ten minutes. '
                   'Let the dough rise for one hour. Bake at 230 degrees for thirty minutes. '
                   'Pasta is cooked in boiling salted water. Tomato sauce needs garlic and basil.',
}

ALL_MODES = ['naive', 'hyde_answer', 'hyde_combined', 'crag', 'self_rag', 'bm25', 'fusion', 'router', 'sub_question', 'raptor']


@pytest.fixture
def build_engine(tmp_path, monkeypatch):
    """build_engine(mode, top_k=TOP_K, **llm_options) -> (engine, llm): the engine Evaluation would build."""
    monkeypatch.setattr(config, 'CHROMA_PATH', str(tmp_path / 'chroma'))
    paths = []
    for name, text in DOCS.items():
        (tmp_path / name).write_text(text)
        paths.append(str(tmp_path / name))
    counter = collections.Counter()

    def build(mode, top_k=TOP_K, **llm_options):
        counter[mode] += 1
        llm = ScriptedLLM(**llm_options)
        provider = FakeProvider(llm)
        engine, llm = setup_rag(provider, provider, 'model', 'embed', paths, config.CHROMA_PATH,
                                f'eval_{mode}_{counter[mode]}', '', chunk_size=64, chunk_overlap=0,
                                top_k=top_k, retrieval_mode=mode)
        llm.calls.clear()                     # only what happens while answering, not while indexing
        return engine, llm
    return build


@pytest.fixture
def evaluate(build_engine):
    """evaluate(mode, xai=False, ...) -> (answer, hallucinations, llm); one fresh index per call."""
    def run(mode, xai=False, top_k=TOP_K, **llm_options):
        engine, llm = build_engine(mode, top_k, **llm_options)
        (answer, hallucinations), = run_rag(engine, [{'question': QUESTION}], architecture='xai' if xai else 'naive',
                                            llm=llm, retrieval_mode=mode)
        return answer, hallucinations, llm
    return run


def chunks_in_answer_prompts(llm):
    """Text of every chunk placed in the context of an answer prompt (the echoing LLM puts it in the answer)."""
    found = []
    for prompt in llm.prompts('answer'):
        context = prompt.split('---------------------')[1] if prompt.count('---------------------') >= 2 else ''
        found += [line for line in context.splitlines() if line and not re.match(r'\w+: ', line)]
    return found


# ─── each architecture leaves its own fingerprint of model calls ───

SIGNATURES = {
    'naive':         {'answer': 1},
    'bm25':          {'answer': 1},
    'fusion':        {'answer': 1},
    'raptor':        {'answer': 1},
    'hyde_answer':   {'hyde': 1, 'answer': 1},
    'hyde_combined': {'hyde': 1, 'answer': 1},
    'crag':          {'crag_grade': TOP_K, 'crag_answer': 1},                     # grades every retrieved chunk
    'self_rag':      {'answer': 1, 'selfrag_eval': 1, 'selfrag_rewrite': 1},     # critique -> rewrite
    'router':        {'router_select': 1, 'answer': 1},
    'sub_question':  {'subq_gen': 1, 'answer': 3},                                # 2 sub-questions + combination
}


@pytest.mark.parametrize('mode', ALL_MODES)
def test_architecture_makes_its_own_model_calls(evaluate, mode):
    _, _, llm = evaluate(mode)
    assert dict(collections.Counter(llm.kinds())) == SIGNATURES[mode]


def test_no_two_architectures_share_a_signature_unless_they_differ_in_retrieval(evaluate):
    """Same call fingerprint is only acceptable for modes that differ in WHAT they retrieve, which the tests
    below check one by one (naive / bm25 / fusion / raptor and hyde_answer / hyde_combined)."""
    groups = collections.defaultdict(list)
    for mode in ALL_MODES:
        groups[tuple(sorted(SIGNATURES[mode].items()))].append(mode)
    assert {tuple(g) for g in groups.values() if len(g) > 1} == {
        ('naive', 'bm25', 'fusion', 'raptor'), ('hyde_answer', 'hyde_combined')}


# ─── ...and retrieves / answers in its own way ───

def test_hyde_retrieves_with_the_hypothetical_answer_not_the_question(evaluate):
    naive = chunks_in_answer_prompts(evaluate('naive')[2])
    hyde = chunks_in_answer_prompts(evaluate('hyde_answer')[2])
    assert any('Eiffel' in c for c in naive)
    assert hyde and not any(w in c for c in hyde for w in ('Eiffel', 'Paris'))   # the hypothetical talks about volcanoes
    assert set(hyde) != set(naive)


def test_hyde_combined_mixes_the_question_and_the_hypothetical(evaluate):
    combined = ' '.join(chunks_in_answer_prompts(evaluate('hyde_combined')[2]))
    assert 'Eiffel' in combined or 'Paris' in combined
    assert any(w in combined.lower() for w in ('lava', 'volcano', 'magma', 'vesuvius', 'eruption'))


def test_crag_drops_chunks_graded_irrelevant(evaluate):
    answer, _, llm = evaluate('crag', top_k=6)      # wide enough to also retrieve chunks about other topics
    grades = [llm._reply('crag_grade', p) for p in llm.prompts('crag_grade')]
    assert 'RELEVANT' in grades and 'IRRELEVANT' in grades        # the grader really discriminates
    final_prompt = llm.prompts('crag_answer')[0]
    assert 'Eiffel' in final_prompt
    assert grades.count('RELEVANT') == final_prompt.count('\n---\n') + 1      # exactly the relevant ones are kept
    assert 'dough' not in final_prompt and 'volcano' not in final_prompt.lower()


def test_self_rag_answer_is_the_rewrite_not_the_first_draft(evaluate):
    answer, _, llm = evaluate('self_rag')
    assert 'The previous answer had the following problems' in answer
    assert answer != llm._reply('answer', llm.prompts('answer')[0])


def test_sub_question_answers_each_sub_question_separately(evaluate):
    _, _, llm = evaluate('sub_question')
    prompts = llm.prompts('answer')
    assert any('Query: What is the Eiffel Tower?' in p for p in prompts)
    assert any('Query: Who designed it?' in p for p in prompts)


def test_router_sends_the_question_to_the_selected_engine(evaluate):
    answer, _, llm = evaluate('router')
    assert 'Eiffel' in answer and llm.kinds()[0] == 'router_select'


def test_fusion_merges_dense_and_sparse_results(evaluate):
    chunks = chunks_in_answer_prompts(evaluate('fusion')[2])
    assert len(chunks) == TOP_K and any('Eiffel' in c for c in chunks)


def test_bm25_works_on_keywords(evaluate):
    chunks = chunks_in_answer_prompts(evaluate('bm25')[2])
    assert len(chunks) == TOP_K and any('designed' in c for c in chunks)


def test_raptor_builds_a_summary_tree_in_its_own_collection(evaluate):
    import chromadb
    evaluate('raptor')
    names = [c.name for c in chromadb.PersistentClient(path=config.CHROMA_PATH).list_collections()]
    assert any(n.endswith('_raptor') for n in names)


# ─── XAI: the explainability layer over any architecture ───

@pytest.mark.parametrize('mode', ALL_MODES)
def test_xai_marks_uncited_answers_and_tries_to_refine(evaluate, mode):
    _, hallucinations, llm = evaluate(mode, xai=True)
    assert hallucinations == -2                                  # the model never cited
    assert llm.kinds().count('xai_refine') == 2                  # max_refine attempts, then gives up


@pytest.mark.parametrize('mode', ALL_MODES)
def test_naive_architecture_reports_hallucinations_as_not_applicable(evaluate, mode):
    assert evaluate(mode, xai=False)[1] == -1


def test_xai_accepts_a_verifiable_citation_without_refining(evaluate):
    _, hallucinations, llm = evaluate('naive', xai=True, cite=True)
    assert hallucinations == 0 and 'xai_refine' not in llm.kinds()


def test_xai_flags_an_invented_citation(evaluate):
    answer, hallucinations, llm = evaluate('naive', xai=True, invent='Napoleon conquered Mars in the year 3000')
    assert hallucinations == 1 or hallucinations == 2 or hallucinations > 0
    assert llm.kinds().count('xai_refine') == 2                  # tried to fix it, the model kept inventing


# ─── things that would make architectures not strictly comparable ───

def spy_on_retrieval(engine):
    """Wraps the engine so every text it would search with is recorded. Returns the list it appends to."""
    seen = []
    retrieve, query = engine.retrieve, engine.query

    def record(bundle):
        bundle = QueryBundle(bundle) if isinstance(bundle, str) else bundle
        seen.extend(bundle.custom_embedding_strs or [bundle.query_str])

    def spying_retrieve(bundle):
        record(bundle)
        return retrieve(bundle)

    def spying_query(bundle):
        record(bundle)                       # engines that cannot retrieve and synthesize apart get ONE string
        return query(bundle)

    engine.retrieve, engine.query = spying_retrieve, spying_query
    return seen


XAI_LEAK_LIMIT = ('Known limitation: the router and the sub-question engine receive one single string and delegate '
                  'retrieval to inner engines, so the citation request cannot be kept out of it')
INSTRUCTION = CITATION_INSTRUCTION.strip()


@pytest.mark.parametrize('mode', [
    *[m for m in ALL_MODES if m not in ('router', 'sub_question')],
    *[pytest.param(m, marks=pytest.mark.xfail(strict=True, reason=XAI_LEAK_LIMIT)) for m in ('router', 'sub_question')],
])
def test_xai_does_not_change_the_text_used_for_retrieval(build_engine, mode):
    engine, llm = build_engine(mode)
    searched = spy_on_retrieval(engine)
    run_rag(engine, [{'question': QUESTION}], architecture='xai', llm=llm, retrieval_mode=mode)
    assert searched and INSTRUCTION not in ' '.join(searched)


@pytest.mark.parametrize('mode', ALL_MODES)
def test_xai_still_gives_the_answering_model_the_citation_request_and_the_chunks(evaluate, mode):
    """Keeping the request out of retrieval must not take it away from the model that has to cite."""
    _, _, llm = evaluate(mode, xai=True)
    final = [p for k, p in llm.calls if k in ('answer', 'crag_answer')][-1]
    assert INSTRUCTION in final
    assert 'Eiffel' in final or 'Paris' in final or mode.startswith('hyde')      # the retrieved context is there too


@pytest.mark.parametrize('mode', ALL_MODES)
def test_xai_citations_are_still_verified_against_the_retrieved_chunks(evaluate, mode):
    _, hallucinations, llm = evaluate(mode, xai=True, cite=True)
    assert hallucinations == 0 and 'xai_refine' not in llm.kinds()


def test_citation_instruction_is_only_added_on_the_xai_architecture(build_engine):
    engine, llm = build_engine('naive')
    run_rag(engine, [{'question': QUESTION}], architecture='naive', llm=llm, retrieval_mode='naive')
    assert all(INSTRUCTION not in prompt for _, prompt in llm.calls)


@pytest.mark.parametrize('mode', ['bm25', 'fusion', 'raptor'])      # chunks rebuilt from ChromaDB, not read from the index
def test_every_architecture_shows_the_llm_the_same_chunk_metadata(build_engine, mode):
    def extra_metadata_seen_by_llm(engine):
        nodes = engine.retrieve(QueryBundle(QUESTION))
        visible = {key for n in nodes for key in n.node.metadata if key not in n.node.excluded_llm_metadata_keys}
        return visible - {'file_path'}                      # file_path is the one key the vector retriever shows

    wide = 9                                                 # wide enough for RAPTOR to return leaf chunks, not just summaries
    assert extra_metadata_seen_by_llm(build_engine('naive', wide)[0]) == set()
    assert extra_metadata_seen_by_llm(build_engine(mode, wide)[0]) == set()
