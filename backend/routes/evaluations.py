import threading
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, request, jsonify

from db import agents_col, config_snapshots_col, evaluation_runs_col
from middleware.auth_middleware import token_required
from services.evaluation_service import parse_questions_csv, run_evaluation

evaluations_bp = Blueprint('evaluations', __name__)

AGENT_NOT_FOUND    = 'Agent not found'
INVALID_ID         = 'Invalid ID'
SNAPSHOT_NOT_FOUND = 'Configuration snapshot not found'
RUN_NOT_FOUND       = 'Evaluation run not found'


def _serialize_summary(run):
    return {
        '_id': str(run['_id']),
        'snapshot_id': run['snapshot_id'],
        'snapshot_name': run['snapshot_name'],
        'status': run['status'],
        'xai': run['xai'],
        'n_exec': run['n_exec'],
        'retrieval_mode': run.get('retrieval_mode', 'naive'),
        'language': run['language'],
        'num_questions': len(run.get('dataset', [])),
        'created_at': run['created_at'].isoformat(),
        'finished_at': run['finished_at'].isoformat() if run.get('finished_at') else None,
        'error': run.get('error'),
        'global_results': run.get('results', {}).get('global') if run.get('results') else None,
        'progress': run.get('progress'),
    }


def _serialize_detail(run):
    detail = _serialize_summary(run)
    detail['results'] = run.get('results')
    return detail


@evaluations_bp.route('/api/agents/<agent_id>/evaluations', methods=['GET'])
@token_required
def list_evaluations(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    runs = list(evaluation_runs_col.find(
        {'agent_id': agent_id, 'user_id': request.user_id}
    ).sort('created_at', -1))

    return jsonify([_serialize_summary(r) for r in runs]), 200


@evaluations_bp.route('/api/agents/<agent_id>/evaluations/<run_id>', methods=['GET'])
@token_required
def get_evaluation(agent_id, run_id):
    try:
        run = evaluation_runs_col.find_one({
            '_id': ObjectId(run_id), 'agent_id': agent_id, 'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not run:
        return jsonify({'error': RUN_NOT_FOUND}), 404

    return jsonify(_serialize_detail(run)), 200


@evaluations_bp.route('/api/agents/<agent_id>/evaluations/<run_id>', methods=['DELETE'])
@token_required
def delete_evaluation(agent_id, run_id):
    try:
        result = evaluation_runs_col.delete_one({
            '_id': ObjectId(run_id), 'agent_id': agent_id, 'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if result.deleted_count == 0:
        return jsonify({'error': RUN_NOT_FOUND}), 404

    return jsonify({'message': 'Evaluation run deleted'}), 200


@evaluations_bp.route('/api/agents/<agent_id>/evaluations', methods=['POST'])
@token_required
def create_evaluation(agent_id):
    try:
        agent = agents_col.find_one({'_id': ObjectId(agent_id), 'user_id': request.user_id})
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not agent:
        return jsonify({'error': AGENT_NOT_FOUND}), 404

    snapshot_id = request.form.get('snapshot_id', '').strip()
    try:
        snapshot = config_snapshots_col.find_one({
            '_id': ObjectId(snapshot_id), 'agent_id': agent_id, 'user_id': request.user_id
        })
    except Exception:
        return jsonify({'error': INVALID_ID}), 400

    if not snapshot:
        return jsonify({'error': SNAPSHOT_NOT_FOUND}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No dataset file has been uploaded'}), 400

    try:
        dataset = parse_questions_csv(request.files['file'].read())
    except Exception as e:
        return jsonify({'error': f'Could not parse the CSV file: {str(e)}'}), 400

    if not dataset:
        return jsonify({'error': 'The CSV file has no questions'}), 400

    language = request.form.get('language', 'en').strip()
    xai = request.form.get('xai', 'false').strip().lower() == 'true'
    try:
        n_exec = max(1, int(request.form.get('n_exec', 1)))
    except ValueError:
        n_exec = 1

    run = {
        'agent_id': agent_id,
        'user_id': request.user_id,
        'snapshot_id': snapshot_id,
        'snapshot_name': snapshot['name'],
        'dataset': dataset,
        'language': language,
        'xai': xai,
        'n_exec': n_exec,
        'retrieval_mode': snapshot.get('rag_config', {}).get('retrieval_mode', 'naive'),
        'status': 'running',
        'results': None,
        'error': None,
        'created_at': datetime.now(timezone.utc),
        'finished_at': None,
    }
    result = evaluation_runs_col.insert_one(run)
    run_id = str(result.inserted_id)

    thread = threading.Thread(target=run_evaluation, args=(run_id,), daemon=True)
    thread.start()

    run['_id'] = result.inserted_id
    return jsonify(_serialize_summary(run)), 202