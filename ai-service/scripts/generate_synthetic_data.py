"""
generate_synthetic_data.py — NSE Scheduler Synthetic Historical Data Generator
Generates realistic synthetic project records and upserts them into the
MongoDB `historicalProjects` collection to augment the ~45 real CSV records.

Usage:
    python scripts/generate_synthetic_data.py --count 200
    python scripts/generate_synthetic_data.py  # defaults to 150 records
"""

import argparse
import math
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient, UpdateOne
import os

load_dotenv()

fake = Faker()
random.seed(42)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/nse_scheduler")
DB_NAME = "nse_scheduler"
COLLECTION = "historicalProjects"

# ---------------------------------------------------------------------------
# Reference data — mirrors real NSE project characteristics
# ---------------------------------------------------------------------------

PROJECT_TYPES = [
    "Office Tenant Improvement",
    "Government Facility",
    "Medical / Healthcare",
    "Retail Fit-Out",
    "Industrial / Warehouse",
    "Data Center",
    "Education",
    "Mixed-Use",
    "Parking Garage",
    "Hospitality",
]

SUPERVISORS = [
    "Gary Golden",
    "Mike Jackson",
    "Joe Lawhorn",
    "John Dennis",
    "Oscar Pereira",
    "Justin Ward",
]

# Efficiency distribution params per project type
# Tuple: (mean_efficiency, std_dev)
# Reflects real-world variance: government jobs tend toward lower efficiency,
# small retail fit-outs tend toward higher efficiency.
EFFICIENCY_PARAMS: dict[str, tuple[float, float]] = {
    "Office Tenant Improvement":  (0.88, 0.10),
    "Government Facility":        (0.80, 0.14),
    "Medical / Healthcare":       (0.82, 0.12),
    "Retail Fit-Out":             (0.92, 0.08),
    "Industrial / Warehouse":     (0.90, 0.09),
    "Data Center":                (0.78, 0.15),
    "Education":                  (0.85, 0.11),
    "Mixed-Use":                  (0.83, 0.13),
    "Parking Garage":             (0.87, 0.10),
    "Hospitality":                (0.86, 0.10),
}

# Budget size bands (totalManHours range) by project type
BUDGET_BANDS: dict[str, tuple[int, int]] = {
    "Office Tenant Improvement":  (400,  3500),
    "Government Facility":        (800,  5000),
    "Medical / Healthcare":       (600,  4000),
    "Retail Fit-Out":             (50,   800),
    "Industrial / Warehouse":     (200,  2000),
    "Data Center":                (1000, 6000),
    "Education":                  (500,  3000),
    "Mixed-Use":                  (600,  4500),
    "Parking Garage":             (100,  1500),
    "Hospitality":                (300,  2500),
}

# Crew size range by project type
CREW_BANDS: dict[str, tuple[int, int]] = {
    "Office Tenant Improvement":  (2, 8),
    "Government Facility":        (3, 12),
    "Medical / Healthcare":       (3, 10),
    "Retail Fit-Out":             (1, 4),
    "Industrial / Warehouse":     (2, 6),
    "Data Center":                (4, 14),
    "Education":                  (3, 9),
    "Mixed-Use":                  (3, 10),
    "Parking Garage":             (1, 5),
    "Hospitality":                (2, 7),
}


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def generate_record(index: int) -> dict:
    project_type = random.choice(PROJECT_TYPES)
    supervisor = random.choice(SUPERVISORS)

    # Budget
    budget_lo, budget_hi = BUDGET_BANDS[project_type]
    ce_budgeted_hrs = round(random.uniform(budget_lo, budget_hi), 1)

    # Change orders: 0-25% of budget, occasionally negative (scope reduction)
    co_sign = 1 if random.random() > 0.15 else -1
    ce_approved_co_hrs = round(co_sign * random.uniform(0, ce_budgeted_hrs * 0.25), 1)
    ce_total_hrs = ce_budgeted_hrs + ce_approved_co_hrs

    # Efficiency — clamp to [0.40, 1.40] to avoid unrealistic outliers
    eff_mean, eff_std = EFFICIENCY_PARAMS[project_type]
    actual_efficiency = clamp(random.gauss(eff_mean, eff_std), 0.40, 1.40)

    # Worked hours derived from efficiency
    ce_worked_hours = round(ce_total_hrs / actual_efficiency, 1)
    ce_hours_overrun = round(ce_worked_hours - ce_total_hrs, 1)
    ce_pct_overrun = round(ce_hours_overrun / ce_total_hrs, 4) if ce_total_hrs > 0 else None

    # Crew and schedule
    crew_lo, crew_hi = CREW_BANDS[project_type]
    crew_size = random.randint(crew_lo, crew_hi)
    man_weeks = ce_total_hrs / 40
    ideal_weeks = man_weeks / crew_size
    realistic_duration_weeks = round(ideal_weeks / actual_efficiency, 2)
    actual_duration_weeks = round(
        realistic_duration_weeks * random.uniform(0.85, 1.15), 2
    )

    # Dates — project started anywhere in the past 5 years
    start_date = fake.date_time_between(start_date="-5y", end_date="-3m")
    end_date = start_date + timedelta(weeks=actual_duration_weeks)

    # Square footage (optional — only populated for DW-type projects ~60% of the time)
    sq_footage = (
        round(random.uniform(2000, 80000))
        if random.random() < 0.60
        else None
    )

    # Synthetic job number: prefix SYN + 5-digit index
    job_number = f"SYN{str(index).zfill(5)}"

    return {
        "jobNumber":              job_number,
        "jobName":                fake.company() + " " + random.choice(["Renovation", "Fit-Out", "Build-Out", "Remodel", "Installation"]),
        "supervisor":             supervisor,
        "projectType":            project_type,
        "isSynthetic":            True,

        # CE columns
        "ce_budgetedHrs":         ce_budgeted_hrs,
        "ce_approvedCoHrs":       ce_approved_co_hrs,
        "ce_totalHrs":            ce_total_hrs,
        "ce_workedHours":         ce_worked_hours,
        "ce_hoursOverrun":        ce_hours_overrun,
        "ce_percentageOverrun":   ce_pct_overrun,

        # Derived analytical fields (mirrors ingest.py derivation)
        "actualEfficiency":       round(actual_efficiency, 4),
        "actualDurationWeeks":    actual_duration_weeks,
        "wasOverBudget":          ce_hours_overrun > 0,

        # Schedule
        "startDate":              start_date,
        "endDate":                end_date,

        # Optional enrichment
        "sqFootage":              sq_footage,
        "crewSize":               crew_size,

        "ingestedAt":             datetime.utcnow(),
    }


# ---------------------------------------------------------------------------
# Write to MongoDB
# ---------------------------------------------------------------------------

def upsert_synthetic(records: list[dict]) -> None:
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION]

    ops = [
        UpdateOne(
            {"jobNumber": rec["jobNumber"]},
            {"$set": rec},
            upsert=True,
        )
        for rec in records
    ]

    result = collection.bulk_write(ops)
    print(
        f"  Upserted {result.upserted_count} new | "
        f"Modified {result.modified_count} existing | "
        f"Total: {len(ops)}"
    )
    client.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(count: int) -> None:
    print(f"[1/2] Generating {count} synthetic project records...")
    records = [generate_record(i + 1) for i in range(count)]

    eff_values = [r["actualEfficiency"] for r in records]
    print(
        f"      Efficiency range: {min(eff_values):.3f} – {max(eff_values):.3f} "
        f"| mean: {sum(eff_values)/len(eff_values):.3f}"
    )

    print("[2/2] Upserting to MongoDB...")
    upsert_synthetic(records)

    print(f"\n✅ Synthetic data generation complete ({count} records).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic NSE historical project records."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=150,
        help="Number of synthetic records to generate (default: 150)",
    )
    args = parser.parse_args()
    run(args.count)
