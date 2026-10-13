# usage_store.py
"""
Usage tracking backed by the Supabase `usage_logs` table
(schema: supabase/migrations/20261013_usage_logs.sql).

Logging is best-effort: a failure here must never break the request being logged.
"""
import logging
from typing import Dict, Optional

from supabase_auth import supabase_admin

logger = logging.getLogger(__name__)

MAX_QUERY_TEXT_LENGTH = 1000
RECENT_ACTIVITY_LIMIT = 10


def log_usage(user_id: str, user_email: str, endpoint: str, query_text: Optional[str] = None) -> None:
    """Record one user action. Never raises."""
    if not supabase_admin:
        return
    try:
        supabase_admin.table("usage_logs").insert({
            "user_id": user_id,
            "user_email": user_email,
            "endpoint": endpoint,
            "query_text": (query_text or "")[:MAX_QUERY_TEXT_LENGTH] or None,
        }).execute()
    except Exception as e:
        logger.warning(f"[Usage] Failed to log {endpoint} for {user_email}: {e}")


def get_usage_counts() -> Dict[str, dict]:
    """Return {email: {"total_requests": n, "last_request": ts}} for every user with activity."""
    if not supabase_admin:
        return {}
    try:
        rows = supabase_admin.table("usage_counts").select("*").execute().data or []
        return {r["user_email"]: r for r in rows}
    except Exception as e:
        logger.warning(f"[Usage] Failed to load usage counts: {e}")
        return {}


def get_user_stats(user_email: str) -> dict:
    """Usage statistics for one user: totals, per-endpoint counts and recent activity."""
    empty = {"email": user_email, "total_requests": 0, "by_endpoint": [], "recent_activity": []}
    if not supabase_admin:
        return empty
    try:
        rows = (
            supabase_admin.table("usage_logs")
            .select("endpoint, query_text, created_at")
            .eq("user_email", user_email)
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning(f"[Usage] Failed to load stats for {user_email}: {e}")
        return empty

    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["endpoint"]] = counts.get(r["endpoint"], 0) + 1
    by_endpoint = sorted(
        ({"endpoint": k, "count": v} for k, v in counts.items()),
        key=lambda x: x["count"], reverse=True,
    )
    return {
        "email": user_email,
        "total_requests": len(rows),
        "by_endpoint": by_endpoint,
        "recent_activity": rows[:RECENT_ACTIVITY_LIMIT],
    }
