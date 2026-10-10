"""A complete evaluation, from the HTTP request to the stored results. The heavy parts (language models,
spaCy, BERTScore, Chroma) are replaced; scoring, aggregation, progress, status changes and persistence are real."""
import io
import threading

import pytest
from bson import ObjectId

import db
from services import evaluation_service

CSV = (b'Question;Keywords;Answer\n'
       b'What is the capital?;Poseidonia;The capital is Poseidonia\n'
       b'Which river?;Mnemosyne|river;The river is the Mnemosyne\n')


class FakeToken:
    def __init__(self, text):
        self.lemma_ = text


class FakeNlp:
    """Tokenizes on spaces; lemma == the word itself."""
    lang = 'en'

    def __call__(self, text):
        return [FakeToken(w.strip('.,?')) for w in text.split()]


@pytest.fixture
def user(token_for):
    return token_for('u1')


@pytest.fixture
def setup(monkeypatch):
    """Runs the evaluation thread inline and fakes everything that needs a model."""
    answers = {'What is the capital?': 'The capital is Poseidonia.', 'Which river?': 'I do not know.'}
    monkeypatch.setattr(evaluation_service, '_get_nlp', lambda language: FakeNlp())
    monkeypatch.setattr(evaluation_service, '_build_query_engine', lambda *a, **k: (object(), object()))
    monkeypatch.setattr(evaluation_service, 'run_rag',
                        lambda engine, questions, **k: [(answers[questions[0]['question']], -1)])
    monkeypatch.setattr(evaluation_service, 'compute_bertscore', lambda generated, reference, lang='es': 0.5)
    monkeypatch.setattr(evaluation_service, '_cleanup_eval_collection', lambda run_id: None)

    import routes.evaluations as routes

    class InlineThread:
        def __init__(self, target, args, daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(routes.threading, 'Thread', InlineThread)
    return answers


@pytest.fixture
def agent_and_snapshot():
    agent = str(db.agents_col.insert_one({'user_id': 'u1', 'name': 'A', 'prompt': '', 'documents': [
        {'filename': 'a.txt', 'file_path': './uploads/a.txt'}]}).inserted_id)
    snapshot = str(db.config_snapshots_col.insert_one({
        'user_id': 'u1', 'agent_id': agent, 'name': 'baseline', 'rag_config': {'retrieval_mode': 'naive'},
    }).inserted_id)
    return agent, snapshot


def start(client, user, agent, snapshot, csv=CSV, **form):
    data = {'snapshot_id': snapshot, 'language': 'en', 'n_exec': '2', 'file': (io.BytesIO(csv), 'q.csv'), **form}
    return client.post(f'/api/agents/{agent}/evaluations', headers=user, data=data, content_type='multipart/form-data')


def test_finished_run_stores_scores_and_aggregates(client, user, setup, agent_and_snapshot):
    agent, snapshot = agent_and_snapshot
    res = start(client, user, agent, snapshot)
    assert res.status_code == 202

    run = db.evaluation_runs_col.docs[0]
    assert run['status'] == 'done' and run['finished_at']
    per_question = run['results']['per_question']
    assert [q['question'] for q in per_question] == ['What is the capital?', 'Which river?']
    assert per_question[0]['score']['mean'] == 1.0          # "Poseidonia" is in the answer
    assert per_question[1]['score']['mean'] == 0.0          # neither keyword is
    assert per_question[0]['rouge1_mean'] > per_question[1]['rouge1_mean']
    assert per_question[0]['bertscore_mean'] == 0.5

    overall = run['results']['global']
    assert overall['score']['mean'] == 0.5 and overall['score']['min'] == 0.0 and overall['score']['max'] == 1.0
    assert overall['avg_hallucinations'] == -1                # naive architecture: not applicable
    assert overall['avg_bertscore'] == 0.5


def test_every_question_is_asked_n_exec_times(client, user, setup, agent_and_snapshot, monkeypatch):
    asked = []
    monkeypatch.setattr(evaluation_service, 'run_rag',
                        lambda engine, questions, exec_num=1, **k: asked.append((exec_num, questions[0]['question'])) or [('x', -1)])
    agent, snapshot = agent_and_snapshot
    start(client, user, agent, snapshot, n_exec='3')
    assert len(asked) == 6 and {n for n, _ in asked} == {1, 2, 3}


def test_progress_is_reported_while_running(client, user, setup, agent_and_snapshot, monkeypatch):
    seen = []
    original = evaluation_service._update_progress

    def spy(run_id, progress):
        seen.append(progress.get('phase'))
        original(run_id, progress)

    monkeypatch.setattr(evaluation_service, '_update_progress', spy)
    agent, snapshot = agent_and_snapshot
    start(client, user, agent, snapshot, n_exec='1')
    assert seen[0] == 'queued' and 'querying' in seen


def test_failure_marks_the_run_as_error_with_the_reason(client, user, setup, agent_and_snapshot, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('LLM server unreachable')

    monkeypatch.setattr(evaluation_service, '_build_query_engine', boom)
    agent, snapshot = agent_and_snapshot
    start(client, user, agent, snapshot)
    run = db.evaluation_runs_col.docs[0]
    assert run['status'] == 'error' and 'unreachable' in run['error'] and run['finished_at']


def test_agent_without_documents_fails_with_a_clear_message(client, user, setup, agent_and_snapshot):
    agent, snapshot = agent_and_snapshot
    db.agents_col.update_one({'_id': ObjectId(agent)}, {'$set': {'documents': []}})
    start(client, user, agent, snapshot)
    run = db.evaluation_runs_col.docs[0]
    assert run['status'] == 'error' and 'no documents' in run['error']


def test_results_are_readable_through_the_api_after_the_run(client, user, setup, agent_and_snapshot):
    agent, snapshot = agent_and_snapshot
    start(client, user, agent, snapshot)
    run_id = str(db.evaluation_runs_col.docs[0]['_id'])
    detail = client.get(f'/api/agents/{agent}/evaluations/{run_id}', headers=user).get_json()
    assert detail['status'] == 'done' and detail['results']['global']['score']['mean'] == 0.5
    listed = client.get(f'/api/agents/{agent}/evaluations', headers=user).get_json()
    assert listed[0]['global_results']['score']['mean'] == 0.5


# ─── request validation ──────────────────────────────────

@pytest.mark.parametrize('form, status', [
    ({'n_exec': '0'}, 400), ({'n_exec': 'abc'}, 400), ({'n_exec': '999'}, 400),
    ({'language': 'fr'}, 400), ({'snapshot_id': 'nope'}, 400),
    ({'snapshot_id': '64b64b64b64b64b64b64b64b'}, 404),
])
def test_invalid_evaluation_requests_are_rejected(client, user, setup, agent_and_snapshot, form, status):
    agent, snapshot = agent_and_snapshot
    assert start(client, user, agent, snapshot, **form).status_code == status
    assert db.evaluation_runs_col.docs == []


@pytest.mark.parametrize('csv', [b'', b'Question;Keywords\n', b'Foo;Bar\nx;y\n', b'\xff\xfe\x00bad'])
def test_bad_datasets_are_rejected(client, user, setup, agent_and_snapshot, csv):
    agent, snapshot = agent_and_snapshot
    assert start(client, user, agent, snapshot, csv=csv).status_code == 400
    assert db.evaluation_runs_col.docs == []


def test_missing_dataset_file_is_rejected(client, user, setup, agent_and_snapshot):
    agent, snapshot = agent_and_snapshot
    res = client.post(f'/api/agents/{agent}/evaluations', headers=user, data={'snapshot_id': snapshot, 'language': 'en'})
    assert res.status_code == 400


# ─── scoring helpers ─────────────────────────────────────

def test_validate_counts_found_keywords():
    nlp = FakeNlp()
    assert evaluation_service.validate('alpha beta', 'alpha|beta|gamma|delta', nlp) == 0.5
    assert evaluation_service.validate('anything', '', nlp) == 0.0
    assert evaluation_service.validate('ALPHA', 'alpha', nlp) == 1.0


def test_aggregate_of_one_value_has_no_variance():
    assert evaluation_service._aggregate([0.4]) == {'mean': 0.4, 'min': 0.4, 'max': 0.4, 'variance': 0.0, 'std': 0.0}


def test_rouge_of_identical_texts_is_one():
    assert evaluation_service.compute_rouge('the cat sat', 'the cat sat')['rouge1'] == 1.0
