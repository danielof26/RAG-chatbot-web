# backend/routes/auth.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
import config
from db import users_col as users

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON required'}), 400

    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must have at least 6 characters'}), 400

    if users.find_one({'email': email}):
        return jsonify({'error': 'Email already in use'}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    users.insert_one({
        'email': email,
        'password': hashed,
        'created_at': datetime.now(timezone.utc)
    })

    return jsonify({'message': 'User registered successfully'}), 201


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON requerido'}), 400

    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    user = users.find_one({'email': email})

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify({'error': 'Wrong credentials'}), 401

    
    token = jwt.encode({
        'user_id': str(user['_id']),
        'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRATION_HOURS)
    }, config.JWT_SECRET, algorithm='HS256')

    return jsonify({'token': token, 'email': email}), 200
