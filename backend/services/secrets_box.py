"""Protection of stored secrets: one-way hashing for our own API keys, encryption for third-party provider keys."""
import hashlib
import os
import stat

from cryptography.fernet import Fernet

import config

ENCRYPTED_PREFIX = 'enc:v1:'
_KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.encryption_key')
_fernet = None


def hash_api_key(raw_key: str) -> str:
    # Keys are 256-bit random tokens, so a fast hash is enough (no need for bcrypt).
    return hashlib.sha256(raw_key.encode()).hexdigest()


def mask(value: str) -> str:
    return value[:8] + '...' if len(value) > 8 else '...'


def _load_key() -> bytes:
    key = getattr(config, 'ENCRYPTION_KEY', None) or os.environ.get('RAG_ENCRYPTION_KEY')
    if key:
        return key.encode() if isinstance(key, str) else key
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, 'rb') as f:
            return f.read().strip()
    key = Fernet.generate_key()
    fd = os.open(_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, 'wb') as f:
        f.write(key)
    return key


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)


def encrypt(value: str) -> str:
    if is_encrypted(value):
        return value
    return ENCRYPTED_PREFIX + _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Values without the prefix are legacy plaintext and are returned as they are."""
    if not is_encrypted(value):
        return value
    return _get_fernet().decrypt(value[len(ENCRYPTED_PREFIX):].encode()).decode()
