# ============================================================
# 27pips — auth/routes.py  |  Registration, Login, Logout,
#                              Forgot / Reset Password
# ============================================================
import os
import secrets
import hashlib
import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

from flask import (Blueprint, request, jsonify, session,
                   render_template, redirect, url_for, current_app)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Token validity window
RESET_TOKEN_HOURS = 1

# SMTP connection + send timeout (seconds) — prevents Gunicorn worker hang
SMTP_TIMEOUT = 8


# ── helpers ───────────────────────────────────────────────
def _hash_token(raw_token: str) -> str:
    """SHA-256 hash a raw token before storing in the DB."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _make_t():
    """Build a t() resolver for the current session language."""
    from i18n import get_translations
    lang    = session.get('lang', 'en')
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


def _send_reset_email(to_email: str, reset_url: str, t_func) -> bool:
    """
    Send a password-reset email using plain smtplib (no Flask-Mail import
    needed — avoids the circular-import crash).

    Returns True on success.  On ANY failure, logs the error and the reset
    URL to the server console and returns False.  The caller always shows
    the same user-facing message regardless, so the form never crashes.
    """
    mail_user   = current_app.config.get('MAIL_USERNAME', '').strip()
    mail_pass   = current_app.config.get('MAIL_PASSWORD', '').strip()
    mail_server = current_app.config.get('MAIL_SERVER',   'smtp.gmail.com')
    mail_port   = int(current_app.config.get('MAIL_PORT', 587))
    mail_sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@27pips.com')

    # --- guard: if credentials are empty skip the network call entirely ---
    if not mail_user or not mail_pass:
        log.info('[PASSWORD RESET] SMTP credentials not configured. '
                 'Reset link (dev/staging): %s', reset_url)
        return False

    subject = t_func('reset_email_subject')
    body = '\n\n'.join([
        t_func('reset_email_greeting'),
        t_func('reset_email_body'),
        reset_url,
        t_func('reset_email_expiry', hours=RESET_TOKEN_HOURS),
        t_func('reset_email_ignore'),
        '— 27pips / Shema Trading Hub',
    ])

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From']    = mail_sender
    msg['To']      = to_email

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=SMTP_TIMEOUT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(mail_user, mail_pass)
            smtp.sendmail(mail_sender, [to_email], msg.as_string())
        log.info('[PASSWORD RESET] Email sent to %s', to_email)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        log.warning('[PASSWORD RESET] SMTP auth failed (%s). '
                    'Reset link: %s', exc, reset_url)
    except smtplib.SMTPServerDisconnected as exc:
        log.warning('[PASSWORD RESET] SMTP server disconnected (%s). '
                    'Reset link: %s', exc, reset_url)
    except smtplib.SMTPException as exc:
        log.warning('[PASSWORD RESET] SMTP error (%s). '
                    'Reset link: %s', exc, reset_url)
    except OSError as exc:
        # Covers socket.timeout, ConnectionRefusedError, etc.
        log.warning('[PASSWORD RESET] Network error sending email (%s). '
                    'Reset link: %s', exc, reset_url)
    except Exception as exc:          # absolute last-resort catch
        log.error('[PASSWORD RESET] Unexpected error (%s). '
                  'Reset link: %s', exc, reset_url)

    return False


# ── REGISTER ──────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data     = request.get_json()
    username = (data.get('username') or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    password =  data.get('password') or ''

    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    db       = get_db()
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
    email    = (data.get('email')    or '').strip().lower()
    password =  data.get('password') or ''

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


# ── FORGOT PASSWORD ────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    t            = _make_t()
    message      = None
    message_type = 'success'

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()

        if not email:
            message      = t('reset_error_email_required')
            message_type = 'error'
        else:
            db  = get_db()
            row = db.execute(
                'SELECT id FROM users WHERE email = ?', (email,)
            ).fetchone()

            if row:
                raw_token  = secrets.token_urlsafe(32)
                token_hash = _hash_token(raw_token)
                expires_at = (datetime.now(timezone.utc)
                              + timedelta(hours=RESET_TOKEN_HOURS))

                # Invalidate prior unused tokens for this user
                db.execute(
                    'UPDATE password_reset_tokens '
                    'SET used = 1 WHERE user_id = ? AND used = 0',
                    (row['id'],)
                )
                db.execute(
                    'INSERT INTO password_reset_tokens '
                    '(user_id, token_hash, expires_at) VALUES (?, ?, ?)',
                    (row['id'], token_hash,
                     expires_at.strftime('%Y-%m-%d %H:%M:%S'))
                )
                db.commit()

                reset_url = url_for('auth.reset_password',
                                    token=raw_token, _external=True)

                # Non-blocking — any SMTP failure is caught inside
                _send_reset_email(email, reset_url, t)

            db.close()

            # Always identical message — prevents user enumeration
            message = t('reset_request_sent')

    return render_template(
        'auth/forgot_password.html',
        message=message,
        message_type=message_type,
        user=None,
    )


# ── RESET PASSWORD ────────────────────────────────────────
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

    # Normalise expires_at to UTC-aware datetime
    expires_at = row['expires_at']
    if isinstance(expires_at, str):
        expires_at = (datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                      .replace(tzinfo=timezone.utc))
    elif getattr(expires_at, 'tzinfo', None) is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        db.close()
        return render_template('auth/reset_password.html',
                               error=t('reset_error_token_expired'),
                               token=None, user=None)

    if request.method == 'POST':
        password  = request.form.get('password',  '') or ''
        password2 = request.form.get('password2', '') or ''

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
    return render_template('auth/reset_success.html', user=None)
