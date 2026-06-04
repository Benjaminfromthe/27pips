# ============================================================
# 27pips — analytics/coaching.py
# Automated Psychological Coaching Assistant
#
# Design: EVENT-DRIVEN, not polling.
#   A polling daemon that wakes every N minutes and scans all
#   users is wasteful and slow.  Instead this module is called
#   from journal/routes.py immediately after every trade save —
#   the same daemon-thread hook that triggers performance
#   recompute.  Response time = milliseconds, CPU cost = zero
#   when no trades are being logged.
#
# Cool-Down Logic:
#   After each trade save, we look at the user's last N trades
#   within the LOOKBACK_HOURS window.  If the tail of that list
#   shows LOSS_THRESHOLD or more consecutive losses we fire the
#   alert.  A de-duplication guard in coaching_alerts ensures
#   we send at most once per COOLDOWN_RESEND_HOURS window so a
#   user in a losing streak is never spammed.
#
# Configurable via env vars (with safe defaults):
#   COACH_LOSS_THRESHOLD     = 3   (consecutive losses to trigger)
#   COACH_LOOKBACK_HOURS     = 4   (only trades within this window)
#   COACH_COOLDOWN_RESEND_H  = 6   (min hours between repeat alerts)
# ============================================================

import logging
import os
import traceback
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# ── Configurable thresholds (env-var overridable) ──────────
LOSS_THRESHOLD      = int(os.environ.get('COACH_LOSS_THRESHOLD',    3))
LOOKBACK_HOURS      = int(os.environ.get('COACH_LOOKBACK_HOURS',    4))
COOLDOWN_RESEND_H   = int(os.environ.get('COACH_COOLDOWN_RESEND_H', 6))


# ── Public entry point ─────────────────────────────────────

def check_and_alert(user_id: int, app_config: dict) -> bool:
    """
    Check whether a cool-down alert should be sent to user_id.
    Returns True if an alert was fired, False otherwise.

    Safe to call from a daemon thread — never raises, never blocks
    the caller.  Uses its own DB connection and closes it when done.
    """
    try:
        from database import get_db
        db = get_db()
        try:
            user_row = db.execute(
                'SELECT username, email FROM users WHERE id = ?',
                (user_id,)
            ).fetchone()
            if not user_row:
                return False

            username = user_row['username']
            email    = user_row['email']

            # ── 1. Fetch recent closed trades in the lookback window ──
            cutoff = (datetime.now(timezone.utc)
                      - timedelta(hours=LOOKBACK_HOURS))
            cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

            rows = db.execute(
                '''SELECT outcome
                   FROM journal
                   WHERE user_id = ?
                     AND outcome IN ('Win', 'Loss')
                     AND created_at >= ?
                   ORDER BY created_at DESC''',
                (user_id, cutoff_str)
            ).fetchall()

            if not rows:
                return False

            outcomes = [r['outcome'] for r in rows]

            # ── 2. Count consecutive losses from the MOST RECENT trade ──
            consecutive_losses = 0
            for outcome in outcomes:          # already ordered DESC (newest first)
                if outcome == 'Loss':
                    consecutive_losses += 1
                else:
                    break                     # streak broken — stop counting

            log.info(
                '[COACH] user_id=%s: %d consecutive losses in last %dh '
                '(threshold=%d)',
                user_id, consecutive_losses, LOOKBACK_HOURS, LOSS_THRESHOLD
            )

            if consecutive_losses < LOSS_THRESHOLD:
                return False

            # ── 3. De-duplication — was an alert already sent recently? ──
            recent_alert = db.execute(
                '''SELECT sent_at FROM coaching_alerts
                   WHERE user_id = ?
                   ORDER BY sent_at DESC
                   LIMIT 1''',
                (user_id,)
            ).fetchone()

            if recent_alert:
                sent_at = recent_alert['sent_at']
                if isinstance(sent_at, str):
                    sent_at = datetime.strptime(sent_at, '%Y-%m-%d %H:%M:%S')\
                                      .replace(tzinfo=timezone.utc)
                elif getattr(sent_at, 'tzinfo', None) is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)

                hours_since = (datetime.now(timezone.utc) - sent_at)\
                              .total_seconds() / 3600
                if hours_since < COOLDOWN_RESEND_H:
                    log.info(
                        '[COACH] Suppressed duplicate alert for user_id=%s '
                        '(last sent %.1fh ago, cooldown=%dh)',
                        user_id, hours_since, COOLDOWN_RESEND_H
                    )
                    return False

            # ── 4. Find the Psychology lesson link ────────────────────
            lesson_url = _get_psychology_lesson_url(db, app_config)

            # ── 5. Record the alert BEFORE sending (avoids race conditions) ──
            now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            db.execute(
                '''INSERT INTO coaching_alerts
                   (user_id, alert_type, consecutive_losses,
                    lookback_hours, sent_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, 'COOL_DOWN', consecutive_losses,
                 LOOKBACK_HOURS, now_str)
            )
            db.commit()

        finally:
            db.close()

        # ── 6. Send the cool-down email ────────────────────────────────
        _send_cooldown_email(
            email, username, consecutive_losses,
            lesson_url, app_config
        )
        return True

    except Exception:
        log.error('[COACH] Unexpected error for user_id=%s:\n%s',
                  user_id, traceback.format_exc())
        return False


# ── Helpers ────────────────────────────────────────────────

def _get_psychology_lesson_url(db, app_config: dict = None) -> str:
    """
    Find the lesson most likely to be the Psychology / mindset lesson.
    Falls back to the education homepage if none is found.
    """
    base_url = (app_config or {}).get(
        'APP_BASE_URL',
        os.environ.get('APP_BASE_URL', 'https://two7pips.onrender.com')
    )

    # Search by keyword — matches our seeded lesson title
    row = db.execute(
        '''SELECT id FROM lessons
           WHERE LOWER(title) LIKE '%psychol%'
              OR LOWER(title) LIKE '%mindset%'
              OR LOWER(title) LIKE '%mental%'
           LIMIT 1'''
    ).fetchone()

    if row:
        return f"{base_url}/education/lesson/{row['id']}"
    return f"{base_url}/education/"


def _send_cooldown_email(to_email: str, username: str,
                         loss_count: int, lesson_url: str,
                         app_config: dict) -> None:
    """
    Build and dispatch the psychological cool-down alert email.
    Reuses the existing _spawn_email / _dispatch_email infrastructure
    from auth/routes.py — no new email code needed.
    """
    from blueprints.auth.routes import (
        _snapshot_mail_cfg, _spawn_email, _html_wrapper
    )

    cfg = _snapshot_mail_cfg(app_config)

    subject = f"⚠️ 27pips — Time to Step Back, {username}"

    body_text = '\n\n'.join([
        f"Hi {username},",
        (f"Our coaching assistant has detected {loss_count} consecutive "
         f"losses in the last {LOOKBACK_HOURS} hours."),
        "This is a signal to step back, breathe, and reset — not to revenge trade.",
        "📚 Psychological Reset Lesson:",
        lesson_url,
        "Remember: Protecting your capital IS a trade.",
        "— 27pips Coaching Assistant / Shema Trading Hub",
        "If you believe this alert is incorrect, simply continue trading "
        "and we'll recalibrate automatically.",
    ])

    content_html = f"""
  <div style="background:#7f1d1d;border:1px solid #dc2626;border-radius:10px;
              padding:16px;margin-bottom:20px;text-align:center">
    <p style="color:#fca5a5;font-size:1.1rem;font-weight:800;margin:0">
      ⚠️ Cool-Down Alert
    </p>
  </div>
  <p style="color:#94a3b8;margin-bottom:12px">Hi <strong style="color:#f1f5f9">{username}</strong>,</p>
  <p style="color:#94a3b8;margin-bottom:20px">
    Our coaching assistant has detected
    <strong style="color:#ef4444">{loss_count} consecutive losses</strong>
    in the last <strong style="color:#f1f5f9">{LOOKBACK_HOURS} hours</strong>.
  </p>
  <div style="background:#1e293b;border-left:4px solid #ef4444;
              border-radius:0 10px 10px 0;padding:16px;margin-bottom:20px">
    <p style="color:#fca5a5;font-weight:700;margin:0 0 6px">
      This is a signal to step back — not to revenge trade.
    </p>
    <p style="color:#94a3b8;font-size:0.88rem;margin:0">
      Protecting your capital IS a trade. The market will still be there tomorrow.
    </p>
  </div>
  <p style="color:#94a3b8;margin-bottom:16px">
    📚 Take a few minutes to reset with this lesson:
  </p>
  <a href="{lesson_url}"
     style="display:inline-block;background:#3b82f6;color:#fff;
            padding:14px 28px;border-radius:10px;text-decoration:none;
            font-weight:700;font-size:1rem;margin-bottom:24px">
    🧠 Psychological Reset Lesson
  </a>
  <p style="color:#64748b;font-size:0.78rem;margin-top:8px">
    This alert will not repeat for {COOLDOWN_RESEND_H} hours.
    If you believe it's incorrect, simply continue trading and we'll recalibrate.
  </p>"""

    body_html = _html_wrapper(
        content_html,
        "You are receiving this because you are a 27pips member. "
        "This is an automated coaching alert — no action is required."
    )

    log.info('[COACH] Sending cool-down alert to user %s (%s losses)',
             username, loss_count)
    _spawn_email(cfg, to_email, subject, body_text, body_html,
                 log_tag='COACH')
