# ============================================================
# 27pips — analytics/routes.py  |  Equity curve API
# ============================================================
from flask import Blueprint, jsonify, session
from database import get_db

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/equity')
def equity_curve():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.', 'auth_required': True}), 401

    uid = session['user_id']
    db  = get_db()

    # Get starting balance from tracker
    tracker = db.execute(
        'SELECT starting_balance FROM tracker WHERE user_id = ?', (uid,)
    ).fetchone()
    starting = tracker['starting_balance'] if tracker else 10000.0

    # Get all trades ordered chronologically
    trades = db.execute(
        '''SELECT pips_gained_lost, lot_size, outcome, created_at
           FROM journal WHERE user_id = ?
           ORDER BY created_at ASC''',
        (uid,)
    ).fetchall()
    db.close()

    if not trades:
        return jsonify({
            'success': True,
            'has_data': False,
            'labels': [],
            'data': [],
            'starting_balance': starting
        })

    # Build running equity curve
    labels  = ['Start']
    data    = [round(starting, 2)]
    balance = starting

    for i, t in enumerate(trades, 1):
        pips     = t['pips_gained_lost'] or 0
        lot_size = t['lot_size'] or 0
        pnl      = pips * lot_size * 10   # standard pip value formula
        balance  = round(balance + pnl, 2)

        # Label: date if available, else trade number
        label = f"Trade #{i}"
        if t['created_at']:
            try:
                label = t['created_at'][:10]   # YYYY-MM-DD
            except Exception:
                pass

        labels.append(label)
        data.append(balance)

    net_pnl    = round(balance - starting, 2)
    net_pct    = round((net_pnl / starting) * 100, 2) if starting else 0
    is_profit  = net_pnl >= 0

    return jsonify({
        'success':          True,
        'has_data':         True,
        'labels':           labels,
        'data':             data,
        'starting_balance': starting,
        'current_balance':  balance,
        'net_pnl':          net_pnl,
        'net_pct':          net_pct,
        'is_profit':        is_profit,
        'total_trades':     len(trades)
    })


# ── POST /api/analytics/performance/compute ────────────────
# Triggers the Leaking Alpha engine for the logged-in user.
# Called after every new trade is logged, or on demand.
@analytics_bp.route('/performance/compute', methods=['POST'])
def compute_performance():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.'}), 401

    from blueprints.analytics.performance import compute_and_store
    try:
        risk_free = float((session.get('risk_free_rate') or 0))
    except (ValueError, TypeError):
        risk_free = 0.0

    result = compute_and_store(session['user_id'], risk_free_rate=risk_free)
    if result is None:
        return jsonify({
            'success':  True,
            'computed': False,
            'message':  'No closed trades found. Log trades with Win/Loss outcomes to see metrics.',
        })

    return jsonify({'success': True, 'computed': True, 'metrics': result})


# ── GET /api/analytics/performance ─────────────────────────
# Returns the last-computed metrics for the dashboard.
@analytics_bp.route('/performance')
def get_performance():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.', 'auth_required': True}), 401

    from blueprints.analytics.performance import fetch_metrics, compute_and_store
    metrics = fetch_metrics(session['user_id'])

    # Auto-compute on first visit if no metrics exist yet
    if metrics is None:
        metrics = compute_and_store(session['user_id'])

    if metrics is None:
        return jsonify({
            'success':    True,
            'has_data':   False,
            'message':    'No closed trades yet.',
        })

    return jsonify({'success': True, 'has_data': True, 'metrics': metrics})
