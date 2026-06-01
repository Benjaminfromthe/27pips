# ============================================================
# 27pips — upgrade/routes.py  |  Premium tier simulation
# ============================================================
from flask import Blueprint, render_template, redirect, url_for, session, request
from database import get_db

upgrade_bp = Blueprint('upgrade', __name__)

@upgrade_bp.route('/')
def upgrade_page():
    user = None
    tier = 'free'
    if 'user_id' in session:
        user = {'username': session['username']}
        db   = get_db()
        row  = db.execute('SELECT tier FROM users WHERE id=?', (session['user_id'],)).fetchone()
        db.close()
        tier = row['tier'] if row else 'free'
    return render_template('upgrade.html', user=user, tier=tier)

@upgrade_bp.route('/simulate', methods=['POST'])
def simulate_upgrade():
    if 'user_id' not in session:
        return redirect(url_for('upgrade.upgrade_page'))
    db = get_db()
    db.execute("UPDATE users SET tier='premium' WHERE id=?", (session['user_id'],))
    db.commit()
    db.close()
    session['tier'] = 'premium'
    # Redirect home with success flash via query param
    return redirect('/?upgraded=1')
