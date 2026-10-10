"""Public chat and Ollama-compatible endpoints: who can call them and with which API key."""
import pytest

import db


@pytest.fixture(autouse=True)
def fake_answer(monkeypatch):
    """The RAG itself is not under test here, only the access control in front of it."""
    monkeypatch.setattr('routes.agents.query_agent', lambda *a, **k: 'an answer')
    monkeypatch.setattr('routes.ollama.query_agent', lambda *a, **k: 'an answer')
    monkeypatch.setattr('routes.ollama.stream_query_agent', lambda *a, **k: iter(['an ', 'answer']))


def make_agent(**fields):
    return str(db.agents_col.insert_one({'user_id': 'owner', 'name': 'A', 'documents': [], **fields}).inserted_id)


def make_key(client, token_for, agent_id):
    res = client.post(f'/api/agents/{agent_id}/api-keys', json={'name': 'k'}, headers=token_for('owner'))
    assert res.status_code == 201
    return res.get_json()['key']


# Every public way to ask a question: (method, path template, json body)
CHAT_ROUTES = [
    ('/api/public/agents/{a}/chat', {'question': 'hi'}),
    ('/{a}/api/generate', {'prompt': 'hi', 'stream': False}),
    ('/{a}/api/chat', {'messages': [{'role': 'user', 'content': 'hi'}], 'stream': False}),
]
ids = ['public-chat', 'ollama-generate', 'ollama-chat']


# ─── when the agent requires a key ───────────────────────

@pytest.mark.parametrize('path, body', CHAT_ROUTES, ids=ids)
def test_key_required_rejects_missing_and_wrong_key(client, token_for, path, body):
    agent = make_agent(api_key_required=True)
    make_key(client, token_for, agent)
    assert client.post(path.format(a=agent), json=body).status_code == 401
    assert client.post(path.format(a=agent), json=body, headers={'X-API-Key': 'ak-wrong'}).status_code == 401


@pytest.mark.parametrize('path, body', CHAT_ROUTES, ids=ids)
def test_key_required_accepts_the_right_key(client, token_for, path, body):
    agent = make_agent(api_key_required=True)
    key = make_key(client, token_for, agent)
    assert client.post(path.format(a=agent), json=body, headers={'X-API-Key': key}).status_code == 200


@pytest.mark.parametrize('path, body', CHAT_ROUTES, ids=ids)
def test_key_of_another_agent_is_rejected(client, token_for, path, body):
    mine, other = make_agent(api_key_required=True), make_agent(api_key_required=True)
    other_key = make_key(client, token_for, other)
    assert client.post(path.format(a=mine), json=body, headers={'X-API-Key': other_key}).status_code == 401


@pytest.mark.parametrize('path, body', CHAT_ROUTES, ids=ids)
def test_deleted_key_stops_working(client, token_for, path, body):
    agent = make_agent(api_key_required=True)
    key = make_key(client, token_for, agent)
    key_id = str(db.api_keys_col.docs[0]['_id'])
    client.delete(f'/api/agents/{agent}/api-keys/{key_id}', headers=token_for('owner'))
    assert client.post(path.format(a=agent), json=body, headers={'X-API-Key': key}).status_code == 401


def test_keys_are_stored_hashed_and_shown_only_once(client, token_for):
    agent = make_agent(api_key_required=True)
    key = make_key(client, token_for, agent)
    assert key not in str(db.api_keys_col.docs)
    listed = client.get(f'/api/agents/{agent}/api-keys', headers=token_for('owner')).get_json()
    assert key not in str(listed)


# ─── when the agent does not require a key ───────────────

@pytest.mark.parametrize('path, body', CHAT_ROUTES, ids=ids)
def test_agent_without_key_requirement_is_open(client, path, body):
    agent = make_agent(api_key_required=False)
    assert client.post(path.format(a=agent), json=body).status_code == 200


@pytest.mark.parametrize('path, body', CHAT_ROUTES, ids=ids)
def test_unknown_or_malformed_agent_id(client, path, body):
    assert client.post(path.format(a='64b64b64b64b64b64b64b64b'), json=body).status_code == 404
    assert client.post(path.format(a='not-an-id'), json=body).status_code in (400, 404)


@pytest.mark.parametrize('path', ['/api/public/agents/{a}/chat', '/{a}/api/generate', '/{a}/api/chat'])
def test_empty_body_is_a_client_error(client, path):
    agent = make_agent(api_key_required=False)
    assert client.post(path.format(a=agent), json={}).status_code == 400


# ─── KNOWN GAPS (critical point 2) ───────────────────────

@pytest.mark.xfail(strict=True, reason='Known gap (critical point 2): /<id>/api/tags never checks the API key')
def test_tags_endpoint_checks_the_api_key(client, token_for):
    agent = make_agent(api_key_required=True)
    make_key(client, token_for, agent)
    assert client.get(f'/{agent}/api/tags').status_code == 401


@pytest.mark.xfail(strict=True, reason='Known gap (critical point 2): api_key_required defaults to False')
def test_new_agents_require_an_api_key_by_default(client, token_for):
    agent_id = client.post('/api/agents', json={'name': 'new'}, headers=token_for('owner')).get_json()['_id']
    res = client.post(f'/api/public/agents/{agent_id}/chat', json={'question': 'hi'})
    assert res.status_code == 401


@pytest.mark.xfail(strict=True, reason='Known gap (critical point 2): /api/login has no rate limiting')
def test_login_is_rate_limited(client):
    statuses = {client.post('/api/login', json={'email': 'a@x.com', 'password': 'wrong-pass'}).status_code
                for _ in range(50)}
    assert 429 in statuses
