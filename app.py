# ============================================================
# 27pips — app.py  |  Production-ready Flask entry point
# ============================================================
import os
from flask import Flask, render_template, session, request
from database import init_db
from i18n import register_i18n
from blueprints.auth.routes      import auth_bp
from blueprints.education.routes import education_bp
from blueprints.journal.routes   import journal_bp
from blueprints.signals.routes   import signals_bp
from blueprints.tracker.routes   import tracker_bp
from blueprints.admin.routes     import admin_bp
from blueprints.analytics.routes import analytics_bp
from blueprints.upgrade.routes   import upgrade_bp


def create_app():
    app = Flask(__name__)

    # ── Security ─────────────────────────────────────────────
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 'pips-local-dev-key-change-in-prod'
    )

    # ── SMTP config (fallback for password reset) ─────────────
    app.config['MAIL_SERVER']         = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    app.config['MAIL_PORT']           = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get(
        'MAIL_DEFAULT_SENDER',
        os.environ.get('MAIL_USERNAME', 'noreply@27pips.com')
    )
    # ── Resend API (preferred email provider for password reset) ──
    app.config['RESEND_API_KEY']    = os.environ.get('RESEND_API_KEY',    '')
    # Optional: redirect ALL outgoing emails to this address during testing
    # (workaround for Resend's unverified-domain restriction).
    # Remove once your domain is verified at resend.com/domains.
    app.config['RESEND_TEST_EMAIL'] = os.environ.get('RESEND_TEST_EMAIL', '')

    # ── Database ──────────────────────────────────────────────
    with app.app_context():
        init_db()

    # ── Blueprints ────────────────────────────────────────────
    app.register_blueprint(auth_bp,       url_prefix='/auth')
    app.register_blueprint(education_bp,  url_prefix='/education')
    app.register_blueprint(journal_bp,    url_prefix='/journal')
    app.register_blueprint(signals_bp,    url_prefix='/signals')
    app.register_blueprint(tracker_bp,    url_prefix='/tracker')
    app.register_blueprint(admin_bp,      url_prefix='/admin')
    app.register_blueprint(analytics_bp,  url_prefix='/api/analytics')
    app.register_blueprint(upgrade_bp,    url_prefix='/upgrade')

    register_i18n(app)

    # ── Home ──────────────────────────────────────────────────
    @app.route('/')
    def home():
        from database import get_db
        from datetime import datetime, timezone
        user      = None
        user_tier = 'guest'
        if 'user_id' in session:
            db  = get_db()
            row = db.execute(
                'SELECT username, tier FROM users WHERE id=?',
                (session['user_id'],)
            ).fetchone()
            db.close()
            if row:
                user      = {'username': row['username']}
                user_tier = row['tier']

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        db    = get_db()
        row   = db.execute(
            "SELECT COUNT(*) as cnt FROM signals "
            "WHERE DATE(created_at)=? AND status IN ('Active','Pending')",
            (today,)
        ).fetchone()
        db.close()
        signal_count = row['cnt'] if row else 0
        upgraded     = request.args.get('upgraded') == '1'
        return render_template('index.html', user=user,
                               signal_count=signal_count,
                               user_tier=user_tier, upgraded=upgraded)

    return app


# ── Gunicorn entry point ──────────────────────────────────
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    )
