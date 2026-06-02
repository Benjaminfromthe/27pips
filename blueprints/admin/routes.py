# ============================================================
# 27pips — admin/routes.py  |  Secure admin panel
# ============================================================
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import get_db
import os

admin_bp = Blueprint('admin', __name__)

PAIRS   = ['XAUUSD','EURUSD','GBPUSD','USDJPY','USDCHF','AUDUSD',
           'NZDUSD','USDCAD','GBPJPY','NAS100','US30','BTCUSD']
ACTIONS = ['BUY', 'SELL']
STATUSES= ['Pending', 'Active', 'TP Hit', 'Stopped Out']

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated

# ── GET /admin/login ────────────────────────────────────────
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        pin         = request.form.get('pin', '')
        correct_pin = os.environ.get('ADMIN_PIN', '27pips2025')
        if pin == correct_pin:
            session['is_admin'] = True
            return redirect(url_for('admin.admin_signals'))
        error = 'Invalid PIN.'
    return render_template('admin_login.html', error=error)

# ── GET /admin/logout ───────────────────────────────────────
@admin_bp.route('/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin.admin_login'))

# ── GET /admin/signals ──────────────────────────────────────
@admin_bp.route('/signals')
@admin_required
def admin_signals():
    db      = get_db()
    signals = db.execute(
        'SELECT * FROM signals ORDER BY created_at DESC'
    ).fetchall()
    db.close()
    return render_template('admin_signals.html',
                           signals=[dict(s) for s in signals],
                           pairs=PAIRS, actions=ACTIONS, statuses=STATUSES)

# ── POST /admin/signals/add ─────────────────────────────────
@admin_bp.route('/signals/add', methods=['POST'])
@admin_required
def add_signal():
    d = request.form
    pair   = d.get('pair', '').strip()
    action = d.get('action', '').strip()
    entry  = d.get('entry_price', '')
    sl     = d.get('stop_loss', '')
    tp1    = d.get('take_profit_1', '')
    tp2    = d.get('take_profit_2', '')
    status = d.get('status', 'Pending')
    notes  = d.get('notes', '')
    is_premium = 1 if d.get('is_premium') == '1' else 0

    if not pair or not action or not entry:
        return jsonify({'success': False, 'message': 'pair, action, entry_price required.'}), 400

    def to_f(v):
        try: return float(v) if v else None
        except: return None

    db = get_db()
    db.execute(
        '''INSERT INTO signals
           (pair, action, entry_price, stop_loss, take_profit_1, take_profit_2, status, is_premium, notes)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (pair, action, to_f(entry), to_f(sl), to_f(tp1), to_f(tp2), status, is_premium, notes)
    )
    db.commit()
    db.close()
    return redirect(url_for('admin.admin_signals'))

# ── POST /admin/signals/update/<id> ─────────────────────────
@admin_bp.route('/signals/update/<int:signal_id>', methods=['POST'])
@admin_required
def update_signal(signal_id):
    new_status = request.form.get('status', 'Active')
    db = get_db()
    db.execute('UPDATE signals SET status = ? WHERE id = ?', (new_status, signal_id))
    db.commit()
    db.close()
    return redirect(url_for('admin.admin_signals'))

# ── POST /admin/signals/delete/<id> ─────────────────────────
@admin_bp.route('/signals/delete/<int:signal_id>', methods=['POST'])
@admin_required
def delete_signal(signal_id):
    db = get_db()
    db.execute('DELETE FROM signals WHERE id = ?', (signal_id,))
    db.commit()
    db.close()
    return redirect(url_for('admin.admin_signals'))
