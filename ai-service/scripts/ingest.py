"""
ingest.py — NSE Scheduler Historical Data ETL
Reads the job-hours CSV export, cleans and transforms the data,
and upserts records into the MongoDB `historicalProjects` collection.

Usage:
    python scripts/ingest.py --csv "path/to/job_hours.csv"
    python scripts/ingest.py  # defaults to data/job_hours.csv
"""

import argparse
import math
import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "job_hours.csv")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/nse_scheduler")
DB_NAME = "nse_scheduler"
COLLECTION = "historicalProjects"

# Row 0-5 are banner/label rows; row 6 is the real header
SKIP_ROWS = 6

# Excel formula error strings and placeholder values to treat as null
NULL_TOKENS = {"#DIV/0!", "---", "#VALUE!", "#REF!", "#N/A", "tbd", "TBD", ""}


# ---------------------------------------------------------------------------
# Step 1 — Load raw CSV
# ---------------------------------------------------------------------------

def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        skiprows=SKIP_ROWS,
        header=0,
        encoding="cp1252",      # Windows-1252 handles the mojibake characters
        dtype=str,              # Keep everything as string until we cast explicitly
        keep_default_na=False,  # We'll handle nulls ourselves
    )
    return df


# ---------------------------------------------------------------------------
# Step 2 — Rename columns
# Pandas appends .1, .2 suffixes to duplicate column names automatically.
# Map those to unambiguous names.
# ---------------------------------------------------------------------------

COLUMN_RENAME = {
    # Positional names as pandas reads them (stripped of newlines by pandas)
    "Unnamed: 0":                        "keep",
    "Supervisor":                        "supervisor",
    "Job":                               "jobNumber",
    "Job Name":                          "jobName",

    # CE side
    "CE BUDGETED HRS":                   "ce_budgetedHrs",
    "APP CO HRS":                        "ce_approvedCoHrs",
    "TOTAL  HRS(budget  + CO's)":        "ce_totalHrs",
    "WORKED HOURS":                      "ce_workedHours",
    "Hours Overrun ":                    "ce_hoursOverrun",
    "SUBSTANTIALLY DONE DATE":           "substantiallyDoneDate",
    "Percentage Overrun ":               "ce_percentageOverrun",
    "Proj Layout Hrs included? ":        "projLayoutIncluded",

    # BID side (pandas appends .1 to the second occurrence of duplicate names)
    "BID  Estimated HRS":                "bid_estimatedHrs",
    "APP CO HRS.1":                      "bid_approvedCoHrs",
    "TOTAL  HRS(bid est + CO's)":        "bid_totalHrs",
    "WORKED HOURS.1":                    "bid_workedHours",
    "Hours Overrun .1":                  "bid_hoursOverrun",
    "Percentage Overrun .1":             "bid_percentageOverrun",

    # Dates
    "Last Substantial Date Wrk'd":       "lastSubstantialDateWorked",
    "PCO Hours Missing?":                "pcoHoursMissing",
    "1st Day Wrk'd":                     "startDate",
    "Last Day Wrk'd":                    "endDate",

    # Optional enrichment fields
    "Sq Footage":                        "sqFootage",
    "(Labor Hrs + PCO Hrs) / total sq feet": "laborHrsPerSqFt",
    "Type of Project ":                  "projectType",
    "Estimate Variance (for DW)":        "estimateVariance",
}


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Strip surrounding whitespace from all column names first
    df.columns = [c.strip().replace("\n", "") for c in df.columns]
    df = df.rename(columns=COLUMN_RENAME)
    return df


# ---------------------------------------------------------------------------
# Step 3 — Drop non-project rows
# ---------------------------------------------------------------------------

def drop_non_project_rows(df: pd.DataFrame) -> pd.DataFrame:
    # jobNumber must be a numeric-looking string (e.g. "23001", "24009")
    df = df[df["jobNumber"].str.match(r"^\d{5}$", na=False)].copy()
    # Exclude summary rows (e.g. "All Job Totals:") that land a number in the job column
    df = df[~df["supervisor"].str.contains(r"total", case=False, na=False, regex=True)]
    return df


# ---------------------------------------------------------------------------
# Step 4 — Replace Excel error tokens with None
# ---------------------------------------------------------------------------

def sanitize_tokens(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace(list(NULL_TOKENS), None)
    # Strip stray whitespace from string cells
    for i in range(len(df.columns)):
        col_data = df.iloc[:, i]
        if str(col_data.dtype) in ("object", "string"):
            try:
                df.iloc[:, i] = col_data.str.strip()
            except Exception:
                pass
    return df


# ---------------------------------------------------------------------------
# Step 5 — Forward-fill supervisor (sparse column)
# ---------------------------------------------------------------------------

def forward_fill_supervisor(df: pd.DataFrame) -> pd.DataFrame:
    df["supervisor"] = df["supervisor"].replace("", None).ffill()
    return df


# ---------------------------------------------------------------------------
# Step 6 — Cast types
# ---------------------------------------------------------------------------

NUMERIC_COLS = [
    "ce_budgetedHrs", "ce_approvedCoHrs", "ce_totalHrs", "ce_workedHours", "ce_hoursOverrun",
    "bid_estimatedHrs", "bid_approvedCoHrs", "bid_totalHrs", "bid_workedHours", "bid_hoursOverrun",
    "sqFootage",
]

DATE_COLS = ["substantiallyDoneDate", "startDate", "endDate", "lastSubstantialDateWorked"]

PERCENT_COLS = ["ce_percentageOverrun", "bid_percentageOverrun"]


def cast_types(df: pd.DataFrame) -> pd.DataFrame:
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%m/%d/%y", errors="coerce")

    for col in PERCENT_COLS:
        if col in df.columns:
            # Strip "%" if present, then divide by 100
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .pipe(pd.to_numeric, errors="coerce")
                .div(100)
            )

    return df


# ---------------------------------------------------------------------------
# Step 7 — Derive analytical fields
# ---------------------------------------------------------------------------

def derive_fields(df: pd.DataFrame) -> pd.DataFrame:
    # Actual efficiency: how close to budget did the job land?
    # Values < 1.0 mean over-budget; > 1.0 mean under-budget (efficient)
    df["actualEfficiency"] = df.apply(
        lambda r: (
            round(r["ce_budgetedHrs"] / r["ce_workedHours"], 4)
            if (
                pd.notna(r.get("ce_budgetedHrs"))
                and pd.notna(r.get("ce_workedHours"))
                and r.get("ce_workedHours", 0) > 0
                and r.get("ce_budgetedHrs", 0) > 0
            )
            else None
        ),
        axis=1,
    )

    # Actual duration in weeks from first to last day worked
    df["actualDurationWeeks"] = df.apply(
        lambda r: (
            round((r["endDate"] - r["startDate"]).days / 7, 2)
            if pd.notna(r.get("startDate")) and pd.notna(r.get("endDate"))
            else None
        ),
        axis=1,
    )

    # Overrun flag: True if worked hours exceeded budgeted hours
    df["wasOverBudget"] = df.apply(
        lambda r: (
            bool(r["ce_hoursOverrun"] > 0)
            if pd.notna(r.get("ce_hoursOverrun"))
            else None
        ),
        axis=1,
    )

    return df


# ---------------------------------------------------------------------------
# Step 8 — Build upsert documents and write to MongoDB
# ---------------------------------------------------------------------------

def to_python_native(val):
    """Convert numpy/pandas types to Python natives for pymongo."""
    if isinstance(val, pd.Series):
        val = val.iloc[-1]  # fallback: take last value if Series slips through
    if not isinstance(val, (list, dict)):
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(val, float) and math.isnan(val):
        return None
    if hasattr(val, "item"):           # numpy scalar → Python native
        return val.item()
    if isinstance(val, pd.Timestamp):  # Timestamp → datetime
        return val.to_pydatetime()
    return val


def build_document(row: pd.Series) -> dict:
    doc = {}
    for i, col in enumerate(row.index):
        val = row.iloc[i]
        doc[col] = to_python_native(val)
    doc["ingestedAt"] = datetime.now(timezone.utc)
    return doc


def upsert_to_mongo(df: pd.DataFrame) -> None:
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION]

    ops = []
    for _, row in df.iterrows():
        doc = build_document(row)
        job_number = doc.get("jobNumber")
        if not job_number:
            continue
        ops.append(
            UpdateOne(
                {"jobNumber": job_number},
                {"$set": doc},
                upsert=True,
            )
        )

    if ops:
        result = collection.bulk_write(ops)
        print(
            f"  Upserted {result.upserted_count} new | "
            f"Modified {result.modified_count} existing | "
            f"Total ops: {len(ops)}"
        )
    else:
        print("  No valid project rows found to upsert.")

    client.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(csv_path: str) -> None:
    print(f"[1/7] Loading CSV: {csv_path}")
    df = load_raw(csv_path)
    print(f"      Raw shape: {df.shape}")

    print("[2/7] Renaming columns...")
    df = rename_columns(df)

    print("[3/7] Dropping non-project rows...")
    df = drop_non_project_rows(df)
    print(f"      Project rows: {len(df)}")

    print("[4/7] Sanitizing null tokens...")
    df = sanitize_tokens(df)

    print("[5/7] Forward-filling supervisor...")
    df = forward_fill_supervisor(df)

    print("[6/7] Casting types and deriving fields...")
    df = cast_types(df)
    df = derive_fields(df)

    eff_count = df["actualEfficiency"].notna().sum()
    print(f"      Records with computed actualEfficiency: {eff_count}/{len(df)}")

    print("[7/7] Upserting to MongoDB...")
    upsert_to_mongo(df)

    print("\n✅ Ingest complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest NSE job-hours CSV into MongoDB.")
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_PATH,
        help="Path to the job hours CSV file",
    )
    args = parser.parse_args()
    run(args.csv)
