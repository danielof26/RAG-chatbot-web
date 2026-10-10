"""Registration, login and token validation."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

import config
import db

CREDENTIALS = {'email': 'Ana@Example.com', 'password': 'secret123'}


def register(client, **overrides):
    return client.post('/api/register', json={**CREDENTIALS, **overrides})


def login(client, **overrides):
    return client.post('/api/login', json={**CREDENTIALS, **overrides})


def test_register_then_login_returns_a_token_for_that_user(client):
    assert register(client).status_code == 201
    res = login(client)
    assert res.status_code == 200
    payload = jwt.decode(res.get_json()['token'], config.JWT_SECRET, algorithms=['HS256'])
    assert payload['email'] == 'ana@example.com'
    assert payload['user_id'] == str(db.users_col.find_one({'email': 'ana@example.com'})['_id'])


def test_email_is_case_insensitive(client):
    register(client)
    assert login(client, email='ANA@example.COM').status_code == 200


def test_duplicate_registration_is_rejected(client):
    register(client)
    assert register(client, email='ana@example.com').status_code == 409
    assert len(db.users_col.docs) == 1


def test_password_is_stored_hashed(client):
    register(client)
    stored = db.users_col.find_one({'email': 'ana@example.com'})['password']
    assert b'secret123' not in stored


@pytest.mark.parametrize('body', [
    {'email': '', 'password': 'secret123'},
    {'email': 'a@x.com', 'password': ''},
    {'email': 'a@x.com', 'password': '12345'},       # shorter than 6
    {'email': 'a@x.com', 'password': 123456},        # not a string
    {'email': ['a@x.com'], 'password': 'secret123'},
])
def test_invalid_registration_is_rejected(client, body):
    assert client.post('/api/register', json=body).status_code == 400
    assert db.users_col.docs == []


def test_wrong_password_and_unknown_user_get_the_same_answer(client):
    register(client)
    wrong = login(client, password='nope-nope')
    unknown = login(client, email='nobody@example.com')
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()      # does not reveal which emails exist


@pytest.mark.parametrize('body', [None, [], 'text'])
def test_login_requires_a_json_object(client, body):
    assert client.post('/api/login', json=body).status_code == 400


# ─── token validation on a protected route ────────────────

PROTECTED = '/api/agents'


def test_request_without_token_is_rejected(client):
    assert client.get(PROTECTED).status_code == 401


def test_garbage_token_is_rejected(client):
    res = client.get(PROTECTED, headers={'Authorization': 'Bearer not.a.jwt'})
    assert res.status_code == 401 and res.get_json()['error'] == 'Invalid token'


def test_expired_token_is_rejected(client, token_for):
    res = client.get(PROTECTED, headers=token_for('u1', hours=-1))
    assert res.status_code == 401 and res.get_json()['error'] == 'Expired token'


def test_token_signed_with_another_secret_is_rejected(client):
    forged = jwt.encode({'user_id': 'u1', 'email': 'u@x.com', 'exp': datetime.now(timezone.utc) + timedelta(hours=1)},
                        'another-secret', algorithm='HS256')
    assert client.get(PROTECTED, headers={'Authorization': f'Bearer {forged}'}).status_code == 401


def test_unsigned_token_is_rejected(client):
    """The classic `alg: none` attack: a token with no signature must not be accepted."""
    import base64
    import json

    def b64(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()

    exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'user_id': 'u1', 'email': 'u@x.com', 'exp': exp})}."
    assert client.get(PROTECTED, headers={'Authorization': f'Bearer {token}'}).status_code == 401


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason='Known gap: token_required reads payload["user_id"] directly, so a signed token without it crashes (500) instead of 401')
def test_token_without_required_claims_is_rejected(client):
    token = jwt.encode({'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, config.JWT_SECRET, algorithm='HS256')
    res = client.get(PROTECTED, headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 401
