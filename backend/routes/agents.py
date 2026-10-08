from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import os
import threading
import traceback
from db import agents_col, chat_messages_col
from services.rag_config import RagConfig
from middleware.agent_middleware import AGENT_NOT_FOUND, INVALID_ID, with_agent, with_public_agent
from middleware.auth_middleware import token_required, api_key_error
from serializers import isoformat_fields, serialize_doc
from services.job_state import claim_document_for_indexing, set_document_status
from states import DocumentStatus
from services.rag_service import index_document, query_agent, delete_agent_collection, delete_document_vectors
import config

agents_bp = Blueprint('agents', __name__)

DOC_FILENAME    = 'documents.filename'
BODY_REQUIRED   = 'Body JSON required'


def _index_in_background(agent_id, file_path, embed_model, embed_server_id, rag_config, filename):
    try:
        set_document_status(agent_id, filename, DocumentStatus.INDEXING)
        index_document(
            agent_id, file_path,
            embed_model=embed_model,
            embed_server_id=embed_server_id,
            chunk_size=rag_config.get('chunk_size'),
            chunk_overlap=rag_config.get('chunk_overlap')
        )
        set_document_status(agent_id, filename, DocumentStatus.INDEXED)
    except Exception as e:
        traceback.print_exc()
        set_document_status(agent_id, filename, DocumentStatus.ERROR, error=str(e))


def _serialize(agent):
    """Convierte los tipos de MongoDB a tipos serializables en JSON."""
    serialize_doc(agent, ('created_at', 'updated_at'))
    for doc in agent.get('documents', []):
        isoformat_fields(doc, ('uploaded_at',))
    return agent


# ─── CRUD ────────────────────────────────────────────────

@agents_bp.route('/api/agents', methods=['POST'])
@token_required
def create_agent():
    data = request.get_json()
    if not data:
        return jsonify({'error': BODY_REQUIRED}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'You must assign a name to the agent'}), 400

    agent = {
        'user_id': request.user_id,
        'name': name,
        'description': '',
        'prompt': '',
        'llm_model': config.DEFAULT_LLM,
        'embed_model': config.DEFAULT_EMBED_MODEL,
        'rag_config': {
            'similarity_top_k': 5,
            'chunk_size': 512,
            'chunk_overlap': 50,
            'temperature': 0.1
        },
        'documents': [],
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }

    result = agents_col.insert_one(agent)
    agent['_id'] = str(result.inserted_id)
    return jsonify(_serialize(agent)), 201


@agents_bp.route('/api/agents', methods=['GET'])
@token_required
def get_agents():
    agents = list(agents_col.find({'user_id': request.user_id}))
    return jsonify([_serialize(a) for a in agents]), 200


@agents_bp.route('/api/agents/<agent_id>', methods=['GET'])
@token_required
@with_agent
def get_agent(agent_id, agent):
    return jsonify(_serialize(agent)), 200


@agents_bp.route('/api/agents/<agent_id>', methods=['PUT'])
@token_required
def update_agent(agent_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': BODY_REQUIRED}), 400

    allowed = {'name', 'description', 'prompt', 'llm_model', 'embed_model', 'rag_config', 'llm_server_id', 'embed_server_id', 'api_key_required'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({'error': 'Nothing to update'}), 400

    updates['updated_at'] = datetime.now(timezone.utc)

    try:
        result = agents_col.update_one(
            {'_id': ObjectId(agent_id), 'user_id': request.user_id},
            {'$set': updates}
        )
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if result.matched_count == 0:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    agent = agents_col.find_one({'_id': ObjectId(agent_id)})
    return jsonify(_serialize(agent)), 200


@agents_bp.route('/api/agents/<agent_id>', methods=['DELETE'])
@token_required
@with_agent
def delete_agent(agent_id, agent):
    delete_agent_collection(agent_id)
    agents_col.delete_one({'_id': ObjectId(agent_id)})
    return jsonify({'message': 'Agent deleted'}), 200


# ─── Documentos ──────────────────────────────────────────

@agents_bp.route('/api/agents/<agent_id>/documents', methods=['POST'])
@token_required
@with_agent
def upload_document(agent_id, agent):
    if 'file' not in request.files:
        return jsonify({'error': 'No document has been uploaded'}), 400

    file = request.files['file']
    # Solo el nombre base: evita que "../../x" escriba fuera de la carpeta del agente
    filename = os.path.basename(file.filename.replace('\\', '/')) if file.filename else ''
    if filename in ('', '.', '..'):
        return jsonify({'error': 'Document name is empty'}), 400

    # Guardar archivo en disco
    agent_folder = os.path.join(config.UPLOADS_PATH, agent_id)
    os.makedirs(agent_folder, exist_ok=True)
    file_path = os.path.join(agent_folder, filename)
    file.save(file_path)

    # Guardar metadatos en MongoDB con estado pendiente
    agents_col.update_one(
        {'_id': ObjectId(agent_id)},
        {
            '$push': {'documents': {
                'filename': filename,
                'file_path': file_path,
                'uploaded_at': datetime.now(timezone.utc),
                'status': DocumentStatus.PENDING.value
            }},
            '$set': {'updated_at': datetime.now(timezone.utc)}
        }
    )

    # Lanzar la indexación automáticamente
    thread = threading.Thread(
        target=_index_in_background,
        args=(agent_id, file_path, agent.get('embed_model'), agent.get('embed_server_id'), agent.get('rag_config', {}), filename),
        daemon=True
    )
    thread.start()

    return jsonify({'message': f'Document "{filename}" uploaded. Indexing started.'}), 201


@agents_bp.route('/api/agents/<agent_id>/documents', methods=['GET'])
@token_required
@with_agent
def get_documents(agent_id, agent):
    documents = agent.get('documents', [])
    for doc in documents:
        isoformat_fields(doc, ('uploaded_at',))

    return jsonify(documents), 200


@agents_bp.route('/api/agents/<agent_id>/documents/<filename>/index', methods=['POST'])
@token_required
@with_agent
def index_document_endpoint(agent_id, filename, agent):
    doc = next((d for d in agent.get('documents', []) if d['filename'] == filename), None)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not claim_document_for_indexing(agent_id, filename):
        return jsonify({'error': 'Document is already being indexed'}), 409

    thread = threading.Thread(
        target=_index_in_background,
        args=(agent_id, doc['file_path'], agent.get('embed_model'), agent.get('embed_server_id'), agent.get('rag_config', {}), filename),
        daemon=True
    )
    thread.start()

    return jsonify({'message': f'Indexing started for "{filename}"'}), 202


@agents_bp.route('/api/agents/<agent_id>/documents/<filename>', methods=['DELETE'])
@token_required
@with_agent
def delete_document(agent_id, filename, agent):
    documents = agent.get('documents', [])
    doc = next((d for d in documents if d['filename'] == filename), None)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if len(documents) == 1:
        delete_agent_collection(agent_id)
    else:
        delete_document_vectors(agent_id, doc['file_path'])

    try:
        os.remove(doc['file_path'])
    except OSError:
        pass

    agents_col.update_one(
        {'_id': ObjectId(agent_id)},
        {
            '$pull': {'documents': {'filename': filename}},
            '$set': {'updated_at': datetime.now(timezone.utc)}
        }
    )

    return jsonify({'message': f'Document "{filename}" deleted'}), 200


# ─── Chat ────────────────────────────────────────────────

def _save_message(agent_id, user_id, role, content):
    chat_messages_col.insert_one({
        'agent_id': agent_id,
        'user_id': user_id,
        'role': role,
        'content': content,
        'created_at': datetime.now(timezone.utc)
    })


@agents_bp.route('/api/agents/<agent_id>/chat', methods=['POST'])
@token_required
@with_agent
def chat(agent_id, agent):
    data = request.get_json()
    if not data:
        return jsonify({'error': BODY_REQUIRED}), 400

    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'Question is mandatory'}), 400

    # Fetch conversation history for memory-aware retrieval
    rag_config = RagConfig.from_dict(agent.get('rag_config'))
    chat_history = None
    if rag_config.conv_memory:
        turns = int(rag_config.conv_memory_turns)
        recent = list(chat_messages_col.find(
            {'agent_id': agent_id, 'user_id': request.user_id}
        ).sort('created_at', -1).limit(turns * 2))
        recent.reverse()
        chat_history = [{'role': m['role'], 'content': m['content']} for m in recent]

    try:
        answer = query_agent(agent_id, question, agent, chat_history=chat_history)
    except Exception as e:
        return jsonify({'error': f'Error at processing the question: {str(e)}'}), 500

    _save_message(agent_id, request.user_id, 'user', question)
    _save_message(agent_id, request.user_id, 'assistant', answer)

    return jsonify({'answer': answer}), 200


@agents_bp.route('/api/agents/<agent_id>/chat/history', methods=['GET'])
@token_required
@with_agent
def get_chat_history(agent_id, agent):
    messages = list(chat_messages_col.find(
        {'agent_id': agent_id, 'user_id': request.user_id}
    ).sort('created_at', 1))

    for m in messages:
        serialize_doc(m)

    return jsonify(messages), 200


@agents_bp.route('/api/agents/<agent_id>/chat/history', methods=['DELETE'])
@token_required
@with_agent
def clear_chat_history(agent_id, agent):
    chat_messages_col.delete_many({'agent_id': agent_id, 'user_id': request.user_id})
    return jsonify({'message': 'Chat history cleared'}), 200


# ─── Endpoint público (sin JWT, con API Key opcional) ─────

@agents_bp.route('/api/public/agents/<agent_id>/chat', methods=['POST'])
@with_public_agent
def public_chat(agent_id, agent):
    error = api_key_error(agent)
    if error:
        return error

    data = request.get_json()
    if not data:
        return jsonify({'error': BODY_REQUIRED}), 400

    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'Question is mandatory'}), 400

    try:
        answer = query_agent(agent_id, question, agent)
    except Exception as e:
        return jsonify({'error': f'Error at processing the question: {str(e)}'}), 500

    return jsonify({'answer': answer}), 200
