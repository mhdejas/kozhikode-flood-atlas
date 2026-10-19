#!/usr/bin/env python3
"""Download one dated OSM snapshot. Run categories sequentially, not in parallel."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json

BBOX = "11.122,75.532,11.809,76.15"
SELECTORS = {
    "schools": 'nwr["amenity"="school"]',
    "health-amenity": 'nwr["amenity"~"^(hospital|clinic|doctors)$"]',
    "healthcare": 'nwr["healthcare"~"^(hospital|clinic|centre|health_post|doctor|doctors|community_health_worker|rehabilitation)$"]',
    "major-roads": 'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]',
    "waterways": 'way["waterway"~"^(river|stream|canal|drain|ditch)$"]',
}
ENDPOINT = "https://overpass-api.de/api/interpreter"


def download(category, output):
    query = f"[out:json][timeout:120];{SELECTORS[category]}({BBOX});out meta geom;"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "category": category,
        "query": query,
        "endpoint": ENDPOINT,
        "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
    }
    try:
        request = Request(
            ENDPOINT,
            data=query.encode(),
            headers={"User-Agent": "KozhikodeFloodAtlas/1.0 (one-off research)"},
            method="POST",
        )
        with urlopen(request, timeout=150) as response:
            raw = response.read()
        document = json.loads(raw)
        if (
            document.get("remark")
            or document.get("error")
            or not isinstance(document.get("elements"), list)
        ):
            raise ValueError("The server returned an incomplete or malformed snapshot")
        stamp = document.get("osm3s", {}).get("timestamp_osm_base")
        if not stamp:
            raise ValueError("No OSM base timestamp was supplied")
        destination = output / f"{category}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_bytes(raw)
        temporary.replace(destination)
        manifest.update(
            status="success",
            source_osm_base_timestamp=stamp,
            record_count=len(document["elements"]),
            sha256=hashlib.sha256(raw).hexdigest(),
            fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as error:
        manifest["error"] = f"{type(error).__name__}: {error}"
    (output / f"{category}.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    if manifest["status"] != "success":
        raise SystemExit(
            f"Download failed: {manifest['error']}. No cached file is being presented as refreshed."
        )
    print(
        f"Saved {manifest['record_count']:,} source records for {category}; OSM base {stamp}."
    )


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("category", choices=SELECTORS)
    parser.add_argument("--output", type=Path, default=Path(".local-data"))
    args = parser.parse_args()
    download(args.category, args.output)


if __name__ == "__main__":
    main()
