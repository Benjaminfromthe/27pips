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

def create_app():
    app = Flask(__name__)
    app.secret_key = 'pips-super-secret-key-2025-change-in-prod'

    # Initialize database on startup
    with app.app_context():
        init_db()

    # Register blueprints
    app.register_blueprint(auth_bp,       url_prefix='/auth')
    app.register_blueprint(education_bp,  url_prefix='/education')
    app.register_blueprint(journal_bp,    url_prefix='/journal')
    app.register_blueprint(signals_bp,    url_prefix='/signals')
    app.register_blueprint(tracker_bp,    url_prefix='/tracker')

    # Home route — pass session user to template
    @app.route('/')
    def home():
        user = None
        if 'user_id' in session:
            user = {'username': session['username']}
        return render_template('index.html', user=user)

    return app

if __name__ == '__main__':
    app = create_app()
    print("27pips running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
