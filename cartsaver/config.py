"""
CartSaver -- Configuration Module
Reads settings from environment variables / .env file.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Attempt to load a .env file if python-dotenv is available
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed -- rely on system env vars

# ---------------------------------------------------------------------------
# Database backend: "sqlite" (default) or "postgresql"
# ---------------------------------------------------------------------------
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")

# SQLite (zero-config default)
SQLITE_PATH = os.getenv(
    "SQLITE_PATH",
    str(Path(__file__).resolve().parent.parent / "cartsaver.db"),
)

# PostgreSQL (used when DB_BACKEND=postgresql)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "cartsaver")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# ---------------------------------------------------------------------------
# NVIDIA NIM API  (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

# ---------------------------------------------------------------------------
# SendGrid (Email)
# ---------------------------------------------------------------------------
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "cartsaver@example.com")

# ---------------------------------------------------------------------------
# Twilio (SMS + WhatsApp)
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM", "+15005550006")  # test number
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # sandbox

# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------
PIPELINE_SCHEDULE_HOUR = int(os.getenv("PIPELINE_SCHEDULE_HOUR", "9"))
PIPELINE_SCHEDULE_MINUTE = int(os.getenv("PIPELINE_SCHEDULE_MINUTE", "0"))

# ---------------------------------------------------------------------------
# Export directory (CSV files for Power BI)
# ---------------------------------------------------------------------------
EXPORT_DIR = os.getenv("EXPORT_DIR", str(Path(__file__).resolve().parent.parent / "exports_output"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = os.getenv("LOG_DIR", str(Path(__file__).resolve().parent.parent / "logs"))

# ---------------------------------------------------------------------------
# Channel costs (for ROAS calculation)
# ---------------------------------------------------------------------------
COST_EMAIL = float(os.getenv("COST_EMAIL", "0.001"))
COST_SMS = float(os.getenv("COST_SMS", "0.01"))
COST_WHATSAPP = float(os.getenv("COST_WHATSAPP", "0.02"))
