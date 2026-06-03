# ============================================================
# 27pips — auth/routes.py  |  Registration, Login, Logout,
#                              Forgot / Reset Password
# ============================================================
import os
import secrets
import hashlib
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

auth_bp = Blueprint('auth', __name__)

# Token validity window
RESET_TOKEN_HOURS = 1


# ── helpers ───────────────────────────────────────────────
def _hash_token(raw_token: str) -> str:
    """SHA-256 hash a raw token before storing in the DB."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _make_t():
    """Build a t() resolver for the current session language (no Jinja context)."""
    from i18n import get_translations
    lang = session.get('lang', 'en')
    strings = get_translations(lang)
    def t(key, **kwargs):
        text = strings.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text
    return t


def _send_reset_email(app, to_email: str, reset_url: str, t_func) -> bool:
    """
    Attempt to send the password-reset email via Flask-Mail.
    Returns True on success, False on any error (so the route
    can degrade gracefully when SMTP is not configured).
    """
    try:
        from flask_mail import Message
        from app import mail
        subject = t_func('reset_email_subject')
        body = (
            f"{t_func('reset_email_greeting')}\n\n"
            f"{t_func('reset_email_body')}\n\n"
            f"{reset_url}\n\n"
            f"{t_func('reset_email_expiry', hours=RESET_TOKEN_HOURS)}\n\n"
            f"{t_func('reset_email_ignore')}\n\n"
            f"— 27pips / Shema Trading Hub"
        )
        msg = Message(subject=subject, recipients=[to_email], body=body)
        mail.send(msg)
        return True
    except Exception as exc:
        app.logger.warning(f"Password reset email failed: {exc}")
        return False


# ── REGISTER ──────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data     = request.get_json()
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    db = get_db()
    existing = db.execute(
        'SELECT id FROM users WHERE email = ? OR username = ?', (email, username)
    ).fetchone()
    if existing:
        db.close()
        return jsonify({'success': False, 'message': 'Email or username already registered.'}), 409

    pw_hash = generate_password_hash(password)
    db.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (username, email, pw_hash)
    )
    db.commit()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    db.close()
    session['user_id']  = user['id']
    session['username'] = user['username']
    return jsonify({'success': True, 'username': user['username'], 'message': 'Account created!'}), 201


# ── LOGIN ─────────────────────────────────────────────────
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


# ── LOGOUT ────────────────────────────────────────────────
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out.'})


# ── SESSION CHECK ─────────────────────────────────────────
@auth_bp.route('/me')
def me():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session['username']})
    return jsonify({'logged_in': False})


# ── FORGOT PASSWORD — GET: show form, POST: process request ─
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    from flask import current_app
    t = _make_t()

    # Flash-style one-time messages via query params (avoids session complexity)
    message     = None
    message_type = 'success'

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            message      = t('reset_error_email_required')
            message_type = 'error'
        else:
            db  = get_db()
            row = db.execute('SELECT id, username FROM users WHERE email = ?', (email,)).fetchone()

            if row:
                # Generate a cryptographically secure token
                raw_token  = secrets.token_urlsafe(32)
                token_hash = _hash_token(raw_token)
                expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_HOURS)

                # Invalidate any existing unused tokens for this user
                db.execute(
                    'UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0',
                    (row['id'],)
                )
                # Store the new hashed token
                db.execute(
                    'INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)',
                    (row['id'], token_hash, expires_at.strftime('%Y-%m-%d %H:%M:%S'))
                )
                db.commit()

                # Build the reset URL
                reset_url = url_for('auth.reset_password', token=raw_token, _external=True)

                # Attempt email send; log failure but don't reveal it to the user
                email_sent = _send_reset_email(current_app, email, reset_url, t)
                if not email_sent:
                    current_app.logger.info(
                        f"[DEV] Reset link for {email}: {reset_url}"
                    )

            db.close()

            # Always show the same message to prevent user-enumeration attacks
            message = t('reset_request_sent')

    return render_template(
        'auth/forgot_password.html',
        message=message,
        message_type=message_type,
        user=None,
    )


# ── RESET PASSWORD — GET: show form, POST: update password ──
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    t          = _make_t()
    token_hash = _hash_token(token)
    now        = datetime.now(timezone.utc)

    db  = get_db()
    row = db.execute(
        'SELECT r.id, r.user_id, r.expires_at, r.used, u.email '
        'FROM password_reset_tokens r '
        'JOIN users u ON u.id = r.user_id '
        'WHERE r.token_hash = ?',
        (token_hash,)
    ).fetchone()

    # Validate token
    if not row:
        db.close()
        return render_template('auth/reset_password.html',
                               error=t('reset_error_invalid_token'),
                               token=None, user=None)

    if row['used']:
        db.close()
        return render_template('auth/reset_password.html',
                               error=t('reset_error_token_used'),
                               token=None, user=None)

    # Parse expiry — handle both datetime objects and strings
    expires_at = row['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    elif expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        db.close()
        return render_template('auth/reset_password.html',
                               error=t('reset_error_token_expired'),
                               token=None, user=None)

    # Token is valid — handle form submission
    if request.method == 'POST':
        password  = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if len(password) < 6:
            db.close()
            return render_template('auth/reset_password.html',
                                   error=t('reset_error_password_short'),
                                   token=token, user=None)

        if password != password2:
            db.close()
            return render_template('auth/reset_password.html',
                                   error=t('reset_error_password_mismatch'),
                                   token=token, user=None)

        # Update password + mark token used in one transaction
        pw_hash = generate_password_hash(password)
        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (pw_hash, row['user_id']))
        db.execute('UPDATE password_reset_tokens SET used = 1 WHERE id = ?',
                   (row['id'],))
        db.commit()
        db.close()

        return redirect(url_for('auth.reset_success'))

    db.close()
    return render_template('auth/reset_password.html',
                           error=None, token=token, user=None)


# ── RESET SUCCESS ─────────────────────────────────────────
@auth_bp.route('/reset-success')
def reset_success():
    t = _make_t()
    return render_template('auth/reset_success.html', user=None)
