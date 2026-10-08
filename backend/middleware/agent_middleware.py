from functools import wraps

from bson.errors import InvalidId
from flask import jsonify, request

from repositories.agent_repository import AgentRepository

INVALID_ID      = 'Invalid ID'
AGENT_NOT_FOUND = 'Agent not found'


def _load_agent(agent_id: str, owner_scoped: bool):
    """Returns (agent, None) or (None, error_response)."""
    try:
        agent = AgentRepository.find(agent_id, request.user_id if owner_scoped else None)
    except InvalidId:
        return None, (jsonify({'error': INVALID_ID}), 400)
    if not agent:
        return None, (jsonify({'error': AGENT_NOT_FOUND}), 404)
    return agent, None


def _inject_agent(owner_scoped: bool):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            agent, error = _load_agent(kwargs['agent_id'], owner_scoped)
            if error:
                return error
            return f(*args, agent=agent, **kwargs)
        return wrapper
    return decorator


# Loads the agent from the <agent_id> URL parameter and passes it to the view as `agent=`.
# with_agent: only if it belongs to the authenticated user (place it below @token_required).
# with_public_agent: no ownership check (public chat / OpenAPI endpoints).
with_agent        = _inject_agent(owner_scoped=True)
with_public_agent = _inject_agent(owner_scoped=False)
