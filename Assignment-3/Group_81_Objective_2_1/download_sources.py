"""Download into a NEW directory; never silently replace the preserved snapshots.

Usage: python download_sources.py new_snapshot
To use newer data, inspect changes and deliberately copy it into raw/ afterwards.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = {
    'fifa_matches.json': 'https://api.fifa.com/api/v3/calendar/matches?idSeason=285023&count=200&language=en',
    'international_results.csv': 'https://raw.githubusercontent.com/martj42/international_results/master/results.csv',
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    log = []
    for filename, url in SOURCES.items():
        request = Request(url, headers={'User-Agent': 'HIT140-academic-analysis/1.0'})
        with urlopen(request, timeout=120) as response:
            data = response.read()
        (args.destination / filename).write_bytes(data)
        log.append({'file': filename, 'url': url, 'downloaded_utc': datetime.now(timezone.utc).isoformat(),
                    'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    (args.destination / 'source_manifest.json').write_text(json.dumps(log, indent=2) + '\n')
    print('Downloaded snapshots to', args.destination)

if __name__ == '__main__':
    main()
