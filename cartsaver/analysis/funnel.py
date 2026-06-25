"""
CartSaver -- Funnel Analysis
SQL-driven funnel stage counts, drop-off rates, and cart abandoner identification.
Works with both SQLite and PostgreSQL.
"""

import logging
from cartsaver.db.setup import get_connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL Queries  (standard SQL -- compatible with SQLite AND PostgreSQL)
# ---------------------------------------------------------------------------

SQL_STAGE_COUNTS = """
SELECT 'product_view'     AS stage, COUNT(DISTINCT user_id) AS users
  FROM user_events WHERE event_type = 'product_view'
UNION ALL
SELECT 'add_to_cart',             COUNT(DISTINCT user_id)
  FROM user_events WHERE event_type = 'add_to_cart'
UNION ALL
SELECT 'checkout_started',        COUNT(DISTINCT user_id)
  FROM user_events WHERE event_type = 'checkout_started'
UNION ALL
SELECT 'purchase',                COUNT(DISTINCT user_id)
  FROM user_events WHERE event_type = 'purchase';
"""

SQL_CART_ABANDONERS = """
SELECT DISTINCT ue.user_id
  FROM user_events ue
 WHERE ue.event_type = 'add_to_cart'
   AND ue.user_id NOT IN (
       SELECT DISTINCT user_id FROM user_events WHERE event_type = 'purchase'
   );
"""

# Use standard SUM(CASE WHEN ...) instead of PostgreSQL-only FILTER (WHERE ...)
SQL_USER_EVENT_SUMMARY = """
SELECT
    ue.user_id,
    u.name,
    u.email,
    u.phone,
    ue.product_id,
    p.name           AS product_name,
    p.cost_price,
    p.selling_price,
    p.category,
    SUM(CASE WHEN ue.event_type = 'product_view'     THEN 1 ELSE 0 END) AS view_count,
    SUM(CASE WHEN ue.event_type = 'add_to_cart'      THEN 1 ELSE 0 END) AS cart_count,
    SUM(CASE WHEN ue.event_type = 'checkout_started' THEN 1 ELSE 0 END) AS checkout_count,
    SUM(CASE WHEN ue.event_type = 'purchase'         THEN 1 ELSE 0 END) AS purchase_count
FROM user_events ue
JOIN users    u ON u.user_id    = ue.user_id
JOIN products p ON p.product_id = ue.product_id
GROUP BY ue.user_id, u.name, u.email, u.phone,
         ue.product_id, p.name, p.cost_price, p.selling_price, p.category;
"""

# Ordered stages for drop-off computation
STAGE_ORDER = ["product_view", "add_to_cart", "checkout_started", "purchase"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stage_counts(conn=None) -> list[dict]:
    """
    Return a list of dicts: [{"stage": ..., "users": ...}, ...] in funnel order.
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute(SQL_STAGE_COUNTS)
        rows = cur.fetchall()
        cur.close()
        stage_map = {row[0]: row[1] for row in rows}
        result = [{"stage": s, "users": stage_map.get(s, 0)} for s in STAGE_ORDER]
        logger.info("Funnel stage counts: %s", result)
        return result
    finally:
        if close_conn:
            conn.close()


def compute_dropoffs(stage_counts: list[dict]) -> list[dict]:
    """
    Given stage counts, compute drop-off rate between each adjacent stage.

    Returns list of dicts:
        [{"from": "product_view", "to": "add_to_cart",
          "dropoff_pct": 55.0, "from_users": 100, "to_users": 45}, ...]
    """
    dropoffs = []
    for i in range(len(stage_counts) - 1):
        src = stage_counts[i]
        dst = stage_counts[i + 1]
        if src["users"] > 0:
            dropoff = (1.0 - dst["users"] / src["users"]) * 100.0
        else:
            dropoff = 0.0
        dropoffs.append({
            "from": src["stage"],
            "to": dst["stage"],
            "from_users": src["users"],
            "to_users": dst["users"],
            "dropoff_pct": round(dropoff, 2),
        })
    logger.info("Drop-off rates: %s", dropoffs)
    return dropoffs


def get_cart_abandoners(conn=None) -> list[str]:
    """Return list of user_ids who added to cart but never purchased."""
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute(SQL_CART_ABANDONERS)
        rows = cur.fetchall()
        cur.close()
        abandoners = [r[0] for r in rows]
        logger.info("Cart abandoners found: %d", len(abandoners))
        return abandoners
    finally:
        if close_conn:
            conn.close()


def get_user_event_summary(conn=None) -> list[dict]:
    """
    Return per-user, per-product behavioural summary with user and product
    details.  Each row is a dict with keys:
        user_id, name, email, phone, product_id, product_name,
        cost_price, selling_price, category,
        view_count, cart_count, checkout_count, purchase_count
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute(SQL_USER_EVENT_SUMMARY)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        logger.info("User event summaries fetched: %d rows", len(rows))
        return rows
    finally:
        if close_conn:
            conn.close()


def run_funnel_analysis(conn=None):
    """Convenience wrapper: run full funnel analysis and return all data."""
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        stage_counts = get_stage_counts(conn)
        dropoffs = compute_dropoffs(stage_counts)
        abandoners = get_cart_abandoners(conn)
        summaries = get_user_event_summary(conn)
        return {
            "stage_counts": stage_counts,
            "dropoffs": dropoffs,
            "abandoners": abandoners,
            "user_summaries": summaries,
        }
    finally:
        if close_conn:
            conn.close()
