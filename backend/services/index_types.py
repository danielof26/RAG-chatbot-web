"""Index structures other than the vector index: how the chunks of a collection are organized for retrieval.

The vector index lives in ChromaDB and is the default. The others are built in memory from the chunks already
stored there (like the BM25 index), so choosing one applies right away, without re-indexing the documents.
Each type is registered under the id the catalog uses (rag_catalog.py, section 'idx') with a builder that turns
the chunks (TextNodes) into the index and one that turns the index into a query engine.
"""
from llama_index.core.indices import SummaryIndex
from llama_index.core.indices.keyword_table import SimpleKeywordTableIndex
from llama_index.core.llms import MockLLM
from llama_index.core.query_engine import RetrieverQueryEngine

DEFAULT_INDEX_TYPE = 'vector_index'
MAX_KEYWORDS_PER_CHUNK = 10_000

_INDEX_TYPES = {}       # id -> (build_index(nodes), build_engine(index, llm, top_k, synthesis_mode, postprocessors, streaming))


def _register_index_type(index_type: str, build_engine):
    def decorator(build_index):
        _INDEX_TYPES[index_type] = (build_index, build_engine)
        return build_index
    return decorator


def _keyword_engine(index, llm, top_k, synthesis_mode, postprocessors, streaming):
    retriever = index.as_retriever(retriever_mode='simple', num_chunks_per_query=top_k)
    return RetrieverQueryEngine.from_args(retriever, llm=llm, response_mode=synthesis_mode,
                                          node_postprocessors=postprocessors, streaming=streaming)


def _summary_engine(index, llm, top_k, synthesis_mode, postprocessors, streaming):
    # The retriever hands over EVERY chunk (top_k does not apply), so the answer is built bottom-up with
    # tree_summarize whatever synthesis mode is configured: the other modes would not scale to a whole collection.
    return RetrieverQueryEngine.from_args(index.as_retriever(), llm=llm, response_mode='tree_summarize',
                                          node_postprocessors=postprocessors, streaming=streaming)


@_register_index_type('keyword_index', _keyword_engine)
def _keyword_index(nodes):
    # Keyword extraction is regex based: the LLM is never called, MockLLM only keeps the index from resolving
    # the global Settings.llm (which would ask for an OpenAI key). Keywords are taken from the chunk WITH its
    # metadata (file path...), so the default cap of 10 per chunk would be filled by the path and push out the
    # words of the text itself: keep them all.
    return SimpleKeywordTableIndex(nodes, llm=MockLLM(), max_keywords_per_chunk=MAX_KEYWORDS_PER_CHUNK)


@_register_index_type('summary_index', _summary_engine)
def _summary_index(nodes):
    return SummaryIndex(nodes)


INDEX_TYPES = (DEFAULT_INDEX_TYPE, *_INDEX_TYPES)


def build_index(index_type: str, nodes: list):
    return _INDEX_TYPES[index_type][0](nodes)


def build_index_engine(index_type: str, index, llm, top_k: int, synthesis_mode: str, postprocessors: list, streaming: bool):
    return _INDEX_TYPES[index_type][1](index, llm, top_k, synthesis_mode, postprocessors, streaming)
