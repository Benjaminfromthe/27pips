# ============================================================
# 27pips — journal/routes.py  |  Trade journal with file upload
# ============================================================
import os, uuid
from flask import Blueprint, jsonify, request, session
from database import get_db

journal_bp = Blueprint('journal', __name__)

UPLOAD_FOLDER  = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'uploads')
ALLOWED_EXTS   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Login required.', 'auth_required': True}), 401
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTS

# ── GET /journal/entries ────────────────────────────────────
@journal_bp.route('/entries', methods=['GET'])
@login_required
def get_entries():
    db = get_db()
    rows = db.execute(
        '''SELECT id, pair, direction, entry_price, exit_price,
                  lot_size, pips_gained_lost, outcome, notes,
                  chart_image_url, created_at
           FROM journal WHERE user_id = ?
           ORDER BY created_at DESC LIMIT 5''',
        (session['user_id'],)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── POST /journal/add ───────────────────────────────────────
@journal_bp.route('/add', methods=['POST'])
@login_required
def add_entry():
    # Support both JSON and multipart/form-data
    if request.content_type and 'multipart' in request.content_type:
        pair        = request.form.get('pair', '').strip()
        direction   = request.form.get('direction', '').strip()
        entry_price = request.form.get('entry_price', '')
        exit_price  = request.form.get('exit_price')
        lot_size    = request.form.get('lot_size')
        pips        = request.form.get('pips_gained_lost')
        outcome     = request.form.get('outcome')
        notes       = request.form.get('notes', '')
    else:
        data        = request.get_json() or {}
        pair        = data.get('pair', '').strip()
        direction   = data.get('direction', '').strip()
        entry_price = data.get('entry_price', '')
        exit_price  = data.get('exit_price')
        lot_size    = data.get('lot_size')
        pips        = data.get('pips_gained_lost')
        outcome     = data.get('outcome')
        notes       = data.get('notes', '')

    # Validation
    if not pair or not direction or not entry_price:
        return jsonify({'success': False, 'message': 'pair, direction, and entry_price are required.'}), 400
    if direction not in ('Buy', 'Sell'):
        return jsonify({'success': False, 'message': 'direction must be Buy or Sell.'}), 400

    # File upload
    chart_url = None
    if 'chart_image' in request.files:
        file = request.files['chart_image']
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'message': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp.'}), 400
            ext      = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            chart_url = f'/static/uploads/{filename}'

    # Convert types safely
    def to_float(v):
        try: return float(v) if v not in (None, '') else None
        except: return None

    entry_price = to_float(entry_price)
    exit_price  = to_float(exit_price)
    lot_size    = to_float(lot_size)
    pips        = to_float(pips)
    if outcome not in ('Win', 'Loss'): outcome = None

    db = get_db()
    try:
        cursor = db.execute(
            '''INSERT INTO journal
               (user_id, pair, direction, entry_price, exit_price,
                lot_size, pips_gained_lost, outcome, notes, chart_image_url)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (session['user_id'], pair, direction, entry_price, exit_price,
             lot_size, pips, outcome, notes, chart_url)
        )
        new_id = cursor.lastrowid

        # Auto-update tracker balance if pips and lot_size provided
        if pips is not None and lot_size is not None:
            pnl = pips * lot_size * 10
            db.execute(
                'UPDATE tracker SET current_balance = current_balance + ? WHERE user_id = ?',
                (pnl, session['user_id'])
            )

        db.commit()
    finally:
        db.close()

    # Trigger performance recompute + coaching check in background (non-blocking)
    try:
        import threading
        from blueprints.analytics.performance import compute_and_store as _compute
        from blueprints.analytics.coaching    import check_and_alert   as _coach
        _app_config = dict(current_app.config)
        _uid        = session['user_id']

        def _background_tasks():
            _compute(_uid)
            _coach(_uid, _app_config)

        t = threading.Thread(
            target=_background_tasks,
            daemon=True,
            name=f'post-trade-{_uid}'
        )
        t.start()
    except Exception:
        pass  # never block the trade save

    return jsonify({'success': True, 'id': new_id}), 201
