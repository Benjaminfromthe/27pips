# ============================================================
# 27pips — education/routes.py  |  Courses, lessons, progress
# ============================================================
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from database import get_db

education_bp = Blueprint('education', __name__)

# ── GET /education/ — course overview ──────────────────────
@education_bp.route('/')
def education_home():
    db      = get_db()
    courses = db.execute('SELECT * FROM courses ORDER BY order_number').fetchall()
    courses = [dict(c) for c in courses]

    uid = session.get('user_id')
    for course in courses:
        lessons = db.execute(
            'SELECT id FROM lessons WHERE course_id = ?', (course['id'],)
        ).fetchall()
        total = len(lessons)
        completed = 0
        if uid and total:
            lesson_ids = [l['id'] for l in lessons]
            placeholders = ','.join('?' * len(lesson_ids))
            completed = db.execute(
                f'SELECT COUNT(*) FROM user_progress WHERE user_id=? AND lesson_id IN ({placeholders})',
                [uid] + lesson_ids
            ).fetchone()[0]
        course['total_lessons']     = total
        course['completed_lessons'] = completed
        course['progress_pct']      = round((completed / total) * 100) if total else 0

        # Attach lessons with completion flag
        all_lessons = db.execute(
            'SELECT * FROM lessons WHERE course_id=? ORDER BY order_number', (course['id'],)
        ).fetchall()
        lesson_list = []
        for l in all_lessons:
            ld = dict(l)
            ld['is_completed'] = False
            if uid:
                row = db.execute(
                    'SELECT id FROM user_progress WHERE user_id=? AND lesson_id=?',
                    (uid, l['id'])
                ).fetchone()
                ld['is_completed'] = row is not None
            lesson_list.append(ld)
        course['lessons'] = lesson_list

    db.close()
    user = {'username': session['username']} if uid else None
    return render_template('education.html', courses=courses, user=user)


# ── GET /education/lesson/<id> — lesson reader ─────────────
@education_bp.route('/lesson/<int:lesson_id>')
def lesson_view(lesson_id):
    db     = get_db()
    lesson = db.execute('SELECT * FROM lessons WHERE id=?', (lesson_id,)).fetchone()
    if not lesson:
        db.close()
        return "Lesson not found", 404

    lesson = dict(lesson)
    course = db.execute('SELECT * FROM courses WHERE id=?', (lesson['course_id'],)).fetchone()
    course = dict(course)

    # Next lesson
    next_lesson = db.execute(
        'SELECT id, title FROM lessons WHERE course_id=? AND order_number>? ORDER BY order_number LIMIT 1',
        (lesson['course_id'], lesson['order_number'])
    ).fetchone()

    uid          = session.get('user_id')
    is_completed = False
    if uid:
        row = db.execute(
            'SELECT id FROM user_progress WHERE user_id=? AND lesson_id=?', (uid, lesson_id)
        ).fetchone()
        is_completed = row is not None

    db.close()
    user = {'username': session['username']} if uid else None
    return render_template('lesson.html',
                           lesson=lesson, course=course,
                           next_lesson=dict(next_lesson) if next_lesson else None,
                           is_completed=is_completed, user=user)


# ── POST /education/lesson/<id>/complete ───────────────────
@education_bp.route('/lesson/<int:lesson_id>/complete', methods=['POST'])
def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required.', 'auth_required': True}), 401

    db = get_db()
    try:
        db.execute(
            'INSERT OR IGNORE INTO user_progress (user_id, lesson_id) VALUES (?,?)',
            (session['user_id'], lesson_id)
        )
        db.commit()
    finally:
        db.close()

    # Redirect to next lesson or back to education home
    next_id = request.form.get('next_lesson_id')
    if next_id:
        return redirect(url_for('education.lesson_view', lesson_id=int(next_id)))
    return redirect(url_for('education.education_home'))


# ── GET /education/progress — API for dashboard widget ─────
@education_bp.route('/progress')
def progress_api():
    if 'user_id' not in session:
        return jsonify({'logged_in': False})

    db      = get_db()
    uid     = session['user_id']
    courses = db.execute('SELECT * FROM courses ORDER BY order_number').fetchall()
    result  = []
    for c in courses:
        lessons = db.execute('SELECT id FROM lessons WHERE course_id=?', (c['id'],)).fetchall()
        total   = len(lessons)
        if not total:
            continue
        ids   = [l['id'] for l in lessons]
        ph    = ','.join('?' * len(ids))
        done  = db.execute(
            f'SELECT COUNT(*) FROM user_progress WHERE user_id=? AND lesson_id IN ({ph})',
            [uid] + ids
        ).fetchone()[0]
        result.append({
            'course': c['title'],
            'total': total,
            'completed': done,
            'pct': round((done / total) * 100)
        })
    db.close()
    return jsonify({'logged_in': True, 'progress': result})


# ── GET /education/lessons — JSON API (legacy) ─────────────
@education_bp.route('/lessons')
def get_lessons():
    db   = get_db()
    rows = db.execute('SELECT id, title, course_id, order_number, duration_minutes FROM lessons ORDER BY course_id, order_number').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])
