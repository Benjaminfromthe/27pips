# ============================================================
# 27pips — tracker/routes.py  |  Prop firm challenge tracker
# ============================================================
from flask import Blueprint, jsonify, request, session
from database import get_db
from datetime import datetime, timezone

tracker_bp = Blueprint('tracker', __name__)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Login required.', 'auth_required': True}), 401
        return f(*args, **kwargs)
    return decorated

# ── POST /tracker/setup ─────────────────────────────────────
@tracker_bp.route('/setup', methods=['POST'])
@login_required
def setup():
    db  = get_db()
    uid = session['user_id']

    # Check if already exists (409 takes priority)
    existing = db.execute('SELECT id FROM tracker WHERE user_id = ?', (uid,)).fetchone()
    if existing:
        db.close()
        return jsonify({'success': False, 'message': 'Tracker account already exists.'}), 409

    data = request.get_json() or {}
    try:
        starting = float(data.get('starting_balance', 0))
        if starting <= 0:
            raise ValueError
    except (TypeError, ValueError):
        db.close()
        return jsonify({'success': False, 'message': 'starting_balance must be a positive number.'}), 400

    db.execute(
        '''INSERT INTO tracker (user_id, starting_balance, current_balance,
           daily_drawdown_limit, max_loss_limit, target_profit)
           VALUES (?, ?, ?, 5.0, 10.0, 10.0)''',
        (uid, starting, starting)
    )
    db.commit()
    db.close()
    return jsonify({'success': True}), 201


# ── GET /tracker/challenge ──────────────────────────────────
@tracker_bp.route('/challenge')
@login_required
def get_challenge():
    db  = get_db()
    uid = session['user_id']

    row = db.execute('SELECT * FROM tracker WHERE user_id = ?', (uid,)).fetchone()
    if not row:
        db.close()
        return jsonify({'success': False, 'message': 'No tracker account found.', 'setup_required': True}), 404

    t = dict(row)

    # Calculate daily loss today (UTC date)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    losses = db.execute(
        '''SELECT pips_gained_lost, lot_size FROM journal
           WHERE user_id = ? AND outcome = 'Loss'
           AND DATE(created_at) = ?''',
        (uid, today)
    ).fetchall()
    db.close()

    daily_loss_amount = sum(
        abs((r['pips_gained_lost'] or 0) * (r['lot_size'] or 0) * 10)
        for r in losses
    )
    daily_loss_pct = round((daily_loss_amount / t['starting_balance']) * 100, 2) if t['starting_balance'] else 0.0

    profit_progress = round(((t['current_balance'] - t['starting_balance']) / t['starting_balance']) * 100, 2) if t['starting_balance'] else 0.0
    total_loss      = round(((t['starting_balance'] - t['current_balance']) / t['starting_balance']) * 100, 2) if t['current_balance'] < t['starting_balance'] else 0.0

    profit_percent    = round((profit_progress / t['target_profit']) * 100, 1) if t['target_profit'] else 0.0
    daily_used_pct    = round((daily_loss_pct / t['daily_drawdown_limit']) * 100, 1) if t['daily_drawdown_limit'] else 0.0
    max_used_pct      = round((total_loss / t['max_loss_limit']) * 100, 1) if t['max_loss_limit'] else 0.0
    drawdown_breached = daily_loss_pct > t['daily_drawdown_limit']

    return jsonify({
        'account_size':         t['starting_balance'],
        'current_balance':      t['current_balance'],
        'daily_drawdown_limit': t['daily_drawdown_limit'],
        'max_loss_limit':       t['max_loss_limit'],
        'target_profit':        t['target_profit'],
        'daily_loss_today':     daily_loss_pct,
        'total_loss':           total_loss,
        'profit_progress':      profit_progress,
        'profit_percent':       min(profit_percent, 100),
        'daily_used_percent':   min(daily_used_pct, 100),
        'max_used_percent':     min(max_used_pct, 100),
        'drawdown_breached':    drawdown_breached,
    })
