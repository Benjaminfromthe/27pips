# ============================================================
# 27pips — upgrade/routes.py  |  Premium tier simulation
# ============================================================
import logging
import traceback

from flask import (Blueprint, current_app, redirect, render_template,
                   session, url_for)
from database import get_db

upgrade_bp = Blueprint('upgrade', __name__)
log        = logging.getLogger(__name__)


@upgrade_bp.route('/')
def upgrade_page():
    user = None
    tier = 'free'
    if 'user_id' in session:
        user = {'username': session['username']}
        db   = get_db()
        row  = db.execute(
            'SELECT tier FROM users WHERE id=?', (session['user_id'],)
        ).fetchone()
        db.close()
        tier = row['tier'] if row else 'free'
    return render_template('upgrade.html', user=user, tier=tier)


@upgrade_bp.route('/simulate', methods=['POST'])
def simulate_upgrade():
    if 'user_id' not in session:
        return redirect(url_for('upgrade.upgrade_page'))

    db = get_db()
    db.execute("UPDATE users SET tier='premium' WHERE id=?",
               (session['user_id'],))
    db.commit()

    # Fetch email for notification
    row = db.execute(
        'SELECT email, username FROM users WHERE id=?',
        (session['user_id'],)
    ).fetchone()
    db.close()

    session['tier'] = 'premium'

    # ── Account upgrade notification (non-blocking) ────────
    if row:
        try:
            from blueprints.auth.routes import (
                _send_account_update_email, _make_t
            )
            lang = session.get('lang', 'en')
            _send_account_update_email(
                row['email'], row['username'],
                _make_t(lang)('notify_change_upgrade'),
                dict(current_app.config), lang
            )
        except Exception:
            log.error('[UPGRADE NOTIFY] Failed to spawn notification:\n%s',
                      traceback.format_exc())

    return redirect('/?upgraded=1')
