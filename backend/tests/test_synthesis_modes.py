"""Every engine that exposes the synthesis choice in the Advanced tab must actually build the synthesizer
that was chosen (a choice that is silently ignored is worse than a locked pill)."""
import uuid

import chromadb
import pytest
from llama_index.core import Document, VectorStoreIndex, get_response_synthesizer
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.llms import MockLLM

from services import rag_service

MODES = ['compact', 'refine', 'tree_summarize', 'simple_summarize', 'accumulate']


@pytest.fixture(scope='module')
def ctx_parts():
    embed = MockEmbedding(embed_dim=8)
    llm = MockLLM()
    texts = ['Brasil ganó cinco Mundiales.', 'Alemania ganó cuatro Mundiales.', 'Italia ganó cuatro Mundiales.']
    index = VectorStoreIndex.from_documents([Document(text=t) for t in texts], embed_model=embed)
    collection = chromadb.EphemeralClient().create_collection(f'synth_{uuid.uuid4().hex}')
    collection.add(ids=[str(i) for i in range(len(texts))], documents=texts,
                   metadatas=[{'source': 'x'}] * len(texts), embeddings=[[0.1] * 8] * len(texts))
    return index, collection, llm, embed


def _engine(mode, synthesis_mode, parts):
    index, collection, llm, embed = parts
    ctx = rag_service.EngineContext(index=index, chroma_collection=collection, llm=llm, embed_model=embed,
                                    collection_key='synth_test', synthesis_mode=synthesis_mode)
    return rag_service.build_query_engine(mode, ctx)


@pytest.mark.parametrize('synthesis_mode', MODES)
@pytest.mark.parametrize('retrieval_mode', ['naive', 'fusion', 'bm25', 'sub_question'])
def test_engine_builds_the_chosen_synthesizer(retrieval_mode, synthesis_mode, ctx_parts):
    expected = type(get_response_synthesizer(response_mode=synthesis_mode, llm=ctx_parts[2]))
    engine = _engine(retrieval_mode, synthesis_mode, ctx_parts)
    assert type(engine._response_synthesizer) is expected


@pytest.mark.parametrize('synthesis_mode', MODES)
def test_sub_question_answers_each_sub_question_with_the_chosen_synthesizer(synthesis_mode, ctx_parts):
    expected = type(get_response_synthesizer(response_mode=synthesis_mode, llm=ctx_parts[2]))
    engine = _engine('sub_question', synthesis_mode, ctx_parts)
    inner = next(iter(engine._query_engines.values()))
    assert type(inner._response_synthesizer) is expected
