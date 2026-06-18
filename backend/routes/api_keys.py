from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import secrets
from db import agents_col, api_keys_col
from middleware.auth_middleware import token_required

api_keys_bp = Blueprint('api_keys', __name__)

AGENT_NOT_FOUND = 'Agent not found'
INVALID_ID      = 'Invalid ID'
KEY_NOT_FOUND   = 'API key not found'


def _serialize_key(key, reveal=False):
    key['_id'] = str(key['_id'])
    if 'created_at' in key and isinstance(key['created_at'], datetime):
        key['created_at'] = key['created_at'].isoformat()
    if not reveal:
        raw = key.get('key', '')
        key['key'] = raw[:8] + '...' if len(raw) > 8 else raw
    return key


@api_keys_bp.route('/api/agents/<agent_id>/api-keys', methods=['GET'])
@token_required
def list_keys(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    keys = list(api_keys_col.find({'agent_id': agent_id, 'user_id': request.user_id}))
    return jsonify([_serialize_key(k) for k in keys]), 200


@api_keys_bp.route('/api/agents/<agent_id>/api-keys', methods=['POST'])
@token_required
def create_key(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    data = request.get_json() or {}
    name = data.get('name', '').strip() or f"Key {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
    raw_key = 'ak-' + secrets.token_urlsafe(32)

    doc = {
        'agent_id': agent_id,
        'user_id': request.user_id,
        'name': name,
        'key': raw_key,
        'created_at': datetime.now(timezone.utc)
    }
    result = api_keys_col.insert_one(doc)
    doc['_id'] = str(result.inserted_id)

    return jsonify(_serialize_key(doc, reveal=True)), 201


@api_keys_bp.route('/api/agents/<agent_id>/api-keys/<key_id>', methods=['DELETE'])
@token_required
def delete_key(agent_id, key_id):
    try:
        result = api_keys_col.delete_one({
            '_id': ObjectId(key_id),
            'agent_id': agent_id,
            'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if result.deleted_count == 0:
        return jsonify({'error': KEY_NOT_FOUND}), 404

    return jsonify({'message': 'API key deleted'}), 200