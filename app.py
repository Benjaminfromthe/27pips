# ============================================================
# 27pips — app.py  |  Main Flask application entry point
# ============================================================
from flask import Flask, render_template, session
from database import init_db
from blueprints.auth.routes      import auth_bp
from blueprints.education.routes import education_bp
from blueprints.journal.routes   import journal_bp
from blueprints.signals.routes   import signals_bp
from blueprints.tracker.routes   import tracker_bp
from blueprints.admin.routes     import admin_bp
from blueprints.analytics.routes import analytics_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'pips-super-secret-key-2025-change-in-prod'

    with app.app_context():
        init_db()

    app.register_blueprint(auth_bp,       url_prefix='/auth')
    app.register_blueprint(education_bp,  url_prefix='/education')
    app.register_blueprint(journal_bp,    url_prefix='/journal')
    app.register_blueprint(signals_bp,    url_prefix='/signals')
    app.register_blueprint(tracker_bp,    url_prefix='/tracker')
    app.register_blueprint(admin_bp,      url_prefix='/admin')
    app.register_blueprint(analytics_bp,  url_prefix='/api/analytics')

    @app.route('/')
    def home():
        from database import get_db
        from datetime import datetime, timezone
        user = None
        if 'user_id' in session:
            user = {'username': session['username']}
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        db    = get_db()
        row   = db.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE DATE(created_at)=? AND status IN ('Active','Pending')",
            (today,)
        ).fetchone()
        db.close()
        signal_count = row['cnt'] if row else 0
        return render_template('index.html', user=user, signal_count=signal_count)

    return app

if __name__ == '__main__':
    app = create_app()
    print("27pips running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
