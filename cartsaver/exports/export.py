"""
CartSaver -- CSV Export for Power BI
Generates funnel_summary.csv, segments.csv, offer_performance.csv, kpi_summary.csv.
Works with both SQLite and PostgreSQL.
"""

import csv
import logging
from pathlib import Path
from datetime import datetime

from cartsaver.config import EXPORT_DIR, COST_EMAIL, COST_SMS, COST_WHATSAPP
from cartsaver.db.setup import get_connection

logger = logging.getLogger(__name__)


def _ensure_dir():
    p = Path(EXPORT_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# 1. funnel_summary.csv
# ---------------------------------------------------------------------------

def export_funnel_summary(stage_counts: list[dict], dropoffs: list[dict]):
    """
    Write funnel_summary.csv with columns:
        stage, users, dropoff_to_next_pct
    """
    out = _ensure_dir() / "funnel_summary.csv"
    dropoff_map = {d["from"]: d["dropoff_pct"] for d in dropoffs}

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["stage", "users", "dropoff_to_next_pct"])
        for sc in stage_counts:
            writer.writerow([
                sc["stage"],
                sc["users"],
                dropoff_map.get(sc["stage"], ""),
            ])
    logger.info("Exported %s", out)
    return str(out)


# ---------------------------------------------------------------------------
# 2. segments.csv
# ---------------------------------------------------------------------------

def export_segments(segmented_users: list[dict]):
    """
    Write segments.csv with columns:
        user_id, name, email, product_name, intent_tier, view_count,
        cart_count, checkout_count, purchase_count
    """
    out = _ensure_dir() / "segments.csv"
    fields = [
        "user_id", "name", "email", "product_name", "intent_tier",
        "view_count", "cart_count", "checkout_count", "purchase_count",
    ]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(segmented_users)
    logger.info("Exported %s (%d rows)", out, len(segmented_users))
    return str(out)


# ---------------------------------------------------------------------------
# 3. offer_performance.csv
# ---------------------------------------------------------------------------

def export_offer_performance(conn=None):
    """
    Query sent_offers table and write offer_performance.csv:
        discount_tier, messages_sent, conversions, conversion_rate
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        # Standard SQL compatible with both SQLite and PostgreSQL
        sql = """
        SELECT
            CASE
                WHEN discount_applied = 0  THEN 'No Discount (Nudge)'
                WHEN discount_applied = 5  THEN '5% Discount'
                WHEN discount_applied = 10 THEN '10% Discount'
                WHEN discount_applied = 15 THEN '15% Discount'
                ELSE 'Other'
            END AS discount_tier,
            COUNT(*)                                           AS messages_sent,
            SUM(CASE WHEN converted = 1 THEN 1 ELSE 0 END)    AS conversions
        FROM sent_offers
        GROUP BY discount_tier
        ORDER BY discount_tier;
        """
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
    finally:
        if close_conn:
            conn.close()

    out = _ensure_dir() / "offer_performance.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["discount_tier", "messages_sent", "conversions",
                         "conversion_rate"])
        for row in rows:
            tier, sent, conv = row[0], row[1], row[2]
            conv = conv or 0
            rate = (conv / sent * 100) if sent > 0 else 0.0
            writer.writerow([tier, sent, conv, f"{rate:.2f}"])
    logger.info("Exported %s (%d tiers)", out, len(rows))
    return str(out)


# ---------------------------------------------------------------------------
# 4. kpi_summary.csv
# ---------------------------------------------------------------------------

def export_kpi_summary(conn=None):
    """
    Compute high-level KPIs and write kpi_summary.csv:
        kpi, value
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        cur = conn.cursor()

        # Total revenue from purchases
        cur.execute("""
            SELECT COALESCE(SUM(product_price), 0)
              FROM user_events WHERE event_type = 'purchase';
        """)
        revenue = float(cur.fetchone()[0])

        # Total unique users
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_events;")
        total_users = cur.fetchone()[0]

        # Users who purchased
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_events
             WHERE event_type = 'purchase';
        """)
        purchasers = cur.fetchone()[0]

        # Users who added to cart
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_events
             WHERE event_type = 'add_to_cart';
        """)
        carters = cur.fetchone()[0]

        # Users who added to cart but did NOT purchase
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_events
             WHERE event_type = 'add_to_cart'
               AND user_id NOT IN (
                   SELECT DISTINCT user_id FROM user_events
                    WHERE event_type = 'purchase'
               );
        """)
        abandoners = cur.fetchone()[0]

        # Notification costs -- standard SUM/CASE instead of FILTER
        cur.execute("""
            SELECT
                SUM(CASE WHEN channel = 'email'    THEN 1 ELSE 0 END) AS emails,
                SUM(CASE WHEN channel = 'sms'      THEN 1 ELSE 0 END) AS sms_count,
                SUM(CASE WHEN channel = 'whatsapp' THEN 1 ELSE 0 END) AS wa_count
            FROM sent_offers;
        """)
        row = cur.fetchone()
        emails = row[0] or 0
        sms = row[1] or 0
        wa = row[2] or 0

        cur.close()
    finally:
        if close_conn:
            conn.close()

    cvr = (purchasers / total_users * 100) if total_users > 0 else 0.0
    abandonment_rate = (abandoners / carters * 100) if carters > 0 else 0.0

    notif_cost = (
        emails * COST_EMAIL
        + sms * COST_SMS
        + wa * COST_WHATSAPP
    )
    roas = (revenue / notif_cost) if notif_cost > 0 else 0.0

    kpis = [
        ("Revenue", f"{revenue:.2f}"),
        ("CVR (%)", f"{cvr:.2f}"),
        ("Abandonment Rate (%)", f"{abandonment_rate:.2f}"),
        ("ROAS", f"{roas:.2f}"),
        ("Total Users", total_users),
        ("Purchasers", purchasers),
        ("Cart Abandoners", abandoners),
        ("Notification Cost", f"{notif_cost:.4f}"),
        ("Emails Sent", emails),
        ("SMS Sent", sms),
        ("WhatsApp Sent", wa),
    ]

    out = _ensure_dir() / "kpi_summary.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["kpi", "value"])
        writer.writerows(kpis)
    logger.info("Exported %s", out)
    return str(out)


# ---------------------------------------------------------------------------
# Run all exports
# ---------------------------------------------------------------------------

def run_all_exports(stage_counts=None, dropoffs=None, segmented_users=None,
                    conn=None):
    """Export all four CSV files.  Returns list of file paths."""
    paths = []

    if stage_counts and dropoffs:
        paths.append(export_funnel_summary(stage_counts, dropoffs))

    if segmented_users:
        paths.append(export_segments(segmented_users))

    paths.append(export_offer_performance(conn))
    paths.append(export_kpi_summary(conn))

    logger.info("All exports complete -> %s", paths)
    return paths
