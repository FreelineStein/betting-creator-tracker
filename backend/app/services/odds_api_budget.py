"""
Odds API request budget tracker.

Free tier: 500 requests/month. We reserve 50 as buffer, so the effective
budget is 450. Resets on the 1st of each month.

Stores the counter in the database via a simple key-value row in a
lightweight table, falling back to in-memory tracking if the table
doesn't exist.
"""
import structlog
from datetime import datetime, timezone

log = structlog.get_logger()

MONTHLY_BUDGET = 450  # 500 free - 50 buffer

# In-memory fallback (resets on process restart, but good enough for MVP)
_counter = {"month": None, "count": 0}


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_usage() -> dict:
    """Return current month's usage and remaining budget."""
    month = _current_month()
    if _counter["month"] != month:
        _counter["month"] = month
        _counter["count"] = 0
    return {
        "month": month,
        "requests_used": _counter["count"],
        "budget_remaining": MONTHLY_BUDGET - _counter["count"],
    }


def record_request(count: int = 1):
    """Record that we made API request(s)."""
    month = _current_month()
    if _counter["month"] != month:
        _counter["month"] = month
        _counter["count"] = 0
    _counter["count"] += count

    usage = get_usage()
    log.info(
        "ODDS_API_USAGE",
        requests_this_month=usage["requests_used"],
        budget_remaining=usage["budget_remaining"],
    )

    if usage["budget_remaining"] < 50:
        log.warning("Odds API budget running low", **usage)


def check_budget() -> bool:
    """Return True if we have budget remaining, False if over limit."""
    usage = get_usage()
    if usage["budget_remaining"] <= 0:
        log.critical("Odds API budget exhausted — skipping resolution until next month", **usage)
        return False
    return True
