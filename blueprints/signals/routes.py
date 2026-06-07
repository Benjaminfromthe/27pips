# ============================================================
# 27pips — signals/routes.py  |  Live signals with tier gating
# ============================================================
from flask import Blueprint, jsonify, session
from database import get_db

signals_bp = Blueprint('signals', __name__)

@signals_bp.route('/')
def get_signals():
    db       = get_db()
    rows     = db.execute(
        '''SELECT id, pair, action, entry_price, stop_loss,
                  take_profit_1, take_profit_2, status, is_premium, notes, created_at
           FROM signals ORDER BY created_at DESC LIMIT 20'''
    ).fetchall()

    uid       = session.get('user_id')
    user_tier = 'guest'
    if uid:
        u = db.execute('SELECT tier FROM users WHERE id=?', (uid,)).fetchone()
        user_tier = u['tier'] if u else 'free'
    db.close()

    # Guests get last 3 signals as a preview — pair + action + status visible,
    # all prices blurred so they can see the format but not trade on it.
    is_guest    = not uid
    preview_max = 3

    result = []
    for i, r in enumerate(rows):
        s = dict(r)

        # Tier gating: premium signal details hidden from free/guest
        if s['is_premium'] and user_tier not in ('premium', 'pro', 'elite'):
            s['entry_price']   = None
            s['stop_loss']     = None
            s['take_profit_1'] = None
            s['take_profit_2'] = None
            s['gated'] = True
        else:
            s['gated'] = False

        # Guest preview: show first 3 signals with blurred prices
        if is_guest:
            if i < preview_max:
                # Blur the numbers — guest can see pair/action/status
                # but not actual price levels
                s['entry_price']   = None
                s['stop_loss']     = None
                s['take_profit_1'] = None
                s['take_profit_2'] = None
                s['gated']         = True
                s['preview']       = True   # JS uses this to render blur overlay
            else:
                # Don't send remaining signals to guests at all
                continue

        result.append(s)

    return jsonify({
        'signals':   result,
        'user_tier': user_tier,
        'is_guest':  is_guest,
    })


@signals_bp.route('/count')
def signal_count():
    db  = get_db()
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM signals WHERE status IN ('Active','Pending')"
    ).fetchone()
    db.close()
    return jsonify({'count': row['cnt'] if row else 0})
