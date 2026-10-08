from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
from db import config_snapshots_col
from middleware.agent_middleware import INVALID_ID, with_agent
from middleware.auth_middleware import token_required
from serializers import serialize_doc

config_snapshots_bp = Blueprint('config_snapshots', __name__)

SNAPSHOT_NOT_FOUND = 'Configuration snapshot not found'

SNAPSHOT_FIELDS = ['llm_server_id', 'llm_model', 'embed_server_id', 'embed_model', 'rag_config']


def _serialize(snapshot):
    return serialize_doc(snapshot)


@config_snapshots_bp.route('/api/agents/<agent_id>/config-snapshots', methods=['GET'])
@token_required
@with_agent
def list_snapshots(agent_id, agent):
    snapshots = list(config_snapshots_col.find({'agent_id': agent_id, 'user_id': request.user_id}))
    return jsonify([_serialize(s) for s in snapshots]), 200


@config_snapshots_bp.route('/api/agents/<agent_id>/config-snapshots', methods=['POST'])
@token_required
@with_agent
def create_snapshot(agent_id, agent):
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