# ============================================================
# 27pips — signals/routes.py  |  Live signals with tier gating
# ============================================================
from flask import Blueprint, jsonify, session
from database import get_db
from datetime import datetime, timezone

signals_bp = Blueprint('signals', __name__)

@signals_bp.route('/')
def get_signals():
    db      = get_db()
    rows    = db.execute(
        '''SELECT id, pair, action, entry_price, stop_loss,
                  take_profit_1, take_profit_2, status, is_premium, notes, created_at
           FROM signals ORDER BY created_at DESC LIMIT 20'''
    ).fetchall()

    # Get current user tier
    uid      = session.get('user_id')
    user_tier = 'guest'
    if uid:
        u = db.execute('SELECT tier FROM users WHERE id=?', (uid,)).fetchone()
        user_tier = u['tier'] if u else 'free'
    db.close()

    result = []
    for r in rows:
        s = dict(r)
        # Gate premium signals for free/guest users
        if s['is_premium'] and user_tier != 'premium':
            s['entry_price']   = None
            s['stop_loss']     = None
            s['take_profit_1'] = None
            s['take_profit_2'] = None
            s['gated']         = True
        else:
            s['gated'] = False
        result.append(s)

    return jsonify({'signals': result, 'user_tier': user_tier})

@signals_bp.route('/count')
def signal_count():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    db    = get_db()
    row   = db.execute(
        "SELECT COUNT(*) as cnt FROM signals WHERE DATE(created_at)=? AND status IN ('Active','Pending')",
        (today,)
    ).fetchone()
    db.close()
    return jsonify({'count': row['cnt'] if row else 0})
