"""
Download real datasets for project1_saas_analytics.

Datasets:
  1. IBM Telco Customer Churn (7,043 rows) — used for KPI / retention analysis
  2. Udacity A/B Test data (294,478 rows)  — used for A/B test analysis
"""

import io
import sys
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RAW_DIR = Path("data/raw")

DATASETS = {
    "telco_churn.csv": (
        "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d"
        "/master/data/Telco-Customer-Churn.csv"
    ),
    "ab_test.csv": (
        "https://raw.githubusercontent.com/marooned20/Udacity-AB-testing"
        "/master/ab_data.csv"
    ),
}

HEADERS = {"User-Agent": "Mozilla/5.0"}
EXPECTED_ROWS = {"telco_churn.csv": 7043, "ab_test.csv": 294478}


def download(name: str, url: str) -> None:
    dest = RAW_DIR / name
    if dest.exists():
        print(f"  {name} already exists — skipping download")
        return

    print(f"  Downloading {name} ...")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        content = r.read()
    dest.write_bytes(content)

    # Quick row count
    lines = content.count(b"\n")
    expected = EXPECTED_ROWS.get(name)
    status = "OK" if not expected or abs(lines - expected) < 10 else "UNEXPECTED COUNT"
    print(f"  {name} saved — {lines:,} lines [{status}]")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in DATASETS.items():
        download(name, url)
    print("\nData download complete.")
    print(f"Files in {RAW_DIR}:")
    for f in sorted(RAW_DIR.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
