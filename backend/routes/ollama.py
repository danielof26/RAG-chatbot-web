from flask import Blueprint, request, jsonify, Response
from bson import ObjectId
from datetime import datetime, timezone
import json
from db import agents_col
from services.rag_service import query_agent, stream_query_agent

ollama_bp = Blueprint('ollama', __name__)


def _get_agent(agent_id):
    try:
        return agents_col.find_one({'_id': ObjectId(agent_id)})
    except Exception:
        return None


# ─── Generate a completion ───────────────────────────────

@ollama_bp.route('/<agent_id>/api/generate', methods=['POST'])
def generate(agent_id):
    agent = _get_agent(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400

    stream = data.get('stream', True)  # por defecto streaming, igual que Ollama
    model = agent.get('llm_model', 'llama3.2:3b')

    if stream:
        def generate_stream():
            for token in stream_query_agent(agent_id, prompt, agent):
                chunk = {
                    'model': model,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'response': token,
                    'done': False
                }
                yield json.dumps(chunk) + '\n'

            yield json.dumps({
                'model': model,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'response': '',
                'done': True
            }) + '\n'

        return Response(generate_stream(), mimetype='application/x-ndjson')

    start = datetime.now(timezone.utc)
    answer = query_agent(agent_id, prompt, agent)
    end = datetime.now(timezone.utc)
    total_ns = int((end - start).total_seconds() * 1e9)
    prompt_tokens = len(prompt.split())
    answer_tokens = len(answer.split())

    return jsonify({
        'model': model,
        'created_at': end.isoformat(),
        'response': answer,
        'done': True,
        'context': [],
        'total_duration': total_ns,
        'load_duration': 0,
        'prompt_eval_count': prompt_tokens,
        'prompt_eval_duration': int(total_ns * 0.1),
        'eval_count': answer_tokens,
        'eval_duration': int(total_ns * 0.9)
    })


# ─── Generate a chat completion ──────────────────────────

@ollama_bp.route('/<agent_id>/api/chat', methods=['POST'])
def chat(agent_id):
    agent = _get_agent(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    messages = data.get('messages', [])
    if not messages:
        return jsonify({'error': 'messages is required'}), 400

    # Coge el último mensaje del usuario como pregunta
    question = next(
        (m['content'] for m in reversed(messages) if m.get('role') == 'user'),
        None
    )
    if not question:
        return jsonify({'error': 'No user message found'}), 400

    stream = data.get('stream', True)
    model = agent.get('llm_model', 'llama3.2:3b')

    if stream:
        def generate_stream():
            for token in stream_query_agent(agent_id, question, agent):
                chunk = {
                    'model': model,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'message': {'role': 'assistant', 'content': token},
                    'done': False
                }
                yield json.dumps(chunk) + '\n'

            yield json.dumps({
                'model': model,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'message': {'role': 'assistant', 'content': ''},
                'done': True
            }) + '\n'

        return Response(generate_stream(), mimetype='application/x-ndjson')

    start = datetime.now(timezone.utc)
    answer = query_agent(agent_id, question, agent)
    end = datetime.now(timezone.utc)
    total_ns = int((end - start).total_seconds() * 1e9)
    prompt_tokens = len(question.split())
    answer_tokens = len(answer.split())

    return jsonify({
        'model': model,
        'created_at': end.isoformat(),
        'message': {'role': 'assistant', 'content': answer},
        'done': True,
        'total_duration': total_ns,
        'load_duration': 0,
        'prompt_eval_count': prompt_tokens,
        'prompt_eval_duration': int(total_ns * 0.1),
        'eval_count': answer_tokens,
        'eval_duration': int(total_ns * 0.9)
    })
