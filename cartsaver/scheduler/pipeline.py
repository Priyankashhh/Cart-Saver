"""
CartSaver -- Pipeline Orchestrator & Scheduler
Runs the full retention pipeline and optionally schedules it via APScheduler.
Works with both SQLite and PostgreSQL.
"""

import logging
import random
from pathlib import Path
from datetime import datetime

from cartsaver.config import (
    DB_BACKEND,
    PIPELINE_SCHEDULE_HOUR, PIPELINE_SCHEDULE_MINUTE, LOG_DIR,
)
from cartsaver.db.setup import get_connection
from cartsaver.analysis.funnel import run_funnel_analysis
from cartsaver.segmentation.segment import segment_users, TIER_CONVERTED
from cartsaver.engine.discount import compute_offers
from cartsaver.ai.message_gen import generate_messages
from cartsaver.notifications.notify import notify_all
from cartsaver.exports.export import run_all_exports

logger = logging.getLogger(__name__)

# Pipeline run log
_log_dir = Path(LOG_DIR)
_log_dir.mkdir(parents=True, exist_ok=True)
_PIPELINE_LOG = _log_dir / "pipeline.log"


def _log_run(message: str):
    ts = datetime.now().isoformat()
    with open(_PIPELINE_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


# ---------------------------------------------------------------------------
# Placeholder parameter marker  (? for SQLite, %s for PostgreSQL)
# ---------------------------------------------------------------------------

def _ph():
    """Return the correct parameter placeholder for the active backend."""
    return "%s" if DB_BACKEND == "postgresql" else "?"


# ---------------------------------------------------------------------------
# Record sent offers to database
# ---------------------------------------------------------------------------

def _save_offers_to_db(conn, offers: list[dict]):
    """Insert sent offer records into the sent_offers table."""
    rows = []
    for o in offers:
        for channel in ("email", "sms", "whatsapp"):
            rows.append((
                o["user_id"],
                o["product_id"],
                o.get("final_discount_pct", 0),
                o.get("message_type", "nudge"),
                channel,
                o.get("generated_message", ""),
                datetime.now().isoformat(),
                0,       # converted = False  (integer for SQLite compat)
                None,    # conversion_timestamp
            ))

    if not rows:
        return

    ph = _ph()
    cur = conn.cursor()

    if DB_BACKEND == "postgresql":
        from psycopg2.extras import execute_values
        execute_values(
            cur,
            """INSERT INTO sent_offers
               (user_id, product_id, discount_applied, message_type,
                channel, message_text, sent_at, converted, conversion_timestamp)
               VALUES %s""",
            rows,
        )
    else:
        cur.executemany(
            f"""INSERT INTO sent_offers
               (user_id, product_id, discount_applied, message_type,
                channel, message_text, sent_at, converted, conversion_timestamp)
               VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            rows,
        )

    cur.close()
    conn.commit()
    logger.info("Saved %d offer records to database.", len(rows))


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline():
    """Execute the full CartSaver retention pipeline."""
    start = datetime.now()
    logger.info("=== Pipeline run started at %s ===", start.isoformat())
    _log_run("Pipeline started")

    conn = get_connection()
    try:
        # 1. Funnel analysis
        logger.info("Step 1/6 -- Funnel analysis")
        funnel = run_funnel_analysis(conn)

        # 2. Segment users
        logger.info("Step 2/6 -- Customer segmentation")
        segmented = segment_users(funnel["user_summaries"])

        # 3. Filter to actionable users (exclude Converted)
        actionable = [u for u in segmented if u["intent_tier"] != TIER_CONVERTED]
        logger.info("Actionable (non-converted) users: %d", len(actionable))

        # 4. Discount engine
        logger.info("Step 3/6 -- Discount engine")
        offers = compute_offers(actionable)

        # 5. AI message generation
        logger.info("Step 4/6 -- AI message generation")
        offers = generate_messages(offers)

        # 6. Send notifications
        logger.info("Step 5/6 -- Sending notifications")
        offers = notify_all(offers)

        # 7. Save to database
        logger.info("Step 6/6 -- Saving offers to database")
        _save_offers_to_db(conn, offers)

        # 8. Export CSVs
        logger.info("Exporting CSV reports")
        run_all_exports(
            stage_counts=funnel["stage_counts"],
            dropoffs=funnel["dropoffs"],
            segmented_users=segmented,
            conn=conn,
        )

        elapsed = (datetime.now() - start).total_seconds()
        summary = (
            f"Pipeline completed in {elapsed:.1f}s -- "
            f"{len(offers)} offers sent to {len(set(o['user_id'] for o in offers))} users."
        )
        logger.info(summary)
        _log_run(summary)
        return offers

    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        _log_run(f"Pipeline FAILED: {exc}")
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Simulate conversions (for testing / demo purposes)
# ---------------------------------------------------------------------------

def simulate_conversions(conversion_rate: float = 0.30):
    """
    Randomly mark a percentage of sent offers as converted and insert
    corresponding purchase events.
    """
    conn = get_connection()
    ph = _ph()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT offer_id, user_id, product_id
              FROM sent_offers
             WHERE converted = 0;
        """)
        pending = cur.fetchall()
        cur.close()

        if not pending:
            logger.info("No unconverted offers to simulate.")
            return

        to_convert = random.sample(
            pending,
            k=max(1, int(len(pending) * conversion_rate)),
        )

        cur = conn.cursor()
        for row in to_convert:
            offer_id, uid, pid = row[0], row[1], row[2]
            now = datetime.now().isoformat()

            # Mark offer as converted
            cur.execute(f"""
                UPDATE sent_offers
                   SET converted = 1, conversion_timestamp = {ph}
                 WHERE offer_id = {ph};
            """, (now, offer_id))

            # Insert a purchase event
            cur.execute(f"""
                INSERT INTO user_events
                    (user_id, session_id, product_id, event_type,
                     timestamp, product_price, product_category)
                SELECT {ph}, {ph}, {ph}, 'purchase', {ph}, p.selling_price, p.category
                  FROM products p WHERE p.product_id = {ph};
            """, (uid, f"conv-{offer_id}", pid, now, pid))

        cur.close()
        conn.commit()
        logger.info(
            "Simulated %d conversions out of %d pending offers.",
            len(to_convert), len(pending),
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# APScheduler integration
# ---------------------------------------------------------------------------

def start_scheduler():
    """
    Start a blocking APScheduler that runs the pipeline daily at the
    configured time.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger="cron",
        hour=PIPELINE_SCHEDULE_HOUR,
        minute=PIPELINE_SCHEDULE_MINUTE,
        id="cartsaver_daily_pipeline",
        replace_existing=True,
    )

    logger.info(
        "Scheduler started -- pipeline will run daily at %02d:%02d.",
        PIPELINE_SCHEDULE_HOUR, PIPELINE_SCHEDULE_MINUTE,
    )
    _log_run(
        f"Scheduler started (daily at {PIPELINE_SCHEDULE_HOUR:02d}:"
        f"{PIPELINE_SCHEDULE_MINUTE:02d})"
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shut down.")
        _log_run("Scheduler shut down")
