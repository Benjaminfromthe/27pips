# ============================================================
# 27pips — simulator/routes.py  |  Paper Trading Simulator
#
# Price data: Twelve Data free tier (/price endpoint)
#   https://twelvedata.com  — 800 calls/day, 8/min on free plan
#   Set TWELVE_DATA_API_KEY on Render. Without it the simulator
#   falls back to hardcoded last-known prices (still functional).
#
# P&L formula (per trade):
#   Buy:  (current_price - open_price) * lot_size * pip_multiplier
#   Sell: (open_price - current_price) * lot_size * pip_multiplier
#   pip_multiplier = 10 for most pairs; 1000 for JPY pairs; 100 for XAU
# ============================================================
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, session

from database import get_db

simulator_bp = Blueprint('simulator', __name__)
log          = logging.getLogger(__name__)

STARTING_BALANCE = 10_000.0

SUPPORTED_PAIRS = {
    'EURUSD': {'pip_mult': 10,   'digits': 5, 'label': 'EUR/USD'},
    'GBPUSD': {'pip_mult': 10,   'digits': 5, 'label': 'GBP/USD'},
    'USDJPY': {'pip_mult': 1000, 'digits': 3, 'label': 'USD/JPY'},
    'GBPJPY': {'pip_mult': 1000, 'digits': 3, 'label': 'GBP/JPY'},
    'XAUUSD': {'pip_mult': 100,  'digits': 2, 'label': 'XAU/USD (Gold)'},
    'NAS100': {'pip_mult': 1,    'digits': 2, 'label': 'NAS100 (Tech)'},
}

# Fallback prices used when API key is not set
FALLBACK_PRICES = {
    'EURUSD': 1.0850,
    'GBPUSD': 1.2700,
    'USDJPY': 149.80,
    'GBPJPY': 190.20,
    'XAUUSD': 2320.0,
    'NAS100': 17850.0,
}

# Twelve Data uses different symbol format for some pairs
TWELVE_DATA_SYMBOLS = {
    'EURUSD': 'EUR/USD',
    'GBPUSD': 'GBP/USD',
    'USDJPY': 'USD/JPY',
    'GBPJPY': 'GBP/JPY',
    'XAUUSD': 'XAU/USD',
    'NAS100': 'IXIC',   # NASDAQ Composite as proxy
}


# ── helpers ───────────────────────────────────────────────
def _login_required():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.', 'auth_required': True}), 401
    return None


def _get_or_create_account(db, user_id: int) -> dict:
    row = db.execute('SELECT * FROM sim_account WHERE user_id = ?', (user_id,)).fetchone()
    if row:
        return dict(row)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    db.execute(
        'INSERT INTO sim_account (user_id, balance, equity, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?)',
        (user_id, STARTING_BALANCE, STARTING_BALANCE, now, now)
    )
    db.commit()
    return {'user_id': user_id, 'balance': STARTING_BALANCE, 'equity': STARTING_BALANCE}


def _calculate_pnl(pair: str, direction: str, open_price: float,
                   current_price: float, lot_size: float) -> float:
    cfg  = SUPPORTED_PAIRS.get(pair, {'pip_mult': 10})
    diff = (current_price - open_price) if direction == 'Buy' \
           else (open_price - current_price)
    return round(diff * lot_size * cfg['pip_mult'], 2)


def _fetch_price(pair: str) -> float | None:
    """
    Fetch latest price from Twelve Data. Returns None on any error.
    Falls back silently so the app never crashes on API failure.
    """
    api_key = os.environ.get('TWELVE_DATA_API_KEY', '').strip()
    if not api_key:
        return None

    symbol = TWELVE_DATA_SYMBOLS.get(pair, pair)
    url    = (
        f'https://api.twelvedata.com/price'
        f'?symbol={symbol}&apikey={api_key}'
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        price = float(data.get('price', 0))
        return price if price > 0 else None
    except Exception as exc:
        log.debug('[SIMULATOR] Price fetch failed for %s: %s', pair, exc)
        return None


# ── GET /simulator/ — main page ───────────────────────────
@simulator_bp.route('/')
def simulator_home():
    err = _login_required()
    if err:
        return render_template('simulator/index.html',
                               user=None, account=None,
                               open_trades=[], closed_trades=[],
                               pairs=SUPPORTED_PAIRS)
    uid = session['user_id']
    db  = get_db()
    account     = _get_or_create_account(db, uid)
    open_trades = [dict(r) for r in db.execute(
        "SELECT * FROM sim_trades WHERE user_id=? AND status='open' ORDER BY opened_at DESC",
        (uid,)
    ).fetchall()]
    closed_trades = [dict(r) for r in db.execute(
        "SELECT * FROM sim_trades WHERE user_id=? AND status='closed' ORDER BY closed_at DESC LIMIT 20",
        (uid,)
    ).fetchall()]
    db.close()
    user = {'username': session['username']}
    return render_template(
        'simulator/index.html',
        user=user,
        account=account,
        open_trades=open_trades,
        closed_trades=closed_trades,
        pairs=SUPPORTED_PAIRS,
        starting_balance=STARTING_BALANCE,
    )


# ── GET /simulator/price/<pair> — price proxy ─────────────
@simulator_bp.route('/price/<pair>')
def get_price(pair):
    pair = pair.upper()
    if pair not in SUPPORTED_PAIRS:
        return jsonify({'success': False, 'message': 'Unsupported pair'}), 400

    price = _fetch_price(pair)
    if price is None:
        price = FALLBACK_PRICES.get(pair, 1.0)
        source = 'fallback'
    else:
        source = 'live'

    return jsonify({
        'success': True,
        'pair':    pair,
        'price':   price,
        'source':  source,
    })


# ── POST /simulator/open — open a virtual trade ───────────
@simulator_bp.route('/open', methods=['POST'])
def open_trade():
    err = _login_required()
    if err: return err

    data      = request.get_json() or {}
    pair      = data.get('pair', '').upper().strip()
    direction = data.get('direction', '').strip()
    lot_size  = float(data.get('lot_size', 0.1) or 0.1)
    sl        = data.get('stop_loss')
    tp        = data.get('take_profit')

    if pair not in SUPPORTED_PAIRS:
        return jsonify({'success': False, 'message': 'Unsupported pair.'}), 400
    if direction not in ('Buy', 'Sell'):
        return jsonify({'success': False, 'message': 'Direction must be Buy or Sell.'}), 400
    if lot_size <= 0 or lot_size > 10:
        return jsonify({'success': False, 'message': 'Lot size must be between 0.01 and 10.'}), 400

    # Get live price
    price = _fetch_price(pair)
    if price is None:
        price = FALLBACK_PRICES.get(pair, 1.0)

    uid = session['user_id']
    db  = get_db()
    try:
        account = _get_or_create_account(db, uid)
        now     = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        db.execute(
            '''INSERT INTO sim_trades
               (user_id, pair, direction, lot_size, open_price, stop_loss,
                take_profit, status, opened_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)''',
            (uid, pair, direction, lot_size, price,
             float(sl) if sl else None,
             float(tp) if tp else None, now)
        )
        db.commit()
        trade_id = db.execute('SELECT MAX(id) FROM sim_trades WHERE user_id=?', (uid,)).fetchone()[0]
    finally:
        db.close()

    log.info('[SIM] user_id=%s opened %s %s %s @ %.5f',
             uid, direction, lot_size, pair, price)
    return jsonify({
        'success':    True,
        'trade_id':   trade_id,
        'open_price': price,
        'pair':       pair,
        'direction':  direction,
        'lot_size':   lot_size,
    })


# ── POST /simulator/close/<id> — close a virtual trade ────
@simulator_bp.route('/close/<int:trade_id>', methods=['POST'])
def close_trade(trade_id):
    err = _login_required()
    if err: return err

    uid = session['user_id']
    db  = get_db()
    try:
        trade = db.execute(
            "SELECT * FROM sim_trades WHERE id=? AND user_id=? AND status='open'",
            (trade_id, uid)
        ).fetchone()
        if not trade:
            return jsonify({'success': False, 'message': 'Trade not found.'}), 404

        trade = dict(trade)

        # Get close price
        close_price = _fetch_price(trade['pair'])
        if close_price is None:
            close_price = FALLBACK_PRICES.get(trade['pair'], trade['open_price'])

        pnl     = _calculate_pnl(trade['pair'], trade['direction'],
                                  trade['open_price'], close_price,
                                  trade['lot_size'])
        now     = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        db.execute(
            '''UPDATE sim_trades
               SET close_price=?, pnl=?, status='closed', closed_at=?
               WHERE id=?''',
            (close_price, pnl, now, trade_id)
        )

        # Update account balance
        db.execute(
            'UPDATE sim_account SET balance = balance + ?, equity = equity + ?, updated_at = ? '
            'WHERE user_id = ?',
            (pnl, pnl, now, uid)
        )
        db.commit()

        account = dict(db.execute('SELECT * FROM sim_account WHERE user_id=?', (uid,)).fetchone())
    finally:
        db.close()

    log.info('[SIM] user_id=%s closed trade_id=%s pnl=%.2f', uid, trade_id, pnl)
    return jsonify({
        'success':     True,
        'close_price': close_price,
        'pnl':         pnl,
        'balance':     account['balance'],
    })


# ── GET /simulator/status — current P&L snapshot ──────────
@simulator_bp.route('/status')
def get_status():
    err = _login_required()
    if err: return err

    uid = session['user_id']
    db  = get_db()
    try:
        account = _get_or_create_account(db, uid)
        trades  = [dict(r) for r in db.execute(
            "SELECT * FROM sim_trades WHERE user_id=? AND status='open'",
            (uid,)
        ).fetchall()]
    finally:
        db.close()

    # Calculate unrealised P&L for all open trades
    total_unrealised = 0.0
    trade_pnls = {}
    for t in trades:
        price = _fetch_price(t['pair'])
        if price is None:
            price = FALLBACK_PRICES.get(t['pair'], t['open_price'])
        upnl = _calculate_pnl(t['pair'], t['direction'],
                               t['open_price'], price, t['lot_size'])
        total_unrealised += upnl
        trade_pnls[t['id']] = {'price': price, 'pnl': upnl}

    equity = round(account['balance'] + total_unrealised, 2)

    return jsonify({
        'success':          True,
        'balance':          account['balance'],
        'equity':           equity,
        'unrealised_pnl':   round(total_unrealised, 2),
        'trade_pnls':       trade_pnls,
    })


# ── POST /simulator/reset — reset virtual account ─────────
@simulator_bp.route('/reset', methods=['POST'])
def reset_account():
    err = _login_required()
    if err: return err

    uid = session['user_id']
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    db  = get_db()
    try:
        # Close all open trades at current price (no P&L)
        db.execute(
            "UPDATE sim_trades SET status='closed', closed_at=?, pnl=0 "
            "WHERE user_id=? AND status='open'",
            (now, uid)
        )
        # Reset balance
        db.execute(
            'UPDATE sim_account SET balance=?, equity=?, updated_at=? WHERE user_id=?',
            (STARTING_BALANCE, STARTING_BALANCE, now, uid)
        )
        if db.execute('SELECT id FROM sim_account WHERE user_id=?', (uid,)).fetchone() is None:
            db.execute(
                'INSERT INTO sim_account (user_id, balance, equity, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (uid, STARTING_BALANCE, STARTING_BALANCE, now, now)
            )
        db.commit()
    finally:
        db.close()

    return jsonify({'success': True, 'balance': STARTING_BALANCE})
