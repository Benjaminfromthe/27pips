# ============================================================
# 27pips — signals/routes.py  |  Live trade signals feed
# ============================================================
from flask import Blueprint, jsonify
from database import get_db
from datetime import datetime, timezone

signals_bp = Blueprint('signals', __name__)

# ── GET /signals/ — public feed ────────────────────────────
@signals_bp.route('/')
def get_signals():
    db   = get_db()
    rows = db.execute(
        '''SELECT id, pair, action, entry_price, stop_loss,
                  take_profit_1, take_profit_2, status, notes, created_at
           FROM signals ORDER BY created_at DESC LIMIT 20'''
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── GET /signals/count — hero badge count ──────────────────
@signals_bp.route('/count')
def signal_count():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    db    = get_db()
    row   = db.execute(
        '''SELECT COUNT(*) as cnt FROM signals
           WHERE DATE(created_at) = ?
           AND status IN ('Active','Pending')''',
        (today,)
    ).fetchone()
    db.close()
    return jsonify({'count': row['cnt'] if row else 0})
