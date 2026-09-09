"""
HIT140 Group 81 - Analytic Task 4: Shooting
Jobanpreet Singh

This file collects the raw 2026 World Cup squad shooting table from FBref.
It does not do any statistical analysis.

Run:
    python 00_collect_fbref_shooting.py

A saved copy of the raw CSV is included with the project so the analysis can
still be reproduced if the website blocks automated requests later.
"""

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

URL = "https://fbref.com/en/comps/1/shooting/World-Cup-Stats"
OUTFILE = Path(__file__).resolve().parent / "fbref_world_cup_2026_shooting_raw.csv"


def flatten_columns(columns):
    """Keep the last part of FBref's multi-row table headings."""
    if not isinstance(columns, pd.MultiIndex):
        return [str(col).strip() for col in columns]

    output = []
    for col in columns:
        parts = [str(item).strip() for item in col if str(item) != "nan"]
        output.append(parts[-1] if parts else "")
    return output


def main():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/151 Safari/537.36"
        )
    }

    try:
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(
            "FBref could not be downloaded automatically. "
            "Use the included raw CSV saved on 7 September 2026.\n"
            f"Reason: {exc}"
        )

    tables = pd.read_html(StringIO(response.text))
    shooting = None

    for table in tables:
        table = table.copy()
        table.columns = flatten_columns(table.columns)

        needed = {"Squad", "Sh", "SoT", "SoT/90"}
        if needed.issubset(table.columns):
            first_name = str(table.iloc[0]["Squad"]).strip().lower()
            if not first_name.startswith("vs "):
                shooting = table
                break

    if shooting is None:
        raise SystemExit("The squad shooting table was not found on the FBref page.")

    wanted = [
        "Squad", "# Pl", "90s", "Gls", "Sh", "SoT", "SoT%",
        "Sh/90", "SoT/90", "G/Sh", "G/SoT", "PK", "PKatt",
    ]
    missing = [column for column in wanted if column not in shooting.columns]
    if missing:
        raise SystemExit(f"Expected columns are missing: {missing}")

    shooting = shooting[wanted].copy()
    shooting["Squad"] = shooting["Squad"].astype(str).str.strip()
    shooting = shooting.drop_duplicates(subset="Squad")

    if len(shooting) != 48:
        raise SystemExit(f"Expected 48 team rows but found {len(shooting)}.")

    shooting.to_csv(OUTFILE, index=False)
    print(f"Saved {len(shooting)} team rows to {OUTFILE.name}")
    print(f"Source: {URL}")


if __name__ == "__main__":
    main()
