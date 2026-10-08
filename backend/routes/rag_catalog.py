from flask import Blueprint, jsonify

from middleware.auth_middleware import token_required
from rag_catalog import get_catalog

rag_catalog_bp = Blueprint('rag_catalog', __name__)


@rag_catalog_bp.route('/api/rag/techniques', methods=['GET'])
@token_required
def list_techniques():
    return jsonify(get_catalog()), 200
