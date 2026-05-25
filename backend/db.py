from pymongo import MongoClient
import config

client = MongoClient(config.MONGO_URI)
db = client.get_default_database()

users_col = db['users']
agents_col = db['agents']
