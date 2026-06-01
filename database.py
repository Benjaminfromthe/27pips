# ============================================================
# 27pips — database.py  |  SQLite initialization
# ============================================================
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'pips.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        account_balance REAL DEFAULT 0.0,
        account_creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Journal
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
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
    )''')

    # Tracker
    c.execute('''CREATE TABLE IF NOT EXISTS tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
        starting_balance REAL NOT NULL,
        current_balance REAL NOT NULL,
        daily_drawdown_limit REAL NOT NULL DEFAULT 5.0,
        max_loss_limit REAL NOT NULL DEFAULT 10.0,
        target_profit REAL NOT NULL DEFAULT 10.0
    )''')

    # Signals
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
        entry_price REAL NOT NULL,
        stop_loss REAL,
        take_profit_1 REAL,
        take_profit_2 REAL,
        status TEXT NOT NULL DEFAULT 'Pending'
               CHECK(status IN ('Pending','Active','TP Hit','Stopped Out')),
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print("Database ready — pips.db")
