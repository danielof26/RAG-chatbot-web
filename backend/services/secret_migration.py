from db import api_keys_col, llm_servers_col
from services.secrets_box import encrypt, hash_api_key, is_encrypted, mask


def migrate_plaintext_secrets() -> dict:
    """Idempotent: protects secrets stored by older versions. Returns how many documents were converted."""
    keys = 0
    for doc in api_keys_col.find({'key': {'$exists': True}}):
        raw = doc['key']
        api_keys_col.update_one(
            {'_id': doc['_id']},
            {'$set': {'key_hash': hash_api_key(raw), 'key_prefix': mask(raw)}, '$unset': {'key': ''}},
        )
        keys += 1

    servers = 0
    for doc in llm_servers_col.find({'api_key': {'$exists': True}}):
        if not is_encrypted(doc['api_key']):
            llm_servers_col.update_one({'_id': doc['_id']}, {'$set': {'api_key': encrypt(doc['api_key'])}})
            servers += 1

    return {'api_keys': keys, 'llm_servers': servers}
