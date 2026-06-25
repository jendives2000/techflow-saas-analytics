"""
Create the 'techflow' PostgreSQL database and load both datasets.

Prerequisites:
  - PostgreSQL 14 running on localhost:5432
  - PG_PASSWORD set in .env (or passed via environment)
  - CSVs already in project1_saas_analytics/data/raw/ (run download_data.py first)

What this does:
  1. Creates database 'techflow' if it doesn't exist
  2. Creates tables: customers, ab_test
  3. Loads the CSVs using COPY (fast bulk load)
  4. Prints row counts to verify
"""

import io
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DB = os.getenv("PG_DB", "techflow")

RAW_DIR = Path("data/raw")
TELCO_CSV = RAW_DIR / "telco_churn.csv"
AB_CSV = RAW_DIR / "ab_test.csv"


def connect(database="postgres"):
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER,
        password=PG_PASSWORD, database=database
    )


def create_database():
    """Create the techflow database if it doesn't already exist."""
    conn = connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PG_DB,))
    if cur.fetchone():
        print(f"  Database '{PG_DB}' already exists — skipping creation")
    else:
        cur.execute(f'CREATE DATABASE "{PG_DB}"')
        print(f"  Database '{PG_DB}' created")
    cur.close()
    conn.close()


CREATE_CUSTOMERS = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id       TEXT PRIMARY KEY,
    gender            TEXT,
    senior_citizen    INTEGER,
    partner           TEXT,
    dependents        TEXT,
    subscription_months INTEGER,
    phone_service     TEXT,
    multiple_lines    TEXT,
    internet_service  TEXT,
    online_security   TEXT,
    online_backup     TEXT,
    device_protection TEXT,
    tech_support      TEXT,
    streaming_tv      TEXT,
    streaming_movies  TEXT,
    plan_type         TEXT,
    paperless_billing TEXT,
    payment_method    TEXT,
    monthly_mrr       NUMERIC(8,2),
    lifetime_value    NUMERIC(10,2),
    churned           TEXT
);
"""

CREATE_AB_TEST = """
CREATE TABLE IF NOT EXISTS ab_test (
    user_id      INTEGER,
    ts           TIMESTAMP,
    grp          TEXT,
    landing_page TEXT,
    converted    INTEGER
);
"""


def load_customers(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  customers table already has {count:,} rows — skipping load")
        cur.close()
        return

    print("  Loading customers from CSV ...")
    import csv
    # The IBM dataset has ~11 rows where TotalCharges is a whitespace string
    # (new customers with tenure=0). Clean those to empty string so Postgres
    # treats them as NULL instead of raising InvalidTextRepresentation.
    clean_buf = io.StringIO()
    writer = csv.writer(clean_buf)
    with open(TELCO_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            # lifetime_value is column index 19 (0-based); strip whitespace-only
            if len(row) > 19 and row[19].strip() == "":
                row[19] = ""
            writer.writerow(row)
    clean_buf.seek(0)
    cur.copy_expert(
        """COPY customers (
            customer_id, gender, senior_citizen, partner, dependents,
            subscription_months, phone_service, multiple_lines,
            internet_service, online_security, online_backup,
            device_protection, tech_support, streaming_tv,
            streaming_movies, plan_type, paperless_billing,
            payment_method, monthly_mrr, lifetime_value, churned
        ) FROM STDIN WITH (FORMAT csv, HEADER false, NULL '')""",
        clean_buf
    )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM customers")
    print(f"  customers loaded: {cur.fetchone()[0]:,} rows")
    cur.close()


def load_ab_test(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ab_test")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  ab_test table already has {count:,} rows — skipping load")
        cur.close()
        return

    print("  Loading ab_test from CSV (294k rows — may take a moment) ...")
    with open(AB_CSV, "r", encoding="utf-8") as f:
        next(f)
        cur.copy_expert(
            """COPY ab_test (user_id, ts, grp, landing_page, converted)
               FROM STDIN WITH (FORMAT csv, HEADER false, NULL '')""",
            f
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM ab_test")
    print(f"  ab_test loaded: {cur.fetchone()[0]:,} rows")
    cur.close()


def main():
    print("=== TechFlow Database Setup ===\n")

    if not TELCO_CSV.exists() or not AB_CSV.exists():
        print("ERROR: CSV files not found. Run tools/download_data.py first.")
        sys.exit(1)

    print("1. Creating database ...")
    create_database()

    print("\n2. Connecting to techflow ...")
    conn = connect(PG_DB)

    print("\n3. Creating tables ...")
    cur = conn.cursor()
    cur.execute(CREATE_CUSTOMERS)
    cur.execute(CREATE_AB_TEST)
    conn.commit()
    cur.close()
    print("  Tables ready: customers, ab_test")

    print("\n4. Loading data ...")
    load_customers(conn)
    load_ab_test(conn)

    print("\n5. Quick verification ...")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), AVG(monthly_mrr), SUM(monthly_mrr) FROM customers")
    n, avg_mrr, total_mrr = cur.fetchone()
    cur.execute("SELECT churned, COUNT(*) FROM customers GROUP BY churned ORDER BY churned")
    churn_counts = dict(cur.fetchall())
    cur.execute("SELECT grp, COUNT(*), AVG(converted) FROM ab_test GROUP BY grp ORDER BY grp")
    ab_stats = cur.fetchall()
    cur.close()
    conn.close()

    churn_n = churn_counts.get("Yes", 0)
    active_n = churn_counts.get("No", 0)
    print(f"  customers: {n:,} total | {active_n:,} active | {churn_n:,} churned ({churn_n/n:.1%})")
    print(f"  MRR: avg ${avg_mrr:.2f}/customer | total ${total_mrr:,.0f}")
    print(f"  ab_test groups:")
    for grp, cnt, rate in ab_stats:
        print(f"    {grp}: {cnt:,} users, {rate:.2%} conversion rate")

    print("\n=== Setup complete. Database 'techflow' is ready. ===")


if __name__ == "__main__":
    main()
