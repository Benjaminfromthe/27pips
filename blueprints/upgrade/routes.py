# ============================================================
# 27pips — upgrade/routes.py  |  Flutterwave Payment Integration
#
# Flow:
#   1. User visits /upgrade — sees plan cards
#   2. Clicks "Start Pro" or "Go Elite" — JS calls FlutterwaveCheckout()
#   3. User pays (card / MTN MoMo / Airtel Money / etc.)
#   4. Flutterwave calls POST /upgrade/webhook with payment result
#   5. Webhook verifies hash, marks payment confirmed, upgrades tier
#   6. JS callback also calls POST /upgrade/confirm/<tx_ref> as a
#      client-side backup (belt-and-suspenders)
#
# Plans:
#   pro   → $29/month  (tier = 'pro')
#   elite → $79/month  (tier = 'elite')
#   Note: 'premium' kept as legacy alias for 'pro'
# ============================================================
import hashlib
import hmac
import logging
import os
import secrets
import traceback
from datetime import datetime, timezone

from flask import (Blueprint, current_app, jsonify, redirect,
                   render_template, request, session, url_for)

from database import get_db

upgrade_bp = Blueprint('upgrade', __name__)
log        = logging.getLogger(__name__)

# Plan definitions — single source of truth
PLANS = {
    'pro': {
        'name':     'Pro Trader',
        'amount':   29,
        'currency': 'USD',
        'tier':     'pro',
    },
    'elite': {
        'name':     'Elite',
        'amount':   79,
        'currency': 'USD',
        'tier':     'elite',
    },
}


# ── helpers ───────────────────────────────────────────────
def _flw_public_key() -> str:
    return current_app.config.get('FLW_PUBLIC_KEY', '')


def _flw_secret_key() -> str:
    return current_app.config.get('FLW_SECRET_KEY', '')


def _flw_secret_hash() -> str:
    return current_app.config.get('FLW_SECRET_HASH', '')


def _is_test_mode() -> bool:
    pk = _flw_public_key()
    return not pk or pk.startswith('FLWPUBK_TEST')


def _make_tx_ref(user_id: int, plan: str) -> str:
    """Unique transaction reference: pips-<plan>-<user_id>-<random>"""
    rand = secrets.token_hex(6)
    return f"pips-{plan}-{user_id}-{rand}"


def _verify_flw_hash(payload: dict) -> bool:
    """
    Verify Flutterwave webhook signature.
    Flutterwave sends 'verif-hash' header which must match FLW_SECRET_HASH.
    """
    secret_hash = _flw_secret_hash()
    if not secret_hash:
        log.warning('[PAYMENT] FLW_SECRET_HASH not set — skipping hash verification')
        return True   # allow in dev/test with no hash configured
    received = request.headers.get('verif-hash', '')
    return hmac.compare_digest(received, secret_hash)


def _activate_plan(user_id: int, plan: str, tx_ref: str,
                   flw_ref: str = None) -> bool:
    """
    Set the user's tier in DB, mark payment confirmed.
    Returns True on success, False if user not found.
    """
    plan_cfg = PLANS.get(plan)
    if not plan_cfg:
        log.warning('[PAYMENT] Unknown plan: %s', plan)
        return False

    tier = plan_cfg['tier']
    now  = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    try:
        # Update user tier
        db.execute('UPDATE users SET tier = ? WHERE id = ?', (tier, user_id))

        # Mark payment confirmed (idempotent)
        db.execute(
            '''UPDATE payments
               SET status = 'confirmed', flw_ref = ?, confirmed_at = ?
               WHERE tx_ref = ?''',
            (flw_ref, now, tx_ref)
        )
        db.commit()
        log.info('[PAYMENT] Activated plan=%s tier=%s for user_id=%s tx_ref=%s',
                 plan, tier, user_id, tx_ref)
        return True
    except Exception:
        log.error('[PAYMENT] _activate_plan error:\n%s', traceback.format_exc())
        return False
    finally:
        db.close()


# ── GET /upgrade/ — plan selection page ──────────────────
@upgrade_bp.route('/')
def upgrade_page():
    user      = None
    tier      = 'free'
    user_email = ''

    if 'user_id' in session:
        user = {'username': session['username']}
        db   = get_db()
        row  = db.execute(
            'SELECT tier, email FROM users WHERE id=?',
            (session['user_id'],)
        ).fetchone()
        db.close()
        if row:
            tier       = row['tier'] or 'free'
            user_email = row['email'] or ''

    return render_template(
        'upgrade.html',
        user=user,
        tier=tier,
        user_email=user_email,
        plans=PLANS,
        flw_public_key=_flw_public_key(),
        is_test_mode=_is_test_mode(),
    )


# ── POST /upgrade/init — create pending payment record ────
@upgrade_bp.route('/init', methods=['POST'])
def init_payment():
    """
    Called from JS before opening the Flutterwave modal.
    Creates a pending payment row and returns the tx_ref.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.'}), 401

    data = request.get_json() or {}
    plan = data.get('plan', '').lower().strip()

    if plan not in PLANS:
        return jsonify({'success': False, 'message': f'Unknown plan: {plan}'}), 400

    plan_cfg = PLANS[plan]
    uid      = session['user_id']
    tx_ref   = _make_tx_ref(uid, plan)
    now      = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    try:
        db.execute(
            '''INSERT INTO payments
               (user_id, tx_ref, plan, amount, currency, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)''',
            (uid, tx_ref, plan, plan_cfg['amount'],
             plan_cfg['currency'], now)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({
        'success': True,
        'tx_ref':  tx_ref,
        'plan':    plan,
        'amount':  plan_cfg['amount'],
        'currency': plan_cfg['currency'],
        'plan_name': plan_cfg['name'],
    })


# ── POST /upgrade/confirm/<tx_ref> — client-side callback ─
@upgrade_bp.route('/confirm/<tx_ref>', methods=['POST'])
def confirm_payment(tx_ref):
    """
    Called by the Flutterwave JS callback on successful payment.
    This is the client-side confirmation — also verify server-side
    via the webhook for production reliability.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.'}), 401

    data    = request.get_json() or {}
    flw_ref = data.get('flw_ref', '')
    status  = data.get('status', '')

    if status != 'successful':
        log.info('[PAYMENT] Client confirm: non-successful status=%s tx_ref=%s',
                 status, tx_ref)
        return jsonify({'success': False, 'message': 'Payment not successful.'})

    # Fetch the pending payment to get plan
    db  = get_db()
    row = db.execute(
        'SELECT user_id, plan, status FROM payments WHERE tx_ref = ?',
        (tx_ref,)
    ).fetchone()
    db.close()

    if not row:
        return jsonify({'success': False, 'message': 'Transaction not found.'})

    if str(row['user_id']) != str(session['user_id']):
        return jsonify({'success': False, 'message': 'Unauthorized.'}), 403

    if row['status'] == 'confirmed':
        # Already activated (webhook beat us here)
        plan_tier = PLANS.get(row['plan'], {}).get('tier', 'pro')
        session['tier'] = plan_tier
        return jsonify({'success': True, 'tier': plan_tier, 'already': True})

    ok = _activate_plan(session['user_id'], row['plan'], tx_ref, flw_ref)
    if ok:
        plan_tier = PLANS.get(row['plan'], {}).get('tier', 'pro')
        session['tier'] = plan_tier

        # Send upgrade notification email (non-blocking)
        try:
            from blueprints.auth.routes import _send_account_update_email, _make_t
            db2 = get_db()
            urow = db2.execute(
                'SELECT email, username FROM users WHERE id=?',
                (session['user_id'],)
            ).fetchone()
            db2.close()
            if urow:
                lang = session.get('lang', 'en')
                _send_account_update_email(
                    urow['email'], urow['username'],
                    _make_t(lang)('notify_change_upgrade'),
                    dict(current_app.config), lang
                )
        except Exception:
            log.error('[UPGRADE NOTIFY] Failed:\n%s', traceback.format_exc())

        return jsonify({'success': True, 'tier': plan_tier})

    return jsonify({'success': False, 'message': 'Could not activate plan.'}), 500


# ── POST /upgrade/webhook — Flutterwave server-side event ─
@upgrade_bp.route('/webhook', methods=['POST'])
def flw_webhook():
    """
    Flutterwave posts here when a payment event occurs.
    Configure this URL in your Flutterwave dashboard:
    https://two7pips.onrender.com/upgrade/webhook
    """
    if not _verify_flw_hash(request.json or {}):
        log.warning('[PAYMENT WEBHOOK] Invalid hash — rejected')
        return jsonify({'status': 'unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    event   = payload.get('event', '')
    data    = payload.get('data', {})

    log.info('[PAYMENT WEBHOOK] event=%s tx_ref=%s status=%s',
             event, data.get('tx_ref'), data.get('status'))

    if event != 'charge.completed':
        return jsonify({'status': 'ignored'})

    if data.get('status') != 'successful':
        log.info('[PAYMENT WEBHOOK] Non-successful status — ignored')
        return jsonify({'status': 'ignored'})

    tx_ref  = data.get('tx_ref', '')
    flw_ref = data.get('flw_ref', '')

    if not tx_ref:
        return jsonify({'status': 'missing tx_ref'}), 400

    # Parse user_id and plan from tx_ref: pips-<plan>-<user_id>-<rand>
    parts = tx_ref.split('-')
    if len(parts) < 4 or parts[0] != 'pips':
        log.warning('[PAYMENT WEBHOOK] Unexpected tx_ref format: %s', tx_ref)
        return jsonify({'status': 'bad tx_ref'}), 400

    plan    = parts[1]
    user_id = parts[2]

    try:
        user_id = int(user_id)
    except ValueError:
        log.warning('[PAYMENT WEBHOOK] Non-integer user_id in tx_ref: %s', tx_ref)
        return jsonify({'status': 'bad tx_ref'}), 400

    ok = _activate_plan(user_id, plan, tx_ref, flw_ref)
    return jsonify({'status': 'ok' if ok else 'error'})


# ── POST /upgrade/simulate — SANDBOX ONLY test shortcut ───
@upgrade_bp.route('/simulate', methods=['POST'])
def simulate_upgrade():
    """
    Sandbox shortcut — only active when FLW_PUBLIC_KEY is unset or is a test key.
    Instantly upgrades to premium without payment for testing.
    """
    if 'user_id' not in session:
        return redirect(url_for('upgrade.upgrade_page'))

    if not _is_test_mode():
        log.warning('[SIMULATE] Blocked — live mode is active')
        return jsonify({'error': 'Simulation disabled in live mode.'}), 403

    db  = get_db()
    row = db.execute(
        'SELECT email, username FROM users WHERE id=?',
        (session['user_id'],)
    ).fetchone()
    db.execute("UPDATE users SET tier='pro' WHERE id=?",
               (session['user_id'],))
    db.commit()
    db.close()

    session['tier'] = 'pro'

    if row:
        try:
            from blueprints.auth.routes import _send_account_update_email, _make_t
            lang = session.get('lang', 'en')
            _send_account_update_email(
                row['email'], row['username'],
                _make_t(lang)('notify_change_upgrade'),
                dict(current_app.config), lang
            )
        except Exception:
            log.error('[UPGRADE NOTIFY] Failed:\n%s', traceback.format_exc())

    return redirect('/?upgraded=1')
