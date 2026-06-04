# ============================================================
# 27pips — analytics/performance.py
# Leaking Alpha Audit Engine
#
# Calculates per-user trading performance metrics:
#   • MAE  (Maximum Adverse Excursion)
#   • MFE  (Maximum Favorable Excursion)
#   • MAE/MFE Efficiency ratios
#   • Sortino Ratio (downside-deviation-based risk-adjusted return)
#   • Win rate, profit factor, avg win/loss
#
# Note on MAE/MFE:
#   Tick-by-tick high/low data is not captured in the journal table.
#   We use the following principled proxies:
#     MAE = |pips_gained_lost| when outcome = Loss  (the trade went fully
#           against you before you closed — worst case excursion ≈ actual loss)
#           For winning trades MAE is estimated as 0 (best case; no adverse data)
#     MFE = |pips_gained_lost| when outcome = Win   (you captured all the move)
#           For losing trades MFE is estimated as 0 (worst case; no favourable data)
#   MAE Efficiency = pips_gained_lost / MFE  (how much of the potential gain was
#                   captured — only meaningful for winning trades)
#   MFE Efficiency = (pips_gained_lost + |MAE|) / MAE  (how well the stop was placed)
#
# Sortino Ratio formula:
#   R_i  = pips gained/lost per trade (return series)
#   T    = number of trades
#   μ    = mean(R_i)
#   MAR  = minimum acceptable return (risk_free_rate, default 0)
#   DD_i = min(R_i - MAR, 0)   for each trade
#   σ_d  = sqrt( sum(DD_i²) / T )   (downside deviation)
#   Sortino = (μ - MAR) / σ_d        (∞ if σ_d == 0 and μ > MAR)
# ============================================================

import math
import logging
from datetime import datetime, timezone
from database import get_db

log = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────

def compute_and_store(user_id: int, risk_free_rate: float = 0.0) -> dict:
    """
    Main entry point.  Iterates through all closed trades for user_id,
    computes all metrics, upserts into performance_metrics, and returns
    the metrics dict.  Returns None if the user has no closed trades.

    A 'closed trade' is any journal row that has pips_gained_lost != NULL
    and outcome IN ('Win','Loss').
    """
    db = get_db()
    try:
        trades = _fetch_closed_trades(db, user_id)
        if not trades:
            log.info('[PERF] user_id=%s has no closed trades — skipping', user_id)
            return None

        metrics = _calculate_metrics(trades, risk_free_rate)
        metrics['user_id']       = user_id
        metrics['risk_free_rate'] = risk_free_rate
        _upsert_metrics(db, metrics)
        db.commit()
        log.info('[PERF] Metrics stored for user_id=%s: %s', user_id, metrics)
        return metrics
    finally:
        db.close()


def fetch_metrics(user_id: int) -> dict | None:
    """
    Retrieve the last-computed metrics for user_id from performance_metrics.
    Returns None if no metrics exist yet (user has never triggered a compute).
    """
    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM performance_metrics WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


# ── Internal helpers ───────────────────────────────────────

def _fetch_closed_trades(db, user_id: int) -> list[dict]:
    """
    Cursor-style iteration over closed trades.
    Closed = has a numeric pips_gained_lost AND outcome is Win or Loss.
    """
    rows = db.execute(
        '''SELECT id, pair, direction, entry_price, exit_price,
                  lot_size, pips_gained_lost, outcome, created_at
           FROM journal
           WHERE user_id = ?
             AND pips_gained_lost IS NOT NULL
             AND outcome IN ('Win', 'Loss')
           ORDER BY created_at ASC''',
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _calculate_metrics(trades: list[dict], risk_free_rate: float) -> dict:
    """
    Core calculation engine — pure Python, database-agnostic.
    Iterates through trades like a procedural cursor loop.
    """
    trade_count = len(trades)
    win_count   = 0
    loss_count  = 0
    win_pips    = []
    loss_pips   = []   # stored as positive values
    mae_list    = []
    mfe_list    = []
    returns     = []   # R_i series for Sortino

    # ── Cursor loop over trades ────────────────────────────
    for trade in trades:
        pips    = float(trade['pips_gained_lost'] or 0)
        outcome = trade['outcome']

        returns.append(pips)

        if outcome == 'Win':
            win_count += 1
            win_pips.append(pips)
            # MAE proxy: 0 (no adverse data for winning trades)
            # MFE proxy: full pip gain (all of the move was captured)
            mae_list.append(0.0)
            mfe_list.append(abs(pips))
        else:
            loss_count += 1
            loss_pips.append(abs(pips))
            # MAE proxy: full pip loss (worst adverse excursion = the actual loss)
            # MFE proxy: 0 (no favorable data for losing trades)
            mae_list.append(abs(pips))
            mfe_list.append(0.0)

    # ── Aggregate stats ────────────────────────────────────
    win_rate    = round(win_count / trade_count * 100, 2) if trade_count else 0.0
    avg_win     = round(sum(win_pips) / len(win_pips), 4)   if win_pips  else 0.0
    avg_loss    = round(sum(loss_pips) / len(loss_pips), 4) if loss_pips else 0.0
    net_pips    = round(sum(returns), 4)

    # Profit factor = gross wins / gross losses
    gross_win   = sum(win_pips)
    gross_loss  = sum(loss_pips)
    profit_factor = round(gross_win / gross_loss, 4) if gross_loss > 0 else None

    # ── MAE / MFE ──────────────────────────────────────────
    avg_mae = round(sum(mae_list) / len(mae_list), 4) if mae_list else 0.0
    avg_mfe = round(sum(mfe_list) / len(mfe_list), 4) if mfe_list else 0.0

    # MAE Efficiency: avg_win / avg_mfe  (did wins capture most of their potential?)
    # Range 0–1; higher is better
    mae_efficiency = round(avg_win / avg_mfe, 4) if avg_mfe > 0 else None

    # MFE Efficiency: avg_loss / avg_mae  (how close to max adverse did we get stopped?)
    # Range 0–1; lower is better (stopped before MAE)
    mfe_efficiency = round(avg_loss / avg_mae, 4) if avg_mae > 0 else None

    # ── Sortino Ratio ──────────────────────────────────────
    sortino = _sortino_ratio(returns, risk_free_rate)

    return {
        'trade_count':   trade_count,
        'win_count':     win_count,
        'loss_count':    loss_count,
        'win_rate':      win_rate,
        'avg_win_pips':  avg_win,
        'avg_loss_pips': avg_loss,
        'profit_factor': profit_factor,
        'avg_mae_pips':  avg_mae,
        'avg_mfe_pips':  avg_mfe,
        'mae_efficiency': mae_efficiency,
        'mfe_efficiency': mfe_efficiency,
        'sortino_ratio': sortino,
        'net_pips':      net_pips,
    }


def _sortino_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float | None:
    """
    Sortino Ratio = (mean_return - MAR) / downside_deviation
    MAR (minimum acceptable return) = risk_free_rate per trade.

    Downside deviation uses the full sample (denominator = N, not N-1)
    which is standard for trading metrics.

    Returns None if there are fewer than 2 trades (not statistically meaningful).
    Returns None if downside deviation is 0 and mean <= MAR (no signal).
    Returns a large positive sentinel (999.0) if σ_d == 0 and mean > MAR
    (all returns above MAR with no downside risk — effectively infinite Sortino).
    """
    n = len(returns)
    if n < 2:
        return None

    mean_return = sum(returns) / n
    mar         = risk_free_rate

    # Downside deviations: only negative deviations below MAR count
    downside_sq = [(min(r - mar, 0.0) ** 2) for r in returns]
    variance_d  = sum(downside_sq) / n
    sigma_d     = math.sqrt(variance_d)

    if sigma_d == 0:
        return 999.0 if mean_return > mar else None

    sortino = (mean_return - mar) / sigma_d
    return round(sortino, 4)


def _upsert_metrics(db, metrics: dict) -> None:
    """
    Insert or update the performance_metrics row for this user.
    Uses INSERT OR IGNORE + UPDATE pattern (works on both SQLite and PostgreSQL
    via our existing DBConnection.execute() translator).
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Try insert first; if unique constraint fires (user already has a row)
    # the ON CONFLICT DO NOTHING means nothing happens, then UPDATE runs.
    db.execute(
        '''INSERT OR IGNORE INTO performance_metrics (user_id) VALUES (?)''',
        (metrics['user_id'],)
    )
    db.execute(
        '''UPDATE performance_metrics SET
               computed_at    = ?,
               trade_count    = ?,
               win_count      = ?,
               loss_count     = ?,
               win_rate       = ?,
               avg_win_pips   = ?,
               avg_loss_pips  = ?,
               profit_factor  = ?,
               avg_mae_pips   = ?,
               avg_mfe_pips   = ?,
               mae_efficiency = ?,
               mfe_efficiency = ?,
               sortino_ratio  = ?,
               risk_free_rate = ?,
               net_pips       = ?
           WHERE user_id = ?''',
        (
            now,
            metrics['trade_count'],
            metrics['win_count'],
            metrics['loss_count'],
            metrics['win_rate'],
            metrics['avg_win_pips'],
            metrics['avg_loss_pips'],
            metrics['profit_factor'],
            metrics['avg_mae_pips'],
            metrics['avg_mfe_pips'],
            metrics['mae_efficiency'],
            metrics['mfe_efficiency'],
            metrics['sortino_ratio'],
            metrics['risk_free_rate'],
            metrics['net_pips'],
            metrics['user_id'],
        )
    )
