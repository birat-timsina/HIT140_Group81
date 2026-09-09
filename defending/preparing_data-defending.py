"""Wrangle, clean, prepare and sample the FIFA World Cup 2026 data.

Run after 01_download_data.py:
    python 02_prepare_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


MINIMUM_MINUTES = 180
TARGET_SAMPLE_PER_POSITION = 60
RANDOM_SEED = 2026

PROJECT_FOLDER = Path(__file__).resolve().parent
RAW_FOLDER = PROJECT_FOLDER / "raw_data"
DATA_FOLDER = PROJECT_FOLDER / "data"


def load_json(file_path: Path) -> dict | list:
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_text(items: list[dict], default: str = "Unknown") -> str:
    """Extract the first description from FIFA's multilingual text list."""
    if not items:
        return default
    return items[0].get("Description", default)


def build_player_table(squads: list[dict]) -> pd.DataFrame:
    """Create one metadata row per player from the 48 squad responses."""
    rows = []

    for squad in squads:
        team_name = get_text(squad.get("TeamName", []))
        team_id = str(squad.get("IdTeam", ""))
        country_code = squad.get("IdCountry", "")

        for player in squad.get("Players", []):
            rows.append(
                {
                    "player_id": str(player.get("IdPlayer", "")),
                    "player_name": get_text(player.get("PlayerName", [])),
                    "team_id": team_id,
                    "team_name": team_name,
                    "country_code": country_code,
                    "position": get_text(player.get("PositionLocalized", [])),
                    "jersey_number": player.get("JerseyNum"),
                }
            )

    table = pd.DataFrame(rows)
    table = table.drop_duplicates(subset="player_id", keep="first")
    return table


def build_statistics_table(player_stats: dict) -> pd.DataFrame:
    """Turn FIFA's nested list of statistics into a rectangular table."""
    rows = []

    for player_id, statistics in player_stats.items():
        row = {"player_id": str(player_id)}

        for statistic in statistics:
            statistic_name, statistic_value, is_post_match = statistic
            row[statistic_name] = statistic_value
            row[f"{statistic_name}_is_post_match"] = is_post_match

        rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    required_files = [
        RAW_FOLDER / "player_stats.json",
        RAW_FOLDER / "team_squads.json",
    ]
    missing_files = [str(path) for path in required_files if not path.exists()]
    if missing_files:
        raise FileNotFoundError(
            "Run 01_download_data.py first. Missing: " + ", ".join(missing_files)
        )

    print("Step 1: Loading the preserved raw JSON files...")
    player_stats = load_json(RAW_FOLDER / "player_stats.json")
    squads = load_json(RAW_FOLDER / "team_squads.json")

    print("Step 2: Converting the squad and statistics JSON into tables...")
    players = build_player_table(squads)
    statistics = build_statistics_table(player_stats)

    print("Step 3: Joining player details to player statistics by player_id...")
    merged = players.merge(statistics, on="player_id", how="left", validate="one_to_one")

    rename_columns = {
        "TimePlayed": "minutes_played",
        "MatchesPlayed": "matches_played",
        "DefensivePressuresApplied": "defensive_pressures",
        "DirectDefensivePressuresApplied": "direct_defensive_pressures",
        "ForcedTurnovers": "forced_turnovers",
    }
    merged = merged.rename(columns=rename_columns)

    required_columns = list(rename_columns.values())
    for column in required_columns:
        if column not in merged.columns:
            raise KeyError(f"The required FIFA field '{column}' was not found.")
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    print("Step 4: Checking identifiers, missing values and impossible values...")
    if merged["player_id"].duplicated().any():
        raise ValueError("Duplicate player IDs remain after cleaning.")

    negative_minutes = (merged["minutes_played"] < 0).sum()
    negative_pressures = (merged["direct_defensive_pressures"] < 0).sum()
    if negative_minutes or negative_pressures:
        raise ValueError("Negative minutes or pressure counts were found.")

    print("Step 5: Calculating comparable per-90-minute defensive measures...")
    valid_minutes = merged["minutes_played"].gt(0)
    merged.loc[valid_minutes, "direct_pressures_per90"] = (
        merged.loc[valid_minutes, "direct_defensive_pressures"]
        / merged.loc[valid_minutes, "minutes_played"]
        * 90
    )
    merged.loc[valid_minutes, "all_pressures_per90"] = (
        merged.loc[valid_minutes, "defensive_pressures"]
        / merged.loc[valid_minutes, "minutes_played"]
        * 90
    )
    merged.loc[valid_minutes, "forced_turnovers_per90"] = (
        merged.loc[valid_minutes, "forced_turnovers"]
        / merged.loc[valid_minutes, "minutes_played"]
        * 90
    )

    keep_columns = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "country_code",
        "position",
        "jersey_number",
        "matches_played",
        "minutes_played",
        "defensive_pressures",
        "direct_defensive_pressures",
        "forced_turnovers",
        "direct_pressures_per90",
        "all_pressures_per90",
        "forced_turnovers_per90",
    ]
    cleaned = merged[keep_columns].copy()
    cleaned.to_csv(DATA_FOLDER / "all_players_cleaned.csv", index=False)

    print("Step 6: Defining the analysis population...")
    population = cleaned.loc[
        cleaned["position"].isin(["Defender", "Midfielder"])
        & cleaned["minutes_played"].ge(MINIMUM_MINUTES)
        & cleaned["direct_pressures_per90"].notna()
    ].copy()
    population = population.sort_values(["position", "player_name"]).reset_index(drop=True)
    population.to_csv(DATA_FOLDER / "analysis_population.csv", index=False)

    group_sizes = population.groupby("position", observed=True).size()
    if not {"Defender", "Midfielder"}.issubset(group_sizes.index):
        raise ValueError("Both position groups are required for the analysis.")

    print("Step 7: Taking a stratified random sample without replacement...")
    sample_size = min(TARGET_SAMPLE_PER_POSITION, int(group_sizes.min()))
    sample_parts = []

    for position in ["Defender", "Midfielder"]:
        group = population.loc[population["position"] == position]
        sample_parts.append(group.sample(n=sample_size, random_state=RANDOM_SEED))

    sample = pd.concat(sample_parts, ignore_index=True)
    sample = sample.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
    sample.to_csv(DATA_FOLDER / "analysis_sample.csv", index=False)

    data_dictionary = pd.DataFrame(
        [
            ["player_id", "FIFA player identifier", "text"],
            ["player_name", "Player's official FIFA display name", "text"],
            ["team_name", "National team", "text"],
            ["position", "FIFA position category", "categorical"],
            ["matches_played", "Matches in which the player appeared", "count"],
            ["minutes_played", "Total tournament minutes played", "continuous"],
            ["direct_defensive_pressures", "Direct pressures recorded by FIFA", "count"],
            [
                "direct_pressures_per90",
                "Direct pressures / minutes played x 90",
                "continuous",
            ],
        ],
        columns=["column", "meaning", "data_type"],
    )
    data_dictionary.to_csv(DATA_FOLDER / "data_dictionary.csv", index=False)

    print("\nPreparation complete.")
    print("Population counts:")
    print(group_sizes.to_string())
    print(f"Sample per position: {sample_size}")
    print(f"Total sample size: {len(sample)}")
    print(f"Prepared files saved in: {DATA_FOLDER}")


if __name__ == "__main__":
    main()
