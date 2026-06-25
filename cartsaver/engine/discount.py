"""
CartSaver — Profit-Aware Discount Engine
Computes heuristic purchase probability, selects discount tier, and checks
post-discount margin to decide between a discount offer and a nudge.
"""

import logging
from cartsaver.segmentation.segment import (
    TIER_VERY_HIGH, TIER_HIGH, TIER_LOW, TIER_CONVERTED,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic purchase probability by segment
# ---------------------------------------------------------------------------
# These probabilities answer: "How likely is this user to purchase WITHOUT
# any intervention?"
#
# • Very High Intent — they came very close (checkout) but didn't buy.
#   Paradoxically this means price friction is high ⇒ low natural probability.
# • High Intent — strong interest but didn't reach checkout.
# • Low Intent — just browsing, high natural probability they'd return or not.
# ---------------------------------------------------------------------------

_BASE_PROBABILITY = {
    TIER_VERY_HIGH: 0.15,   # 15 % — needs strong push
    TIER_HIGH:      0.35,   # 35 % — moderate push
    TIER_LOW:       0.65,   # 65 % — may come back on own
    TIER_CONVERTED: 1.00,   # already bought
}


def _purchase_probability(row: dict) -> float:
    """Compute a heuristic purchase probability for a user-product row."""
    tier = row.get("intent_tier", TIER_LOW)
    base = _BASE_PROBABILITY.get(tier, 0.65)

    # Slight adjustments based on raw behaviour depth
    views = int(row.get("view_count", 0))
    carts = int(row.get("cart_count", 0))

    # More views without conversion → slightly lower probability
    if views > 12:
        base = max(0.05, base - 0.05)

    # Multiple cart adds suggest hesitation
    if carts >= 2:
        base = max(0.05, base - 0.05)

    return round(base, 4)


# ---------------------------------------------------------------------------
# Discount tiers (from the spec)
# ---------------------------------------------------------------------------
# probability > 80%  → 0 % discount
# 50–80 %            → 5 %
# 20–50 %            → 10 %
# < 20 %             → 15 %
# ---------------------------------------------------------------------------

def _discount_tier(probability: float) -> float:
    """Map probability to a discount percentage."""
    if probability > 0.80:
        return 0.0
    if probability >= 0.50:
        return 5.0
    if probability >= 0.20:
        return 10.0
    return 15.0


# ---------------------------------------------------------------------------
# Margin helpers
# ---------------------------------------------------------------------------

def compute_margin(selling_price: float, cost_price: float) -> float:
    """Return margin percentage: ((sell - cost) / sell) * 100."""
    if selling_price <= 0:
        return 0.0
    return ((selling_price - cost_price) / selling_price) * 100.0


def post_discount_margin(selling_price: float, cost_price: float,
                         discount_pct: float) -> float:
    """Margin after applying the given discount to the selling price."""
    discounted = selling_price * (1.0 - discount_pct / 100.0)
    if discounted <= 0:
        return 0.0
    return ((discounted - cost_price) / discounted) * 100.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_offer(row: dict) -> dict:
    """
    For a single segmented user-product row, decide the discount and
    message type.

    Returns a dict with added keys:
        purchase_probability, raw_discount_pct, final_discount_pct,
        message_type ('discount' | 'nudge' | 'skip'),
        original_margin, post_discount_margin
    """
    tier = row.get("intent_tier", TIER_LOW)

    # Skip already-converted users
    if tier == TIER_CONVERTED:
        row.update({
            "purchase_probability": 1.0,
            "raw_discount_pct": 0.0,
            "final_discount_pct": 0.0,
            "message_type": "skip",
            "original_margin": None,
            "post_discount_margin": None,
        })
        return row

    sell = float(row.get("selling_price", 0))
    cost = float(row.get("cost_price", 0))

    prob = _purchase_probability(row)
    raw_disc = _discount_tier(prob)
    margin = compute_margin(sell, cost)

    if raw_disc > 0:
        pdm = post_discount_margin(sell, cost, raw_disc)
        if pdm >= 20.0:
            # Discount is viable
            final_disc = raw_disc
            msg_type = "discount"
        else:
            # Margin too thin — fall back to nudge
            final_disc = 0.0
            msg_type = "nudge"
            pdm = margin  # no discount applied
    else:
        # No discount needed (high natural probability)
        final_disc = 0.0
        msg_type = "nudge"
        pdm = margin

    row.update({
        "purchase_probability": prob,
        "raw_discount_pct": raw_disc,
        "final_discount_pct": final_disc,
        "message_type": msg_type,
        "original_margin": round(margin, 2),
        "post_discount_margin": round(pdm, 2),
    })

    logger.debug(
        "User %s | product %s | prob=%.2f | disc=%s%% | type=%s | margin=%.1f→%.1f",
        row.get("user_id", "?")[:8], row.get("product_name", "?"),
        prob, final_disc, msg_type, margin, pdm,
    )
    return row


def compute_offers(segmented_users: list[dict]) -> list[dict]:
    """
    Process all segmented user rows through the discount engine.
    Filters out 'skip' (already converted) entries.
    """
    results = []
    for row in segmented_users:
        enriched = compute_offer(row)
        if enriched["message_type"] != "skip":
            results.append(enriched)
    logger.info(
        "Discount engine produced %d actionable offers (from %d segments).",
        len(results), len(segmented_users),
    )
    return results
