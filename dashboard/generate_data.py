"""
CartSaver -- Dashboard Data Generator
Reads from SQLite database and generates data.json for the web dashboard.
Optionally generates AI executive briefing via NVIDIA NIM API.
"""

import json
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cartsaver.config import (
    SQLITE_PATH, NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL,
    COST_EMAIL, COST_SMS, COST_WHATSAPP,
)
from cartsaver.db.setup import get_connection

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent


def fetch_dashboard_data():
    """Pull all KPIs, funnel, segments, and offer data from the database."""
    conn = get_connection()
    cur = conn.cursor()

    # --- Funnel stage counts ---
    cur.execute("""
        SELECT 'product_view' AS stage, COUNT(DISTINCT user_id) FROM user_events WHERE event_type='product_view'
        UNION ALL SELECT 'add_to_cart', COUNT(DISTINCT user_id) FROM user_events WHERE event_type='add_to_cart'
        UNION ALL SELECT 'checkout_started', COUNT(DISTINCT user_id) FROM user_events WHERE event_type='checkout_started'
        UNION ALL SELECT 'purchase', COUNT(DISTINCT user_id) FROM user_events WHERE event_type='purchase';
    """)
    funnel_rows = cur.fetchall()
    funnel = [{"stage": r[0], "users": r[1]} for r in funnel_rows]
    funnel_map = {r[0]: r[1] for r in funnel_rows}

    # --- Drop-offs ---
    stages_ordered = ["product_view", "add_to_cart", "checkout_started", "purchase"]
    dropoffs = []
    for i in range(len(stages_ordered) - 1):
        src = funnel_map.get(stages_ordered[i], 0)
        dst = funnel_map.get(stages_ordered[i + 1], 0)
        pct = round((1 - dst / src) * 100, 2) if src > 0 else 0
        dropoffs.append({
            "from": stages_ordered[i],
            "to": stages_ordered[i + 1],
            "from_users": src,
            "to_users": dst,
            "dropoff_pct": pct,
        })

    # --- Core KPIs ---
    cur.execute("SELECT COALESCE(SUM(product_price), 0) FROM user_events WHERE event_type='purchase';")
    revenue = float(cur.fetchone()[0])

    cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_events;")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type='purchase';")
    purchasers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type='add_to_cart';")
    carters = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM user_events
        WHERE event_type='add_to_cart'
          AND user_id NOT IN (SELECT DISTINCT user_id FROM user_events WHERE event_type='purchase');
    """)
    abandoners = cur.fetchone()[0]

    cvr = round((purchasers / total_users * 100), 2) if total_users > 0 else 0
    abandonment_rate = round((abandoners / carters * 100), 2) if carters > 0 else 0
    retention_rate = round(100 - abandonment_rate, 2)

    # --- Notification stats ---
    cur.execute("""
        SELECT
            SUM(CASE WHEN channel='email' THEN 1 ELSE 0 END),
            SUM(CASE WHEN channel='sms' THEN 1 ELSE 0 END),
            SUM(CASE WHEN channel='whatsapp' THEN 1 ELSE 0 END),
            COUNT(*),
            SUM(CASE WHEN converted=1 THEN 1 ELSE 0 END)
        FROM sent_offers;
    """)
    row = cur.fetchone()
    emails_sent = row[0] or 0
    sms_sent = row[1] or 0
    wa_sent = row[2] or 0
    total_offers = row[3] or 0
    total_conversions = row[4] or 0

    notif_cost = emails_sent * COST_EMAIL + sms_sent * COST_SMS + wa_sent * COST_WHATSAPP
    roas = round(revenue / notif_cost, 2) if notif_cost > 0 else 0

    # --- Offer performance by discount tier ---
    cur.execute("""
        SELECT
            CASE
                WHEN discount_applied = 0  THEN 'No Discount (Nudge)'
                WHEN discount_applied = 5  THEN '5% Discount'
                WHEN discount_applied = 10 THEN '10% Discount'
                WHEN discount_applied = 15 THEN '15% Discount'
                ELSE 'Other'
            END AS tier,
            COUNT(*) AS sent,
            SUM(CASE WHEN converted=1 THEN 1 ELSE 0 END) AS conversions
        FROM sent_offers GROUP BY tier ORDER BY tier;
    """)
    offer_perf = []
    for r in cur.fetchall():
        conv = r[2] or 0
        offer_perf.append({
            "tier": r[0],
            "sent": r[1],
            "conversions": conv,
            "conversion_rate": round(conv / r[1] * 100, 2) if r[1] > 0 else 0,
        })

    # --- Segment distribution ---
    cur.execute("""
        SELECT
            ue.user_id,
            SUM(CASE WHEN ue.event_type='product_view' THEN 1 ELSE 0 END) AS views,
            SUM(CASE WHEN ue.event_type='add_to_cart' THEN 1 ELSE 0 END) AS carts,
            SUM(CASE WHEN ue.event_type='checkout_started' THEN 1 ELSE 0 END) AS checkouts,
            SUM(CASE WHEN ue.event_type='purchase' THEN 1 ELSE 0 END) AS purchases
        FROM user_events ue GROUP BY ue.user_id;
    """)
    segment_counts = {"Very High Intent": 0, "High Intent": 0, "Low Intent": 0, "Converted": 0}
    for r in cur.fetchall():
        views, carts, checkouts, purchases = r[1], r[2], r[3], r[4]
        if purchases > 0:
            segment_counts["Converted"] += 1
        elif views >= 10 and carts > 0 and checkouts > 0:
            segment_counts["Very High Intent"] += 1
        elif views >= 5 and carts > 0:
            segment_counts["High Intent"] += 1
        else:
            segment_counts["Low Intent"] += 1

    # --- Revenue by category ---
    cur.execute("""
        SELECT product_category, ROUND(SUM(product_price), 2)
        FROM user_events WHERE event_type='purchase'
        GROUP BY product_category ORDER BY SUM(product_price) DESC;
    """)
    rev_by_category = [{"category": r[0], "revenue": float(r[1])} for r in cur.fetchall()]

    # --- Top abandoned products ---
    cur.execute("""
        SELECT p.name, COUNT(DISTINCT ue.user_id) as abandon_count
        FROM user_events ue
        JOIN products p ON p.product_id = ue.product_id
        WHERE ue.event_type = 'add_to_cart'
          AND ue.user_id NOT IN (
              SELECT DISTINCT ue2.user_id FROM user_events ue2
              WHERE ue2.event_type = 'purchase' AND ue2.product_id = ue.product_id
          )
        GROUP BY p.name ORDER BY abandon_count DESC LIMIT 5;
    """)
    top_abandoned = [{"product": r[0], "count": r[1]} for r in cur.fetchall()]

    # --- Revenue target (set to 50000 as aspirational) ---
    revenue_target = 50000
    revenue_achievement = round(revenue / revenue_target * 100, 2)
    revenue_gap = round(revenue - revenue_target, 2)

    # Estimate revenue at risk (abandoners * avg product price)
    cur.execute("""
        SELECT COALESCE(AVG(product_price), 0) FROM user_events WHERE event_type='add_to_cart';
    """)
    avg_cart_price = float(cur.fetchone()[0])
    revenue_at_risk = round(abandoners * avg_cart_price, 2)

    # Recovery opportunity (what we could get at 30-50% conversion)
    recovery_low = round(revenue_at_risk * 0.30, 2)
    recovery_high = round(revenue_at_risk * 0.50, 2)

    cur.close()
    conn.close()

    data = {
        "generated_at": datetime.now().isoformat(),
        "kpis": {
            "revenue": revenue,
            "revenue_target": revenue_target,
            "revenue_achievement": revenue_achievement,
            "revenue_gap": revenue_gap,
            "revenue_at_risk": revenue_at_risk,
            "recovery_low": recovery_low,
            "recovery_high": recovery_high,
            "cvr": cvr,
            "retention_rate": retention_rate,
            "abandonment_rate": abandonment_rate,
            "roas": roas,
            "total_users": total_users,
            "purchasers": purchasers,
            "abandoners": abandoners,
            "total_conversions": total_conversions,
            "total_offers_sent": total_offers,
            "notification_cost": round(notif_cost, 4),
            "emails_sent": emails_sent,
            "sms_sent": sms_sent,
            "whatsapp_sent": wa_sent,
        },
        "funnel": funnel,
        "dropoffs": dropoffs,
        "offer_performance": offer_perf,
        "segments": segment_counts,
        "revenue_by_category": rev_by_category,
        "top_abandoned_products": top_abandoned,
    }
    return data


def generate_ai_briefing(data: dict) -> list[dict]:
    """Use NVIDIA NIM API to generate executive briefing insights."""
    if not NVIDIA_API_KEY:
        logger.warning("No NVIDIA API key -- using fallback briefing.")
        return _fallback_briefing(data)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)

        kpis = data["kpis"]
        funnel = data["funnel"]
        dropoffs = data["dropoffs"]

        prompt = f"""You are a senior e-commerce analytics consultant. Based on the following CartSaver platform data, generate exactly 4 executive briefing insights as a JSON array.

DATA:
- Revenue: ${kpis['revenue']:,.0f} (Target: ${kpis['revenue_target']:,.0f}, Achievement: {kpis['revenue_achievement']}%)
- Conversion Rate: {kpis['cvr']}%
- Abandonment Rate: {kpis['abandonment_rate']}%
- Revenue at Risk: ${kpis['revenue_at_risk']:,.0f}
- Total Users: {kpis['total_users']}, Purchasers: {kpis['purchasers']}, Abandoners: {kpis['abandoners']}
- ROAS: {kpis['roas']}
- Funnel: {json.dumps(funnel)}
- Drop-offs: {json.dumps(dropoffs)}
- Offers Sent: {kpis['total_offers_sent']}, Conversions from offers: {kpis['total_conversions']}
- Top abandoned products: {json.dumps(data['top_abandoned_products'])}
- Segments: {json.dumps(data['segments'])}

For each insight, return a JSON object with these keys:
- "icon": one of "$", "funnel", "target", "chart" (pick the most relevant)
- "title": short title (e.g. "Revenue Performance")
- "description": 2-3 sentence analysis
- "impact": "HIGH IMPACT" or "MEDIUM IMPACT"
- "confidence": a percentage string like "85%"
- "priority": integer 1-4
- "action": one specific recommended action

Return ONLY a valid JSON array with exactly 4 objects. No markdown, no explanation."""

        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": "You are a data analytics expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1024,
        )
        text = response.choices[0].message.content.strip()
        # Parse the JSON response
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        insights = json.loads(text)
        logger.info("AI executive briefing generated (%d insights).", len(insights))
        return insights
    except Exception as exc:
        logger.warning("AI briefing generation failed: %s -- using fallback.", exc)
        return _fallback_briefing(data)


def _fallback_briefing(data: dict) -> list[dict]:
    """Template-based executive briefing when API is unavailable."""
    k = data["kpis"]
    return [
        {
            "icon": "$",
            "title": "Revenue Performance",
            "description": f"Revenue of ${k['revenue']:,.0f} is ${abs(k['revenue_gap']):,.0f} {'above' if k['revenue_gap'] >= 0 else 'below'} the ${k['revenue_target']:,.0f} target ({k['revenue_achievement']}% achievement).",
            "impact": "HIGH IMPACT",
            "confidence": "90%",
            "priority": 1,
            "action": "Increase conversion and retention initiatives to close the revenue gap.",
        },
        {
            "icon": "funnel",
            "title": "Funnel Bottleneck Analysis",
            "description": f"Cart abandonment rate is {k['abandonment_rate']}%. {k['abandoners']} users added items to cart but did not purchase, representing ${k['revenue_at_risk']:,.0f} in at-risk revenue.",
            "impact": "HIGH IMPACT",
            "confidence": "85%",
            "priority": 2,
            "action": "Optimize checkout flow and deploy targeted discount offers for cart abandoners.",
        },
        {
            "icon": "target",
            "title": "Offer Conversion Effectiveness",
            "description": f"{k['total_offers_sent']} offers sent across 3 channels resulted in {k['total_conversions']} conversions. ROAS stands at {k['roas']:,.0f}x, indicating strong notification ROI.",
            "impact": "MEDIUM IMPACT",
            "confidence": "80%",
            "priority": 3,
            "action": "Scale up high-performing discount tiers and optimize message personalization.",
        },
        {
            "icon": "chart",
            "title": "Recovery Opportunity",
            "description": f"Estimated recovery potential of ${k['recovery_low']:,.0f} to ${k['recovery_high']:,.0f} from at-risk revenue through targeted retention campaigns.",
            "impact": "MEDIUM IMPACT",
            "confidence": "75%",
            "priority": 4,
            "action": "Focus Very High Intent segment with personalized checkout reminders.",
        },
    ]


def main():
    logger.info("Generating dashboard data...")
    data = fetch_dashboard_data()

    logger.info("Generating AI executive briefing...")
    data["executive_briefing"] = generate_ai_briefing(data)

    out = DASHBOARD_DIR / "data.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Dashboard data written to %s", out)


if __name__ == "__main__":
    main()
