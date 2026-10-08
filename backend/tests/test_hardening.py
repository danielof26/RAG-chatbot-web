"""Input validation, upload limits, cascade delete and error hygiene."""
import io
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from bson import ObjectId

import config
import db
from services.rag_config import validate_rag_config


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
    result = db.agents_col.insert_one({'user_id': 'u1', 'name': 'A', 'documents': []})
    return str(result.inserted_id)


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'UPLOADS_PATH', str(tmp_path))
    # uploading starts an indexing thread: replace it so no model or Chroma is touched
    monkeypatch.setattr('routes.agents._index_in_background', lambda *a, **k: None)
    return tmp_path


def upload(client, auth, agent, name='a.txt', content=b'hello'):
    return client.post(f'/api/agents/{agent}/documents', headers=auth,
                       data={'file': (io.BytesIO(content), name)}, content_type='multipart/form-data')


# ─── rag_config validation ───────────────────────────────

@pytest.mark.parametrize('bad', [
    {'similarity_top_k': 10**9}, {'similarity_top_k': '5'}, {'similarity_top_k': 0}, {'similarity_top_k': True},
    {'similarity_top_k': 2.5}, {'temperature': 9}, {'temperature': None}, {'similarity_cutoff': 3},
    {'chunk_size': 100, 'chunk_overlap': 100}, {'rerank': 'yes'}, {'retrieval_mode': 'magic'},
    {'synthesis_mode': ['compact']}, {'conv_memory_mode': 'x'}, {'conv_memory_turns': 1000}, 'text', [],
])
def test_invalid_rag_config_is_rejected(bad):
    assert validate_rag_config(bad)


def test_valid_rag_config_and_frontend_payload_are_accepted():
    payload = {'similarity_top_k': 5, 'chunk_size': 512, 'chunk_overlap': 50, 'temperature': 0, 'retrieval_mode': 'crag',
               'synthesis_mode': 'compact', 'sim_filter': False, 'similarity_cutoff': 0.7, 'rerank': True,
               'rerank_top_n': 3, 'fusion_num_queries': 1, 'xai': False, 'long_reorder': False,
               'conv_memory': True, 'conv_memory_mode': 'condense', 'conv_memory_turns': 3}
    assert validate_rag_config(payload) is None
    assert validate_rag_config({'similarity_cutoff': None}) is None


def test_update_agent_rejects_bad_rag_config_and_keeps_the_old_one(client, auth, agent):
    res = client.put(f'/api/agents/{agent}', json={'rag_config': {'similarity_top_k': 10**9}}, headers=auth)
    assert res.status_code == 400 and 'similarity_top_k' in res.get_json()['error']
    assert 'rag_config' not in db.agents_col.find_one({'_id': ObjectId(agent)})


def test_every_catalog_mode_is_a_valid_choice():
    from rag_catalog import MODE_TECHS
    for mode in MODE_TECHS:
        assert validate_rag_config({'retrieval_mode': mode}) is None


# ─── uploads ─────────────────────────────────────────────

def test_duplicate_filename_is_rejected_and_the_first_file_is_kept(client, auth, agent, uploads):
    assert upload(client, auth, agent, content=b'first').status_code == 201
    second = upload(client, auth, agent, content=b'second')
    assert second.status_code == 409
    assert (uploads / agent / 'a.txt').read_bytes() == b'first'
    assert len(db.agents_col.find_one({'_id': ObjectId(agent)})['documents']) == 1


def test_unsupported_extension_is_rejected(client, auth, agent, uploads):
    assert upload(client, auth, agent, name='virus.exe').status_code == 400
    assert upload(client, auth, agent, name='noextension').status_code == 400
    assert not (uploads / agent).exists()


def test_extension_check_is_case_insensitive(client, auth, agent, uploads):
    assert upload(client, auth, agent, name='REPORT.PDF').status_code == 201


def test_oversized_request_gets_a_json_413(client, auth, agent, uploads, monkeypatch):
    from app import app
    monkeypatch.setitem(app.config, 'MAX_CONTENT_LENGTH', 100)
    res = upload(client, auth, agent, content=b'x' * 1000)
    assert res.status_code == 413 and 'too large' in res.get_json()['error']


# ─── retry indexing ──────────────────────────────────────

def test_indexing_clears_the_vectors_of_the_file_first(monkeypatch):
    from routes import agents
    calls = []
    monkeypatch.setattr(agents, 'set_document_status', lambda *a, **k: calls.append(('status', a[2].value)))
    monkeypatch.setattr(agents, 'delete_document_vectors', lambda agent_id, path: calls.append(('delete', path)))
    monkeypatch.setattr(agents, 'index_document', lambda *a, **k: calls.append(('index', a[1])))
    agents._index_in_background('a1', '/f/x.txt', 'm', 's', {}, 'x.txt')
    assert [c[0] for c in calls] == ['status', 'delete', 'index', 'status']


# ─── cascade delete ──────────────────────────────────────

def test_deleting_an_agent_removes_everything_it_owns(client, auth, agent, uploads, monkeypatch):
    monkeypatch.setattr('services.agent_cleanup.delete_agent_collection', lambda agent_id: None)
    upload(client, auth, agent)
    other = db.agents_col.insert_one({'user_id': 'u1', 'name': 'B', 'documents': []}).inserted_id
    for col in (db.api_keys_col, db.chat_messages_col, db.config_snapshots_col, db.evaluation_runs_col):
        col.insert_one({'agent_id': agent})
        col.insert_one({'agent_id': str(other)})

    assert client.delete(f'/api/agents/{agent}', headers=auth).status_code == 200

    for col in (db.api_keys_col, db.chat_messages_col, db.config_snapshots_col, db.evaluation_runs_col):
        assert [d['agent_id'] for d in col.docs] == [str(other)]
    assert db.agents_col.find_one({'_id': ObjectId(agent)}) is None
    assert db.agents_col.find_one({'_id': other})
    assert not (uploads / agent).exists()


# ─── error hygiene ───────────────────────────────────────

def test_unexpected_errors_are_not_leaked_to_the_client(client, auth, agent, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('connect to http://10.0.0.5:11434 failed at /srv/app/secret.py')
    monkeypatch.setattr('routes.agents.query_agent', boom)
    for url, headers in ((f'/api/agents/{agent}/chat', auth), (f'/api/public/agents/{agent}/chat', {})):
        res = client.post(url, json={'question': 'hi'}, headers=headers)
        assert res.status_code == 500
        assert '10.0.0.5' not in res.get_data(as_text=True) and 'secret.py' not in res.get_data(as_text=True)


def test_deliberate_value_errors_still_reach_the_user(client, auth, agent, monkeypatch):
    def not_configured(*a, **k):
        raise ValueError('No embedding server configured for this agent.')
    monkeypatch.setattr('routes.agents.query_agent', not_configured)
    res = client.post(f'/api/agents/{agent}/chat', json={'question': 'hi'}, headers=auth)
    assert 'No embedding server configured' in res.get_json()['error']


# ─── unexpected input types ──────────────────────────────

@pytest.mark.parametrize('body', [{'email': 5, 'password': 'secret1'}, {'email': 'a@b.c', 'password': 12345678},
                                  {'email': None, 'password': None}, [1, 2], 'text'])
def test_auth_with_wrong_types_is_a_400_not_a_500(client, body):
    for endpoint in ('register', 'login'):
        assert client.post(f'/api/{endpoint}', json=body).status_code in (400, 401)


@pytest.mark.parametrize('body', [{'question': 5}, {'question': ['x']}, {'question': None}, [1], 'text'])
def test_chat_with_wrong_types_is_a_400(client, auth, agent, body):
    assert client.post(f'/api/agents/{agent}/chat', json=body, headers=auth).status_code == 400
    assert client.post(f'/api/public/agents/{agent}/chat', json=body).status_code == 400


def test_other_endpoints_survive_wrong_types(client, auth, agent):
    assert client.post('/api/agents', json={'name': 5}, headers=auth).status_code == 400
    assert client.post('/api/llm-servers', json={'name': 5, 'type': 5}, headers=auth).status_code == 400
    assert client.post(f'/{agent}/api/generate', json={'prompt': 5}).status_code == 400
    assert client.post(f'/{agent}/api/chat', json={'messages': 'hi'}).status_code == 400
    assert client.post(f'/{agent}/api/chat', json={'messages': [5, {'role': 'user', 'content': 7}]}).status_code == 400
    assert client.post(f'/api/agents/{agent}/api-keys', json={'name': 5}, headers=auth).status_code == 201


# ─── evaluations ─────────────────────────────────────────

def test_dataset_csv_limits_and_clear_errors():
    from services.evaluation_service import parse_questions_csv
    assert parse_questions_csv(b'Question;Keywords;Answer\nq;k;a\n')[0]['question'] == 'q'
    with pytest.raises(ValueError, match='missing column'):
        parse_questions_csv(b'Pregunta;Palabras\nq;k\n')
    with pytest.raises(ValueError, match='larger'):
        parse_questions_csv(b'x' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='more than'):
        parse_questions_csv(b'Question;Keywords\n' + b'q;k\n' * 501)
    with pytest.raises(ValueError):
        parse_questions_csv(b'\xff\xfe\x00')


@pytest.fixture
def snapshot(agent):
    return str(db.config_snapshots_col.insert_one({'agent_id': agent, 'user_id': 'u1', 'name': 's', 'rag_config': {}}).inserted_id)


def start_evaluation(client, auth, agent, snapshot, **form):
    data = {'snapshot_id': snapshot, 'file': (io.BytesIO(b'Question;Keywords\nq;k\n'), 'd.csv'), **form}
    return client.post(f'/api/agents/{agent}/evaluations', headers=auth, data=data, content_type='multipart/form-data')


@pytest.mark.parametrize('form', [{'n_exec': '9999'}, {'n_exec': '0'}, {'n_exec': 'abc'}, {'language': 'fr'}])
def test_evaluation_rejects_unbounded_or_unknown_parameters(client, auth, agent, snapshot, form, monkeypatch):
    monkeypatch.setattr('routes.evaluations.run_evaluation', lambda run_id: None)
    assert start_evaluation(client, auth, agent, snapshot, **form).status_code == 400
    assert db.evaluation_runs_col.docs == []


def test_evaluation_accepts_valid_parameters(client, auth, agent, snapshot, monkeypatch):
    monkeypatch.setattr('routes.evaluations.run_evaluation', lambda run_id: None)
    assert start_evaluation(client, auth, agent, snapshot, n_exec='10', language='es').status_code == 202


def test_evaluations_run_in_parallel_up_to_the_limit(monkeypatch):
    import threading
    import time
    from services import evaluation_service as ev
    db.evaluation_runs_col.insert_one({'_id': ObjectId('0' * 24)})
    running, peak, lock = 0, 0, threading.Lock()

    def fake_run(run_id, run):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.2)
        with lock:
            running -= 1

    monkeypatch.setattr(ev, '_run_evaluation_now', fake_run)
    monkeypatch.setattr(ev, '_update_progress', lambda *a: None)
    threads = [threading.Thread(target=ev.run_evaluation, args=('0' * 24,)) for _ in range(ev.MAX_CONCURRENT_EVALUATIONS + 2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak == ev.MAX_CONCURRENT_EVALUATIONS > 1


# ─── vector deletion ─────────────────────────────────────

def test_deleting_a_document_removes_its_chunks_even_if_the_stored_path_has_a_dot_slash(monkeypatch):
    """Chroma keeps the reader's normalized path ('uploads/a/x.txt'); Mongo keeps './uploads/a/x.txt'."""
    import chromadb
    from services import rag_service
    collection = chromadb.EphemeralClient().get_or_create_collection('delete_test')
    collection.add(ids=['1', '2', '3'], documents=['a', 'b', 'c'], embeddings=[[1.0], [1.0], [1.0]],
                   metadatas=[{'file_path': 'uploads/a/x.txt'}, {'file_path': 'uploads/a/x.txt'},
                              {'file_path': 'uploads/a/y.txt'}])
    monkeypatch.setattr(rag_service, '_get_chroma_store', lambda agent_id: (collection, None, None))
    monkeypatch.setattr(rag_service, 'invalidate_derived_indexes', lambda agent_id: None)

    rag_service.delete_document_vectors('a', './uploads/a/x.txt')

    assert collection.get()['ids'] == ['3']
