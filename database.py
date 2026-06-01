# ============================================================
# 27pips — database.py  |  SQLite initialization + seed data
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
    c    = conn.cursor()

    # ── Users ──────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        account_balance REAL DEFAULT 0.0,
        account_creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── Journal ────────────────────────────────────────────
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

    # ── Tracker ────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
        starting_balance REAL NOT NULL,
        current_balance REAL NOT NULL,
        daily_drawdown_limit REAL NOT NULL DEFAULT 5.0,
        max_loss_limit REAL NOT NULL DEFAULT 10.0,
        target_profit REAL NOT NULL DEFAULT 10.0
    )''')

    # ── Signals ────────────────────────────────────────────
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

    # ── Courses ────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        slug TEXT NOT NULL UNIQUE,
        order_number INTEGER DEFAULT 0
    )''')

    # ── Lessons ────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL REFERENCES courses(id),
        title TEXT NOT NULL,
        content TEXT,
        order_number INTEGER DEFAULT 0,
        duration_minutes INTEGER DEFAULT 5
    )''')

    # ── User Progress ──────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS user_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        lesson_id INTEGER NOT NULL REFERENCES lessons(id),
        completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, lesson_id)
    )''')

    conn.commit()

    # ── Seed curriculum if empty ───────────────────────────
    existing = c.execute('SELECT COUNT(*) FROM courses').fetchone()[0]
    if existing == 0:
        _seed_curriculum(c)
        conn.commit()

    conn.close()
    print("Database ready — pips.db")


def _seed_curriculum(c):
    """Seed 2 courses with 3 lessons each for immediate testing."""

    # Course 1: Beginner
    c.execute("INSERT INTO courses (title, description, slug, order_number) VALUES (?,?,?,?)",
        ('Pre-School: Forex Basics',
         'Start from zero. Learn what forex is, how currency pairs work, and how to read a chart.',
         'beginner', 1))
    beginner_id = c.lastrowid

    beginner_lessons = [
        (beginner_id, 'What is Forex?',
         '''<h2>What is the Forex Market?</h2>
<p>The <strong>foreign exchange market (Forex or FX)</strong> is the largest financial market in the world, with over <strong>$7.5 trillion</strong> traded daily. Unlike stock markets, forex has no central exchange — it operates 24 hours a day, 5 days a week across global financial centers.</p>
<h3>Why Trade Forex?</h3>
<ul>
  <li>✅ High liquidity — you can enter and exit trades instantly</li>
  <li>✅ Low barriers to entry — start with as little as $100</li>
  <li>✅ Trade in both directions — profit from rising AND falling markets</li>
  <li>✅ Leverage available — control large positions with small capital</li>
</ul>
<h3>Who Trades Forex?</h3>
<p>Central banks, commercial banks, hedge funds, corporations, and retail traders like you all participate in the forex market.</p>
<blockquote>💡 <strong>Key Takeaway:</strong> Forex is the exchange of one currency for another. When you travel abroad and exchange money, you're participating in the forex market.</blockquote>''',
         1, 5),

        (beginner_id, 'Currency Pairs Explained',
         '''<h2>Understanding Currency Pairs</h2>
<p>In forex, currencies are always traded in <strong>pairs</strong>. You're simultaneously buying one currency and selling another.</p>
<h3>Anatomy of a Currency Pair</h3>
<p>Take <strong>EUR/USD = 1.0850</strong>:</p>
<ul>
  <li><strong>EUR</strong> = Base currency (what you're buying)</li>
  <li><strong>USD</strong> = Quote currency (what you're selling)</li>
  <li><strong>1.0850</strong> = It costs $1.0850 to buy €1</li>
</ul>
<h3>The Major Pairs</h3>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
  <tr style="background:rgba(16,185,129,0.1)"><th style="padding:8px;text-align:left">Pair</th><th style="padding:8px;text-align:left">Nickname</th></tr>
  <tr><td style="padding:8px">EUR/USD</td><td style="padding:8px">The Euro</td></tr>
  <tr><td style="padding:8px">GBP/USD</td><td style="padding:8px">Cable</td></tr>
  <tr><td style="padding:8px">USD/JPY</td><td style="padding:8px">The Yen</td></tr>
  <tr><td style="padding:8px">XAU/USD</td><td style="padding:8px">Gold</td></tr>
</table>
<blockquote>💡 <strong>Key Takeaway:</strong> Always know which currency is the base and which is the quote. The price tells you how much of the quote currency you need to buy one unit of the base.</blockquote>''',
         2, 7),

        (beginner_id, 'What is a Pip?',
         '''<h2>Pips, Lots, and Position Sizing</h2>
<p>A <strong>pip</strong> (Percentage in Point) is the smallest standard price movement in forex. For most pairs, 1 pip = 0.0001.</p>
<h3>Example</h3>
<p>If EUR/USD moves from <strong>1.0850 → 1.0860</strong>, that's a <strong>10 pip</strong> move.</p>
<h3>Lot Sizes</h3>
<ul>
  <li><strong>Standard Lot</strong> = 100,000 units → 1 pip = $10</li>
  <li><strong>Mini Lot</strong> = 10,000 units → 1 pip = $1</li>
  <li><strong>Micro Lot</strong> = 1,000 units → 1 pip = $0.10</li>
</ul>
<h3>Why Pips Matter</h3>
<p>Pips are how traders measure profit and loss. If you buy 1 standard lot of EUR/USD and it moves 50 pips in your favor, you made <strong>$500</strong>.</p>
<blockquote>💡 <strong>Key Takeaway:</strong> Master pip calculation before risking real money. Always know your pip value before entering a trade.</blockquote>''',
         3, 8),
    ]

    # Course 2: Intermediate
    c.execute("INSERT INTO courses (title, description, slug, order_number) VALUES (?,?,?,?)",
        ('Elementary: Chart Reading',
         'Learn to read price charts, identify key levels, and understand candlestick patterns.',
         'intermediate', 2))
    inter_id = c.lastrowid

    inter_lessons = [
        (inter_id, 'Support and Resistance',
         '''<h2>Support and Resistance — The Foundation of Technical Analysis</h2>
<p><strong>Support</strong> is a price level where buying pressure is strong enough to prevent the price from falling further. <strong>Resistance</strong> is where selling pressure prevents the price from rising further.</p>
<h3>How to Identify Key Levels</h3>
<ul>
  <li>Look for price areas where the market has <strong>reversed multiple times</strong></li>
  <li>Round numbers (1.1000, 1.0500) often act as psychological S/R</li>
  <li>Previous highs and lows are natural S/R zones</li>
</ul>
<h3>The Role Reversal Concept</h3>
<p>When price breaks through a resistance level, that level often becomes new support — and vice versa. This is called <strong>role reversal</strong> and is one of the most powerful concepts in trading.</p>
<blockquote>💡 <strong>Key Takeaway:</strong> Support and resistance are zones, not exact lines. Always look for confluence — multiple reasons for price to react at a level.</blockquote>''',
         1, 10),

        (inter_id, 'Candlestick Patterns',
         '''<h2>Reading Candlestick Patterns</h2>
<p>Candlesticks show four key prices: <strong>Open, High, Low, Close</strong>. The body shows the range between open and close. The wicks show the extremes.</p>
<h3>Key Reversal Patterns</h3>
<ul>
  <li>🕯️ <strong>Doji</strong> — Open ≈ Close. Market indecision. Watch for direction after.</li>
  <li>🔨 <strong>Hammer</strong> — Long lower wick at support. Bullish reversal signal.</li>
  <li>⭐ <strong>Shooting Star</strong> — Long upper wick at resistance. Bearish reversal signal.</li>
  <li>🌙 <strong>Engulfing</strong> — One candle completely engulfs the previous. Strong reversal.</li>
</ul>
<h3>How to Use Them</h3>
<p>Never trade a candlestick pattern in isolation. Always confirm with:</p>
<ul>
  <li>Key support/resistance level</li>
  <li>Trend direction</li>
  <li>Volume or momentum indicator</li>
</ul>
<blockquote>💡 <strong>Key Takeaway:</strong> Candlestick patterns are clues, not guarantees. Use them as confirmation, not as standalone signals.</blockquote>''',
         2, 8),

        (inter_id, 'Trend Lines & Market Structure',
         '''<h2>Trend Lines and Market Structure</h2>
<p>The most fundamental concept in trading: <strong>the trend is your friend</strong>. Understanding market structure tells you whether to look for buys, sells, or to stay out.</p>
<h3>Market Structure</h3>
<ul>
  <li>📈 <strong>Uptrend</strong> = Higher Highs (HH) + Higher Lows (HL)</li>
  <li>📉 <strong>Downtrend</strong> = Lower Highs (LH) + Lower Lows (LL)</li>
  <li>↔️ <strong>Ranging</strong> = Price bouncing between two levels</li>
</ul>
<h3>Drawing Trend Lines</h3>
<p>In an uptrend, connect the <strong>higher lows</strong>. In a downtrend, connect the <strong>lower highs</strong>. A break of the trend line signals a potential reversal.</p>
<h3>Trading With the Trend</h3>
<p>Always trade in the direction of the higher timeframe trend. If the daily chart is bullish, look for buy setups on the 1-hour chart.</p>
<blockquote>💡 <strong>Key Takeaway:</strong> Identify the trend on a higher timeframe first, then drop to a lower timeframe to find your entry. This is called top-down analysis.</blockquote>''',
         3, 12),
    ]

    for lesson in beginner_lessons + inter_lessons:
        c.execute(
            'INSERT INTO lessons (course_id, title, content, order_number, duration_minutes) VALUES (?,?,?,?,?)',
            lesson
        )
