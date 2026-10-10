"""One user must never read, change or use another user's resources.

Two users, `alice` and `bob`. Everything alice owns is requested with bob's token and must look like it does
not exist (404). Tests marked xfail(strict=True) document a KNOWN gap: they fail today and will start
failing as "unexpected pass" the moment the gap is fixed, which is the signal to remove the marker."""
import pytest
from bson import ObjectId

import db
from services import rag_service

ALICE, BOB = 'alice', 'bob'


@pytest.fixture
def alice(token_for):
    return token_for(ALICE)


@pytest.fixture
def bob(token_for):
    return token_for(BOB)


@pytest.fixture
def alice_agent():
    return str(db.agents_col.insert_one({
        'user_id': ALICE, 'name': 'Alice agent', 'documents': [{'filename': 'a.txt', 'file_path': './x/a.txt'}],
    }).inserted_id)


@pytest.fixture
def alice_server():
    return str(db.llm_servers_col.insert_one({
        'user_id': ALICE, 'name': 'Alice Gemini', 'type': 'gemini', 'api_key': 'encrypted',
    }).inserted_id)


@pytest.fixture
def alice_snapshot(alice_agent):
    return str(db.config_snapshots_col.insert_one({
        'user_id': ALICE, 'agent_id': alice_agent, 'name': 'snap', 'rag_config': {},
    }).inserted_id)


@pytest.fixture
def alice_key(alice_agent):
    return str(db.api_keys_col.insert_one({
        'user_id': ALICE, 'agent_id': alice_agent, 'name': 'k', 'key_hash': 'h', 'key_prefix': 'ak-xxx',
    }).inserted_id)


@pytest.fixture
def alice_run(alice_agent, alice_snapshot):
    from datetime import datetime, timezone
    return str(db.evaluation_runs_col.insert_one({
        'user_id': ALICE, 'agent_id': alice_agent, 'snapshot_id': alice_snapshot, 'snapshot_name': 'snap',
        'status': 'done', 'xai': False, 'n_exec': 1, 'language': 'en', 'dataset': [], 'results': None,
        'created_at': datetime.now(timezone.utc),
    }).inserted_id)


# ─── agents ──────────────────────────────────────────────

def test_listing_only_shows_own_agents(client, alice_agent, bob):
    assert client.get('/api/agents', headers=bob).get_json() == []


@pytest.mark.parametrize('method, path, body', [
    ('get',    '/api/agents/{a}', None),
    ('put',    '/api/agents/{a}', {'name': 'hacked'}),
    ('delete', '/api/agents/{a}', None),
    ('get',    '/api/agents/{a}/documents', None),
    ('delete', '/api/agents/{a}/documents/a.txt', None),
    ('post',   '/api/agents/{a}/documents/a.txt/index', None),
    ('post',   '/api/agents/{a}/chat', {'question': 'hi'}),
    ('get',    '/api/agents/{a}/chat/history', None),
    ('delete', '/api/agents/{a}/chat/history', None),
    ('get',    '/api/agents/{a}/api-keys', None),
    ('post',   '/api/agents/{a}/api-keys', {'name': 'mine now'}),
    ('get',    '/api/agents/{a}/config-snapshots', None),
    ('post',   '/api/agents/{a}/config-snapshots', {'name': 'mine now'}),
    ('get',    '/api/agents/{a}/evaluations', None),
])
def test_other_users_agent_routes_answer_404(client, bob, alice_agent, method, path, body):
    res = getattr(client, method)(path.format(a=alice_agent), headers=bob, **({'json': body} if body else {}))
    assert res.status_code == 404


def test_other_user_cannot_modify_or_delete_the_agent(client, bob, alice_agent):
    client.put(f'/api/agents/{alice_agent}', json={'name': 'hacked'}, headers=bob)
    client.delete(f'/api/agents/{alice_agent}', headers=bob)
    stored = db.agents_col.find_one({'_id': ObjectId(alice_agent)})
    assert stored and stored['name'] == 'Alice agent'


def test_owner_still_has_access(client, alice, alice_agent):
    assert client.get(f'/api/agents/{alice_agent}', headers=alice).status_code == 200


# ─── chat history ────────────────────────────────────────

def test_history_of_a_shared_agent_id_is_per_user(client, alice, bob, alice_agent):
    db.chat_messages_col.insert_one({'agent_id': alice_agent, 'user_id': ALICE, 'role': 'user', 'content': 'secret'})
    assert client.get(f'/api/agents/{alice_agent}/chat/history', headers=alice).get_json()[0]['content'] == 'secret'
    assert client.get(f'/api/agents/{alice_agent}/chat/history', headers=bob).status_code == 404


# ─── nested resources addressed directly by id ───────────

def test_other_user_cannot_delete_snapshot_key_or_run(client, bob, alice_agent, alice_snapshot, alice_key, alice_run):
    base = f'/api/agents/{alice_agent}'
    assert client.delete(f'{base}/config-snapshots/{alice_snapshot}', headers=bob).status_code == 404
    assert client.delete(f'{base}/api-keys/{alice_key}', headers=bob).status_code == 404
    assert client.delete(f'{base}/evaluations/{alice_run}', headers=bob).status_code == 404
    assert len(db.config_snapshots_col.docs) == len(db.api_keys_col.docs) == len(db.evaluation_runs_col.docs) == 1


def test_other_user_cannot_read_an_evaluation(client, bob, alice_agent, alice_run):
    assert client.get(f'/api/agents/{alice_agent}/evaluations/{alice_run}', headers=bob).status_code == 404


def test_owner_can_read_own_evaluation(client, alice, alice_agent, alice_run):
    assert client.get(f'/api/agents/{alice_agent}/evaluations/{alice_run}', headers=alice).status_code == 200


def test_cannot_evaluate_with_another_users_snapshot(client, bob, alice_agent, alice_snapshot):
    """Bob owns nothing here: both the agent and the snapshot are alice's."""
    res = client.post(f'/api/agents/{alice_agent}/evaluations', headers=bob, data={'snapshot_id': alice_snapshot})
    assert res.status_code == 404


def test_snapshot_of_my_agent_must_belong_to_me(client, alice, bob, alice_snapshot):
    """Bob's own agent + alice's snapshot id: the snapshot lookup is scoped by user and agent."""
    bob_agent = str(db.agents_col.insert_one({'user_id': BOB, 'name': 'B', 'documents': []}).inserted_id)
    res = client.post(f'/api/agents/{bob_agent}/evaluations', headers=bob, data={'snapshot_id': alice_snapshot})
    assert res.status_code == 404


# ─── LLM servers ─────────────────────────────────────────

def test_servers_are_listed_per_user(client, bob, alice_server):
    assert client.get('/api/llm-servers', headers=bob).get_json() == []


def test_other_user_cannot_delete_or_list_models_of_a_server(client, bob, alice_server):
    assert client.delete(f'/api/llm-servers/{alice_server}', headers=bob).status_code == 404
    assert client.get(f'/api/llm-servers/{alice_server}/models', headers=bob).status_code == 404
    assert len(db.llm_servers_col.docs) == 1


def test_api_key_is_never_returned_in_clear(client, alice, monkeypatch):
    monkeypatch.setattr('routes.llm_servers.get_provider', lambda server: type('P', (), {'validate': lambda self: True})())
    res = client.post('/api/llm-servers', headers=alice, json={'name': 'g', 'type': 'gemini', 'api_key': 'AIzaSECRETVALUE1234'})
    assert res.status_code == 201
    assert 'SECRETVALUE' not in res.get_data(as_text=True)
    assert 'SECRETVALUE' not in client.get('/api/llm-servers', headers=alice).get_data(as_text=True)
    assert 'SECRETVALUE' not in db.llm_servers_col.docs[0]['api_key']       # encrypted at rest


# ─── KNOWN GAPS: using somebody else's LLM server (critical point 1) ────────

IDOR = 'Known gap (critical point 1): the server id is never checked against the agent owner'


@pytest.mark.xfail(strict=True, reason=IDOR)
@pytest.mark.parametrize('field', ['llm_server_id', 'embed_server_id'])
def test_agent_cannot_be_saved_pointing_to_another_users_server(client, bob, alice_server, field):
    bob_agent = str(db.agents_col.insert_one({'user_id': BOB, 'name': 'B', 'documents': []}).inserted_id)
    res = client.put(f'/api/agents/{bob_agent}', json={field: alice_server}, headers=bob)
    assert res.status_code in (400, 403, 404)
    assert field not in db.agents_col.find_one({'_id': ObjectId(bob_agent)})


@pytest.mark.xfail(strict=True, reason=IDOR)
@pytest.mark.parametrize('resolver', ['_resolve_server', '_resolve_embed_server'])
def test_rag_service_does_not_resolve_a_server_of_another_owner(alice_server, resolver):
    agent = {'user_id': BOB, 'llm_server_id': alice_server, 'embed_server_id': alice_server}
    assert getattr(rag_service, resolver)(agent) is None


@pytest.mark.xfail(strict=True, reason=IDOR)
@pytest.mark.parametrize('resolver', ['_resolve_llm_provider', '_resolve_embed_provider'])
def test_evaluation_does_not_resolve_a_server_of_another_owner(alice_server, resolver):
    from services import evaluation_service
    snapshot = {'user_id': BOB, 'llm_server_id': alice_server, 'embed_server_id': alice_server}
    with pytest.raises(Exception):
        provider = getattr(evaluation_service, resolver)(snapshot)
        if provider.__class__.__name__ == 'OllamaProvider':
            raise ValueError          # silent fallback to the local Ollama is also acceptable
        pytest.fail(f'resolved a foreign server: {provider!r}')
