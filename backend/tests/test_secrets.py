from services import secrets_box
from services.secret_migration import migrate_plaintext_secrets
import db


def test_hash_is_deterministic_and_not_the_key():
    assert secrets_box.hash_api_key('ak-abc') == secrets_box.hash_api_key('ak-abc')
    assert secrets_box.hash_api_key('ak-abc') != secrets_box.hash_api_key('ak-abd')
    assert 'ak-abc' not in secrets_box.hash_api_key('ak-abc')


def test_encrypt_roundtrip_and_prefix():
    token = secrets_box.encrypt('sk-secret-value')
    assert token.startswith(secrets_box.ENCRYPTED_PREFIX)
    assert 'sk-secret-value' not in token
    assert secrets_box.decrypt(token) == 'sk-secret-value'


def test_encrypt_is_idempotent_and_decrypt_passes_legacy_plaintext():
    token = secrets_box.encrypt('x' * 20)
    assert secrets_box.encrypt(token) == token
    assert secrets_box.decrypt('legacy-plaintext') == 'legacy-plaintext'


def test_mask():
    assert secrets_box.mask('ak-1234567890') == 'ak-12345...'
    assert secrets_box.mask('short') == '...'


def test_migration_protects_legacy_secrets_and_is_idempotent():
    db.api_keys_col.insert_one({'agent_id': 'a', 'key': 'ak-legacy-key-123'})
    db.llm_servers_col.insert_one({'name': 's', 'type': 'gemini', 'api_key': 'plain-provider-key'})

    assert migrate_plaintext_secrets() == {'api_keys': 1, 'llm_servers': 1}

    key = db.api_keys_col.docs[0]
    assert 'key' not in key
    assert key['key_hash'] == secrets_box.hash_api_key('ak-legacy-key-123')
    assert key['key_prefix'] == 'ak-legac...'
    server = db.llm_servers_col.docs[0]
    assert secrets_box.decrypt(server['api_key']) == 'plain-provider-key'

    assert migrate_plaintext_secrets() == {'api_keys': 0, 'llm_servers': 0}
