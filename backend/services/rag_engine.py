import chromadb
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from services.query_strategies import get_query_strategy, _clean_answer
from services.xai import XAIDecorator, _write_xai_trace
from services.rag_service import EngineContext, build_postprocessors, build_query_engine


def setup_rag(llm_provider, embed_provider, model_name, embed_model, file_paths, chroma_path, chroma_col,
              prompt, chunk_size=1024, chunk_overlap=200, top_k=15, temperature=0.1, synthesis_mode='compact',
              similarity_cutoff=None, rerank=False, rerank_top_n=3, retrieval_mode='naive',
              fusion_num_queries=1, long_reorder=False):
    """
    Initialises the LLM, embedding model, ChromaDB vector store and LlamaIndex query engine.
    Dispatches on retrieval_mode using the same engine builders as rag_service.py (chat path),
    so evaluations exercise the real router/fusion/raptor/sub_question/bm25 engines instead of
    always falling back to the plain vector engine.
    """
    llm = llm_provider.build_llm(model=model_name, system_prompt=prompt, temperature=temperature)

    embedder = embed_provider.build_embedding(model=embed_model)

    db                = chromadb.PersistentClient(path=chroma_path)
    chroma_collection = db.get_or_create_collection(chroma_col)
    vector_store      = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context   = StorageContext.from_defaults(vector_store=vector_store)

    if chroma_collection.count() == 0:
        documents = SimpleDirectoryReader(input_files=file_paths).load_data()
        splitter  = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        index = VectorStoreIndex.from_documents(documents, storage_context=storage_context, transformations=[splitter], embed_model=embedder)
    else:
        index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embedder, storage_context=storage_context)

    ctx = EngineContext(
        index=index, chroma_collection=chroma_collection, llm=llm, embed_model=embedder, collection_key=chroma_col,
        top_k=top_k, top_q=fusion_num_queries, synthesis_mode=synthesis_mode,
        postprocessors=build_postprocessors(similarity_cutoff, rerank, rerank_top_n, long_reorder),
    )
    query_engine = build_query_engine(retrieval_mode, ctx)
    return query_engine, llm


def run_rag(query_engine, questions, architecture="naive", llm=None,
            xai_log_path=None, exec_num=1, retrieval_mode='naive'):
    """
    Returns list of (answer, hallucinations_count) tuples.

    hallucinations_count values:
      -1 → naive architecture (not applicable)
      -2 → XAI: model never produced citations even after all refinement attempts
       0 → XAI: all citations verified against retrieved chunks
      >0 → XAI: number of unverified citations (potential hallucinations)
    """
    answers = []

    for i, q in enumerate(questions):
        # ─── FASE 1: User Query ───────────────────────────────────────────
        # ─── FASE 2: Document Retrieval ──────────────────────────────────
        # ─── FASE 3: Transparent Response Generation ─────────────────────
        strategy = get_query_strategy(retrieval_mode)
        if architecture == "xai":
            # ─── FASE 4-6: Explainability layer + feedback + refine (see xai.py) ──
            strategy = XAIDecorator(strategy)
        rag_answer, response = strategy.execute(query_engine, q["question"], llm)
        rag_answer     = _clean_answer(rag_answer)
        hallucinations = -1

        if architecture == "xai":
            hallucinations = response.hallucinations
            # ─── XAI TRACE LOG ───────────────────────────────────────────
            if xai_log_path:
                source_texts = [node.text for node in response.source_nodes]
                _write_xai_trace(
                    xai_log_path, exec_num, i, q["question"],
                    rag_answer, hallucinations, response, source_texts, response.citations,
                    response.process_log
                )

        # ─── FASE 7: Final Output ─────────────────────────────────────────
        answers.append((rag_answer, hallucinations))

    return answers
