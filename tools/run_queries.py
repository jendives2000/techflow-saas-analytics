"""
Run all SQL queries from sql/queries.sql against the local techflow database.

Outputs:
  - Prints each result set to the terminal (first 20 rows)
  - Saves each result as a CSV to data/processed/

Prerequisites:
  - techflow database set up (run tools/setup_db.py first)
  - PG_PASSWORD in .env
"""

import io
import os
import sys
import csv
from pathlib import Path

import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = int(os.getenv("PG_PORT", 5432))
PG_USER     = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DB       = os.getenv("PG_DB", "techflow")

SQL_FILE    = Path("sql/queries.sql")
PROCESSED   = Path("data/processed")


def connect():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER,
        password=PG_PASSWORD, database=PG_DB,
        cursor_factory=DictCursor
    )


def split_queries(sql_text: str) -> list[tuple[str, str]]:
    """
    Parse the SQL file into (label, query) pairs.
    Labels are extracted from the '-- Q...' comment lines.
    """
    blocks = []
    current_label = "unlabeled"
    current_lines = []

    for line in sql_text.splitlines():
        stripped = line.strip()

        # A label line looks like: -- Q1 — SELECT + ...
        if stripped.startswith("-- Q") or stripped.startswith("-- BONUS"):
            if current_lines:
                sql = "\n".join(current_lines).strip()
                if sql and sql not in ("", "--"):
                    blocks.append((current_label, sql))
            current_label = stripped.lstrip("- ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Last block
    if current_lines:
        sql = "\n".join(current_lines).strip()
        if sql:
            blocks.append((current_label, sql))

    # Filter out empty, comment-only, or unlabeled header blocks
    return [
        (label, sql) for label, sql in blocks
        if label != "unlabeled"
        and sql.replace("-", "").replace("\n", "").replace(" ", "")
    ]


def run_query(cur, label: str, sql: str, save_as: str):
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            print("  (no rows returned)")
            return

        cols = [d[0] for d in cur.description]
        col_widths = [max(len(c), max((len(str(r[c])) for r in rows), default=0)) for c in cols]

        # Header
        header = "  " + "  ".join(c.ljust(col_widths[i]) for i, c in enumerate(cols))
        print(header)
        print("  " + "-" * (len(header) - 2))

        # Rows (cap at 20 for terminal display)
        for row in rows[:20]:
            print("  " + "  ".join(str(row[c]).ljust(col_widths[i]) for i, c in enumerate(cols)))

        if len(rows) > 20:
            print(f"  ... ({len(rows)} rows total — see {save_as})")

        # Save full result to CSV
        out_path = PROCESSED / save_as
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for row in rows:
                writer.writerow([row[c] for c in cols])
        print(f"  Saved → {out_path}")

    except Exception as e:
        print(f"  ERROR: {e}")


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    sql_text = SQL_FILE.read_text(encoding="utf-8")
    blocks = split_queries(sql_text)

    conn = connect()
    cur = conn.cursor()

    filenames = [
        "q1_customers_by_plan.csv",
        "q2_mrr_by_plan.csv",
        "q3_newest_customers.csv",
        "q4_lifecycle_stage.csv",
        "q5_churn_by_lifecycle.csv",
        "q6_ltv_by_lifecycle.csv",
        "q7_high_value_churned.csv",
        "q8_top_churned_by_plan.csv",
        "qbonus_ab_test_summary.csv",
    ]

    print("=== TechFlow SQL Query Runner ===")
    print(f"Executing {len(blocks)} queries from {SQL_FILE}\n")

    for i, (label, sql) in enumerate(blocks):
        fname = filenames[i] if i < len(filenames) else f"query_{i+1}.csv"
        run_query(cur, label, sql, fname)

    cur.close()
    conn.close()

    print(f"\n{'='*65}")
    print(f"All queries done. CSVs in {PROCESSED}/")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
