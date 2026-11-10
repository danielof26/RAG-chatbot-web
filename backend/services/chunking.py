"""Chunking strategies: how documents are split into the nodes that get embedded and stored.

Shared by the chat path (rag_service.index_document) and the evaluation path (rag_engine.setup_rag), so both
index a document exactly the same way. Each strategy is a builder registered under the id the catalog uses
(rag_catalog.py, section 'chunk'); the splitting only happens at indexing time, so a change of strategy
applies to documents indexed afterwards.
"""
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter, SentenceWindowNodeParser
from llama_index.core.postprocessor import MetadataReplacementPostProcessor

DEFAULT_CHUNK_STRATEGY = 'fixed_size'

# Sentence window: each node is ONE sentence (precise embedding) that carries its neighbours in metadata,
# and the window replaces the sentence in the prompt (see query_postprocessors).
SENTENCE_WINDOW_SIZE = 3
WINDOW_METADATA_KEY = 'window'

# Semantic chunking: a new chunk starts where the embedding distance between consecutive sentences is above
# this percentile of all the distances in the document.
SEMANTIC_BREAKPOINT_PERCENTILE = 95

_NODE_PARSER_BUILDERS = {}


def _register_chunking(strategy: str):
    def decorator(builder):
        _NODE_PARSER_BUILDERS[strategy] = builder
        return builder
    return decorator


@_register_chunking('fixed_size')
def _fixed_size(chunk_size, chunk_overlap, embed_model):
    return SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


@_register_chunking('sent_window')
def _sentence_window(chunk_size, chunk_overlap, embed_model):
    return SentenceWindowNodeParser.from_defaults(window_size=SENTENCE_WINDOW_SIZE,
                                                  window_metadata_key=WINDOW_METADATA_KEY)


@_register_chunking('semantic_chunk')
def _semantic(chunk_size, chunk_overlap, embed_model):
    return SemanticSplitterNodeParser(embed_model=embed_model,
                                      breakpoint_percentile_threshold=SEMANTIC_BREAKPOINT_PERCENTILE)


CHUNK_STRATEGIES = tuple(_NODE_PARSER_BUILDERS)


def build_node_parser(strategy: str, chunk_size: int, chunk_overlap: int, embed_model):
    """The node parser for `strategy`. chunk_size/chunk_overlap only matter to the fixed-size strategy."""
    builder = _NODE_PARSER_BUILDERS.get(strategy or DEFAULT_CHUNK_STRATEGY)
    if builder is None:
        raise ValueError(f'Unknown chunk strategy: {strategy}')
    return builder(chunk_size, chunk_overlap, embed_model)


def query_postprocessors(strategy: str) -> list:
    """Postprocessors a strategy needs when answering. Sentence window swaps each retrieved sentence for its
    window; it runs first so rerankers and filters see the text that will reach the LLM."""
    if strategy == 'sent_window':
        return [MetadataReplacementPostProcessor(target_metadata_key=WINDOW_METADATA_KEY)]
    return []
