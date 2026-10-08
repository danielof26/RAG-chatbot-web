"""Catalog of the RAG techniques offered in the Advanced tab (served by GET /api/rag/techniques).

Single source of truth for the UI: which techniques exist, whether they are implemented, and which ones
cannot be combined. Declare each incompatibility on one side only; get_catalog() makes the lists symmetric.
`impl` must be True only for techniques the backend can run (see _register_engine in rag_service.py and
query_strategies.py).
"""
import copy

SECTIONS = [
    {
        'id': 'pre', 'num': 1,
        'title': 'Pre-retrieval · Query transformation',
        'desc': 'Applied before the retriever to improve semantic matching. All combinable with each other. The Router is exclusive in index selection but can coexist with the rest.',
        'techniques': [
            {'id': 'naive', 'label': 'Naive (direct)', 'impl': True, 'incompat': ['hyde_answer', 'hyde_combined'],
             'desc': 'Uses the question as-is for retrieval. No transformation applied — the baseline. Compatible with CRAG (which also retrieves naively, then filters).'},
            {'id': 'hyde_answer', 'label': 'HyDE Answer', 'impl': True, 'incompat': ['naive', 'hyde_combined', 'crag'],
             'desc': 'Generates a hypothetical answer and uses its embedding as the retrieval query.'},
            {'id': 'hyde_combined', 'label': 'HyDE Combined', 'impl': True, 'incompat': ['naive', 'hyde_answer', 'crag'],
             'desc': 'Embeds both the original question and a hypothetical answer for retrieval.'},
            {'id': 'multi_query', 'label': 'Multi-Query', 'impl': False, 'incompat': [],
             'desc': 'Generates N reformulations of the question and fuses all results to improve recall.'},
            {'id': 'step_back', 'label': 'Step-back Prompting', 'impl': False, 'incompat': [],
             'desc': 'Abstracts the question to a higher-level concept before retrieving.'},
            {'id': 'sub_question', 'label': 'Sub-question Engine', 'impl': True, 'incompat': ['hyde_answer', 'hyde_combined', 'crag', 'self_rag', 'router', 'fusion', 'raptor'],
             'desc': 'Decomposes complex questions into sub-questions, each with its own retrieval, then combines the partial answers.'},
            {'id': 'router', 'label': 'Adaptive Router', 'impl': True, 'incompat': ['hyde_answer', 'hyde_combined', 'crag', 'self_rag'],
             'desc': 'Classifies the query type (factual, multi-hop, summary, out-of-domain) and routes it to the most suitable engine automatically.'},
        ],
    },
    {
        'id': 'idx', 'num': 2,
        'title': 'Indexing · Knowledge base structure',
        'desc': 'How documents are organized in the index. Choose one per collection — mutually exclusive.',
        'techniques': [
            {'id': 'vector_index', 'label': 'Vector Store Index', 'impl': True, 'incompat': ['summary_index', 'tree_index', 'keyword_index', 'kg_index'],
             'desc': 'Dense semantic index — the standard choice for most RAG pipelines.'},
            {'id': 'summary_index', 'label': 'Summary Index (List)', 'impl': False, 'incompat': ['vector_index', 'tree_index', 'keyword_index', 'kg_index'],
             'desc': 'Indexes document summaries, useful for high-level summarization queries.'},
            {'id': 'tree_index', 'label': 'Tree Index', 'impl': False, 'incompat': ['vector_index', 'summary_index', 'keyword_index', 'kg_index'],
             'desc': 'Hierarchical index built by recursively summarizing chunks up a tree.'},
            {'id': 'keyword_index', 'label': 'Keyword Table Index', 'impl': False, 'incompat': ['vector_index', 'summary_index', 'tree_index', 'kg_index'],
             'desc': 'Keyword-based index, precise for exact-match technical retrieval.'},
            {'id': 'kg_index', 'label': 'Knowledge Graph Index', 'impl': False, 'incompat': ['vector_index', 'summary_index', 'tree_index', 'keyword_index'],
             'desc': 'Graph-based index for documents with rich entity relationships.'},
        ],
    },
    {
        'id': 'chunk', 'num': 3,
        'title': 'Chunking · Document preprocessing',
        'desc': 'How documents are split before indexing. Choose one. Changes apply only when re-indexing.',
        'techniques': [
            {'id': 'fixed_size', 'label': 'Fixed-size', 'impl': True, 'incompat': ['sent_window', 'semantic_chunk', 'hierarchical'],
             'desc': 'Splits by token count. Configure size and overlap in the fields below.'},
            {'id': 'sent_window', 'label': 'Sentence window', 'impl': False, 'incompat': ['fixed_size', 'semantic_chunk', 'hierarchical'],
             'desc': 'Chunks by sentence and retrieves with a surrounding context window.'},
            {'id': 'semantic_chunk', 'label': 'Semantic chunking', 'impl': False, 'incompat': ['fixed_size', 'sent_window', 'hierarchical'],
             'desc': 'Splits at semantic boundaries detected by embedding similarity.'},
            {'id': 'hierarchical', 'label': 'Hierarchical chunking', 'impl': False, 'incompat': ['fixed_size', 'sent_window', 'semantic_chunk'],
             'desc': 'Creates chunks at multiple granularity levels (parent + child nodes).'},
        ],
    },
    {
        'id': 'ret', 'num': 4,
        'title': 'Retrieval · Retriever strategy',
        'desc': 'How relevant nodes are searched within the index. All combinable — Fusion is literally dense + sparse together.',
        'techniques': [
            {'id': 'vec_retriever', 'label': 'Vector Store (dense)', 'impl': True, 'incompat': [],
             'desc': 'Semantic similarity search using embeddings — the standard retriever.'},
            {'id': 'bm25', 'label': 'BM25 (sparse/keyword)', 'impl': True, 'incompat': ['fusion', 'router', 'sub_question', 'raptor', 'hyde_answer', 'hyde_combined'],
             'desc': 'Classic keyword retrieval — complements dense search for exact terms. Used alone here, with no embeddings involved.'},
            {'id': 'auto_merging', 'label': 'Auto-Merging', 'impl': False, 'incompat': [],
             'desc': 'Merges child chunks into parent when enough siblings are retrieved.'},
            {'id': 'recursive', 'label': 'Recursive Retriever', 'impl': False, 'incompat': [],
             'desc': 'Follows references between nodes recursively to complete context.'},
            {'id': 'fusion', 'label': 'Fusion (dense + sparse)', 'impl': True, 'incompat': ['hyde_answer', 'hyde_combined', 'crag', 'self_rag', 'router', 'raptor'],
             'desc': 'Combines vector and BM25 retrievers with reciprocal rank fusion for hybrid retrieval.'},
            {'id': 'raptor', 'label': 'RAPTOR (hierarchical tree)', 'impl': True, 'incompat': ['fusion', 'router', 'hyde_answer', 'hyde_combined'],
             'desc': 'Recursively clusters chunks by embedding similarity, generates LLM summaries per cluster and organises them into a tree. Retrieval traverses the tree to return both fine-grained and high-level nodes. Ideal for long or structured documents. The first query builds the index — subsequent ones reuse it.'},
            {'id': 'auto_retrieval', 'label': 'Auto-Retrieval', 'impl': False, 'incompat': [],
             'desc': 'Extracts metadata filters from the query to narrow the search space.'},
        ],
    },
    {
        'id': 'post', 'num': 5,
        'title': 'Post-retrieval · Filtering & reranking',
        'desc': 'Applied after retrieval to improve chunk quality. Most are combinable in pipeline — except the two reranking methods, choose one.',
        'techniques': [
            {'id': 'crag', 'label': 'CRAG — Corrective RAG', 'impl': True, 'incompat': ['rerank_ce', 'rerank_llm', 'hyde_answer', 'hyde_combined'],
             'desc': 'LLM grades each chunk as relevant/ambiguous/irrelevant and filters the irrelevant ones.'},
            {'id': 'self_rag', 'label': 'Self-RAG', 'impl': True, 'incompat': [],
             'desc': 'After generating, the LLM evaluates its own answer (PASS/FAIL). If FAIL, retries with chunks embedded directly in the prompt.'},
            {'id': 'rerank_ce', 'label': 'Reranking (cross-encoder)', 'impl': True, 'incompat': ['crag', 'rerank_llm'],
             'desc': 'Reranks chunks using a sentence-transformer cross-encoder model.'},
            {'id': 'rerank_llm', 'label': 'Reranking (LLM)', 'impl': False, 'incompat': ['crag', 'rerank_ce'],
             'desc': 'Reranks chunks by asking the LLM to score each one for relevance.'},
            {'id': 'sim_filter', 'label': 'SimilarityPostprocessor', 'impl': True, 'incompat': [],
             'desc': 'Discards chunks whose similarity score is below a set threshold.'},
            {'id': 'xai', 'label': 'XAI — Explainable RAG', 'impl': True, 'incompat': [],
             'desc': 'After synthesis, verifies that each cited fragment exists verbatim in the retrieved chunks. Retries up to 2 times if hallucinations are detected. Produces a full traceability log.'},
            {'id': 'kw_filter', 'label': 'KeywordNodePostprocessor', 'impl': False, 'incompat': [],
             'desc': 'Filters chunks that do not contain required keywords.'},
            {'id': 'prev_next', 'label': 'PrevNextNodePostprocessor', 'impl': False, 'incompat': [],
             'desc': 'Expands each retrieved chunk with its neighbouring chunks for context.'},
            {'id': 'long_reorder', 'label': 'LongContextReorder', 'impl': True, 'incompat': [],
             'desc': 'Reorders chunks to place the most relevant at start and end of prompt.'},
        ],
    },
    {
        'id': 'syn', 'num': 6,
        'title': 'Response synthesis',
        'desc': 'How retrieved chunks are assembled into the final answer. Choose one — mutually exclusive.',
        'techniques': [
            {'id': 'compact', 'label': 'Compact (default)', 'impl': True, 'incompat': ['refine', 'tree_summarize', 'simple_summarize', 'accumulate'],
             'desc': 'Packs chunks into the fewest possible LLM prompts before generating.'},
            {'id': 'refine', 'label': 'Refine', 'impl': True, 'incompat': ['compact', 'tree_summarize', 'simple_summarize', 'accumulate'],
             'desc': 'Iteratively refines the answer chunk by chunk.'},
            {'id': 'tree_summarize', 'label': 'Tree Summarize', 'impl': True, 'incompat': ['compact', 'refine', 'simple_summarize', 'accumulate'],
             'desc': 'Builds a summary tree bottom-up — best for very long documents.'},
            {'id': 'simple_summarize', 'label': 'Simple Summarize', 'impl': True, 'incompat': ['compact', 'refine', 'tree_summarize', 'accumulate'],
             'desc': 'Truncates all chunks into a single prompt — fastest but may lose information.'},
            {'id': 'accumulate', 'label': 'Accumulate', 'impl': True, 'incompat': ['compact', 'refine', 'tree_summarize', 'simple_summarize'],
             'desc': 'Generates an answer per chunk independently, then combines them.'},
        ],
    },
]

# Techniques that are always on and cannot be toggled
DEFAULT_TECHS = ['vector_index', 'vec_retriever', 'fixed_size']

# retrieval_mode -> techniques shown as selected when an agent is saved with that mode
MODE_TECHS = {
    'naive': ['naive', 'compact'],
    'crag': ['naive', 'crag', 'compact'],
    'hyde_answer': ['hyde_answer', 'compact'],
    'hyde_combined': ['hyde_combined', 'compact'],
    'self_rag': ['naive', 'self_rag', 'compact'],
    'router': ['router', 'compact'],
    'fusion': ['fusion', 'compact'],
    'raptor': ['raptor', 'compact'],
    'sub_question': ['sub_question', 'compact'],
    'bm25': ['bm25', 'compact'],
}

# When several techniques are selected, the first one found here decides retrieval_mode / synthesis_mode
MODE_PRIORITY = ['crag', 'self_rag', 'router', 'sub_question', 'raptor', 'fusion', 'bm25', 'hyde_combined', 'hyde_answer', 'naive']
SYNTHESIS_PRIORITY = ['refine', 'tree_summarize', 'simple_summarize', 'accumulate', 'compact']


def _make_symmetric(sections: list):
    by_id = {t['id']: t for s in sections for t in s['techniques']}
    for tech in by_id.values():
        for other_id in list(tech['incompat']):
            other = by_id.get(other_id)
            if other and tech['id'] not in other['incompat']:
                other['incompat'].append(tech['id'])


def get_catalog() -> dict:
    sections = copy.deepcopy(SECTIONS)
    _make_symmetric(sections)
    return {
        'sections': sections,
        'default_techs': list(DEFAULT_TECHS),
        'mode_techs': copy.deepcopy(MODE_TECHS),
        'mode_priority': list(MODE_PRIORITY),
        'synthesis_priority': list(SYNTHESIS_PRIORITY),
    }
