# backend/app.py
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Permite peticiones desde React (localhost:5173)

@app.route("/api/hello", methods=["GET"])
def hello():
    return jsonify({"message": "Hola desde Flask! 🐍"})

if __name__ == "__main__":
    app.run(debug=True, port=5001)