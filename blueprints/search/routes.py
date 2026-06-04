# ============================================================
# 27pips — search/routes.py  |  Site-wide search API
# ============================================================
import re
from flask import Blueprint, jsonify, request, session
from database import get_db, USE_POSTGRES

search_bp = Blueprint('search', __name__)

MAX_RESULTS_PER_TYPE = 4   # max hits per category
MAX_QUERY_LEN        = 100  # prevent abuse


def _like(col: str, placeholder: str) -> str:
    """Return a case-insensitive LIKE clause for the active DB backend."""
    if USE_POSTGRES:
        return f"{col} ILIKE {placeholder}"
    return f"LOWER({col}) LIKE LOWER({placeholder})"


@search_bp.route('/')
def search():
    """
    GET /search/?q=<query>
    Returns JSON: { results: [ {type, title, subtitle, url, icon} ] }
    Searched tables:
      - lessons    (education)
      - courses    (education)
      - signals    (live signals — pair name only)
    Public endpoint — no auth required.  Query is sanitised before use.
    """
    raw   = request.args.get('q', '').strip()
    lang  = session.get('lang', 'en')

    # ── sanitise ──────────────────────────────────────────────────────
    # Strip anything that could be used for SQL injection beyond parameterisation
    q = raw[:MAX_QUERY_LEN]
    if not q or len(q) < 2:
        return jsonify({'results': [], 'query': q})

    pattern  = f'%{q}%'
    results  = []
    db       = get_db()

    # ── Education: Lessons ────────────────────────────────────────────
    try:
        lesson_sql = f'''
            SELECT l.id, l.title, l.duration_minutes, c.title AS course_title
            FROM   lessons l
            JOIN   courses c ON c.id = l.course_id
            WHERE  {_like("l.title", "?")}
            ORDER  BY l.order_number
            LIMIT  {MAX_RESULTS_PER_TYPE}
        '''
        rows = db.execute(lesson_sql, (pattern,)).fetchall()
        for r in rows:
            results.append({
                'type':     'lesson',
                'icon':     '📖',
                'title':    r['title'],
                'subtitle': r['course_title'],
                'url':      f'/education/lesson/{r["id"]}',
                'meta':     f'{r["duration_minutes"]} min',
            })
    except Exception:
        pass

    # ── Education: Courses ────────────────────────────────────────────
    try:
        course_sql = f'''
            SELECT id, title, description
            FROM   courses
            WHERE  {_like("title", "?")} OR {_like("description", "?")}
            ORDER  BY order_number
            LIMIT  {MAX_RESULTS_PER_TYPE}
        '''
        rows = db.execute(course_sql, (pattern, pattern)).fetchall()
        for r in rows:
            results.append({
                'type':     'course',
                'icon':     '🎓',
                'title':    r['title'],
                'subtitle': r['description'] or '',
                'url':      '/education/',
                'meta':     '',
            })
    except Exception:
        pass

    # ── Signals: Pair name ────────────────────────────────────────────
    try:
        signal_sql = f'''
            SELECT id, pair, action, status
            FROM   signals
            WHERE  {_like("pair", "?")}
            ORDER  BY created_at DESC
            LIMIT  {MAX_RESULTS_PER_TYPE}
        '''
        rows = db.execute(signal_sql, (pattern,)).fetchall()
        for r in rows:
            results.append({
                'type':     'signal',
                'icon':     '⚡',
                'title':    r['pair'],
                'subtitle': f'{r["action"]} — {r["status"]}',
                'url':      '/#signals',
                'meta':     r['status'],
            })
    except Exception:
        pass

    # ── Static platform tools (always included when query matches) ────
    tools = [
        {
            'key': 'journal',
            'icon': '📓',
            'title_key': 'nav_journal',
            'subtitle_key': 'journal_sub',
            'url': '/#journal',
        },
        {
            'key': 'tracker',
            'icon': '🏆',
            'title_key': 'nav_tracker',
            'subtitle_key': 'tracker_sub',
            'url': '/#funded',
        },
        {
            'key': 'signals',
            'icon': '⚡',
            'title_key': 'nav_signals',
            'subtitle_key': 'signals_sub',
            'url': '/#signals',
        },
        {
            'key': 'education',
            'icon': '📚',
            'title_key': 'nav_education',
            'subtitle_key': 'edu_sub',
            'url': '/education/',
        },
        {
            'key': 'upgrade',
            'icon': '👑',
            'title_key': 'nav_upgrade',
            'subtitle_key': 'upgrade_page_sub',
            'url': '/upgrade',
        },
    ]

    from i18n import get_translations
    strings = get_translations(lang)
    q_lower = q.lower()

    for tool in tools:
        title    = strings.get(tool['title_key'],    tool['key'])
        subtitle = strings.get(tool['subtitle_key'], '')
        # Match against translated title and the key itself
        if q_lower in title.lower() or q_lower in tool['key'].lower():
            # Avoid duplicating a signal result already added above
            if not any(r['url'] == tool['url'] and r['type'] == 'signal'
                       for r in results):
                results.append({
                    'type':     'tool',
                    'icon':     tool['icon'],
                    'title':    title,
                    'subtitle': subtitle[:80] + ('…' if len(subtitle) > 80 else ''),
                    'url':      tool['url'],
                    'meta':     '',
                })

    db.close()

    # De-duplicate by URL, keep first occurrence, cap total at 10
    seen    = set()
    unique  = []
    for r in results:
        if r['url'] not in seen:
            seen.add(r['url'])
            unique.append(r)
        if len(unique) >= 10:
            break

    return jsonify({'results': unique, 'query': q})
