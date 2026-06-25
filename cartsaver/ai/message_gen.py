"""
CartSaver — AI Message Generation via NVIDIA NIM API
Uses OpenAI-compatible client pointed at NVIDIA NIM endpoint.
Falls back to template-based messages when API is unavailable.
"""

import logging

from cartsaver.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NVIDIA NIM / OpenAI client initialisation
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Lazy-initialise the OpenAI client pointing at NVIDIA NIM."""
    global _client
    if _client is not None:
        return _client

    if not NVIDIA_API_KEY:
        logger.warning("NVIDIA_API_KEY not set — will use template fallback.")
        return None

    try:
        from openai import OpenAI
        _client = OpenAI(
            api_key=NVIDIA_API_KEY,
            base_url=NVIDIA_BASE_URL,
        )
        logger.info("NVIDIA NIM client initialised (model=%s).", NVIDIA_MODEL)
        return _client
    except Exception as exc:
        logger.warning("Failed to create NVIDIA NIM client: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

DISCOUNT_SYSTEM = (
    "You are a friendly and persuasive e-commerce marketing copywriter. "
    "Write a SHORT retention message (3-4 sentences max) that includes: "
    "the customer's first name, the product name, the exact discount percentage, "
    "a sense of urgency, and a clear call-to-action. Do NOT use markdown."
)

NUDGE_SYSTEM = (
    "You are a friendly and persuasive e-commerce marketing copywriter. "
    "Write a SHORT persuasive message (3-4 sentences max) that includes: "
    "the customer's first name, the product name, highlights of the product's "
    "benefits, and a gentle call-to-action. Do NOT mention any discount. "
    "Do NOT use markdown."
)


def _build_user_prompt(row: dict) -> str:
    """Build the user-turn prompt from the offer row."""
    msg_type = row.get("message_type", "nudge")
    name = row.get("name", "Customer")
    product = row.get("product_name", "our product")
    discount = row.get("final_discount_pct", 0)
    category = row.get("category", "")

    if msg_type == "discount":
        return (
            f"Customer name: {name}\n"
            f"Product: {product} (Category: {category})\n"
            f"Discount: {discount}% off\n"
            f"Write a discount offer message."
        )
    else:
        return (
            f"Customer name: {name}\n"
            f"Product: {product} (Category: {category})\n"
            f"Write a nudge message highlighting the product benefits."
        )


# ---------------------------------------------------------------------------
# Fallback template messages (when API is unavailable)
# ---------------------------------------------------------------------------

def _fallback_discount_message(row: dict) -> str:
    name = row.get("name", "Customer")
    product = row.get("product_name", "our product")
    discount = row.get("final_discount_pct", 0)
    return (
        f"Hi {name}! 🎉 Great news — we're offering you an exclusive "
        f"{discount}% discount on {product}! This offer won't last long, "
        f"so grab it before it's gone. Shop now and save!"
    )


def _fallback_nudge_message(row: dict) -> str:
    name = row.get("name", "Customer")
    product = row.get("product_name", "our product")
    return (
        f"Hi {name}! 👋 We noticed you were checking out {product}. "
        f"It's one of our most popular picks — loved for its quality and value. "
        f"Don't miss out, come back and complete your order today!"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_message(row: dict) -> str:
    """
    Generate a personalised message for a single offer row.

    Uses NVIDIA NIM API when available; otherwise falls back to templates.
    """
    msg_type = row.get("message_type", "nudge")
    client = _get_client()

    if client is not None:
        system_prompt = DISCOUNT_SYSTEM if msg_type == "discount" else NUDGE_SYSTEM
        user_prompt = _build_user_prompt(row)
        try:
            response = client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=256,
            )
            text = response.choices[0].message.content.strip()
            logger.info("NIM generated message for user %s (%s).",
                        row.get("user_id", "?")[:8], msg_type)
            return text
        except Exception as exc:
            logger.warning("NIM API call failed: %s — using fallback.", exc)

    # Fallback
    if msg_type == "discount":
        return _fallback_discount_message(row)
    return _fallback_nudge_message(row)


def generate_messages(offers: list[dict]) -> list[dict]:
    """
    Generate messages for all offer rows.  Adds ``generated_message`` key.
    """
    for row in offers:
        row["generated_message"] = generate_message(row)
    logger.info("Generated messages for %d offers.", len(offers))
    return offers
