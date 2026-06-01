from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import os
from db import agents_col
from middleware.auth_middleware import token_required
from services.rag_service import index_document, query_agent, delete_agent_collection
import config

agents_bp = Blueprint('agents', __name__)


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
        return jsonify({'error': 'Body JSON required'}), 400

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
        return jsonify({'error': 'Invalid ID agent'}), 400

    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    return jsonify(_serialize(agent)), 200


@agents_bp.route('/api/agents/<agent_id>', methods=['PUT'])
@token_required
def update_agent(agent_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON required'}), 400

    allowed = {'name', 'description', 'prompt', 'llm_model', 'embed_model', 'rag_config'}
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
        return jsonify({'error': 'Invalid ID agent'}), 400

    if result.matched_count == 0:
        return jsonify({'error': 'Agent not found'}), 404

    agent = agents_col.find_one({'_id': ObjectId(agent_id)})
    return jsonify(_serialize(agent)), 200


@agents_bp.route('/api/agents/<agent_id>', methods=['DELETE'])
@token_required
def delete_agent(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': 'Invalid ID agent'}), 400

    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

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
        return jsonify({'error': 'Invalid ID agent'}), 400

    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

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

    # Indexar en ChromaDB
    try:
        index_document(agent_id, file_path, embed_model=agent.get('embed_model'))
    except Exception as e:
        return jsonify({'error': f'Error at document indexing: {str(e)}'}), 500

    # Guardar metadatos en MongoDB
    agents_col.update_one(
        {'_id': ObjectId(agent_id)},
        {
            '$push': {'documents': {
                'filename': file.filename,
                'file_path': file_path,
                'uploaded_at': datetime.now(timezone.utc)
            }},
            '$set': {'updated_at': datetime.now(timezone.utc)}
        }
    )

    return jsonify({'message': f'Document "{file.filename}" uploaded and indexed correctly'}), 201


# ─── Chat ────────────────────────────────────────────────

@agents_bp.route('/api/agents/<agent_id>/chat', methods=['POST'])
@token_required
def chat(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': 'Invalid ID agent'}), 400

    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON required'}), 400

    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'Question is mandatory'}), 400

    try:
        answer = query_agent(agent_id, question, agent)
    except Exception as e:
        return jsonify({'error': f'Error at processing the question: {str(e)}'}), 500

    return jsonify({'answer': answer}), 200
