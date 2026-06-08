# backend/app.py
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from routes.auth import auth_bp
from routes.agents import agents_bp
from routes.ollama import ollama_bp
from routes.llm_servers import llm_servers_bp

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path='')
CORS(app)

app.register_blueprint(auth_bp)
app.register_blueprint(agents_bp)
app.register_blueprint(ollama_bp)
app.register_blueprint(llm_servers_bp)


@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve_react(path):
    file_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.exists(file_path):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')


if __name__ == "__main__":
    app.run(debug=True, port=5001)
