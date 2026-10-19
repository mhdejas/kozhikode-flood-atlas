"""Semantic checks for the checked-in Kozhikode Flood Atlas site."""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(__import__("os").environ.get("FLOOD_SITE_DIR", ROOT / "site"))
DATA = SITE / "data"


def load(name):
    with (DATA / name).open(encoding="utf-8") as source:
        return json.load(source)


class SiteDataTests(unittest.TestCase):
    def test_scenario_summary_contract(self):
        rows = {
            row["return_period_years"]: row for row in load("scenario_summary.json")
        }
        expected = {
            10: (59, 32, 116.9484109),
            25: (63, 32, 123.4508244),
            50: (79, 34, 133.894028),
        }
        self.assertEqual(set(rows), set(expected))
        for year, (schools, hospitals, roads) in expected.items():
            self.assertEqual(rows[year]["schools_overlap"], schools)
            self.assertEqual(rows[year]["hospitals_overlap"], hospitals)
            self.assertAlmostEqual(
                rows[year]["major_roads_overlap_km"], roads, places=7
            )
            self.assertEqual(rows[year]["schools_total_mapped"], 1339)
            self.assertEqual(rows[year]["hospitals_total_mapped"], 662)
            self.assertAlmostEqual(
                rows[year]["major_roads_total_km"], 1948.0575308, places=7
            )

    def test_facility_inventory_and_flags_match_summary(self):
        features = load("facilities.geojson")["features"]
        self.assertEqual(
            Counter(f["properties"]["kind"] for f in features),
            {"school": 1339, "hospital": 662},
        )
        summary = {r["return_period_years"]: r for r in load("scenario_summary.json")}
        for year in (10, 25, 50):
            self.assertEqual(
                sum(f["properties"].get(f"overlap_{year}yr") is True for f in features),
                summary[year]["schools_overlap"] + summary[year]["hospitals_overlap"],
            )

    def test_local_body_inventory_and_nonnegative_totals(self):
        features = load("local_bodies.geojson")["features"]
        self.assertEqual(len(features), 78)
        self.assertEqual(
            Counter(f["properties"]["type"] for f in features),
            {"gram_panchayat": 70, "municipality": 7, "corporation": 1},
        )
        rows = load("local_body_summary.json")
        self.assertEqual(len(rows), 79)
        self.assertEqual(sum(row["type"] != "unmatched" for row in rows), 78)
        unmatched = [row for row in rows if row["type"] == "unmatched"]
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["id"], "UNMATCHED")
        for props in rows:
            for year in (10, 25, 50):
                for total, overlap in (
                    ("schools_total", f"schools_overlap_{year}"),
                    ("hospitals_total", f"hospitals_overlap_{year}"),
                    ("roads_total_km", f"roads_overlap_km_{year}"),
                ):
                    self.assertGreaterEqual(props[total], 0)
                    self.assertGreaterEqual(props[overlap], 0)
                    self.assertLessEqual(props[overlap], props[total] + 1e-6)

    def test_observed_layer_is_explicitly_unavailable(self):
        self.assertFalse(load("observed_status.json")["available"])

    def test_waterways_are_valid_line_geojson(self):
        waterways = load("waterways.geojson")
        self.assertEqual(waterways["type"], "FeatureCollection")
        self.assertEqual(len(waterways["features"]), 8364)
        for feature in waterways["features"]:
            self.assertIn(
                feature["geometry"]["type"], {"LineString", "MultiLineString"}
            )
            self.assertTrue(feature["geometry"]["coordinates"])

    def test_context_metadata_contract(self):
        metadata = load("context_metadata.json")
        self.assertEqual(metadata["flood_grid_m_approx"], 90)
        self.assertEqual(
            metadata["terrain"].get(
                "display_grid_m", metadata["terrain"].get("source_grid_m")
            ),
            30,
        )
        south_west, north_east = metadata["terrain"]["bounds"]
        self.assertLess(south_west[0], north_east[0])
        self.assertLess(south_west[1], north_east[1])
        self.assertEqual(metadata["waterways"]["feature_count"], 8364)

    def test_html_local_dependencies_and_anchors(self):
        html = (SITE / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r"(?:href|src)=['\"]([^'\"]+)['\"]", html)
        anchors = set(re.findall(r"id=[\'\"]([^\'\"]+)", html))
        for ref in refs:
            if ref.startswith(("http://", "https://", "mailto:", "#")):
                if ref.startswith("#"):
                    self.assertIn(ref[1:], anchors, ref)
                continue
            self.assertTrue((SITE / ref).exists(), ref)
        css = (SITE / "styles.css").read_text(encoding="utf-8")
        for ref in re.findall(r"url\(['\"]?([^'\")]+)", css):
            if not ref.startswith(("http://", "https://", "data:")):
                self.assertTrue((SITE / ref).exists(), ref)

    def test_private_paths_and_token_patterns_are_absent(self):
        text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in SITE.rglob("*")
            if path.is_file()
        )
        self.assertNotRegex(text, r"/workspace/|/home/ubuntu/|AKIA[0-9A-Z]{16}")
        self.assertNotRegex(
            text, r"(?:password|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]+['\"]"
        )


if __name__ == "__main__":
    unittest.main()
