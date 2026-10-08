# backend/app.py
import os
import sys
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from routes.auth import auth_bp
from routes.agents import agents_bp
from routes.ollama import ollama_bp
from routes.llm_servers import llm_servers_bp
from routes.api_keys import api_keys_bp
from routes.openapi import openapi_bp
from routes.config_snapshots import config_snapshots_bp
from routes.evaluations import evaluations_bp
from routes.rag_catalog import rag_catalog_bp
from services.job_state import recover_interrupted_jobs
from services.secret_migration import migrate_plaintext_secrets
from upload_policy import MAX_REQUEST_BYTES

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

# static_folder=None: the built-in static route would shadow serve_react and 404 on reloads of SPA routes
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_BYTES
CORS(app)


@app.errorhandler(413)
def request_too_large(_):
    return jsonify({'error': f'The upload is too large (maximum {MAX_REQUEST_BYTES // (1024 * 1024)} MB)'}), 413

app.register_blueprint(auth_bp)
app.register_blueprint(agents_bp)
app.register_blueprint(ollama_bp)
app.register_blueprint(llm_servers_bp)
app.register_blueprint(api_keys_bp)
app.register_blueprint(openapi_bp)
app.register_blueprint(config_snapshots_bp)
app.register_blueprint(evaluations_bp)
app.register_blueprint(rag_catalog_bp)

# Threads don't survive a restart: mark jobs that were in progress as failed instead of leaving them spinning.
try:
    recovered = recover_interrupted_jobs()
    if any(recovered.values()):
        print(f'[startup] Marked interrupted jobs as error: {recovered}')
except Exception as e:
    print(f'[startup] Could not recover interrupted jobs: {e}')

try:
    migrated = migrate_plaintext_secrets()
    if any(migrated.values()):
        print(f'[startup] Protected plaintext secrets: {migrated}')
except Exception as e:
    print(f'[startup] Could not migrate plaintext secrets: {e}')


@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve_react(path):
    file_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.exists(file_path):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')


if __name__ == "__main__":
    # El debugger de Werkzeug permite ejecutar código remoto: solo se activa con --debug
    app.run(debug='--debug' in sys.argv, port=5001, host='0.0.0.0')
