from bson import ObjectId

from db import agents_col


class AgentRepository:
    """Single place that knows how agents are looked up in MongoDB."""

    @staticmethod
    def find(agent_id: str, user_id: str = None):
        """Returns the agent (restricted to its owner when user_id is given) or None if it doesn't exist.
        Raises bson.errors.InvalidId when agent_id is not a valid ObjectId."""
        query = {'_id': ObjectId(agent_id)}
        if user_id is not None:
            query['user_id'] = user_id
        return agents_col.find_one(query)
