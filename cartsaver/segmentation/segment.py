"""
CartSaver — Rule-Based Customer Segmentation
Classifies users into intent tiers based on their event behaviour.
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent tier definitions
# ---------------------------------------------------------------------------
#
#   Very High Intent → viewed 10+ times + added cart + started checkout + no purchase
#   High Intent      → viewed 5+  times + added to cart + no purchase
#   Low Intent       → viewed only + no cart
#
# Users who already purchased are labelled "Converted" and skipped.
# ---------------------------------------------------------------------------

TIER_VERY_HIGH = "Very High Intent"
TIER_HIGH = "High Intent"
TIER_LOW = "Low Intent"
TIER_CONVERTED = "Converted"


def classify(row: dict) -> str:
    """
    Classify a single user-product summary row into an intent tier.

    Parameters
    ----------
    row : dict
        Must contain keys: view_count, cart_count, checkout_count, purchase_count

    Returns
    -------
    str  — one of the tier constants.
    """
    views = int(row.get("view_count", 0))
    carts = int(row.get("cart_count", 0))
    checkouts = int(row.get("checkout_count", 0))
    purchases = int(row.get("purchase_count", 0))

    if purchases > 0:
        return TIER_CONVERTED

    if views >= 10 and carts > 0 and checkouts > 0:
        return TIER_VERY_HIGH

    if views >= 5 and carts > 0:
        return TIER_HIGH

    if carts == 0:
        return TIER_LOW

    # Edge case: added to cart with < 5 views and no checkout
    # Treat as moderate / High Intent (still abandoned cart)
    return TIER_HIGH


def segment_users(user_summaries: list[dict]) -> list[dict]:
    """
    Take the output of ``funnel.get_user_event_summary()`` and add an
    ``intent_tier`` key to each row.

    Returns only non-converted users (i.e. those eligible for re-engagement).
    """
    segmented = []
    tier_counts = {TIER_VERY_HIGH: 0, TIER_HIGH: 0, TIER_LOW: 0, TIER_CONVERTED: 0}

    for row in user_summaries:
        tier = classify(row)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        row["intent_tier"] = tier
        segmented.append(row)

    logger.info("Segmentation results: %s", tier_counts)

    # Return all rows (including Converted) — pipeline will filter as needed
    return segmented
