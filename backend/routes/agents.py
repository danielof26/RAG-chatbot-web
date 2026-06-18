from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import os
import threading
import traceback
from db import agents_col, api_keys_col
from middleware.auth_middleware import token_required
from services.rag_service import index_document, query_agent, delete_agent_collection, delete_document_vectors
import config

agents_bp = Blueprint('agents', __name__)

DOC_FILENAME    = 'documents.filename'
DOC_STATUS      = 'documents.$.status'
INVALID_ID      = 'Invalid ID agent'
AGENT_NOT_FOUND = 'Agent not found'
BODY_REQUIRED   = 'Body JSON required'


def _index_in_background(agent_id, file_path, embed_model, embed_server_id, filename):
    try:
        agents_col.update_one(
            {'_id': ObjectId(agent_id), DOC_FILENAME: filename},
            {'$set': {DOC_STATUS: 'indexing'}}
        )
        index_document(agent_id, file_path, embed_model=embed_model, embed_server_id=embed_server_id)
        agents_col.update_one(
            {'_id': ObjectId(agent_id), DOC_FILENAME: filename},
            {'$set': {DOC_STATUS: 'indexed'}}
        )
    except Exception as e:
        traceback.print_exc()
        agents_col.update_one(
            {'_id': ObjectId(agent_id), DOC_FILENAME: filename},
            {'$set': {DOC_STATUS: 'error', 'documents.$.error': str(e)}}
        )


def _serialize(agent):
    """Convierte los tipos de MongoDB a tipos serializables en JSON."""
    agent['_id'] = str(agent['_id'])
    for field in ['created_at', 'updated_at']:
        if field in agent and isinstance(agent[field], datetime):
            agent[field] = agent[field].isoformat()
    if 'documents' in agent:
        for doc in agent['documents']:
            if 'uploaded_at' in doc and isinstance(doc['uploaded_at'], datetime):
                doc['uploaded_at'] = doc['uploaded_at'].isoformat()
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
            'chunk_overlap': 50
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
def get_agent(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404
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
def delete_agent(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    delete_agent_collection(agent_id)
    agents_col.delete_one({'_id': ObjectId(agent_id)})
    return jsonify({'message': 'Agent deleted'}), 200


# ─── Documentos ──────────────────────────────────────────

@agents_bp.route('/api/agents/<agent_id>/documents', methods=['POST'])
@token_required
def upload_document(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No document has been uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Document name is empty'}), 400

    # Guardar archivo en disco
    agent_folder = os.path.join(config.UPLOADS_PATH, agent_id)
    os.makedirs(agent_folder, exist_ok=True)
    file_path = os.path.join(agent_folder, file.filename)
    file.save(file_path)

    # Guardar metadatos en MongoDB con estado pendiente
    agents_col.update_one(
        {'_id': ObjectId(agent_id)},
        {
            '$push': {'documents': {
                'filename': file.filename,
                'file_path': file_path,
                'uploaded_at': datetime.now(timezone.utc),
                'status': 'pending'
            }},
            '$set': {'updated_at': datetime.now(timezone.utc)}
        }
    )

    # Lanzar la indexación automáticamente
    thread = threading.Thread(
        target=_index_in_background,
        args=(agent_id, file_path, agent.get('embed_model'), agent.get('embed_server_id'), file.filename),
        daemon=True
    )
    thread.start()

    return jsonify({'message': f'Document "{file.filename}" uploaded. Indexing started.'}), 201


@agents_bp.route('/api/agents/<agent_id>/documents', methods=['GET'])
@token_required
def get_documents(agent_id):
    try:
        agent = agents_col.find_one(
            {'_id': ObjectId(agent_id), 'user_id': request.user_id},
            {'documents': 1}
        )
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    documents = agent.get('documents', [])
    for doc in documents:
        if 'uploaded_at' in doc and isinstance(doc['uploaded_at'], datetime):
            doc['uploaded_at'] = doc['uploaded_at'].isoformat()

    return jsonify(documents), 200


@agents_bp.route('/api/agents/<agent_id>/documents/<filename>/index', methods=['POST'])
@token_required
def index_document_endpoint(agent_id, filename):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    doc = next((d for d in agent.get('documents', []) if d['filename'] == filename), None)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if doc.get('status') == 'indexing':
        return jsonify({'error': 'Document is already being indexed'}), 409

    thread = threading.Thread(
        target=_index_in_background,
        args=(agent_id, doc['file_path'], agent.get('embed_model'), agent.get('embed_server_id'), filename),
        daemon=True
    )
    thread.start()

    return jsonify({'message': f'Indexing started for "{filename}"'}), 202


@agents_bp.route('/api/agents/<agent_id>/documents/<filename>', methods=['DELETE'])
@token_required
def delete_document(agent_id, filename):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    doc = next((d for d in agent.get('documents', []) if d['filename'] == filename), None)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

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

@agents_bp.route('/api/agents/<agent_id>/chat', methods=['POST'])
@token_required
def chat(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

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


# ─── Endpoint público (sin JWT, con API Key opcional) ─────

@agents_bp.route('/api/public/agents/<agent_id>/chat', methods=['POST'])
def public_chat(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id)})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    if agent.get('api_key_required', False):
        provided = request.headers.get('X-API-Key', '')
        valid = api_keys_col.find_one({'agent_id': agent_id, 'key': provided})
        if not valid:
            return jsonify({'error': 'Invalid or missing API key'}), 401

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
