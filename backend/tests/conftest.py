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
        value = doc.get(field)
        if isinstance(cond, dict):
            if '$exists' in cond and (field in doc) != cond['$exists']:
                return False
            if '$in' in cond and value not in cond['$in']:
                return False
        elif value != cond:
            return False
    return True


class FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc.setdefault('_id', ObjectId())
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id=doc['_id'])

    def find(self, query=None, projection=None):
        return [dict(d) for d in self.docs if _match(d, query or {})]

    def find_one(self, query=None):
        found = self.find(query)
        return found[0] if found else None

    def update_one(self, query, update):
        for d in self.docs:
            if _match(d, query):
                d.update(update.get('$set', {}))
                for field, value in update.get('$push', {}).items():
                    d.setdefault(field, []).append(value)
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
