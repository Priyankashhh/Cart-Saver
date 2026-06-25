"""
CartSaver -- Database Setup
Creates tables and seeds dummy data for testing.
Supports SQLite (default, zero-config) and PostgreSQL.
"""

import random
import uuid
import sqlite3
import logging
from datetime import datetime, timedelta

from cartsaver.config import (
    DB_BACKEND, SQLITE_PATH,
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection():
    """Return a DB-API 2.0 connection (SQLite or PostgreSQL)."""
    if DB_BACKEND == "postgresql":
        import psycopg2
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        # Make rows accessible by column name
        conn.row_factory = sqlite3.Row
        return conn


# ---------------------------------------------------------------------------
# DDL -- Table creation (SQLite-compatible syntax)
# ---------------------------------------------------------------------------

SQL_CREATE_TABLES_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    user_id   TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    email     TEXT NOT NULL,
    phone     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    cost_price    REAL NOT NULL,
    selling_price REAL NOT NULL,
    category      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_events (
    event_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          TEXT NOT NULL REFERENCES users(user_id),
    session_id       TEXT NOT NULL,
    product_id       TEXT NOT NULL REFERENCES products(product_id),
    event_type       TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    product_price    REAL NOT NULL,
    product_category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_offers (
    offer_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              TEXT NOT NULL REFERENCES users(user_id),
    product_id           TEXT NOT NULL REFERENCES products(product_id),
    discount_applied     REAL NOT NULL DEFAULT 0,
    message_type         TEXT NOT NULL,
    channel              TEXT NOT NULL,
    message_text         TEXT,
    sent_at              TEXT NOT NULL,
    converted            INTEGER NOT NULL DEFAULT 0,
    conversion_timestamp TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_type ON user_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_user ON user_events(user_id);
"""

SQL_CREATE_TABLES_PG = """
CREATE TABLE IF NOT EXISTS users (
    user_id   VARCHAR(36) PRIMARY KEY,
    name      VARCHAR(120) NOT NULL,
    email     VARCHAR(200) NOT NULL,
    phone     VARCHAR(30)  NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(36) PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    cost_price    NUMERIC(10,2) NOT NULL,
    selling_price NUMERIC(10,2) NOT NULL,
    category      VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS user_events (
    event_id         SERIAL PRIMARY KEY,
    user_id          VARCHAR(36)  NOT NULL REFERENCES users(user_id),
    session_id       VARCHAR(36)  NOT NULL,
    product_id       VARCHAR(36)  NOT NULL REFERENCES products(product_id),
    event_type       VARCHAR(30)  NOT NULL,
    timestamp        TIMESTAMP    NOT NULL DEFAULT NOW(),
    product_price    NUMERIC(10,2) NOT NULL,
    product_category VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_offers (
    offer_id             SERIAL PRIMARY KEY,
    user_id              VARCHAR(36) NOT NULL REFERENCES users(user_id),
    product_id           VARCHAR(36) NOT NULL REFERENCES products(product_id),
    discount_applied     NUMERIC(5,2) NOT NULL DEFAULT 0,
    message_type         VARCHAR(20)  NOT NULL,
    channel              VARCHAR(20)  NOT NULL,
    message_text         TEXT,
    sent_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    converted            BOOLEAN NOT NULL DEFAULT FALSE,
    conversion_timestamp TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_type ON user_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_user ON user_events(user_id);
"""


def create_tables(conn):
    """Execute DDL to create all tables (idempotent)."""
    if DB_BACKEND == "postgresql":
        cur = conn.cursor()
        cur.execute(SQL_CREATE_TABLES_PG)
        cur.close()
        conn.commit()
    else:
        # SQLite: executescript handles multiple statements
        conn.executescript(SQL_CREATE_TABLES_SQLITE)
        conn.commit()
    logger.info("Tables created successfully (%s).", DB_BACKEND)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Ananya", "Vikram",
    "Neha", "Arjun", "Meera", "Karan", "Sneha",
    "Ishaan", "Kavya", "Rahul", "Divya", "Aditya",
]

PRODUCTS = [
    # (name, cost_price, selling_price, category)
    ("Wireless Earbuds Pro",        450,   999,  "Electronics"),
    ("Running Shoes X200",          800,  1999,  "Footwear"),
    ("Organic Green Tea (100 bags)", 120,   349,  "Grocery"),
    ("Cotton Casual Shirt",         300,   799,  "Clothing"),
    ("Stainless Steel Water Bottle", 150,   499,  "Kitchen"),
    ("Bluetooth Speaker Mini",      600,  1499,  "Electronics"),
    ("Yoga Mat Premium",            200,   699,  "Fitness"),
    ("Leather Wallet Classic",      250,   899,  "Accessories"),
    ("LED Desk Lamp",               350,   999,  "Home"),
    ("Bamboo Sunglasses",           180,   599,  "Accessories"),
]

EVENT_TYPES = ["product_view", "add_to_cart", "remove_from_cart",
               "checkout_started", "purchase"]


def _generate_users(n: int = 15):
    """Generate n user records."""
    users = []
    for i in range(n):
        uid = str(uuid.uuid4())
        name = FIRST_NAMES[i % len(FIRST_NAMES)]
        email = f"{name.lower()}{i}@example.com"
        phone = f"+9199{random.randint(10000000, 99999999)}"
        users.append((uid, name, email, phone))
    return users


def _generate_products():
    """Generate product records from the static list."""
    products = []
    for name, cost, sell, cat in PRODUCTS:
        pid = str(uuid.uuid4())
        products.append((pid, name, cost, sell, cat))
    return products


def _generate_events(users, products, n_events: int = 70):
    """
    Generate realistic event sequences for users.

    Strategy -- to ensure realistic funnel distributions:
      - ~30% of user-product pairs become full purchasers
      - ~15% become checkout abandoners  (Very High Intent)
      - ~25% become cart abandoners  (High Intent)
      - ~30% are view-only  (Low Intent)
    """
    events = []
    base_time = datetime.now() - timedelta(days=7)

    for user in users:
        uid = user[0]
        # Pick 1-3 products this user interacts with
        user_products = random.sample(products, k=random.randint(1, 3))

        for prod in user_products:
            pid, pname, _, sell_price, cat = prod
            session = str(uuid.uuid4())
            t = base_time + timedelta(
                hours=random.randint(0, 168),
                minutes=random.randint(0, 59),
            )

            # Determine journey depth for this user-product pair
            roll = random.random()
            if roll < 0.30:
                # Full purchaser
                journey = ["product_view"] * random.randint(2, 6) + [
                    "add_to_cart", "checkout_started", "purchase"
                ]
            elif roll < 0.45:
                # Checkout abandoner  (Very High Intent)
                journey = ["product_view"] * random.randint(10, 15) + [
                    "add_to_cart", "checkout_started"
                ]
            elif roll < 0.70:
                # Cart abandoner  (High Intent)
                journey = ["product_view"] * random.randint(5, 9) + [
                    "add_to_cart"
                ]
            else:
                # Viewer only  (Low Intent)
                journey = ["product_view"] * random.randint(1, 4)

            for evt in journey:
                t += timedelta(seconds=random.randint(10, 300))
                ts = t.isoformat()
                events.append((uid, session, pid, evt, ts, sell_price, cat))

    # Ensure we have at least n_events
    while len(events) < n_events:
        user = random.choice(users)
        prod = random.choice(products)
        t = base_time + timedelta(hours=random.randint(0, 168))
        events.append((
            user[0], str(uuid.uuid4()), prod[0],
            "product_view", t.isoformat(), prod[3], prod[4],
        ))

    return events


def seed_data(conn):
    """Insert dummy users, products, and events."""
    users = _generate_users()
    products = _generate_products()
    events = _generate_events(users, products)

    cur = conn.cursor()

    # Clear old data (order matters for foreign keys)
    cur.execute("DELETE FROM sent_offers;")
    cur.execute("DELETE FROM user_events;")
    cur.execute("DELETE FROM products;")
    cur.execute("DELETE FROM users;")

    if DB_BACKEND == "postgresql":
        from psycopg2.extras import execute_values
        execute_values(
            cur,
            "INSERT INTO users (user_id, name, email, phone) VALUES %s",
            users,
        )
        execute_values(
            cur,
            "INSERT INTO products (product_id, name, cost_price, selling_price, category) VALUES %s",
            products,
        )
        execute_values(
            cur,
            """INSERT INTO user_events
               (user_id, session_id, product_id, event_type, timestamp, product_price, product_category)
               VALUES %s""",
            events,
        )
    else:
        cur.executemany(
            "INSERT INTO users (user_id, name, email, phone) VALUES (?,?,?,?)",
            users,
        )
        cur.executemany(
            "INSERT INTO products (product_id, name, cost_price, selling_price, category) VALUES (?,?,?,?,?)",
            products,
        )
        cur.executemany(
            """INSERT INTO user_events
               (user_id, session_id, product_id, event_type, timestamp, product_price, product_category)
               VALUES (?,?,?,?,?,?,?)""",
            events,
        )

    cur.close()
    conn.commit()
    logger.info(
        "Seeded %d users, %d products, %d events.",
        len(users), len(products), len(events),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_setup():
    """Create tables and seed dummy data end-to-end."""
    conn = get_connection()
    try:
        create_tables(conn)
        seed_data(conn)
    finally:
        conn.close()
    logger.info("Database setup complete.")
