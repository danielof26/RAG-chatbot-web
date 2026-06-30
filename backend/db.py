from pymongo import MongoClient
import config

client = MongoClient(config.MONGO_URI)
db = client.get_default_database()

users_col = db['users']
agents_col = db['agents']
llm_servers_col = db['llm_servers']
api_keys_col = db['api_keys']
chat_messages_col = db['chat_messages']
config_snapshots_col = db['config_snapshots']
evaluation_runs_col = db['evaluation_runs']
