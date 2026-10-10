"""Test setup: replaces every MongoDB collection in `db` with an in-memory fake BEFORE the app modules are
imported, so the tests never touch a real database."""
import os
import sys
from types import SimpleNamespace

import pytest
from bson import ObjectId
from cryptography.fernet import Fernet

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db  # noqa: E402


def _match(doc, query):
    for field, cond in query.items():
        if '.' in field:                                   # "documents.filename": any array element matches
            head, tail = field.split('.', 1)
            items = doc.get(head)
            if not isinstance(items, list) or not any(isinstance(i, dict) and _match(i, {tail: cond}) for i in items):
                return False
            continue
        value = doc.get(field)
        if isinstance(cond, dict):
            if '$exists' in cond and (field in doc) != cond['$exists']:
                return False
            if '$in' in cond and value not in cond['$in']:
                return False
            if '$nin' in cond and value in cond['$nin']:
                return False
            if '$elemMatch' in cond and not any(_match(i, cond['$elemMatch']) for i in (value or [])):
                return False
        elif value != cond:
            return False
    return True


def _positional_index(doc, query, array):
    """Index of the first element of `doc[array]` selected by the query (what Mongo's `$` operator refers to)."""
    condition = {}
    for field, cond in query.items():
        if field.startswith(array + '.'):
            condition[field[len(array) + 1:]] = cond
        elif field == array and isinstance(cond, dict) and '$elemMatch' in cond:
            condition.update(cond['$elemMatch'])
    return next(i for i, item in enumerate(doc.get(array, [])) if _match(item, condition))


def _apply_set(doc, query, fields):
    for key, value in fields.items():
        if '.$.' in key:
            array, sub = key.split('.$.')
            doc[array][_positional_index(doc, query, array)][sub] = value
        else:
            doc[key] = value


class FakeCursor(list):
    """The slice of pymongo's Cursor the app uses: chainable sort() and limit()."""

    def sort(self, key, direction=1):
        super().sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def limit(self, n):
        del self[n:]
        return self


class FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc.setdefault('_id', ObjectId())
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id=doc['_id'])

    def find(self, query=None, projection=None):
        return FakeCursor(dict(d) for d in self.docs if _match(d, query or {}))

    def find_one(self, query=None):
        found = self.find(query)
        return found[0] if found else None

    def update_one(self, query, update):
        for d in self.docs:
            if _match(d, query):
                _apply_set(d, query, update.get('$set', {}))
                for field, value in update.get('$push', {}).items():
                    d.setdefault(field, []).append(value)
                for field, pulled in update.get('$pull', {}).items():
                    d[field] = [i for i in d.get(field, []) if not _match(i, pulled)]
                for field in update.get('$unset', {}):
                    d.pop(field, None)
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    def update_many(self, *args, **kwargs):
        return SimpleNamespace(matched_count=0, modified_count=0)

    def delete_one(self, query):
        for d in self.docs:
            if _match(d, query):
                self.docs.remove(d)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def delete_many(self, query):
        kept = [d for d in self.docs if not _match(d, query)]
        deleted, self.docs[:] = len(self.docs) - len(kept), kept
        return SimpleNamespace(deleted_count=deleted)


COLLECTIONS = [n for n in dir(db) if n.endswith('_col')]
for _name in COLLECTIONS:
    setattr(db, _name, FakeCollection())


@pytest.fixture(autouse=True)
def clean_db():
    for name in COLLECTIONS:
        getattr(db, name).docs.clear()


@pytest.fixture(autouse=True)
def fixed_encryption_key(monkeypatch):
    from services import secrets_box
    monkeypatch.setattr(secrets_box, '_fernet', Fernet(Fernet.generate_key()))


@pytest.fixture
def client():
    from app import app
    return app.test_client()


@pytest.fixture
def token_for():
    """Factory: `token_for('u1')` returns the Authorization header of that user."""
    import jwt
    from datetime import datetime, timedelta, timezone
    import config

    def make(user_id, hours=1):
        token = jwt.encode({'user_id': user_id, 'email': f'{user_id}@x.com',
                            'exp': datetime.now(timezone.utc) + timedelta(hours=hours)},
                           config.JWT_SECRET, algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}
    return make
