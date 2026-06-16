"""
AutoRisk — Phase 1: NHTSA Data Pipeline
Fetches complaints, recalls, and investigations for a target vehicle list.
Outputs: data/complaints.csv, data/recalls.csv, data/investigations.csv

Usage:
    python src/fetch_nhtsa.py                  # fetch all vehicles in TARGET_VEHICLES
    python src/fetch_nhtsa.py --test           # single vehicle smoke test
"""

import requests
import pandas as pd
import time
import logging
import argparse
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.nhtsa.gov"

# These are the top used-car picks in the $5–10k / 2008–2018 range.
# Add or remove rows freely — this is your entire scope for Phase 1.
TARGET_VEHICLES = [
    # (make, model, year)
    ("toyota",  "camry",    2012),
    ("toyota",  "camry",    2013),
    ("toyota",  "camry",    2014),
    ("toyota",  "corolla",  2012),
    ("toyota",  "corolla",  2014),
    ("honda",   "civic",    2012),
    ("honda",   "civic",    2014),
    ("honda",   "accord",   2012),
    ("honda",   "accord",   2014),
    ("honda",   "crv",      2013),
    ("ford",    "fusion",   2012),
    ("ford",    "fusion",   2014),
    ("ford",    "escape",   2013),
    ("chevrolet","malibu",  2013),
    ("chevrolet","cruze",   2012),
    ("chevrolet","equinox", 2013),
    ("nissan",  "altima",   2013),
    ("nissan",  "sentra",   2014),
    ("hyundai", "elantra",  2013),
    ("hyundai", "sonata",   2013),
    ("kia",     "optima",   2013),
    ("kia",     "soul",     2014),
    ("mazda",   "mazda3",   2013),
    ("subaru",  "outback",  2013),
    ("subaru",  "forester", 2014),
    ("volkswagen","jetta",  2013),
    ("bmw",     "3series",  2012),
    ("jeep",    "cherokee", 2014),
    ("dodge",   "charger",  2013),
    ("ram",     "1500",     2013),
]

RATE_LIMIT_DELAY = 0.5   # seconds between requests — NHTSA is tolerant but be polite
MAX_RETRIES      = 3
OUTPUT_DIR       = Path("data")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── NHTSA API helpers ─────────────────────────────────────────────────────────

def _get(url: str, params: dict = None) -> dict | None:
    """GET with retry + rate limiting. Returns parsed JSON or None on failure."""
    headers = {"User-Agent": "AutoRisk/1.0 (github.com/yourname/autorisk)"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            log.warning(f"HTTP {e.response.status_code} on attempt {attempt}: {url}")
        except requests.exceptions.RequestException as e:
            log.warning(f"Request error on attempt {attempt}: {e}")
        time.sleep(RATE_LIMIT_DELAY * attempt)   # back off on retry
    log.error(f"Failed after {MAX_RETRIES} attempts: {url}")
    return None


def fetch_complaints(make: str, model: str, year: int) -> list[dict]:
    """
    Endpoint: GET /complaints/complaintsByVehicle
    Returns raw complaint records for one make/model/year.

    Key fields in each record:
      - odiNumber       : unique complaint ID
      - dateOfIncident  : when it happened
      - components      : e.g. "POWER TRAIN:AUTOMATIC TRANSMISSION"
      - summary         : free-text description — this is what NLP will consume
      - injuries, deaths, fires, rollover : safety signals
      - crash           : bool
    """
    url = f"{BASE_URL}/complaints/complaintsByVehicle"
    data = _get(url, {"make": make, "model": model, "modelYear": year})
    if not data or not data.get("results"):
        return []

    records = []
    for r in data["results"]:
        records.append({
            "make":             make.lower(),
            "model":            model.lower(),
            "year":             year,
            "complaint_id":     r.get("odiNumber"),
            "incident_date":    r.get("dateOfIncident"),
            "components":       r.get("components", ""),
            "summary":          r.get("summary", ""),       # NLP target
            "injuries":         r.get("numberOfInjuries", 0),
            "deaths":           r.get("numberOfDeaths", 0),
            "fire":             r.get("fireOccurred", False),
            "crash":            r.get("crash", False),
            "mileage":          r.get("mileage"),
        })
    return records


def fetch_recalls(make: str, model: str, year: int) -> list[dict]:
    """
    Endpoint: GET /recalls/recallsByVehicle
    Returns recall campaigns for one make/model/year.

    Key fields:
      - NHTSACampaignNumber : recall ID
      - Component           : what was recalled
      - Summary / Remedy    : description and fix
      - ReportReceivedDate  : when NHTSA got the report
      - PotentialNumberOfUnitsAffected
    """
    url = f"{BASE_URL}/recalls/recallsByVehicle"
    data = _get(url, {"make": make, "model": model, "modelYear": year})
    if not data or not data.get("results"):
        return []

    records = []
    for r in data["results"]:
        records.append({
            "make":             make.lower(),
            "model":            model.lower(),
            "year":             year,
            "recall_id":        r.get("NHTSACampaignNumber"),
            "report_date":      r.get("ReportReceivedDate"),
            "component":        r.get("Component", ""),
            "summary":          r.get("Summary", ""),
            "remedy":           r.get("Remedy", ""),
            "units_affected":   r.get("PotentialNumberOfUnitsAffected", 0),
        })
    return records


def fetch_investigations(make: str, model: str, year: int) -> list[dict]:
    """
    Endpoint: GET /investigations/byVehicle
    Returns NHTSA safety investigations for one make/model/year.
    Investigations = potential problems being formally looked at, may become recalls.

    Key fields:
      - NHTSAActionNumber  : investigation ID
      - Subject            : what's being investigated
      - Summary
      - OpeningDate / ClosingDate
    """
    url = f"{BASE_URL}/investigations/byVehicle"
    data = _get(url, {"make": make, "model": model, "modelYear": year})
    if not data or not data.get("results"):
        return []

    records = []
    for r in data["results"]:
        records.append({
            "make":             make.lower(),
            "model":            model.lower(),
            "year":             year,
            "investigation_id": r.get("NHTSAActionNumber"),
            "subject":          r.get("Subject", ""),
            "summary":          r.get("Summary", ""),
            "opening_date":     r.get("OpeningDate"),
            "closing_date":     r.get("ClosingDate"),
            "status":           r.get("InvestigationStatus", ""),
        })
    return records


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(vehicles: list[tuple]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_complaints     = []
    all_recalls        = []
    all_investigations = []

    total = len(vehicles)
    for i, (make, model, year) in enumerate(vehicles, 1):
        log.info(f"[{i}/{total}] Fetching {year} {make.title()} {model.title()}")

        complaints     = fetch_complaints(make, model, year)
        recalls        = fetch_recalls(make, model, year)
        investigations = fetch_investigations(make, model, year)

        all_complaints.extend(complaints)
        all_recalls.extend(recalls)
        all_investigations.extend(investigations)

        log.info(
            f"  → {len(complaints)} complaints  "
            f"{len(recalls)} recalls  "
            f"{len(investigations)} investigations"
        )

        time.sleep(RATE_LIMIT_DELAY)

    # Save to CSV
    def save(records, filename, label):
        if not records:
            log.warning(f"No {label} records found — {filename} not written.")
            return
        df = pd.DataFrame(records)
        path = OUTPUT_DIR / filename
        df.to_csv(path, index=False)
        log.info(f"Saved {len(df):,} {label} records → {path}")
        return df

    save(all_complaints,     "complaints.csv",     "complaint")
    save(all_recalls,        "recalls.csv",        "recall")
    save(all_investigations, "investigations.csv", "investigation")

    # Quick summary so you can sanity-check immediately
    print("\n── Summary ─────────────────────────────────────────────────────")
    print(f"  Vehicles fetched : {total}")
    print(f"  Total complaints : {len(all_complaints):,}")
    print(f"  Total recalls    : {len(all_recalls):,}")
    print(f"  Investigations   : {len(all_investigations):,}")
    print(f"  Output dir       : {OUTPUT_DIR.resolve()}")
    print("────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoRisk — NHTSA data fetcher")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a single vehicle smoke test (2012 Toyota Camry)"
    )
    args = parser.parse_args()

    if args.test:
        log.info("Running smoke test: 2012 Toyota Camry")
        run([("toyota", "camry", 2012)])
    else:
        run(TARGET_VEHICLES)
