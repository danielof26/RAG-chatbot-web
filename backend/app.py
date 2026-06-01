# backend/app.py
from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.agents import agents_bp
from routes.ollama import ollama_bp

app = Flask(__name__)
CORS(app)

# Registrar rutas
app.register_blueprint(auth_bp)
app.register_blueprint(agents_bp)
app.register_blueprint(ollama_bp)

@app.route("/api/hello", methods=["GET"])
def hello():
    return {"message": "Hola desde Flask! 🐍"}

if __name__ == "__main__":
    app.run(debug=True, port=5001)
