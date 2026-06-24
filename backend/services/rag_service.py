from llama_index.core import VectorStoreIndex, Settings, SimpleDirectoryReader, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.ollama import Ollama
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
import config
from services.llm_providers import get_provider


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


def _setup_settings(agent_config: dict):
    llm_model     = agent_config.get('llm_model', config.DEFAULT_LLM)
    embed_model   = agent_config.get('embed_model', config.DEFAULT_EMBED_MODEL)
    system_prompt = agent_config.get('prompt', '')
    temperature   = agent_config.get('rag_config', {}).get('temperature', 0.1)

    server = _resolve_server(agent_config)
    if server:
        provider = get_provider(server)
        Settings.llm = provider.build_llm(model=llm_model, system_prompt=system_prompt, temperature=temperature)
    else:
        Settings.llm = Ollama(
            model=llm_model,
            request_timeout=600.0,
            system_prompt=system_prompt or None,
            context_window=8000,
            temperature=temperature
        )

    embed_server = _resolve_embed_server(agent_config)
    if not embed_server:
        raise ValueError(
            'No embedding server configured for this agent. '
            'Go to Documents → Embedding Server and select one.'
        )

    embed_provider = get_provider(embed_server)
    Settings.embed_model = embed_provider.build_embedding(embed_model)


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
    _setup_settings({
        'embed_model': embed_model or config.DEFAULT_EMBED_MODEL,
        'embed_server_id': embed_server_id
    })

    _, _, storage_context = _get_chroma_store(agent_id)

    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()

    splitter = SentenceSplitter(
        chunk_size=chunk_size or 512,
        chunk_overlap=chunk_overlap or 50
    )
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        transformations=[splitter]
    )


def query_agent(agent_id: str, question: str, agent_config: dict) -> str:
    """
    Hace una pregunta al RAG del agente y devuelve la respuesta.
    Si el agente no tiene documentos, avisa al usuario.
    """
    _setup_settings(agent_config)

    chroma_collection, vector_store, storage_context = _get_chroma_store(agent_id)

    if chroma_collection.count() == 0:
        return "This agent has no knowledge documents yet. Upload a document first."

    top_k = agent_config.get('rag_config', {}).get('similarity_top_k', 5)

    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context
    )
    query_engine = index.as_query_engine(similarity_top_k=top_k)
    response = query_engine.query(question)
    return str(response).strip()


def stream_query_agent(agent_id: str, question: str, agent_config: dict):
    """
    Generador que cede tokens uno a uno para modo streaming.
    El caller itera sobre él para construir la respuesta progresivamente.
    """
    _setup_settings(agent_config)

    chroma_collection, vector_store, storage_context = _get_chroma_store(agent_id)

    if chroma_collection.count() == 0:
        yield "This agent has no knowledge documents yet. Upload a document first."
        return

    top_k = agent_config.get('rag_config', {}).get('similarity_top_k', 5)

    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context
    )
    query_engine = index.as_query_engine(similarity_top_k=top_k, streaming=True)
    streaming_response = query_engine.query(question)

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


def delete_agent_collection(agent_id: str):
    """
    Borra la colección ChromaDB del agente cuando se elimina el agente.
    """
    try:
        db = chromadb.PersistentClient(path=config.CHROMA_PATH)
        db.delete_collection(f"agent_{agent_id}")
    except Exception:
        pass
