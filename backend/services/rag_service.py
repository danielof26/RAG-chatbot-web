from llama_index.core import VectorStoreIndex, Settings, SimpleDirectoryReader, StorageContext
from llama_index.core.indices.prompt_helper import ChatPromptHelper, PromptHelper
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.postprocessor import LongContextReorder
from llama_index.llms.ollama import Ollama
import copy
import threading
from dataclasses import dataclass, field
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
import config
from services.llm_providers import CONTEXT_WINDOW, get_provider
from services.query_strategies import get_query_strategy
from services.rag_config import RagConfig


# LlamaIndex sizes prompt packing from the *global* Settings.llm when building any response synthesizer.
# Per-request models are passed explicitly (see RagContext), so Settings.llm is never set; without these
# process-wide constants it would silently fall back to a 3900-token window instead of CONTEXT_WINDOW.
Settings.prompt_helper = PromptHelper(context_window=CONTEXT_WINDOW)
Settings.chat_prompt_helper = ChatPromptHelper(context_window=CONTEXT_WINDOW)


def _condense_question(question: str, chat_history: list, llm) -> str:
    """Reformulates a follow-up question as a standalone question using chat history."""
    if not chat_history:
        return question
    history_text = '\n'.join(
        f"{'Human' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in chat_history
    )
    prompt = (
        "Given the following conversation history and a follow-up question, "
        "rephrase the follow-up question as a standalone question that captures "
        "all necessary context.\n\n"
        f"Chat History:\n{history_text}\n\n"
        f"Follow-up Question: {question}\n\n"
        "Standalone Question:"
    )
    return str(llm.complete(prompt)).strip()


def _resolve_server(agent_config: dict):
    """Obtiene el servidor LLM configurado en el agente desde MongoDB, o None."""
    server_id = agent_config.get('llm_server_id')
    if not server_id:
        return None
    from db import llm_servers_col
    from bson import ObjectId
    try:
        return llm_servers_col.find_one({'_id': ObjectId(str(server_id))})
    except Exception:
        return None


def _resolve_embed_server(agent_config: dict):
    """Obtiene el servidor de embeddings configurado en el agente, o None."""
    server_id = agent_config.get('embed_server_id')
    if not server_id:
        return None
    from db import llm_servers_col
    from bson import ObjectId
    try:
        return llm_servers_col.find_one({'_id': ObjectId(str(server_id))})
    except Exception:
        return None


@dataclass(frozen=True)
class RagContext:
    """Per-request models. Passed explicitly everywhere instead of the process-global llama_index Settings,
    so concurrent requests of agents with different models cannot overwrite each other."""
    llm: object
    embed_model: object


def _build_context(agent_config: dict) -> RagContext:
    llm_model     = agent_config.get('llm_model', config.DEFAULT_LLM)
    embed_model   = agent_config.get('embed_model', config.DEFAULT_EMBED_MODEL)
    system_prompt = agent_config.get('prompt', '')
    temperature   = RagConfig.from_dict(agent_config.get('rag_config')).temperature

    server = _resolve_server(agent_config)
    if server:
        provider = get_provider(server)
        llm = provider.build_llm(model=llm_model, system_prompt=system_prompt, temperature=temperature)
    else:
        llm = Ollama(
            model=llm_model,
            request_timeout=600.0,
            system_prompt=system_prompt or None,
            context_window=CONTEXT_WINDOW,
            temperature=temperature
        )

    embed_server = _resolve_embed_server(agent_config)
    if not embed_server:
        raise ValueError(
            'No embedding server configured for this agent. '
            'Go to Documents → Embedding Server and select one.'
        )

    embed_provider = get_provider(embed_server)
    return RagContext(llm=llm, embed_model=embed_provider.build_embedding(embed_model))


def _get_chroma_store(agent_id: str):
    """Abre (o crea) la colección ChromaDB del agente y devuelve los objetos necesarios."""
    db = chromadb.PersistentClient(path=config.CHROMA_PATH)
    collection_name = f"agent_{agent_id}"
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return chroma_collection, vector_store, storage_context


def index_document(agent_id: str, file_path: str, embed_model: str = None, embed_server_id: str = None,
                    chunk_size: int = None, chunk_overlap: int = None):
    """
    Indexa un documento en la colección ChromaDB del agente.
    Se puede llamar varias veces para añadir más documentos.
    """
    models = _build_context({
        'embed_model': embed_model or config.DEFAULT_EMBED_MODEL,
        'embed_server_id': embed_server_id
    })

    _, _, storage_context = _get_chroma_store(agent_id)

    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()

    splitter = SentenceSplitter(
        chunk_size=chunk_size or 512,
        chunk_overlap=chunk_overlap or 50
    )
    try:
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            transformations=[splitter],
            embed_model=models.embed_model
        )
    finally:
        invalidate_derived_indexes(agent_id)


def _build_router_engine(index, llm, top_k: int, node_postprocessors=None):
    from llama_index.core.query_engine import RouterQueryEngine, SubQuestionQueryEngine, CustomQueryEngine
    from llama_index.core.selectors import LLMSingleSelector
    from llama_index.core.tools import QueryEngineTool

    node_postprocessors = node_postprocessors or []
    engine_simple = index.as_query_engine(similarity_top_k=top_k, response_mode='compact', llm=llm,
                                           node_postprocessors=node_postprocessors)

    from llama_index.core.question_gen import LLMQuestionGenerator
    engine_multihop = SubQuestionQueryEngine.from_defaults(
        query_engine_tools=[
            QueryEngineTool.from_defaults(
                query_engine=engine_simple,
                description="Useful for answering questions about the documents"
            )
        ],
        question_gen=LLMQuestionGenerator.from_defaults(llm=llm),
        llm=llm,
        use_async=False
    )

    engine_summary = index.as_query_engine(similarity_top_k=top_k * 3, response_mode='tree_summarize', llm=llm,
                                            node_postprocessors=node_postprocessors)

    class _OODEngine(CustomQueryEngine):
        def custom_query(self, query_str: str):
            return "No tengo información sobre ese tema en los documentos disponibles."

    tools = [
        QueryEngineTool.from_defaults(
            query_engine=engine_simple,
            description=(
                "Use for simple factual questions about a specific person, event, date, or number. "
                "Examples: '¿Quién es X?', '¿Cuándo ocurrió Y?', '¿Cuántos Z tiene?'"
            )
        ),
        QueryEngineTool.from_defaults(
            query_engine=engine_multihop,
            description=(
                "Use for complex questions requiring reasoning across multiple sources or in steps. "
                "Examples: '¿Cómo influyó X en Y?', '¿Qué relación hay entre A y B?'"
            )
        ),
        QueryEngineTool.from_defaults(
            query_engine=engine_summary,
            description=(
                "Use for broad questions asking for an overview or summary of a topic. "
                "Examples: 'Resume el documento', '¿De qué tratan los documentos?'"
            )
        ),
        QueryEngineTool.from_defaults(
            query_engine=_OODEngine(),
            description=(
                "Use ONLY when the question is clearly unrelated to the uploaded documents "
                "and cannot be answered from the available context."
            )
        ),
    ]

    return RouterQueryEngine(selector=LLMSingleSelector.from_defaults(llm=llm), query_engine_tools=tools, llm=llm, verbose=True)


def _build_sub_question_engine(index, llm, top_k: int, node_postprocessors=None):
    """
    Descompone la pregunta en sub-preguntas (vía LLMQuestionGenerator) y responde cada una
    por separado contra el índice vectorial antes de combinar las respuestas parciales.
    Misma construcción que la rama 'multihop' interna de _build_router_engine, pero aquí
    se aplica siempre en lugar de dejar que el selector del router decida si usarla o no.
    """
    from llama_index.core.query_engine import SubQuestionQueryEngine
    from llama_index.core.question_gen import LLMQuestionGenerator
    from llama_index.core.tools import QueryEngineTool

    base_engine = index.as_query_engine(similarity_top_k=top_k, response_mode='compact', llm=llm,
                                         node_postprocessors=node_postprocessors or [])
    return SubQuestionQueryEngine.from_defaults(
        query_engine_tools=[
            QueryEngineTool.from_defaults(
                query_engine=base_engine,
                description="Useful for answering questions about the documents"
            )
        ],
        question_gen=LLMQuestionGenerator.from_defaults(llm=llm),
        llm=llm,
        use_async=False
    )


# Chroma stores these alongside a node's own metadata for its internal bookkeeping (notably
# _node_content, a JSON dump of the entire original node — text, relationships, class info —
# which can be larger than the chunk's own text). They must be stripped before reusing a
# chunk's metadata to build a brand new Document/TextNode, or that bookkeeping leaks into the
# new node's own metadata and inflates every token budget (chunking, embedding, LLM prompt)
# that accounts for metadata size.
_CHROMA_INTERNAL_METADATA_KEYS = {'_node_content', '_node_type', 'doc_id', 'ref_doc_id', 'document_id'}


def _clean_chroma_metadata(meta: dict) -> dict:
    return {k: v for k, v in (meta or {}).items() if k not in _CHROMA_INTERNAL_METADATA_KEYS}


def _build_raptor_engine(collection_key: str, chroma_collection, llm, embed_model, top_k: int, synthesis_mode: str, node_postprocessors=None):
    """
    collection_key identifies the RAPTOR tree's own ChromaDB collection (separate from the
    base vector index). The chat path uses "agent_{agent_id}" and the evaluation path uses
    "eval_{run_id}", matching each one's own base collection name.
    """
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core import Document
    from services.raptor_retriever import RaptorRetriever

    db = chromadb.PersistentClient(path=config.CHROMA_PATH)
    raptor_chroma = db.get_or_create_collection(f"{collection_key}_raptor")
    raptor_vector_store = ChromaVectorStore(chroma_collection=raptor_chroma)

    if raptor_chroma.count() == 0:
        print(f"[RAPTOR] Building tree for {collection_key}...")
        raw = chroma_collection.get(include=['documents', 'metadatas'])
        documents = [
            Document(text=text, metadata=_clean_chroma_metadata(meta))
            for text, meta in zip(raw['documents'], raw['metadatas'])
        ]
    else:
        print(f"[RAPTOR] Reusing existing tree ({raptor_chroma.count()} nodes) for {collection_key}.")
        documents = []

    retriever = RaptorRetriever(
        documents,
        embed_model=embed_model,
        llm=llm,
        vector_store=raptor_vector_store,
        similarity_top_k=top_k,
        tree_depth=2,
        mode="collapsed",
    )

    return RetrieverQueryEngine.from_args(retriever, llm=llm, response_mode=synthesis_mode,
                                           node_postprocessors=node_postprocessors or [])




# Building the BM25 index tokenizes every chunk of the collection, so it is cached per collection and
# reused across requests. An entry is valid while the collection keeps the same number of chunks, and
# is dropped explicitly whenever documents are added or removed (invalidate_derived_indexes).
_BM25_CACHE_MAX = 32
_bm25_cache = {}      # collection name -> (chunk count, BM25Retriever)
_bm25_lock = threading.Lock()


def _build_bm25_base(chroma_collection):
    from llama_index.retrievers.bm25 import BM25Retriever
    from llama_index.core.schema import TextNode

    raw = chroma_collection.get(include=['documents', 'metadatas'])
    nodes = [
        TextNode(text=doc, metadata=_clean_chroma_metadata(meta))
        for doc, meta in zip(raw['documents'], raw['metadatas'])
    ]
    return BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=max(len(nodes), 1))


def _build_bm25_retriever(chroma_collection, top_k: int):
    """Sparse/keyword retriever (term frequency, no embeddings) over the chunks already in ChromaDB."""
    name, count = chroma_collection.name, chroma_collection.count()
    with _bm25_lock:
        cached = _bm25_cache.get(name)
        if cached is None or cached[0] != count:
            _bm25_cache.pop(name, None)
            if len(_bm25_cache) >= _BM25_CACHE_MAX:
                _bm25_cache.pop(next(iter(_bm25_cache)))
            cached = (count, _build_bm25_base(chroma_collection))
            _bm25_cache[name] = cached
    # Per-request shallow copy: shares the (read-only) index but has its own top_k.
    retriever = copy.copy(cached[1])
    retriever.similarity_top_k = max(1, min(top_k, int(retriever.bm25.scores['num_docs'])))
    return retriever


def invalidate_bm25_cache(collection_name: str):
    with _bm25_lock:
        _bm25_cache.pop(collection_name, None)


def invalidate_derived_indexes(agent_id: str):
    """Drops what is derived from the agent's chunks (BM25 index, RAPTOR tree) after its documents change.
    Both are rebuilt lazily by the next query that needs them."""
    invalidate_bm25_cache(f"agent_{agent_id}")
    try:
        chromadb.PersistentClient(path=config.CHROMA_PATH).delete_collection(f"agent_{agent_id}_raptor")
    except Exception:
        pass


def _build_bm25_engine(chroma_collection, llm, top_k: int, node_postprocessors=None):
    from llama_index.core.query_engine import RetrieverQueryEngine
    return RetrieverQueryEngine.from_args(_build_bm25_retriever(chroma_collection, top_k), llm=llm,
                                           node_postprocessors=node_postprocessors or [])


def _build_fusion_engine(index, chroma_collection, llm, top_k: int, top_q: int, node_postprocessors=None):
    from llama_index.core.retrievers import QueryFusionRetriever
    from llama_index.core.query_engine import RetrieverQueryEngine

    vector_retriever = index.as_retriever(similarity_top_k=top_k)
    bm25_retriever = _build_bm25_retriever(chroma_collection, top_k)

    fusion_retriever = QueryFusionRetriever(
        [vector_retriever, bm25_retriever],
        llm=llm,
        similarity_top_k=top_k,
        num_queries=top_q,
        mode="reciprocal_rerank",
        use_async=False,
        verbose=True,
    )
    return RetrieverQueryEngine.from_args(fusion_retriever, llm=llm, node_postprocessors=node_postprocessors or [])


@dataclass
class EngineContext:
    """Everything an engine builder may need; shared by the chat path and the evaluation path."""
    index: object
    chroma_collection: object
    llm: object
    embed_model: object
    collection_key: str          # "agent_{id}" in chat, "eval_{run_id}" in evaluation (names the RAPTOR tree)
    top_k: int = 5
    top_q: int = 1               # fusion_num_queries
    synthesis_mode: str = 'compact'
    postprocessors: list = field(default_factory=list)
    streaming: bool = False


RERANK_MODEL = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
_reranker_base = None
_reranker_lock = threading.Lock()


def _get_reranker(top_n):
    """The cross-encoder is loaded once; each call gets a cheap copy that shares it but has its own top_n."""
    global _reranker_base
    with _reranker_lock:
        if _reranker_base is None:
            _reranker_base = SentenceTransformerRerank(model=RERANK_MODEL, top_n=top_n)
    return _reranker_base.model_copy(update={'top_n': top_n})


def build_postprocessors(similarity_cutoff=None, rerank=False, rerank_top_n=3, long_reorder=False) -> list:
    postprocessors = []
    if similarity_cutoff:
        postprocessors.append(SimilarityPostprocessor(similarity_cutoff=similarity_cutoff))
    if rerank:
        postprocessors.append(_get_reranker(rerank_top_n))
    if long_reorder:
        postprocessors.append(LongContextReorder())
    return postprocessors


# retrieval_mode -> function(EngineContext) -> query engine. Modes not registered here
# (naive, hyde_*, crag, self_rag) use the plain vector engine; they differ only in their QueryStrategy.
_ENGINE_BUILDERS = {}


def _register_engine(mode: str):
    def decorator(builder):
        _ENGINE_BUILDERS[mode] = builder
        return builder
    return decorator


@_register_engine('router')
def _router_engine(ctx):
    return _build_router_engine(ctx.index, ctx.llm, ctx.top_k, node_postprocessors=ctx.postprocessors)


@_register_engine('fusion')
def _fusion_engine(ctx):
    return _build_fusion_engine(ctx.index, ctx.chroma_collection, ctx.llm, ctx.top_k, ctx.top_q, node_postprocessors=ctx.postprocessors)


@_register_engine('raptor')
def _raptor_engine(ctx):
    return _build_raptor_engine(ctx.collection_key, ctx.chroma_collection, ctx.llm, ctx.embed_model, ctx.top_k, ctx.synthesis_mode,
                                node_postprocessors=ctx.postprocessors)


@_register_engine('sub_question')
def _sub_question_engine(ctx):
    return _build_sub_question_engine(ctx.index, ctx.llm, ctx.top_k, node_postprocessors=ctx.postprocessors)


@_register_engine('bm25')
def _bm25_engine(ctx):
    return _build_bm25_engine(ctx.chroma_collection, ctx.llm, ctx.top_k, node_postprocessors=ctx.postprocessors)


def _vector_engine(ctx):
    return ctx.index.as_query_engine(similarity_top_k=ctx.top_k, response_mode=ctx.synthesis_mode, llm=ctx.llm,
                                     node_postprocessors=ctx.postprocessors, streaming=ctx.streaming)


def build_query_engine(retrieval_mode: str, ctx: EngineContext):
    return _ENGINE_BUILDERS.get(retrieval_mode, _vector_engine)(ctx)


# Modes whose answer is produced by strategy.execute() in one piece (custom engines, or strategies
# that retrieve/critique on their own), so they cannot stream token by token.
NON_STREAMING_MODES = frozenset({'crag', 'self_rag', 'router', 'fusion', 'raptor', 'sub_question', 'bm25'})


def query_agent(agent_id: str, question: str, agent_config: dict, chat_history: list = None) -> str:
    """
    Hace una pregunta al RAG del agente y devuelve la respuesta.
    Si el agente no tiene documentos, avisa al usuario.
    """
    models = _build_context(agent_config)

    chroma_collection, vector_store, storage_context = _get_chroma_store(agent_id)

    if chroma_collection.count() == 0:
        return "This agent has no knowledge documents yet. Upload a document first."

    rag_config = RagConfig.from_dict(agent_config.get('rag_config'))
    retrieval_mode = rag_config.retrieval_mode

    # Conversational memory: reformulate question or build synthesis context
    effective_question = question
    synthesis_question = None
    if rag_config.conv_memory and chat_history:
        conv_mode = rag_config.conv_memory_mode
        if conv_mode == 'condense':
            effective_question = _condense_question(question, chat_history, models.llm)
        else:  # simple: include history in synthesis prompt, keep original for retrieval
            history_lines = '\n'.join(
                f"{'Human' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
                for m in chat_history
            )
            synthesis_question = (
                f"Conversation history:\n{history_lines}\n\n"
                f"Current question: {question}"
            )

    index = VectorStoreIndex.from_vector_store(vector_store, embed_model=models.embed_model, storage_context=storage_context)
    ctx = EngineContext(
        index=index, chroma_collection=chroma_collection, llm=models.llm, embed_model=models.embed_model,
        collection_key=f"agent_{agent_id}",
        top_k=rag_config.similarity_top_k, top_q=rag_config.fusion_num_queries,
        synthesis_mode=rag_config.synthesis_mode,
        postprocessors=build_postprocessors(rag_config.effective_cutoff, rag_config.rerank,
                                            rag_config.rerank_top_n, rag_config.long_reorder),
        streaming=False,
    )
    query_engine = build_query_engine(retrieval_mode, ctx)
    strategy = get_query_strategy(retrieval_mode)
    answer, _ = strategy.execute(query_engine, effective_question, models.llm, synthesis_question=synthesis_question)
    if not answer or not answer.strip():
        answer = "I could not find relevant information in the documents to answer this question."
    return answer


def stream_query_agent(agent_id: str, question: str, agent_config: dict, chat_history: list = None):
    """
    Generador que cede tokens uno a uno para modo streaming.
    El caller itera sobre él para construir la respuesta progresivamente.
    """
    models = _build_context(agent_config)

    chroma_collection, vector_store, storage_context = _get_chroma_store(agent_id)

    if chroma_collection.count() == 0:
        yield "This agent has no knowledge documents yet. Upload a document first."
        return

    rag_config = RagConfig.from_dict(agent_config.get('rag_config'))
    retrieval_mode = rag_config.retrieval_mode

    # Conversational memory
    effective_question = question
    synthesis_question = None
    if rag_config.conv_memory and chat_history:
        conv_mode = rag_config.conv_memory_mode
        if conv_mode == 'condense':
            effective_question = _condense_question(question, chat_history, models.llm)
        else:
            history_lines = '\n'.join(
                f"{'Human' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
                for m in chat_history
            )
            synthesis_question = (
                f"Conversation history:\n{history_lines}\n\n"
                f"Current question: {question}"
            )

    index = VectorStoreIndex.from_vector_store(vector_store, embed_model=models.embed_model, storage_context=storage_context)
    ctx = EngineContext(
        index=index, chroma_collection=chroma_collection, llm=models.llm, embed_model=models.embed_model,
        collection_key=f"agent_{agent_id}",
        top_k=rag_config.similarity_top_k, top_q=rag_config.fusion_num_queries,
        synthesis_mode=rag_config.synthesis_mode,
        postprocessors=build_postprocessors(rag_config.effective_cutoff, rag_config.rerank,
                                            rag_config.rerank_top_n, rag_config.long_reorder),
        streaming=True,
    )
    query_engine = build_query_engine(retrieval_mode, ctx)
    strategy = get_query_strategy(retrieval_mode)
    if retrieval_mode in NON_STREAMING_MODES:
        answer, _ = strategy.execute(query_engine, effective_question, models.llm, synthesis_question=synthesis_question)
        for word in answer.split(' '):
            yield word + ' '
    else:
        q = synthesis_question or effective_question
        query = strategy.build_query(effective_question, models.llm)
        from llama_index.core import QueryBundle
        if isinstance(query, QueryBundle):
            query = QueryBundle(query_str=q, custom_embedding_strs=query.custom_embedding_strs)
        else:
            query = q
        streaming_response = query_engine.query(query)
        for token in streaming_response.response_gen:
            yield token


def delete_document_vectors(agent_id: str, file_path: str):
    """
    Borra de la colección ChromaDB del agente todos los vectores que pertenecen
    a un documento concreto, identificándolos por el metadato 'file_path' que
    SimpleDirectoryReader adjunta a cada chunk al indexar.
    """
    chroma_collection, _, _ = _get_chroma_store(agent_id)
    try:
        chroma_collection.delete(where={'file_path': file_path})
    except Exception:
        pass
    invalidate_derived_indexes(agent_id)


def delete_agent_collection(agent_id: str):
    """
    Borra la colección ChromaDB del agente cuando se elimina el agente.
    """
    db = chromadb.PersistentClient(path=config.CHROMA_PATH)
    for name in (f"agent_{agent_id}", f"agent_{agent_id}_raptor"):
        try:
            db.delete_collection(name)
        except Exception:
            pass
    invalidate_bm25_cache(f"agent_{agent_id}")
