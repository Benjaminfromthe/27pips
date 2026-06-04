# ============================================================
# 27pips — auth/routes.py  |  Registration, Login, Logout,
#                              Forgot / Reset Password,
#                              Transactional Account Notifications
# ============================================================
import hashlib
import logging
import secrets
import smtplib
import threading
import traceback
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import (Blueprint, current_app, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

RESET_TOKEN_HOURS = 1
SMTP_TIMEOUT      = 10   # seconds — used only in SMTP fallback


# ============================================================
# CORE EMAIL ENGINE  (shared by all notification types)
# ============================================================

def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _make_t(lang: str = 'en'):
    """Build a t() resolver for the given language (safe to call anywhere)."""
    from i18n import get_translations
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


def _snapshot_mail_cfg(app_config: dict) -> dict:
    """Extract mail settings from app.config into a plain dict (thread-safe)."""
    return {
        'resend_api_key': app_config.get('RESEND_API_KEY',       '').strip(),
        'mail_user':      app_config.get('MAIL_USERNAME',        '').strip(),
        'mail_pass':      app_config.get('MAIL_PASSWORD',        '').strip(),
        'mail_server':    app_config.get('MAIL_SERVER',          'smtp.gmail.com'),
        'mail_port':      int(app_config.get('MAIL_PORT',        587)),
        'mail_sender':    app_config.get('MAIL_DEFAULT_SENDER',  'onboarding@resend.dev'),
    }


def _is_provider_configured(cfg: dict) -> bool:
    return bool(cfg['resend_api_key'] or (cfg['mail_user'] and cfg['mail_pass']))


def _dispatch_email(cfg: dict, to_email: str,
                    subject: str, body_text: str, body_html: str,
                    log_tag: str = 'EMAIL') -> None:
    """
    Low-level send function.  Tries Resend first, then SMTP, then logs.
    Must be called from a background daemon thread only.
    Never raises — all exceptions are caught and logged.
    """
    resend_key = cfg['resend_api_key']
    mail_user  = cfg['mail_user']
    mail_pass  = cfg['mail_pass']

    # ── Resend API (HTTPS, works on all cloud platforms) ──────────────
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            resend.Emails.send({
                'from':    cfg['mail_sender'],
                'to':      [to_email],
                'subject': subject,
                'text':    body_text,
                'html':    body_html,
            })
            log.info('[%s] Sent via Resend to %s', log_tag, to_email)
            return
        except Exception:
            log.error('[%s] Resend failed:\n%s', log_tag, traceback.format_exc())
            # Fall through to SMTP

    # ── SMTP fallback ─────────────────────────────────────────────────
    if mail_user and mail_pass:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = cfg['mail_sender']
        msg['To']      = to_email
        msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(body_html, 'html',  'utf-8'))

        try:
            with smtplib.SMTP(cfg['mail_server'], cfg['mail_port'],
                              timeout=SMTP_TIMEOUT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(mail_user, mail_pass)
                smtp.sendmail(cfg['mail_sender'], [to_email], msg.as_string())
            log.info('[%s] Sent via SMTP to %s', log_tag, to_email)
            return
        except smtplib.SMTPAuthenticationError:
            log.warning('[%s] SMTP auth failed — check MAIL_USERNAME/PASSWORD', log_tag)
        except OSError as exc:
            log.warning('[%s] SMTP network error: %s', log_tag, exc)
        except Exception:
            log.error('[%s] SMTP unexpected error:\n%s', log_tag, traceback.format_exc())

    # ── No provider configured ────────────────────────────────────────
    log.info('[%s] No email provider configured (to=%s). '
             'Set RESEND_API_KEY or MAIL_USERNAME+MAIL_PASSWORD on Render.',
             log_tag, to_email)


def _spawn_email(cfg: dict, to_email: str,
                 subject: str, body_text: str, body_html: str,
                 log_tag: str = 'EMAIL') -> None:
    """Spawn a daemon thread to send one email. Returns immediately."""
    t = threading.Thread(
        target=_dispatch_email,
        args=(cfg, to_email, subject, body_text, body_html, log_tag),
        daemon=True,
        name=f'{log_tag.lower()}-{to_email}',
    )
    t.start()


# ============================================================
# NOTIFICATION BUILDERS
# ============================================================

def _html_wrapper(content_html: str, support_note: str) -> str:
    """Wrap email content in the 27pips branded dark-card layout."""
    return f"""
<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;
            padding:32px;background:#0f172a;color:#f1f5f9;border-radius:16px">
  <h2 style="color:#10b981;margin:0 0 4px">
    27<span style="color:#f1f5f9">pips</span>
  </h2>
  <p style="color:#475569;font-size:0.75rem;margin:0 0 24px">
    Shema Trading Hub
  </p>
  {content_html}
  <hr style="border:none;border-top:1px solid #334155;margin:24px 0">
  <p style="color:#64748b;font-size:0.78rem">{support_note}</p>
  <p style="color:#475569;font-size:0.72rem;margin-top:8px">
    © 2025 27pips / Shema Trading Hub
  </p>
</div>"""


def _send_account_created_email(to_email: str, username: str,
                                app_config: dict, lang: str = 'en') -> None:
    """
    Fire-and-forget welcome email after successful registration.
    Called on the request thread; email is sent in a daemon thread.
    Never blocks, never raises.
    """
    t   = _make_t(lang)
    cfg = _snapshot_mail_cfg(app_config)

    subject   = t('notify_welcome_subject')
    body_text = '\n\n'.join([
        t('notify_welcome_greeting', username=username),
        t('notify_welcome_body'),
        t('notify_welcome_get_started'),
        t('notify_security_note'),
        '— 27pips / Shema Trading Hub',
    ])
    content_html = f"""
  <h3 style="margin:0 0 12px;color:#f1f5f9">{t('notify_welcome_subject')}</h3>
  <p style="color:#94a3b8;margin-bottom:12px">
    {t('notify_welcome_greeting', username=username)}
  </p>
  <p style="color:#94a3b8;margin-bottom:20px">{t('notify_welcome_body')}</p>
  <ul style="color:#94a3b8;padding-left:20px;margin-bottom:20px;line-height:1.9">
    <li>📚 {t('nav_education')}</li>
    <li>⚡ {t('nav_signals')}</li>
    <li>📓 {t('nav_journal')}</li>
    <li>🏆 {t('nav_tracker')}</li>
  </ul>
  <p style="color:#94a3b8;margin-bottom:24px">
    {t('notify_welcome_get_started')}
  </p>"""

    body_html = _html_wrapper(content_html, t('notify_security_note'))

    log.info('[WELCOME] Spawning email thread for %s', to_email)
    _spawn_email(cfg, to_email, subject, body_text, body_html, log_tag='WELCOME')


def _send_account_update_email(to_email: str, username: str,
                               change_description: str,
                               app_config: dict, lang: str = 'en') -> None:
    """
    Fire-and-forget security notification after any account change
    (password reset, email update, tier change, etc.).
    Called on the request thread; email is sent in a daemon thread.
    Never blocks, never raises.
    """
    t   = _make_t(lang)
    cfg = _snapshot_mail_cfg(app_config)

    subject   = t('notify_update_subject')
    body_text = '\n\n'.join([
        t('notify_update_greeting', username=username),
        t('notify_update_body', change=change_description),
        t('notify_update_time',
          time=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')),
        t('notify_security_note'),
        '— 27pips / Shema Trading Hub',
    ])
    content_html = f"""
  <h3 style="margin:0 0 12px;color:#f1f5f9">{t('notify_update_subject')}</h3>
  <p style="color:#94a3b8;margin-bottom:12px">
    {t('notify_update_greeting', username=username)}
  </p>
  <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
              padding:16px;margin-bottom:20px">
    <p style="color:#10b981;font-weight:700;margin:0 0 4px">
      {t('notify_update_change_label')}
    </p>
    <p style="color:#f1f5f9;margin:0">{change_description}</p>
  </div>
  <p style="color:#64748b;font-size:0.82rem;margin-bottom:4px">
    {t('notify_update_time',
       time=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}
  </p>"""

    body_html = _html_wrapper(content_html, t('notify_security_note'))

    log.info('[ACCOUNT UPDATE] Spawning email thread for %s (%s)',
             to_email, change_description)
    _spawn_email(cfg, to_email, subject, body_text, body_html,
                 log_tag='ACCOUNT UPDATE')


# ============================================================
# AUTH ROUTES
# ============================================================

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
        return jsonify({'success': False,
                        'message': 'Email or username already registered.'}), 409

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

    # ── Welcome email (non-blocking) ──────────────────────
    try:
        lang = session.get('lang', 'en')
        _send_account_created_email(
            email, username, dict(current_app.config), lang
        )
    except Exception:
        log.error('[WELCOME] Failed to spawn email:\n%s', traceback.format_exc())

    return jsonify({'success': True, 'username': user['username'],
                    'message': 'Account created!'}), 201


# ── LOGIN ─────────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = (data.get('email')    or '').strip().lower()
    password =  data.get('password') or ''

    if not email or not password:
        return jsonify({'success': False,
                        'message': 'Email and password required.'}), 400

    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    db.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False,
                        'message': 'Invalid email or password.'}), 401

    session['user_id']  = user['id']
    session['username'] = user['username']
    return jsonify({'success': True, 'username': user['username'],
                    'message': 'Welcome back!'})


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


# ============================================================
# PASSWORD RESET FLOW
# ============================================================

def _fire_reset_email(app_config: dict, to_email: str,
                      reset_url: str, t_func) -> bool:
    """
    Build reset email and spawn daemon thread.
    Returns True if a provider is configured (email will be sent),
    False if no provider (caller shows link inline instead).
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
    content_html = f"""
  <h3 style="margin:0 0 12px;color:#f1f5f9">{t_func('reset_email_subject')}</h3>
  <p style="color:#94a3b8;margin-bottom:8px">{t_func('reset_email_greeting')}</p>
  <p style="color:#94a3b8;margin-bottom:24px">{t_func('reset_email_body')}</p>
  <a href="{reset_url}"
     style="display:inline-block;background:#10b981;color:#fff;padding:14px 28px;
            border-radius:10px;text-decoration:none;font-weight:700;
            font-size:1rem;margin-bottom:24px">
    {t_func('reset_update_password_btn')}
  </a>
  <p style="color:#64748b;font-size:0.8rem;margin-top:16px">
    {t_func('reset_email_expiry', hours=RESET_TOKEN_HOURS)}
  </p>"""

    body_html = _html_wrapper(content_html, t_func('reset_email_ignore'))
    cfg       = _snapshot_mail_cfg(app_config)

    log.info('[RESET] Spawning email thread (Resend: %s, SMTP: %s)',
             bool(cfg['resend_api_key']),
             bool(cfg['mail_user'] and cfg['mail_pass']))

    _spawn_email(cfg, to_email, subject, body_text, body_html, log_tag='RESET')
    return _is_provider_configured(cfg)


# ── FORGOT PASSWORD ────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    t            = _make_t(session.get('lang', 'en'))
    message      = None
    message_type = 'success'
    reset_url    = None

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

                log.info('[RESET] Token stored for user_id=%s', row['id'])
                email_sent = _fire_reset_email(
                    dict(current_app.config), email, _reset_url, t
                )
                if not email_sent:
                    reset_url = _reset_url

            db.close()
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
    t          = _make_t(session.get('lang', 'en'))
    token_hash = _hash_token(token)
    now        = datetime.now(timezone.utc)

    db  = get_db()
    row = db.execute(
        'SELECT r.id, r.user_id, r.expires_at, r.used, u.email, u.username '
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

        # Save new password + mark token used
        pw_hash  = generate_password_hash(password)
        user_email    = row['email']
        user_username = row['username']
        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (pw_hash, row['user_id']))
        db.execute('UPDATE password_reset_tokens SET used = 1 WHERE id = ?',
                   (row['id'],))
        db.commit()
        db.close()

        # ── Security notification (non-blocking) ──────────
        try:
            lang = session.get('lang', 'en')
            _send_account_update_email(
                user_email, user_username,
                _make_t(lang)('notify_change_password'),
                dict(current_app.config), lang
            )
        except Exception:
            log.error('[ACCOUNT UPDATE] Failed to spawn notification:\n%s',
                      traceback.format_exc())

        return redirect(url_for('auth.reset_success'))

    db.close()
    return render_template('auth/reset_password.html',
                           error=None, token=token, user=None)


# ── RESET SUCCESS ─────────────────────────────────────────
@auth_bp.route('/reset-success')
def reset_success():
    return render_template('auth/reset_success.html', user=None)
