from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
from db import agents_col, config_snapshots_col
from middleware.auth_middleware import token_required

config_snapshots_bp = Blueprint('config_snapshots', __name__)

AGENT_NOT_FOUND    = 'Agent not found'
INVALID_ID         = 'Invalid ID'
SNAPSHOT_NOT_FOUND = 'Configuration snapshot not found'

SNAPSHOT_FIELDS = ['llm_server_id', 'llm_model', 'embed_server_id', 'embed_model', 'rag_config']


def _serialize(snapshot):
    snapshot['_id'] = str(snapshot['_id'])
    if 'created_at' in snapshot and isinstance(snapshot['created_at'], datetime):
        snapshot['created_at'] = snapshot['created_at'].isoformat()
    return snapshot


@config_snapshots_bp.route('/api/agents/<agent_id>/config-snapshots', methods=['GET'])
@token_required
def list_snapshots(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    snapshots = list(config_snapshots_col.find({'agent_id': agent_id, 'user_id': request.user_id}))
    return jsonify([_serialize(s) for s in snapshots]), 200


@config_snapshots_bp.route('/api/agents/<agent_id>/config-snapshots', methods=['POST'])
@token_required
def create_snapshot(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    data = request.get_json() or {}
    name = data.get('name', '').strip() or f"Config {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    doc = {
        'agent_id': agent_id,
        'user_id': request.user_id,
        'name': name,
        'created_at': datetime.now(timezone.utc)
    }
    for field in SNAPSHOT_FIELDS:
        doc[field] = agent.get(field)

    result = config_snapshots_col.insert_one(doc)
    doc['_id'] = str(result.inserted_id)

    return jsonify(_serialize(doc)), 201


@config_snapshots_bp.route('/api/agents/<agent_id>/config-snapshots/<snapshot_id>', methods=['DELETE'])
@token_required
def delete_snapshot(agent_id, snapshot_id):
    try:
        result = config_snapshots_col.delete_one({
            '_id': ObjectId(snapshot_id),
            'agent_id': agent_id,
            'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if result.deleted_count == 0:
        return jsonify({'error': SNAPSHOT_NOT_FOUND}), 404

    return jsonify({'message': 'Configuration snapshot deleted'}), 200