import os
import shutil

import config
from db import agents_col, api_keys_col, chat_messages_col, config_snapshots_col, evaluation_runs_col
from bson import ObjectId
from services.rag_service import delete_agent_collection

# Collections whose documents belong to one agent through an `agent_id` field.
_AGENT_OWNED = (api_keys_col, chat_messages_col, config_snapshots_col, evaluation_runs_col)


def delete_agent_cascade(agent_id: str):
    """Deletes the agent and everything that belongs to it: API keys, chat history, config snapshots,
    evaluation runs, uploaded files and the vector collections."""
    delete_agent_collection(agent_id)
    for collection in _AGENT_OWNED:
        collection.delete_many({'agent_id': agent_id})
    shutil.rmtree(os.path.join(config.UPLOADS_PATH, agent_id), ignore_errors=True)
    agents_col.delete_one({'_id': ObjectId(agent_id)})
