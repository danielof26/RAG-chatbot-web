from flask import request, jsonify
from functools import wraps
import jwt
import config

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token required'}), 401

        if token.startswith('Bearer '):
            token = token.split(' ')[1]

        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=['HS256'])
            request.user_id = payload['user_id']
            request.user_email = payload['email']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Expired token'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated


def api_key_error(agent):
    """Devuelve una respuesta 401 si el agente exige API key y la petición no trae una válida; si no, None."""
    if not agent.get('api_key_required', False):
        return None
    from db import api_keys_col
    provided = request.headers.get('X-API-Key', '')
    if api_keys_col.find_one({'agent_id': str(agent['_id']), 'key': provided}):
        return None
    return jsonify({'error': 'Invalid or missing API key'}), 401
