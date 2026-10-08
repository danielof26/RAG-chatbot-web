from enum import Enum


class DocumentStatus(str, Enum):
    PENDING  = 'pending'
    INDEXING = 'indexing'
    INDEXED  = 'indexed'
    ERROR    = 'error'


class RunStatus(str, Enum):
    RUNNING = 'running'
    DONE    = 'done'
    ERROR   = 'error'


# status -> statuses it may move to. The values are the strings already stored in MongoDB.
DOCUMENT_TRANSITIONS = {
    DocumentStatus.PENDING:  {DocumentStatus.INDEXING, DocumentStatus.ERROR},
    DocumentStatus.INDEXING: {DocumentStatus.INDEXED, DocumentStatus.ERROR},
    DocumentStatus.INDEXED:  {DocumentStatus.INDEXING},
    DocumentStatus.ERROR:    {DocumentStatus.INDEXING},
}

RUN_TRANSITIONS = {
    RunStatus.RUNNING: {RunStatus.DONE, RunStatus.ERROR},
    RunStatus.DONE:    set(),
    RunStatus.ERROR:   set(),
}

INTERRUPTED_MESSAGE = 'Interrupted by a server restart. Please try again.'


def blocked_sources(target, transitions) -> list:
    """Values of the statuses from which `target` is NOT reachable."""
    return [s.value for s, allowed in transitions.items() if target not in allowed]
