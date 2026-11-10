"""Non-vector index types (services/index_types.py): keyword table and summary index, through the real
evaluation path (setup_rag builds the engine, run_rag answers) with scripted models."""
import itertools

import pytest

import config
from rag_catalog import get_catalog
from services import rag_service
from services.index_types import INDEX_TYPES
from services.rag_config import validate_rag_config
from services.rag_engine import run_rag, setup_rag
from tests.fakes import FakeProvider, ScriptedLLM
from tests.test_evaluation_architectures import DOCS


@pytest.fixture
def ask(tmp_path, monkeypatch):
    """ask(index_type, question, top_k=1, **options) -> (answer, llm)"""
    monkeypatch.setattr(config, 'CHROMA_PATH', str(tmp_path / 'chroma'))
    paths = []
    for name, text in DOCS.items():
        (tmp_path / name).write_text(text)
        paths.append(str(tmp_path / name))
    counter = itertools.count()

    def run(index_type, question, top_k=1, **options):
        llm = ScriptedLLM()
        provider = FakeProvider(llm)
        engine, llm = setup_rag(provider, provider, 'model', 'embed', paths, config.CHROMA_PATH, f'eval_{next(counter)}',
                                '', chunk_size=64, chunk_overlap=0, top_k=top_k, index_type=index_type, **options)
        llm.calls.clear()
        (answer, _), = run_rag(engine, [{'question': question}], llm=llm)
        return answer, llm
    return run


def test_keyword_index_retrieves_the_chunks_that_share_keywords_with_the_question(ask):
    answer, llm = ask('keyword_index', 'What happened to Pompeii?')
    assert 'Vesuvius' in answer
    assert 'Eiffel' not in answer and 'flour' not in answer
    assert llm.kinds() == ['answer']                       # keywords are extracted with regex: no LLM call to retrieve


def test_keyword_index_honours_top_k(ask):
    one, _ = ask('keyword_index', 'Paris Seine', top_k=1)
    many, _ = ask('keyword_index', 'Paris Seine', top_k=3)
    assert len(many) > len(one)


def test_summary_index_gives_the_llm_every_chunk_whatever_the_question(ask):
    answer, llm = ask('summary_index', 'Who designed the Eiffel Tower?', top_k=1)
    sent = ' '.join(llm.prompts('answer'))
    for word in ('Eiffel', 'Etna', 'flour'):              # one word from each of the three documents
        assert word in sent
    assert set(llm.kinds()) == {'answer'}


def test_summary_index_ignores_the_configured_synthesis_mode(ask):
    _, compact = ask('summary_index', 'Summarize', synthesis_mode='compact')
    _, refine = ask('summary_index', 'Summarize', synthesis_mode='refine')
    assert compact.kinds() == refine.kinds()


def test_the_index_is_cached_per_collection_and_dropped_on_invalidation(ask, monkeypatch):
    import chromadb
    ask('keyword_index', 'volcano')       # indexes the documents in a collection named eval_0
    collection = chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection('eval_0')

    built = []
    real = rag_service.build_index
    monkeypatch.setattr(rag_service, 'build_index', lambda index_type, nodes: built.append(index_type) or real(index_type, nodes))
    rag_service.invalidate_collection_caches('eval_0')

    def build_engine():
        ctx = rag_service.EngineContext(index=None, chroma_collection=collection, llm=ScriptedLLM(), embed_model=None,
                                        collection_key='k', index_type='keyword_index')
        return rag_service.build_query_engine('naive', ctx)

    build_engine()
    build_engine()
    assert built == ['keyword_index']     # the second engine reused the index
    rag_service.invalidate_collection_caches('eval_0')
    build_engine()
    assert built == ['keyword_index', 'keyword_index']


# ─── configuration ───

def test_rag_config_accepts_every_index_type_and_refuses_others():
    for index_type in INDEX_TYPES:
        assert validate_rag_config({'index_type': index_type}) is None
    assert 'index_type' in validate_rag_config({'index_type': 'magic'})


@pytest.mark.parametrize('index_type', ['keyword_index', 'summary_index'])
def test_a_non_vector_index_refuses_what_needs_the_vector_index(index_type):
    assert validate_rag_config({'index_type': index_type, 'retrieval_mode': 'naive'}) is None
    assert 'retrieval_mode' in validate_rag_config({'index_type': index_type, 'retrieval_mode': 'fusion'})
    assert 'sim_filter' in validate_rag_config({'index_type': index_type, 'sim_filter': True})
    assert validate_rag_config({'index_type': 'vector_index', 'retrieval_mode': 'fusion', 'sim_filter': True}) is None


def test_the_catalog_locks_exactly_what_the_validation_refuses():
    techs = {t['id']: t for s in get_catalog()['sections'] for t in s['techniques']}
    for index_type in ('keyword_index', 'summary_index'):
        locked = set(techs[index_type]['incompat'])
        assert (set(get_catalog()['mode_priority']) - {'naive'}) | {'sim_filter'} <= locked
        assert 'naive' not in locked
