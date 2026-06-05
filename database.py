# ============================================================
# 27pips — database.py
# Adaptive dual-database layer: SQLite (local) / PostgreSQL (production)
# Detects DATABASE_URL env var → PostgreSQL, otherwise → SQLite
# All existing raw SQL queries work unchanged in both modes.
# ============================================================
import os
import sqlite3

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_URL     = os.environ.get('DATABASE_URL', '')

# Fix Render's legacy postgres:// prefix → postgresql://
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = bool(DB_URL)

# ── Adapter: unified connection wrapper ────────────────────
class DBConnection:
    """
    Wraps both sqlite3 and psycopg2 connections behind a common interface.
    Supports: execute(), fetchone(), fetchall(), commit(), close()
    Uses dict-like row access for both backends.
    """
    def __init__(self):
        if USE_POSTGRES:
            try:
                import psycopg2
                import psycopg2.extras
            except ImportError:
                raise RuntimeError(
                    "psycopg2-binary is required for PostgreSQL. "
                    "Run: pip install psycopg2-binary"
                )
            self._conn   = psycopg2.connect(DB_URL)
            self._cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            self._pg     = True
        else:
            self._conn        = sqlite3.connect(os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'pips.db')))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._cursor = self._conn.cursor()
            self._pg     = False

    def execute(self, sql, params=()):
        # Translate SQLite-specific syntax to PostgreSQL equivalents
        if self._pg:
            import re as _re
            # INSERT OR IGNORE INTO t (...) VALUES (...)
            # → INSERT INTO t (...) VALUES (...) ON CONFLICT DO NOTHING
            if _re.search(r'(?i)INSERT\s+OR\s+IGNORE\s+INTO', sql):
                sql = _re.sub(r'(?i)INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql)
                sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
            # ? placeholders → %s
            sql = sql.replace('?', '%s')
        self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        # psycopg2 RealDictCursor returns dict — wrap for [] access
        if self._pg:
            return _DictRow(dict(row))
        return row   # sqlite3.Row already supports []

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._pg:
            return [_DictRow(dict(r)) for r in rows]
        return rows

    @property
    def lastrowid(self):
        if self._pg:
            self._cursor.execute('SELECT lastval()')
            return self._cursor.fetchone()[0]
        return self._cursor.lastrowid

    def commit(self):
        self._conn.commit()

    def close(self):
        try: self._cursor.close()
        except: pass
        try: self._conn.close()
        except: pass

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


class _DictRow:
    """Thin wrapper so PostgreSQL dicts behave like sqlite3.Row (supports both d['key'] and d[int])."""
    def __init__(self, data: dict):
        self._data = data
        self._keys = list(data.keys())
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]
    def __iter__(self): return iter(self._data.values())
    def get(self, key, default=None): return self._data.get(key, default)
    def keys(self): return self._keys
    def __repr__(self): return repr(self._data)


def get_db() -> DBConnection:
    """Return a unified DB connection (SQLite or PostgreSQL)."""
    return DBConnection()


# ── Schema SQL ─────────────────────────────────────────────
def _schema_sql():
    """Returns CREATE TABLE statements compatible with both SQLite and PostgreSQL."""
    if USE_POSTGRES:
        return [
            '''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                account_balance REAL DEFAULT 0.0,
                tier TEXT NOT NULL DEFAULT 'free',
                account_creation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS journal (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                pair TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('Buy','Sell')),
                entry_price REAL NOT NULL,
                exit_price REAL,
                lot_size REAL,
                pips_gained_lost REAL,
                outcome TEXT CHECK(outcome IN ('Win','Loss')),
                notes TEXT,
                chart_image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS tracker (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                starting_balance REAL NOT NULL,
                current_balance REAL NOT NULL,
                daily_drawdown_limit REAL NOT NULL DEFAULT 5.0,
                max_loss_limit REAL NOT NULL DEFAULT 10.0,
                target_profit REAL NOT NULL DEFAULT 10.0
            )''',
            '''CREATE TABLE IF NOT EXISTS signals (
                id SERIAL PRIMARY KEY,
                pair TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
                entry_price REAL NOT NULL,
                stop_loss REAL,
                take_profit_1 REAL,
                take_profit_2 REAL,
                status TEXT NOT NULL DEFAULT 'Pending'
                       CHECK(status IN ('Pending','Active','TP Hit','Stopped Out')),
                is_premium INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS courses (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                slug TEXT NOT NULL UNIQUE,
                order_number INTEGER DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id),
                title TEXT NOT NULL,
                content TEXT,
                order_number INTEGER DEFAULT 0,
                duration_minutes INTEGER DEFAULT 5
            )''',
            '''CREATE TABLE IF NOT EXISTS user_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                lesson_id INTEGER NOT NULL REFERENCES lessons(id),
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, lesson_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trade_count INTEGER NOT NULL DEFAULT 0,
                win_count INTEGER NOT NULL DEFAULT 0,
                loss_count INTEGER NOT NULL DEFAULT 0,
                win_rate REAL,
                avg_win_pips REAL,
                avg_loss_pips REAL,
                profit_factor REAL,
                avg_mae_pips REAL,
                avg_mfe_pips REAL,
                mae_efficiency REAL,
                mfe_efficiency REAL,
                sortino_ratio REAL,
                risk_free_rate REAL DEFAULT 0.0,
                net_pips REAL,
                UNIQUE(user_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS coaching_alerts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                alert_type TEXT NOT NULL DEFAULT 'COOL_DOWN',
                consecutive_losses INTEGER NOT NULL DEFAULT 0,
                lookback_hours INTEGER NOT NULL DEFAULT 4,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS verify_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )''',
        ]
    else:
        # SQLite schema (original)
        return [
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                account_balance REAL DEFAULT 0.0,
                tier TEXT NOT NULL DEFAULT 'free',
                account_creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                pair TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('Buy','Sell')),
                entry_price REAL NOT NULL,
                exit_price REAL,
                lot_size REAL,
                pips_gained_lost REAL,
                outcome TEXT CHECK(outcome IN ('Win','Loss',NULL)),
                notes TEXT,
                chart_image_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                starting_balance REAL NOT NULL,
                current_balance REAL NOT NULL,
                daily_drawdown_limit REAL NOT NULL DEFAULT 5.0,
                max_loss_limit REAL NOT NULL DEFAULT 10.0,
                target_profit REAL NOT NULL DEFAULT 10.0
            )''',
            '''CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
                entry_price REAL NOT NULL,
                stop_loss REAL,
                take_profit_1 REAL,
                take_profit_2 REAL,
                status TEXT NOT NULL DEFAULT 'Pending'
                       CHECK(status IN ('Pending','Active','TP Hit','Stopped Out')),
                is_premium INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                slug TEXT NOT NULL UNIQUE,
                order_number INTEGER DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL REFERENCES courses(id),
                title TEXT NOT NULL,
                content TEXT,
                order_number INTEGER DEFAULT 0,
                duration_minutes INTEGER DEFAULT 5
            )''',
            '''CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                lesson_id INTEGER NOT NULL REFERENCES lessons(id),
                completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, lesson_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token_hash TEXT NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                trade_count INTEGER NOT NULL DEFAULT 0,
                win_count INTEGER NOT NULL DEFAULT 0,
                loss_count INTEGER NOT NULL DEFAULT 0,
                win_rate REAL,
                avg_win_pips REAL,
                avg_loss_pips REAL,
                profit_factor REAL,
                avg_mae_pips REAL,
                avg_mfe_pips REAL,
                mae_efficiency REAL,
                mfe_efficiency REAL,
                sortino_ratio REAL,
                risk_free_rate REAL DEFAULT 0.0,
                net_pips REAL,
                UNIQUE(user_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS coaching_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                alert_type TEXT NOT NULL DEFAULT 'COOL_DOWN',
                consecutive_losses INTEGER NOT NULL DEFAULT 0,
                lookback_hours INTEGER NOT NULL DEFAULT 4,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS verify_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )''',
        ]


def _seed_signals(db):
    """Seed 5 realistic demo forex signals. Works on both SQLite and PostgreSQL."""
    demo_signals = [
        ('EURUSD', 'BUY',  1.0845, 1.0800, 1.0890, 1.0930, 'Active',      0,
         'Bullish momentum after CPI beat. Break above 1.0850 confirmed.'),
        ('XAUUSD', 'BUY',  2318.50, 2295.00, 2345.00, 2370.00, 'Active',   0,
         'Gold holding key support. Fed pivot expectations driving demand.'),
        ('GBPUSD', 'SELL', 1.2720, 1.2760, 1.2680, 1.2640, 'Pending',      0,
         'Cable rejecting 1.2720 resistance. Bearish engulfing on H4.'),
        ('USDJPY', 'BUY',  149.80, 149.20, 150.50, 151.20, 'TP Hit',       1,
         'BOJ intervention risk fading. Dollar strength resuming. ✅ TP1 hit.'),
        ('NAS100', 'BUY',  17840,  17600,  18100,  18350,  'Active',       1,
         'Tech sector breakout. Strong earnings season momentum.'),
    ]
    for pair, action, entry, sl, tp1, tp2, status, is_premium, notes in demo_signals:
        if USE_POSTGRES:
            db.execute(
                '''INSERT INTO signals
                   (pair, action, entry_price, stop_loss, take_profit_1,
                    take_profit_2, status, is_premium, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (pair, action, entry, sl, tp1, tp2, status, is_premium, notes)
            )
        else:
            db.execute(
                '''INSERT INTO signals
                   (pair, action, entry_price, stop_loss, take_profit_1,
                    take_profit_2, status, is_premium, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (pair, action, entry, sl, tp1, tp2, status, is_premium, notes)
            )


def init_db():
    """Create all tables and seed curriculum if needed."""
    db = get_db()
    try:
        for stmt in _schema_sql():
            db.execute(stmt)

        # SQLite-only migrations for existing DBs
        if not USE_POSTGRES:
            for col_sql in [
                "ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'free'",
                "ALTER TABLE signals ADD COLUMN is_premium INTEGER NOT NULL DEFAULT 0",
            ]:
                try: db.execute(col_sql)
                except: pass
        db.commit()

        # Seed curriculum if empty
        row = db.execute('SELECT COUNT(*) FROM courses').fetchone()
        count = row[0] if row else 0
        if count == 0:
            _seed_curriculum(db)
            db.commit()

        # Seed signals if empty
        sig_row = db.execute('SELECT COUNT(*) FROM signals').fetchone()
        if (sig_row[0] if sig_row else 0) == 0:
            _seed_signals(db)
            db.commit()

        # Migration: ensure "How to Read a Chart" lesson exists
        _ensure_read_chart_lesson(db)
        db.commit()

    finally:
        db.close()
    print(f"Database ready — {'PostgreSQL' if USE_POSTGRES else 'SQLite (pips.db)'}")


def _ensure_read_chart_lesson(db):
    """
    Migration: add 'How to Read a Chart' to the beginner course if it
    doesn't already exist. Safe to call on every startup — no-op if present.
    """
    existing = db.execute(
        "SELECT id FROM lessons WHERE title = 'How to Read a Chart' LIMIT 1"
    ).fetchone()
    if existing:
        return

    # Find the beginner course id
    course = db.execute(
        "SELECT id FROM courses WHERE slug = 'beginner' LIMIT 1"
    ).fetchone()
    if not course:
        return

    course_id = course['id']
    content   = '<p>See lesson content in locale files.</p>'

    if USE_POSTGRES:
        db.execute(
            'INSERT INTO lessons (course_id, title, content, order_number, duration_minutes) '
            'VALUES (%s,%s,%s,%s,%s)',
            (course_id, 'How to Read a Chart', content, 3, 12)
        )
        # Shift "What is a Pip?" to order 4 if it exists
        db.execute(
            "UPDATE lessons SET order_number = 4 "
            "WHERE course_id = %s AND title = 'What is a Pip?'",
            (course_id,)
        )
    else:
        db.execute(
            'INSERT INTO lessons (course_id, title, content, order_number, duration_minutes) '
            'VALUES (?,?,?,?,?)',
            (course_id, 'How to Read a Chart', content, 3, 12)
        )
        db.execute(
            "UPDATE lessons SET order_number = 4 "
            "WHERE course_id = ? AND title = 'What is a Pip?'",
            (course_id,)
        )


def _seed_curriculum(db):
    """Seed 2 courses with 3 lessons each. Works on both SQLite and PostgreSQL."""

    def insert_course(title, description, slug, order_number):
        """Insert a course and return its new id — works on both backends."""
        if USE_POSTGRES:
            db.execute(
                "INSERT INTO courses (title, description, slug, order_number) VALUES (%s,%s,%s,%s) RETURNING id",
                (title, description, slug, order_number)
            )
            row = db._cursor.fetchone()
            return row['id'] if row else None
        else:
            db.execute(
                "INSERT INTO courses (title, description, slug, order_number) VALUES (?,?,?,?)",
                (title, description, slug, order_number)
            )
            return db.lastrowid

    # Course 1: Beginner
    beginner_id = insert_course(
        'Pre-School: Forex Basics',
        'Start from zero. Learn what forex is, how currency pairs work, and how to read a chart.',
        'beginner', 1
    )

    beginner_lessons = [
        (beginner_id, 'What is Forex?',
         '<p>See lesson content in locale files.</p>',
         1, 8),
        (beginner_id, 'Currency Pairs Explained',
         '<p>See lesson content in locale files.</p>',
         2, 10),
        (beginner_id, 'How to Read a Chart',
         '<p>See lesson content in locale files.</p>',
         3, 12),
        (beginner_id, 'What is a Pip?',
         '<p>See lesson content in locale files.</p>',
         4, 8),
    ]

    # Course 2: Intermediate
    inter_id = insert_course(
        'Elementary: Chart Reading',
        'Learn to read price charts, identify key levels, and understand candlestick patterns.',
        'intermediate', 2
    )

    inter_lessons = [
        (inter_id, 'Support and Resistance',
         '<h2>Support and Resistance</h2><p><strong>Support</strong> is where buying pressure prevents the price falling. <strong>Resistance</strong> is where selling pressure prevents rising.</p><h3>Role Reversal</h3><p>When price breaks resistance, that level often becomes new support.</p><blockquote>💡 <strong>Key Takeaway:</strong> Support and resistance are zones, not exact lines.</blockquote>',
         1, 10),
        (inter_id, 'Candlestick Patterns',
         '<h2>Reading Candlestick Patterns</h2><p>Candlesticks show Open, High, Low, Close prices.</p><h3>Key Reversal Patterns</h3><ul><li>🔨 <strong>Hammer</strong> — Bullish reversal at support</li><li>⭐ <strong>Shooting Star</strong> — Bearish reversal at resistance</li><li>🌙 <strong>Engulfing</strong> — Strong reversal signal</li></ul><blockquote>💡 <strong>Key Takeaway:</strong> Use candlestick patterns as confirmation, not standalone signals.</blockquote>',
         2, 8),
        (inter_id, 'Trend Lines & Market Structure',
         '<h2>Trend Lines and Market Structure</h2><ul><li>📈 <strong>Uptrend</strong> = Higher Highs + Higher Lows</li><li>📉 <strong>Downtrend</strong> = Lower Highs + Lower Lows</li><li>↔️ <strong>Ranging</strong> = Bouncing between two levels</li></ul><blockquote>💡 <strong>Key Takeaway:</strong> Always identify the trend on a higher timeframe first.</blockquote>',
         3, 12),
    ]

    for lesson in beginner_lessons + inter_lessons:
        if USE_POSTGRES:
            db.execute(
                'INSERT INTO lessons (course_id, title, content, order_number, duration_minutes) VALUES (%s,%s,%s,%s,%s)',
                lesson
            )
        else:
            db.execute(
                'INSERT INTO lessons (course_id, title, content, order_number, duration_minutes) VALUES (?,?,?,?,?)',
                lesson
            )
