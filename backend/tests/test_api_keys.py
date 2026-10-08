from datetime import datetime, timedelta, timezone

import jwt
import pytest
from bson import ObjectId

import config
import db
from services import secrets_box


@pytest.fixture
def client():
    from app import app
    return app.test_client()


@pytest.fixture
def auth():
    token = jwt.encode({'user_id': 'u1', 'email': 'u@x.com',
                        'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, config.JWT_SECRET, algorithm='HS256')
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def agent():
    result = db.agents_col.insert_one({'user_id': 'u1', 'name': 'A', 'api_key_required': True, 'documents': []})
    return str(result.inserted_id)


def test_created_key_is_shown_once_and_never_stored_in_plaintext(client, auth, agent):
    created = client.post(f'/api/agents/{agent}/api-keys', json={'name': 'k'}, headers=auth)
    assert created.status_code == 201
    raw = created.get_json()['key']
    assert raw.startswith('ak-') and len(raw) > 20

    stored = db.api_keys_col.docs[0]
    assert 'key' not in stored and raw not in str(stored)
    assert stored['key_hash'] == secrets_box.hash_api_key(raw)

    listed = client.get(f'/api/agents/{agent}/api-keys', headers=auth).get_json()
    assert listed[0]['key'] == raw[:8] + '...'
    assert 'key_hash' not in listed[0]


def test_public_endpoint_accepts_only_a_valid_key(client, auth, agent):
    raw = client.post(f'/api/agents/{agent}/api-keys', json={}, headers=auth).get_json()['key']
    from middleware.auth_middleware import api_key_error
    from app import app

    def check(header):
        with app.test_request_context(headers=header):
            return api_key_error(db.agents_col.docs[0] | {'_id': ObjectId(agent)})

    assert check({'X-API-Key': raw}) is None
    assert check({'X-API-Key': 'ak-wrong'})[1] == 401
    assert check({})[1] == 401


def test_other_users_cannot_list_or_create_keys(client, agent):
    token = jwt.encode({'user_id': 'u2', 'email': 'o@x.com',
                        'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, config.JWT_SECRET, algorithm='HS256')
    headers = {'Authorization': f'Bearer {token}'}
    assert client.get(f'/api/agents/{agent}/api-keys', headers=headers).status_code == 404
    assert client.post(f'/api/agents/{agent}/api-keys', json={}, headers=headers).status_code == 404


def test_delete_key(client, auth, agent):
    created = client.post(f'/api/agents/{agent}/api-keys', json={}, headers=auth).get_json()
    assert client.delete(f'/api/agents/{agent}/api-keys/{created["_id"]}', headers=auth).status_code == 200
    assert db.api_keys_col.docs == []


def test_llm_server_listing_masks_the_decrypted_key(client, auth):
    db.llm_servers_col.insert_one({'user_id': 'u1', 'name': 's', 'type': 'gemini',
                                   'api_key': secrets_box.encrypt('AIzaSyABCDEFGH')})
    listed = client.get('/api/llm-servers', headers=auth).get_json()
    assert listed[0]['api_key'] == 'AIzaSyAB...'


def test_get_provider_decrypts_the_key():
    from services.llm_providers import get_provider
    server = {'type': 'gemini', 'api_key': secrets_box.encrypt('AIzaSyABCDEFGH')}
    assert get_provider(server).api_key == 'AIzaSyABCDEFGH'
    assert server['api_key'].startswith(secrets_box.ENCRYPTED_PREFIX)  # the stored dict is not mutated
