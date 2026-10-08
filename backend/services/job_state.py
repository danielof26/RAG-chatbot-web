from datetime import datetime, timezone

from bson import ObjectId

from db import agents_col, evaluation_runs_col
from states import (
    DOCUMENT_TRANSITIONS, INTERRUPTED_MESSAGE, DocumentStatus, RunStatus, blocked_sources,
)

DOC_STATUS = 'documents.$.status'
DOC_ERROR  = 'documents.$.error'


def set_document_status(agent_id: str, filename: str, status: DocumentStatus, error: str = None):
    fields = {DOC_STATUS: status.value}
    if error is not None:
        fields[DOC_ERROR] = error
    agents_col.update_one({'_id': ObjectId(agent_id), 'documents.filename': filename}, {'$set': fields})


def claim_document_for_indexing(agent_id: str, filename: str) -> bool:
    """Atomically moves the document to INDEXING if that transition is allowed from its current status.
    Returns False when it is already being indexed, so two concurrent requests can't both start a job."""
    result = agents_col.update_one(
        {'_id': ObjectId(agent_id),
         'documents': {'$elemMatch': {
             'filename': filename,
             'status': {'$nin': blocked_sources(DocumentStatus.INDEXING, DOCUMENT_TRANSITIONS)},
         }}},
        {'$set': {DOC_STATUS: DocumentStatus.INDEXING.value}}
    )
    return result.matched_count == 1


def finish_run(run_id: str, results: dict):
    evaluation_runs_col.update_one(
        {'_id': ObjectId(run_id)},
        {'$set': {'status': RunStatus.DONE.value, 'results': results, 'finished_at': datetime.now(timezone.utc)}}
    )


def fail_run(run_id: str, message: str):
    evaluation_runs_col.update_one(
        {'_id': ObjectId(run_id)},
        {'$set': {'status': RunStatus.ERROR.value, 'error': message, 'finished_at': datetime.now(timezone.utc)}}
    )


def recover_interrupted_jobs() -> dict:
    """Jobs run in threads of this process, so after a restart anything still marked as in progress is
    dead. Marks those documents/runs as errors (instead of leaving them spinning forever) and removes the
    temporary ChromaDB collections of the interrupted evaluations."""
    in_progress = [DocumentStatus.PENDING.value, DocumentStatus.INDEXING.value]
    docs = agents_col.update_many(
        {'documents.status': {'$in': in_progress}},
        {'$set': {'documents.$[d].status': DocumentStatus.ERROR.value, 'documents.$[d].error': INTERRUPTED_MESSAGE}},
        array_filters=[{'d.status': {'$in': in_progress}}]
    )
    running = [str(r['_id']) for r in evaluation_runs_col.find({'status': RunStatus.RUNNING.value}, {'_id': 1})]
    if running:
        evaluation_runs_col.update_many(
            {'status': RunStatus.RUNNING.value},
            {'$set': {'status': RunStatus.ERROR.value, 'error': INTERRUPTED_MESSAGE,
                      'finished_at': datetime.now(timezone.utc)}}
        )
        _drop_eval_collections(running)
    return {'documents': docs.modified_count, 'evaluations': len(running)}


def _drop_eval_collections(run_ids: list):
    try:
        import chromadb
        import config
        client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    except Exception:
        return
    for run_id in run_ids:
        for name in (f'eval_{run_id}', f'eval_{run_id}_raptor'):
            try:
                client.delete_collection(name)
            except Exception:
                pass
