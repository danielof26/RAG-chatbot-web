"""Chunking strategies (services/chunking.py): each one must split differently, store what its retrieval needs,
and be the one the real indexing paths (chat and evaluation) actually use."""
import pytest
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode

import config
from services.chunking import CHUNK_STRATEGIES, build_node_parser, query_postprocessors
from services.rag_config import validate_rag_config
from services.rag_engine import run_rag, setup_rag
from services.rag_service import build_postprocessors
from tests.fakes import FakeProvider, HashEmbedding, ScriptedLLM

TEXT = ('The Eiffel Tower is in Paris. It was designed by Gustave Eiffel. It was finished in 1889. '
        'It is 330 metres tall. The Louvre holds the Mona Lisa. The Seine crosses Paris. '
        'Mount Etna is a volcano in Sicily. Eruptions release lava and ash. Magma rises through the crater. '
        'Vesuvius destroyed Pompeii. Iceland has many volcanoes. Lava flows can reach several kilometres.')


def nodes_of(strategy, chunk_size=64, chunk_overlap=0):
    return build_node_parser(strategy, chunk_size, chunk_overlap, HashEmbedding()).get_nodes_from_documents([Document(text=TEXT)])


def test_fixed_size_is_the_sentence_splitter_it_always_was():
    expected = SentenceSplitter(chunk_size=64, chunk_overlap=0).get_nodes_from_documents([Document(text=TEXT)])
    assert [n.text for n in nodes_of('fixed_size')] == [n.text for n in expected]


def test_a_missing_strategy_means_fixed_size_and_an_unknown_one_is_refused():
    assert [n.text for n in build_node_parser(None, 64, 0, None).get_nodes_from_documents([Document(text=TEXT)])] == \
           [n.text for n in nodes_of('fixed_size')]
    with pytest.raises(ValueError):
        build_node_parser('nope', 64, 0, None)


def test_sentence_window_makes_one_node_per_sentence_carrying_its_neighbours():
    nodes = nodes_of('sent_window')
    assert len(nodes) == 12
    middle = nodes[3]
    assert middle.text.strip() == 'It is 330 metres tall.'
    assert 'It was designed by Gustave Eiffel.' in middle.metadata['window']
    assert 'The Seine crosses Paris.' in middle.metadata['window']
    # The window is context for the LLM, not part of what gets embedded or shown as metadata
    assert 'window' not in middle.get_content(MetadataMode.EMBED)
    assert 'window' not in middle.get_content(MetadataMode.LLM)


def test_semantic_chunking_groups_sentences_and_ignores_the_chunk_size():
    semantic = nodes_of('semantic_chunk', chunk_size=64)
    assert 1 < len(semantic) < 12
    assert [n.text for n in semantic] == [n.text for n in nodes_of('semantic_chunk', chunk_size=8000)]
    assert ''.join(n.text for n in semantic).replace(' ', '') == TEXT.replace(' ', '')   # nothing lost


def test_only_sentence_window_adds_a_query_postprocessor():
    assert query_postprocessors('fixed_size') == []
    assert query_postprocessors('semantic_chunk') == []
    assert len(query_postprocessors('sent_window')) == 1
    assert len(build_postprocessors(chunk_strategy='sent_window', long_reorder=True)) == 2
    assert build_postprocessors() == []


def test_rag_config_accepts_the_strategies_and_refuses_others():
    for strategy in CHUNK_STRATEGIES:
        assert validate_rag_config({'chunk_strategy': strategy}) is None
    assert 'chunk_strategy' in validate_rag_config({'chunk_strategy': 'magic'})


# ─── through the real indexing + answering path used by Evaluation ───

@pytest.fixture
def answer_with(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'CHROMA_PATH', str(tmp_path / 'chroma'))
    (tmp_path / 'doc.txt').write_text(TEXT)

    def run(strategy):
        llm = ScriptedLLM()
        provider = FakeProvider(llm)
        engine, llm = setup_rag(provider, provider, 'model', 'embed', [str(tmp_path / 'doc.txt')], config.CHROMA_PATH,
                                f'eval_{strategy}', '', chunk_size=64, chunk_overlap=0, top_k=1, chunk_strategy=strategy)
        (answer, _), = run_rag(engine, [{'question': 'Who designed the Eiffel Tower?'}], llm=llm)
        return answer
    return run


def test_sentence_window_answers_with_the_window_instead_of_the_lone_sentence(answer_with):
    fixed = answer_with('fixed_size')
    window = answer_with('sent_window')
    # The best sentence is "It was designed by Gustave Eiffel."; its window (3 sentences each side) reaches the LLM...
    for sentence in ('The Eiffel Tower is in Paris.', 'It was finished in 1889.', 'It is 330 metres tall.'):
        assert sentence in window
    assert 'Mount Etna' not in window                    # ...but not the rest of the document
    assert 'It is 330 metres tall.' not in fixed         # a 64-token chunk of the same document is smaller than that


def test_each_strategy_indexes_a_different_number_of_nodes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'CHROMA_PATH', str(tmp_path / 'chroma'))
    (tmp_path / 'doc.txt').write_text(TEXT)
    counts = {}
    for strategy in CHUNK_STRATEGIES:
        provider = FakeProvider(ScriptedLLM())
        setup_rag(provider, provider, 'model', 'embed', [str(tmp_path / 'doc.txt')], config.CHROMA_PATH,
                  f'eval_{strategy}', '', chunk_size=100, chunk_overlap=0, chunk_strategy=strategy)
        import chromadb
        counts[strategy] = chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection(f'eval_{strategy}').count()
    assert counts['sent_window'] == 12
    assert len(set(counts.values())) == 3
