"""Download the raw FIFA World Cup 2026 data from FIFA's public APIs.

Run this file first:
    python 01_download_data.py

The script does not analyse the data. It only downloads and preserves the
original JSON responses so that the source of every value can be demonstrated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen


SEASON_ID = "285023"
COMPETITION_ID = "17"
LANGUAGE = "en"

PROJECT_FOLDER = Path(__file__).resolve().parent
RAW_FOLDER = PROJECT_FOLDER / "raw_data"

PLAYER_STATS_URL = (
    f"https://fdh-api.fifa.com/v1/stats/season/{SEASON_ID}/players.json"
)
QUALIFIED_TEAMS_URL = (
    "https://api.fifa.com/api/v3/teamsqualified/"
    f"season/{SEASON_ID}?language={LANGUAGE}"
)
SQUAD_URL = (
    "https://api.fifa.com/api/v3/teams/{team_id}/squad"
    f"?idCompetition={COMPETITION_ID}&idSeason={SEASON_ID}&language={LANGUAGE}"
)


def download_json(url: str, attempts: int = 3) -> dict | list:
    """Download JSON with a clear user agent and a small retry mechanism."""
    request = Request(url, headers={"User-Agent": "CDU-HIT140-Student-Project/1.0"})

    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except Exception:
            if attempt == attempts:
                raise
            sleep(2 * attempt)

    raise RuntimeError("The download could not be completed.")


def save_json(data: dict | list, file_path: Path) -> None:
    """Save JSON without changing its values."""
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_team_name(team: dict) -> str:
    """Return the English team name from FIFA's multilingual name field."""
    names = team.get("TeamName", [])
    return names[0].get("Description", "Unknown") if names else "Unknown"


def main() -> None:
    RAW_FOLDER.mkdir(parents=True, exist_ok=True)

    print("Step 1: Downloading the complete player-statistics response...")
    player_stats = download_json(PLAYER_STATS_URL)
    save_json(player_stats, RAW_FOLDER / "player_stats.json")

    print("Step 2: Downloading the list of participating teams...")
    qualified_teams = download_json(QUALIFIED_TEAMS_URL)
    save_json(qualified_teams, RAW_FOLDER / "qualified_teams.json")

    teams = qualified_teams.get("Results", [])
    if len(teams) != 48:
        raise ValueError(f"Expected 48 teams but FIFA returned {len(teams)}.")

    print("Step 3: Downloading one official squad response for each team...")
    squads = []
    squad_urls = []

    for number, team in enumerate(teams, start=1):
        team_id = str(team["IdTeam"])
        team_name = get_team_name(team)
        url = SQUAD_URL.format(team_id=team_id)

        print(f"  {number:02d}/48: {team_name}")
        squad = download_json(url)
        squads.append(squad)
        squad_urls.append(url)

    save_json(squads, RAW_FOLDER / "team_squads.json")

    source_log = {
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_organisation": "FIFA",
        "tournament": "FIFA World Cup 2026",
        "competition_id": COMPETITION_ID,
        "season_id": SEASON_ID,
        "source_page": (
            "https://www.fifa.com/en/tournaments/mens/worldcup/"
            "canadamexicousa2026/statistics"
        ),
        "api_endpoints": {
            "player_statistics": PLAYER_STATS_URL,
            "qualified_teams": QUALIFIED_TEAMS_URL,
            "team_squads": squad_urls,
        },
        "raw_files": [
            "player_stats.json",
            "qualified_teams.json",
            "team_squads.json",
        ],
        "important_source_fields": {
            "TimePlayed": "Total minutes played",
            "DefensivePressuresApplied": "All defensive pressures applied",
            "DirectDefensivePressuresApplied": (
                "Pressures applied directly to the opponent in possession"
            ),
            "ForcedTurnovers": "Possession turnovers forced by the player",
            "MatchesPlayed": "Matches in which the player appeared",
        },
    }
    save_json(source_log, RAW_FOLDER / "source_log.json")

    print("\nDownload complete.")
    print(f"Player IDs in statistics file: {len(player_stats):,}")
    print(f"Participating teams: {len(teams)}")
    print(f"Raw files saved in: {RAW_FOLDER}")


if __name__ == "__main__":
    main()
