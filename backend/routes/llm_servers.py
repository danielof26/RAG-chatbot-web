from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
from db import llm_servers_col
from middleware.auth_middleware import token_required
from request_utils import json_object, public_error_message, str_field
from serializers import serialize_doc
from services.llm_providers import get_provider, PROVIDERS
from services.secrets_box import decrypt, encrypt, mask

llm_servers_bp = Blueprint('llm_servers', __name__)

SERVER_NOT_FOUND = 'LLM server not found'
INVALID_ID = 'Invalid server ID'


def _serialize(server):
    serialize_doc(server)
    if 'api_key' in server:
        server['api_key'] = mask(decrypt(server['api_key']))
    return server


@llm_servers_bp.route('/api/llm-servers', methods=['GET'])
@token_required
def get_llm_servers():
    servers = list(llm_servers_col.find({'user_id': request.user_id}))
    return jsonify([_serialize(s) for s in servers]), 200


@llm_servers_bp.route('/api/llm-servers', methods=['POST'])
@token_required
def create_llm_server():
    data = json_object()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = str_field(data, 'name')
    server_type = str_field(data, 'type')

    if not name:
        return jsonify({'error': 'Name is required'}), 400

    provider_cls = PROVIDERS.get(server_type)
    if not provider_cls:
        return jsonify({'error': f'Type must be one of: {", ".join(PROVIDERS)}'}), 400

    server = {
        'user_id': request.user_id,
        'name': name,
        'type': server_type,
        'created_at': datetime.now(timezone.utc)
    }

    for field in provider_cls.REQUIRED_FIELDS:
        value = str_field(data, field)
        if not value:
            return jsonify({'error': f'{field} is required for {server_type}'}), 400
        server[field] = value

    if not get_provider(server).validate():
        return jsonify({'error': f'Could not connect to the {server_type} server. Check the URL and credentials.'}), 400

    if 'api_key' in server:
        server['api_key'] = encrypt(server['api_key'])
    result = llm_servers_col.insert_one(server)
    server['_id'] = str(result.inserted_id)
    return jsonify(_serialize(server)), 201


@llm_servers_bp.route('/api/llm-servers/<server_id>', methods=['DELETE'])
@token_required
def delete_llm_server(server_id):
    try:
        result = llm_servers_col.delete_one({
            '_id': ObjectId(server_id),
            'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if result.deleted_count == 0:
        return jsonify({'error': SERVER_NOT_FOUND}), 404

    return jsonify({'message': 'Server deleted'}), 200


@llm_servers_bp.route('/api/llm-servers/<server_id>/models', methods=['GET'])
@token_required
def get_server_models(server_id):
    try:
        server = llm_servers_col.find_one({
            '_id': ObjectId(server_id),
            'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not server:
        return jsonify({'error': SERVER_NOT_FOUND}), 404

    try:
        provider = get_provider(server)
        models = provider.get_models()
        return jsonify({'models': models}), 200
    except Exception as e:
        return jsonify({'error': public_error_message(e)}), 500