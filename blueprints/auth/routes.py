# ============================================================
# 27pips — auth/routes.py  |  Registration, Login, Logout,
#                              Forgot / Reset Password
# ============================================================
import os
import secrets
import hashlib
import smtplib
import logging
import threading
import traceback
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

from flask import (Blueprint, request, jsonify, session,
                   render_template, redirect, url_for, current_app)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

RESET_TOKEN_HOURS = 1
SMTP_TIMEOUT      = 10   # seconds — only used if SMTP fallback is active


# ── helpers ───────────────────────────────────────────────
def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _make_t():
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


# ── email worker (runs in daemon thread) ──────────────────
def _email_worker(cfg: dict, to_email: str,
                  subject: str, body_text: str, body_html: str) -> None:
    """
    Daemon thread: tries Resend API first (HTTPS, never blocked),
    falls back to SMTP if Resend API key not set.
    All exceptions are caught — this thread can never crash the app.
    """
    reset_url  = cfg['reset_url']
    resend_key = cfg.get('resend_api_key', '').strip()
    mail_user  = cfg.get('mail_user',  '').strip()
    mail_pass  = cfg.get('mail_pass',  '').strip()

    log.info('[RESET EMAIL] Thread started for %s', to_email)

    # ── Path 1: Resend API (preferred — HTTPS, no SMTP port issues) ──
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            resend.Emails.send({
                'from':    cfg.get('mail_sender', 'onboarding@resend.dev'),
                'to':      [to_email],
                'subject': subject,
                'text':    body_text,
                'html':    body_html,
            })
            log.info('[RESET EMAIL] Sent via Resend to %s', to_email)
            return
        except Exception:
            log.error('[RESET EMAIL] Resend send failed:\n%s\nReset link: %s',
                      traceback.format_exc(), reset_url)
            # Fall through to SMTP fallback

    # ── Path 2: SMTP fallback ──────────────────────────────
    if mail_user and mail_pass:
        mail_server = cfg.get('mail_server', 'smtp.gmail.com')
        mail_port   = int(cfg.get('mail_port', 587))
        mail_sender = cfg.get('mail_sender', 'noreply@27pips.com')

        msg            = MIMEText(body_text, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From']    = mail_sender
        msg['To']      = to_email

        try:
            with smtplib.SMTP(mail_server, mail_port,
                              timeout=SMTP_TIMEOUT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(mail_user, mail_pass)
                smtp.sendmail(mail_sender, [to_email], msg.as_string())
            log.info('[RESET EMAIL] Sent via SMTP to %s', to_email)
            return
        except smtplib.SMTPAuthenticationError:
            log.warning('[RESET EMAIL] SMTP auth failed. '
                        'Check MAIL_USERNAME / MAIL_PASSWORD. '
                        'Reset link: %s', reset_url)
        except OSError as exc:
            log.warning('[RESET EMAIL] SMTP network error (%s). '
                        'Reset link: %s', exc, reset_url)
        except Exception:
            log.error('[RESET EMAIL] SMTP unexpected error:\n%s\n'
                      'Reset link: %s', traceback.format_exc(), reset_url)

    # ── Path 3: No provider configured — log reset link ───
    log.info(
        '[RESET EMAIL] No email provider configured '
        '(set RESEND_API_KEY or MAIL_USERNAME+MAIL_PASSWORD on Render). '
        'Reset link: %s', reset_url
    )


def _fire_reset_email(app_config: dict, to_email: str,
                      reset_url: str, t_func) -> bool:
    """
    Build email content on the request thread, then hand off to a
    daemon thread.  Returns True if an email provider IS configured
    (so the route knows whether to show the link inline or not).
    Returns instantly — zero blocking on request worker.
    """
    subject   = t_func('reset_email_subject')
    body_text = '\n\n'.join([
        t_func('reset_email_greeting'),
        t_func('reset_email_body'),
        reset_url,
        t_func('reset_email_expiry', hours=RESET_TOKEN_HOURS),
        t_func('reset_email_ignore'),
        '— 27pips / Shema Trading Hub',
    ])
    body_html = f"""
<div style="font-family:Inter,sans-serif;max-width:560px;margin:0 auto;padding:32px;background:#0f172a;color:#f1f5f9;border-radius:16px">
  <h2 style="color:#10b981;margin-bottom:8px">27<span style="color:#f1f5f9">pips</span></h2>
  <h3 style="margin-bottom:16px">{t_func('reset_email_subject')}</h3>
  <p style="color:#94a3b8;margin-bottom:8px">{t_func('reset_email_greeting')}</p>
  <p style="color:#94a3b8;margin-bottom:24px">{t_func('reset_email_body')}</p>
  <a href="{reset_url}"
     style="display:inline-block;background:#10b981;color:#fff;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:1rem;margin-bottom:24px">
    {t_func('reset_update_password_btn')}
  </a>
  <p style="color:#64748b;font-size:0.8rem;margin-top:16px">{t_func('reset_email_expiry', hours=RESET_TOKEN_HOURS)}</p>
  <p style="color:#64748b;font-size:0.8rem">{t_func('reset_email_ignore')}</p>
  <hr style="border-color:#334155;margin:24px 0">
  <p style="color:#475569;font-size:0.75rem">© 2025 27pips / Shema Trading Hub</p>
</div>
"""

    # Snapshot all config before leaving request context
    cfg = {
        'resend_api_key': app_config.get('RESEND_API_KEY', '').strip(),
        'mail_user':      app_config.get('MAIL_USERNAME',  '').strip(),
        'mail_pass':      app_config.get('MAIL_PASSWORD',  '').strip(),
        'mail_server':    app_config.get('MAIL_SERVER',    'smtp.gmail.com'),
        'mail_port':      int(app_config.get('MAIL_PORT',  587)),
        'mail_sender':    app_config.get('MAIL_DEFAULT_SENDER', 'onboarding@resend.dev'),
        'reset_url':      reset_url,
    }

    email_provider_configured = bool(
        cfg['resend_api_key'] or (cfg['mail_user'] and cfg['mail_pass'])
    )

    log.info('[RESET] Spawning email thread '
             '(Resend: %s, SMTP: %s)',
             bool(cfg['resend_api_key']),
             bool(cfg['mail_user'] and cfg['mail_pass']))

    thread = threading.Thread(
        target=_email_worker,
        args=(cfg, to_email, subject, body_text, body_html),
        daemon=True,
        name=f'reset-email-{to_email}',
    )
    thread.start()
    return email_provider_configured


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
    reset_url    = None   # shown inline when no email provider is configured

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

                _reset_url = url_for('auth.reset_password',
                                     token=raw_token, _external=True)

                log.info('[RESET] Token stored for user_id=%s — spawning email thread',
                         row['id'])

                email_sent = _fire_reset_email(
                    dict(current_app.config), email, _reset_url, t
                )

                # If no email provider is configured, surface the link
                # directly on the page so users can reset immediately.
                if not email_sent:
                    reset_url = _reset_url

            db.close()

            # Show success message regardless (prevents user enumeration).
            # If reset_url is set the template also shows a clickable button.
            message = t('reset_request_sent')

    return render_template(
        'auth/forgot_password.html',
        message=message,
        message_type=message_type,
        reset_url=reset_url,
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
