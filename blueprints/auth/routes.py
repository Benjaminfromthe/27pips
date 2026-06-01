# ============================================================
# 27pips — auth/routes.py  |  Registration, Login, Logout
# ============================================================
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

auth_bp = Blueprint('auth', __name__)

# ── REGISTER ───────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data     = request.get_json()
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Validation
    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    db = get_db()
    # Check duplicates
    existing = db.execute(
        'SELECT id FROM users WHERE email = ? OR username = ?', (email, username)
    ).fetchone()
    if existing:
        db.close()
        return jsonify({'success': False, 'message': 'Email or username already registered.'}), 409

    # Insert new user
    pw_hash = generate_password_hash(password)
    db.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (username, email, pw_hash)
    )
    db.commit()

    # Auto-login after registration
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    db.close()
    session['user_id']  = user['id']
    session['username'] = user['username']

    return jsonify({'success': True, 'username': user['username'], 'message': 'Account created!'}), 201


# ── LOGIN ──────────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required.'}), 400

    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    db.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401

    session['user_id']  = user['id']
    session['username'] = user['username']

    return jsonify({'success': True, 'username': user['username'], 'message': 'Welcome back!'})


# ── LOGOUT ─────────────────────────────────────────────────
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out.'})


# ── SESSION CHECK ──────────────────────────────────────────
@auth_bp.route('/me')
def me():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session['username']})
    return jsonify({'logged_in': False})
