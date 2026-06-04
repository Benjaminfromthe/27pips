# ============================================================
# 27pips — content/routes.py  |  Paginated "Load More" API
# Endpoint: GET /api/content/?type=<type>&page=<n>
# Supported types: signals, courses
# Page is 1-based.  Page size is defined per type below.
# Returns JSON: { items, has_more, page, total }
# ============================================================
from flask import Blueprint, jsonify, request, session
from database import get_db, USE_POSTGRES

content_bp = Blueprint('content', __name__)

PAGE_SIZES = {
    'signals': 10,
    'courses': 3,
}


def _offset_limit(page: int, page_size: int):
    page  = max(1, page)
    limit = page_size
    offset = (page - 1) * page_size
    return offset, limit


# ── GET /api/content/ ─────────────────────────────────────
@content_bp.route('/')
def get_more_content():
    content_type = request.args.get('type', '').strip().lower()
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    if content_type not in PAGE_SIZES:
        return jsonify({
            'error': f'Unknown content type "{content_type}". '
                     f'Valid: {list(PAGE_SIZES.keys())}'
        }), 400

    page_size        = PAGE_SIZES[content_type]
    offset, limit    = _offset_limit(page, page_size)

    if content_type == 'signals':
        return _get_signals(page, offset, limit, page_size)
    if content_type == 'courses':
        return _get_courses(page, offset, limit, page_size)


# ── Signals ────────────────────────────────────────────────
def _get_signals(page, offset, limit, page_size):
    uid       = session.get('user_id')
    user_tier = 'guest'

    db = get_db()
    try:
        if uid:
            u = db.execute('SELECT tier FROM users WHERE id=?', (uid,)).fetchone()
            user_tier = u['tier'] if u else 'free'

        # Count total for has_more calculation
        total_row = db.execute('SELECT COUNT(*) FROM signals').fetchone()
        total     = total_row[0] if total_row else 0

        rows = db.execute(
            '''SELECT id, pair, action, entry_price, stop_loss,
                      take_profit_1, take_profit_2, status,
                      is_premium, notes, created_at
               FROM signals
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?''',
            (limit, offset)
        ).fetchall()
    finally:
        db.close()

    items = []
    for r in rows:
        s = dict(r)
        # Tier gating — same logic as the main signals route
        if s['is_premium'] and user_tier != 'premium':
            s['entry_price']   = None
            s['stop_loss']     = None
            s['take_profit_1'] = None
            s['take_profit_2'] = None
            s['gated']         = True
        else:
            s['gated'] = False
        items.append(s)

    has_more = (offset + len(rows)) < total

    return jsonify({
        'items':    items,
        'has_more': has_more,
        'page':     page,
        'total':    total,
        'user_tier': user_tier,
    })


# ── Courses ────────────────────────────────────────────────
def _get_courses(page, offset, limit, page_size):
    uid = session.get('user_id')
    db  = get_db()

    try:
        total_row = db.execute('SELECT COUNT(*) FROM courses').fetchone()
        total     = total_row[0] if total_row else 0

        rows = db.execute(
            'SELECT id, title, description, slug, order_number '
            'FROM courses ORDER BY order_number '
            'LIMIT ? OFFSET ?',
            (limit, offset)
        ).fetchall()

        items = []
        for c in rows:
            course = dict(c)

            # Count lessons per course
            lesson_rows = db.execute(
                'SELECT id FROM lessons WHERE course_id=?', (course['id'],)
            ).fetchall()
            lesson_count = len(lesson_rows)
            completed    = 0

            if uid and lesson_count:
                ids          = [l['id'] for l in lesson_rows]
                placeholders = ','.join(['?'] * len(ids))
                row = db.execute(
                    f'SELECT COUNT(*) FROM user_progress '
                    f'WHERE user_id=? AND lesson_id IN ({placeholders})',
                    [uid] + ids
                ).fetchone()
                completed = row[0] if row else 0

            course['total_lessons']     = lesson_count
            course['completed_lessons'] = completed
            course['progress_pct']      = (
                round((completed / lesson_count) * 100) if lesson_count else 0
            )
            items.append(course)
    finally:
        db.close()

    has_more = (offset + len(rows)) < total

    return jsonify({
        'items':    items,
        'has_more': has_more,
        'page':     page,
        'total':    total,
    })
