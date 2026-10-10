"""The whole RAG flow through the HTTP API: upload a document, index it in a real (temporary) ChromaDB,
ask a question and get an answer built from it. Only the language model and the embedding model are fake:
the LLM echoes its prompt, so an answer containing the document text proves that retrieval really put the
chunk into the prompt."""
import io

import pytest
from bson import ObjectId
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.llms import MockLLM

import config
import db
from services import rag_service

DOC_TEXT = 'The capital of Atlantis is Poseidonia and its river is the Mnemosyne.'
NO_DOCS = 'no knowledge documents yet'


class FakeProvider:
    def __init__(self, *a, **k):
        pass

    def build_llm(self, model, system_prompt='', temperature=None):
        return MockLLM()

    def build_embedding(self, model):
        return MockEmbedding(embed_dim=8)


@pytest.fixture
def rag_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'CHROMA_PATH', str(tmp_path / 'chroma'))
    monkeypatch.setattr(config, 'UPLOADS_PATH', str(tmp_path / 'uploads'))
    monkeypatch.setattr(rag_service, 'get_provider', lambda server: FakeProvider())
    # Uploading starts a thread; run the indexing inline so the test is deterministic
    import routes.agents as agents_routes

    class InlineThread:
        def __init__(self, target, args, daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(agents_routes.threading, 'Thread', InlineThread)
    yield


@pytest.fixture
def user(token_for):
    return token_for('u1')


@pytest.fixture
def agent(rag_env, user):
    server_id = str(db.llm_servers_col.insert_one({'user_id': 'u1', 'name': 's', 'type': 'ollama',
                                                   'base_url': 'http://fake'}).inserted_id)
    agent_id = str(db.agents_col.insert_one({
        'user_id': 'u1', 'name': 'Atlas', 'documents': [], 'prompt': '', 'llm_model': 'fake', 'embed_model': 'fake',
        'llm_server_id': server_id, 'embed_server_id': server_id,
        'rag_config': {'similarity_top_k': 3, 'chunk_size': 512, 'chunk_overlap': 50, 'temperature': 0},
    }).inserted_id)
    return agent_id


def upload(client, user, agent, name='atlantis.txt', text=DOC_TEXT):
    return client.post(f'/api/agents/{agent}/documents', headers=user,
                       data={'file': (io.BytesIO(text.encode()), name)}, content_type='multipart/form-data')


def ask(client, user, agent, question='What is the capital of Atlantis?'):
    return client.post(f'/api/agents/{agent}/chat', headers=user, json={'question': question})


def document_status(agent_id):
    return db.agents_col.find_one({'_id': ObjectId(agent_id)})['documents'][0]['status']


def test_chat_before_uploading_anything_says_there_are_no_documents(client, user, agent):
    res = ask(client, user, agent)
    assert res.status_code == 200 and NO_DOCS in res.get_json()['answer']


def test_upload_indexes_the_document_and_the_answer_uses_it(client, user, agent):
    assert upload(client, user, agent).status_code == 201
    assert document_status(agent) == 'indexed'

    res = ask(client, user, agent)
    assert res.status_code == 200
    assert 'Poseidonia' in res.get_json()['answer']          # the retrieved chunk reached the prompt


def test_the_question_is_part_of_what_the_model_receives(client, user, agent):
    upload(client, user, agent)
    answer = ask(client, user, agent, 'Name the river of Atlantis').get_json()['answer']
    assert 'Name the river of Atlantis' in answer


def test_chat_is_saved_in_the_history(client, user, agent):
    upload(client, user, agent)
    ask(client, user, agent, 'first question')
    history = client.get(f'/api/agents/{agent}/chat/history', headers=user).get_json()
    assert [m['role'] for m in history] == ['user', 'assistant']
    assert history[0]['content'] == 'first question'

    client.delete(f'/api/agents/{agent}/chat/history', headers=user)
    assert client.get(f'/api/agents/{agent}/chat/history', headers=user).get_json() == []


def test_deleting_the_only_document_empties_the_knowledge(client, user, agent):
    upload(client, user, agent)
    assert client.delete(f'/api/agents/{agent}/documents/atlantis.txt', headers=user).status_code == 200
    assert NO_DOCS in ask(client, user, agent).get_json()['answer']


def test_deleting_one_of_two_documents_keeps_the_other(client, user, agent):
    upload(client, user, agent, 'atlantis.txt', DOC_TEXT)
    upload(client, user, agent, 'mu.txt', 'Mu is a continent whose capital is Lemuria.')
    client.delete(f'/api/agents/{agent}/documents/atlantis.txt', headers=user)

    answer = ask(client, user, agent, 'capital').get_json()['answer']
    assert 'Lemuria' in answer and 'Poseidonia' not in answer


def test_a_second_agent_does_not_see_the_first_agents_documents(client, user, agent):
    upload(client, user, agent)
    other = str(db.agents_col.insert_one({**db.agents_col.find_one({'_id': ObjectId(agent)}), '_id': ObjectId(),
                                          'documents': []}).inserted_id)
    assert NO_DOCS in ask(client, user, other).get_json()['answer']


# router and sub_question need an LLM that answers with structured JSON, which an echoing fake cannot do
@pytest.mark.parametrize('mode', ['naive', 'bm25', 'fusion'])
def test_retrieval_modes_that_need_no_extra_services_return_an_answer(client, user, agent, mode):
    """The engines are wired through the registry: a typo or a broken builder would show up here."""
    upload(client, user, agent)
    db.agents_col.update_one({'_id': ObjectId(agent)}, {'$set': {'rag_config': {
        'similarity_top_k': 3, 'chunk_size': 512, 'chunk_overlap': 50, 'temperature': 0, 'retrieval_mode': mode}}})
    res = ask(client, user, agent)
    assert res.status_code == 200 and res.get_json()['answer'].strip()


def test_agent_without_embedding_server_gives_a_clear_error(client, user, rag_env):
    agent_id = str(db.agents_col.insert_one({'user_id': 'u1', 'name': 'x', 'documents': []}).inserted_id)
    res = ask(client, user, agent_id)
    assert res.status_code == 500 and 'embedding server' in res.get_json()['error'].lower()


def test_conversational_memory_sends_the_previous_turn_with_the_question(client, user, agent):
    upload(client, user, agent)
    db.agents_col.update_one({'_id': ObjectId(agent)}, {'$set': {'rag_config': {
        'similarity_top_k': 3, 'chunk_size': 512, 'chunk_overlap': 50, 'temperature': 0,
        'conv_memory': True, 'conv_memory_mode': 'simple', 'conv_memory_turns': 3}}})
    ask(client, user, agent, 'Tell me about Atlantis')
    answer = ask(client, user, agent, 'and its river?').get_json()['answer']
    assert 'Tell me about Atlantis' in answer                 # the earlier turn was sent along with the new question
