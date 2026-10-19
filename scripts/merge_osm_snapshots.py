#!/usr/bin/env python3
"""Merge successful OSM downloads by record ID, retaining their source dates."""
from argparse import ArgumentParser
from pathlib import Path
import json
import hashlib


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = {}
    snapshots = []
    for path in args.inputs:
        manifest = json.loads(path.with_name(path.stem + ".manifest.json").read_text())
        if manifest["status"] != "success":
            raise SystemExit(f"Refusing a failed or incomplete source: {path.name}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
            raise SystemExit(f"Checksum mismatch: {path.name}")
        document = json.loads(raw)
        stamp = document["osm3s"]["timestamp_osm_base"]
        snapshots.append(
            {
                "category": manifest["category"],
                "osm_base": stamp,
                "sha256": manifest["sha256"],
            }
        )
        for element in document["elements"]:
            key = (element["type"], element["id"])
            previous = records.get(key)
            score = (element.get("version", 0), stamp)
            old_score = (
                (previous.get("version", 0), previous["_source_snapshot"]["osm_base"])
                if previous
                else None
            )
            if previous is None or score >= old_score:
                record = dict(element)
                record["_source_snapshot"] = {
                    "category": manifest["category"],
                    "osm_base": stamp,
                }
                records[key] = record
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"elements": list(records.values()), "source_snapshots": snapshots},
            ensure_ascii=False,
        )
        + "\n"
    )
    print(
        f"Merged {len(records):,} source records. The result is not a complete or field-verified register."
    )


if __name__ == "__main__":
    main()
