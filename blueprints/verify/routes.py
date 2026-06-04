# ============================================================
# 27pips — verify/routes.py  |  Public Trading Journal Verification
#
# Security model:
#   - Raw token is in the URL; only its SHA-256 hash is stored in DB
#   - No enumeration possible without the 32-byte random token
#   - Data exposed: username, trade stats, ratios — NEVER email,
#     password, balances, notes, chart images, or raw journal rows
#   - Tokens are per-user (UNIQUE user_id); generating a new token
#     invalidates the old one automatically
# ============================================================
import hashlib
import secrets
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, session
from database import get_db

verify_bp = Blueprint('verify', __name__)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── POST /verify/generate — create / rotate the user's token ─
@verify_bp.route('/generate', methods=['POST'])
def generate():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.'}), 401

    uid       = session['user_id']
    raw_token = secrets.token_urlsafe(32)
    tok_hash  = _hash_token(raw_token)
    now       = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    try:
        # Delete any existing token for this user (one token per user)
        db.execute('DELETE FROM verify_tokens WHERE user_id = ?', (uid,))
        db.execute(
            'INSERT INTO verify_tokens (user_id, token_hash, created_at) '
            'VALUES (?, ?, ?)',
            (uid, tok_hash, now)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({'success': True, 'token': raw_token})


# ── DELETE /verify/revoke — remove the user's public link ────
@verify_bp.route('/revoke', methods=['DELETE'])
def revoke():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.'}), 401

    db = get_db()
    try:
        db.execute('DELETE FROM verify_tokens WHERE user_id = ?',
                   (session['user_id'],))
        db.commit()
    finally:
        db.close()

    return jsonify({'success': True})


# ── GET /verify/status — does the logged-in user have a token? ─
@verify_bp.route('/status')
def status():
    if 'user_id' not in session:
        return jsonify({'has_token': False})

    db = get_db()
    try:
        row = db.execute(
            'SELECT created_at FROM verify_tokens WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()
    finally:
        db.close()

    return jsonify({'has_token': row is not None,
                    'created_at': row['created_at'] if row else None})


# ── GET /verify/<token> — public read-only verification page ──
@verify_bp.route('/<token>')
def public_profile(token):
    tok_hash = _hash_token(token)
    db       = get_db()
    try:
        # Resolve token → user
        vrow = db.execute(
            'SELECT v.user_id, v.created_at, u.username '
            'FROM verify_tokens v '
            'JOIN users u ON u.id = v.user_id '
            'WHERE v.token_hash = ?',
            (tok_hash,)
        ).fetchone()

        if not vrow:
            db.close()
            return render_template('verify/not_found.html', user=None), 404

        uid      = vrow['user_id']
        username = vrow['username']

        # Fetch performance metrics — safe subset only
        mrow = db.execute(
            '''SELECT trade_count, win_count, loss_count, win_rate,
                      avg_win_pips, avg_loss_pips, profit_factor,
                      mae_efficiency, sortino_ratio, net_pips, computed_at
               FROM performance_metrics
               WHERE user_id = ?''',
            (uid,)
        ).fetchone()

        # Fetch aggregate journal stats (no private price data)
        jrow = db.execute(
            '''SELECT
                 COUNT(*) AS total_logged,
                 SUM(CASE WHEN outcome = 'Win'  THEN 1 ELSE 0 END) AS wins,
                 SUM(CASE WHEN outcome = 'Loss' THEN 1 ELSE 0 END) AS losses,
                 MIN(created_at) AS first_trade,
                 MAX(created_at) AS last_trade
               FROM journal
               WHERE user_id = ? AND outcome IN ('Win','Loss')''',
            (uid,)
        ).fetchone()

        # Top traded pairs (no prices)
        pairs = db.execute(
            '''SELECT pair, COUNT(*) AS cnt
               FROM journal
               WHERE user_id = ?
               GROUP BY pair
               ORDER BY cnt DESC
               LIMIT 5''',
            (uid,)
        ).fetchall()

    finally:
        db.close()

    metrics = dict(mrow) if mrow else {}
    journal = dict(jrow) if jrow else {}
    top_pairs = [dict(p) for p in pairs] if pairs else []

    # Derive consistency score (0-100)
    # = weighted blend: win_rate(40%) + profit_factor(30%) + sortino(30%)
    consistency = _consistency_score(metrics)

    # Derive badge label
    badge, badge_color = _trader_badge(metrics)

    return render_template(
        'verify/profile.html',
        username=username,
        metrics=metrics,
        journal=journal,
        top_pairs=top_pairs,
        consistency=consistency,
        badge=badge,
        badge_color=badge_color,
        token_created=vrow['created_at'],
        user=None,   # public page — no logged-in session passed to template
    )


# ── Helpers ────────────────────────────────────────────────

def _consistency_score(m: dict) -> int:
    """
    0–100 composite score:
      Win Rate      40 pts  (55%+ = full 40, proportional below)
      Profit Factor 30 pts  (1.5+ = full 30)
      Sortino Ratio 30 pts  (2.0+ = full 30)
    """
    if not m:
        return 0

    wr = m.get('win_rate') or 0
    pf = m.get('profit_factor') or 0
    sr = m.get('sortino_ratio') or 0
    if sr == 999:
        sr = 3.0  # cap infinite Sortino at display max

    wr_pts = min(40, round((wr / 55) * 40)) if wr else 0
    pf_pts = min(30, round((pf / 1.5) * 30)) if pf else 0
    sr_pts = min(30, round((sr / 2.0) * 30)) if sr and sr > 0 else 0

    return min(100, wr_pts + pf_pts + sr_pts)


def _trader_badge(m: dict) -> tuple[str, str]:
    """Return (badge_label, css_color_class) based on metrics."""
    if not m or not m.get('trade_count'):
        return 'Developing', 'neutral'

    sr = m.get('sortino_ratio') or 0
    wr = m.get('win_rate') or 0
    pf = m.get('profit_factor') or 0

    if sr == 999:
        sr = 3.0

    if sr >= 2.0 and wr >= 55 and (pf or 0) >= 1.5:
        return 'Elite Trader',   'gold'
    if sr >= 1.0 and wr >= 50:
        return 'Consistent',     'green'
    if wr >= 45:
        return 'Developing',     'blue'
    return 'Building Edge', 'neutral'
