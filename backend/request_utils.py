"""Safe readers for request JSON: a body or field of an unexpected type must give a 400, never a 500."""
import traceback

from flask import request


def json_object():
    """The JSON body when it is a non-empty object, else None."""
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) and body else None


def str_field(data: dict, key: str, default: str = '') -> str:
    """data[key] stripped, or `default` when it is missing or not a string."""
    value = data.get(key, default)
    return value.strip() if isinstance(value, str) else default


def public_error_message(error: Exception) -> str:
    """Text safe to return to a client. ValueErrors are raised on purpose with a user-facing message;
    anything else may carry internal URLs or paths, so it is logged and replaced by a generic message."""
    if isinstance(error, ValueError):
        return str(error)
    traceback.print_exception(error)
    return 'Internal error while processing the request.'
