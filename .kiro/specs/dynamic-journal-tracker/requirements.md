# Requirements Document

## Introduction

This feature replaces all mock/hardcoded data in the 27pips Forex trading platform with a fully dynamic, database-backed system. It introduces two new SQLite models — **Journal** and **Tracker** — linked to authenticated users, a file-upload-capable trade logging endpoint, automatic balance and drawdown calculations, and real-time UI widgets that reflect live data. A risk alert badge is shown whenever a user's daily losses breach their configured drawdown limit.

The platform is built with Flask + SQLite and already has a working authentication system (session-based, `user_id` stored in session). The existing journal and tracker blueprints currently return hardcoded data.

---

## Glossary

- **Journal**: The SQLite table and associated logic that stores individual trade records per user.
- **Tracker**: The SQLite table and associated logic that stores a user's prop firm challenge account metrics.
- **Trade**: A single forex trade entry recorded by a user, including pair, direction, prices, lot size, outcome, and optional chart image.
- **Pair**: A forex currency pair or instrument (e.g., EUR/USD, XAU/USD).
- **Direction**: The trade side — either `Buy` or `Sell`.
- **Outcome**: The result of a trade — either `Win` or `Loss`.
- **Pips_Gained_Lost**: The number of pips gained (positive) or lost (negative) on a trade.
- **Starting_Balance**: The initial account balance when a Tracker record is created.
- **Current_Balance**: The live account balance, updated automatically each time a trade is logged.
- **Daily_Drawdown_Limit**: The maximum percentage loss allowed in a single calendar day (default 5%).
- **Max_Loss_Limit**: The maximum cumulative percentage loss allowed over the challenge lifetime (default 10%).
- **Target_Profit**: The percentage profit required to pass the prop firm challenge (default 10%).
- **Daily_Loss_Today**: The sum of losses (in percentage of Starting_Balance) from all losing trades logged on the current calendar day.
- **Upload_Directory**: The server-side folder `static/uploads/` where chart image files are saved.
- **Risk_Alert**: A UI warning badge displayed when Daily_Loss_Today exceeds Daily_Drawdown_Limit.
- **Journal_API**: The Flask blueprint at `/journal` that handles trade CRUD operations.
- **Tracker_API**: The Flask blueprint at `/tracker` that handles challenge account data.
- **Database**: The SQLite database file `pips.db` managed via `database.py`.

---

## Requirements

### Requirement 1: Journal Database Model

**User Story:** As a trader, I want my trade entries stored persistently in a database linked to my account, so that my journal survives page refreshes and server restarts.

#### Acceptance Criteria

1. THE Database SHALL contain a `journal` table with columns: `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `user_id` (INTEGER NOT NULL, FOREIGN KEY referencing `users.id`), `pair` (TEXT NOT NULL), `direction` (TEXT NOT NULL, constrained to `Buy` or `Sell`), `entry_price` (REAL NOT NULL), `exit_price` (REAL), `lot_size` (REAL), `pips_gained_lost` (REAL), `outcome` (TEXT, constrained to `Win`, `Loss`, or NULL), `notes` (TEXT), `chart_image_url` (TEXT), `created_at` (DATETIME DEFAULT CURRENT_TIMESTAMP).
2. WHEN the application starts, THE Database SHALL create the `journal` table if it does not already exist.
3. THE Database SHALL enforce referential integrity so that a `journal` row cannot reference a `user_id` that does not exist in the `users` table.

---

### Requirement 2: Tracker Database Model

**User Story:** As a prop firm challenge trader, I want my challenge account metrics stored in the database, so that my progress is preserved and calculated accurately across sessions.

#### Acceptance Criteria

1. THE Database SHALL contain a `tracker` table with columns: `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `user_id` (INTEGER NOT NULL UNIQUE, FOREIGN KEY referencing `users.id`), `starting_balance` (REAL NOT NULL), `current_balance` (REAL NOT NULL), `daily_drawdown_limit` (REAL NOT NULL DEFAULT 5.0), `max_loss_limit` (REAL NOT NULL DEFAULT 10.0), `target_profit` (REAL NOT NULL DEFAULT 10.0).
2. WHEN the application starts, THE Database SHALL create the `tracker` table if it does not already exist.
3. THE Database SHALL enforce a UNIQUE constraint on `user_id` in the `tracker` table so that each user has at most one active challenge account.

---

### Requirement 3: Log Trade Endpoint with File Upload

**User Story:** As a trader, I want to submit a trade entry with an optional chart screenshot via a POST request, so that my trade is saved to the database with all relevant details.

#### Acceptance Criteria

1. WHEN an authenticated user sends a POST request to `/journal/add` with `multipart/form-data` containing `pair`, `direction`, `entry_price`, and at least one optional field, THE Journal_API SHALL insert a new row into the `journal` table and return a JSON response `{"success": true, "id": <new_id>}` with HTTP 201.
2. WHEN the POST request to `/journal/add` includes a file field named `chart_image`, THE Journal_API SHALL save the file to the `static/uploads/` directory with a unique filename and store the relative URL in the `chart_image_url` column.
3. WHEN the POST request to `/journal/add` is missing the required `pair` or `direction` or `entry_price` fields, THE Journal_API SHALL return `{"success": false, "message": "pair, direction, and entry_price are required."}` with HTTP 400.
4. WHEN an unauthenticated user sends a POST request to `/journal/add`, THE Journal_API SHALL return `{"success": false, "message": "Login required.", "auth_required": true}` with HTTP 401.
5. WHEN a file is uploaded to `/journal/add` and the file extension is not in the allowed set (`png`, `jpg`, `jpeg`, `gif`, `webp`), THE Journal_API SHALL return `{"success": false, "message": "Invalid file type. Allowed: png, jpg, jpeg, gif, webp."}` with HTTP 400.
6. WHEN a trade is successfully logged via `/journal/add` and the authenticated user has a `tracker` row, THE Tracker_API SHALL recalculate and update `current_balance` based on the `pips_gained_lost` value and `lot_size` submitted with the trade.

---

### Requirement 4: Auto-Update Current Balance

**User Story:** As a prop firm challenge trader, I want my current balance updated automatically whenever I log a trade, so that my tracker always reflects my real account state.

#### Acceptance Criteria

1. WHEN a trade with a non-null `pips_gained_lost` and `lot_size` is logged by an authenticated user who has a `tracker` row, THE Tracker_API SHALL update `current_balance` by applying the formula: `current_balance = current_balance + (pips_gained_lost * lot_size * 10)`.
2. WHEN a trade is logged with a null or missing `pips_gained_lost`, THE Tracker_API SHALL leave `current_balance` unchanged.
3. THE Tracker_API SHALL perform the balance update within the same database transaction as the journal insert so that the two operations are atomic.

---

### Requirement 5: Dynamic Drawdown and Profit Calculations

**User Story:** As a prop firm challenge trader, I want the tracker to dynamically calculate my daily drawdown usage and profit progress, so that I always see accurate risk metrics.

#### Acceptance Criteria

1. WHEN an authenticated user requests `GET /tracker/challenge`, THE Tracker_API SHALL calculate `daily_loss_today` as the sum of `ABS(pips_gained_lost * lot_size * 10)` for all losing trades (outcome = `Loss`) logged by that user on the current UTC calendar day, expressed as a percentage of `starting_balance`; WHEN no losing trades exist for the current day, THE Tracker_API SHALL return `daily_loss_today` as `0.0`.
2. WHEN an authenticated user requests `GET /tracker/challenge`, THE Tracker_API SHALL calculate `profit_progress` as `((current_balance - starting_balance) / starting_balance) * 100`.
3. WHEN an authenticated user requests `GET /tracker/challenge`, THE Tracker_API SHALL calculate `total_loss` as `((starting_balance - current_balance) / starting_balance) * 100` when `current_balance` is less than `starting_balance`, and `0.0` otherwise.
4. WHEN an authenticated user requests `GET /tracker/challenge`, THE Tracker_API SHALL return a JSON object containing: `account_size`, `current_balance`, `daily_drawdown_limit`, `max_loss_limit`, `target_profit`, `daily_loss_today`, `total_loss`, `profit_progress`, `profit_percent`, `daily_used_percent`, `max_used_percent`, and `drawdown_breached` (boolean).
5. WHEN an authenticated user has no `tracker` row, THE Tracker_API SHALL return `{"success": false, "message": "No tracker account found.", "setup_required": true}` with HTTP 404.

---

### Requirement 6: Risk Alert — Daily Drawdown Warning

**User Story:** As a prop firm challenge trader, I want to see a visible warning when my daily losses exceed my drawdown limit, so that I can stop trading before violating challenge rules.

#### Acceptance Criteria

1. WHEN `daily_loss_today` exceeds `daily_drawdown_limit` for an authenticated user, THE Tracker_API SHALL include `"drawdown_breached": true` in the `GET /tracker/challenge` response.
2. WHEN `daily_loss_today` is less than or equal to `daily_drawdown_limit`, THE Tracker_API SHALL include `"drawdown_breached": false` in the `GET /tracker/challenge` response.
3. WHEN the frontend receives a `GET /tracker/challenge` response with `"drawdown_breached": true`, THE frontend SHALL display a warning badge with the text "⚠️ Daily Drawdown Warning: Risk Parameters Exceeded" in the Prop Firm Challenge Tracker section.
4. WHEN the frontend receives a `GET /tracker/challenge` response with `"drawdown_breached": false`, THE frontend SHALL hide the drawdown warning badge.

---

### Requirement 7: Dynamic Journal Widget — Last 5 Trades

**User Story:** As a trader, I want the Journal widget to display my last 5 real trades from the database, so that I can review my recent activity without leaving the page.

#### Acceptance Criteria

1. WHEN an authenticated user views the Journal section, THE frontend SHALL fetch `GET /journal/entries` and render the 5 most recent trade entries in a table showing: `pair`, `direction`, `entry_price`, `exit_price`, `pips_gained_lost`, `outcome`, and `created_at`.
2. WHEN the `GET /journal/entries` response contains zero entries, THE frontend SHALL display the message "No trades logged yet. Start journaling above." in the Recent Entries area.
3. WHEN a trade entry has `outcome = Win`, THE frontend SHALL render the outcome cell with green styling.
4. WHEN a trade entry has `outcome = Loss`, THE frontend SHALL render the outcome cell with red styling.
5. WHEN an unauthenticated user views the Journal section, THE frontend SHALL display a prompt to log in instead of the trade table.

---

### Requirement 8: Dynamic Tracker Widget — Real Progress Bars

**User Story:** As a prop firm challenge trader, I want the Prop Firm Tracker widget to show real progress bars and values from the database, so that I can monitor my challenge status accurately.

#### Acceptance Criteria

1. WHEN an authenticated user views the Prop Firm Challenge Tracker section, THE frontend SHALL fetch `GET /tracker/challenge` and replace all hardcoded values with the returned data.
2. WHEN the `GET /tracker/challenge` response is received, THE frontend SHALL update the Account Balance card to show `current_balance` formatted as currency and the profit progress bar width as `profit_percent`%.
3. WHEN the `GET /tracker/challenge` response is received, THE frontend SHALL update the Daily Drawdown card to show `daily_loss_today`% used and set the progress bar width to `daily_used_percent`%.
4. WHEN the `GET /tracker/challenge` response is received, THE frontend SHALL update the Max Drawdown card to show `total_loss`% and set the progress bar width to `max_used_percent`%.
5. WHEN the `GET /tracker/challenge` response is received, THE frontend SHALL update the Profit Target card to show `profit_progress`% and set the progress bar width to `profit_percent`%.
6. WHEN `daily_used_percent` is 80 or above, THE frontend SHALL apply a red color class to the Daily Drawdown progress bar to signal danger.
7. WHEN an unauthenticated user views the Prop Firm Challenge Tracker section, THE frontend SHALL display the existing "Connect Your Challenge Account" prompt without fetching live data.

---

### Requirement 9: Tracker Account Setup Endpoint

**User Story:** As a new user, I want to create a tracker account with my starting balance, so that the system can track my prop firm challenge from the beginning.

#### Acceptance Criteria

1. WHEN an authenticated user sends a POST request to `/tracker/setup` with a JSON body containing `starting_balance` (a positive number), THE Tracker_API SHALL first check whether a `tracker` row already exists for that user; IF a row already exists, THE Tracker_API SHALL return `{"success": false, "message": "Tracker account already exists."}` with HTTP 409 regardless of the `starting_balance` value; WHEN no existing row is found and `starting_balance` is a positive number, THE Tracker_API SHALL insert a new row into the `tracker` table with `current_balance` equal to `starting_balance` and default limit values, and return `{"success": true}` with HTTP 201.
2. WHEN the `starting_balance` field is missing or not a positive number and no existing tracker row is found, THE Tracker_API SHALL return `{"success": false, "message": "starting_balance must be a positive number."}` with HTTP 400.

---

### Requirement 10: Journal Entries Retrieval Endpoint

**User Story:** As a trader, I want to retrieve my trade history via an API, so that the frontend can display my recent trades dynamically.

#### Acceptance Criteria

1. WHEN an authenticated user sends a GET request to `/journal/entries`, THE Journal_API SHALL return a JSON array of the user's trade entries ordered by `created_at` descending, limited to the 5 most recent records.
2. WHEN an authenticated user has no trade entries, THE Journal_API SHALL return an empty JSON array `[]` with HTTP 200.
3. WHEN an unauthenticated user sends a GET request to `/journal/entries`, THE Journal_API SHALL return `{"success": false, "message": "Login required.", "auth_required": true}` with HTTP 401.
