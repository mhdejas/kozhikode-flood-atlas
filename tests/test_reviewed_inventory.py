"""Checks for the reviewed inventory; these do not establish real-world accuracy."""

from collections import Counter
import unittest

from test_data import load


class ReviewedInventoryTests(unittest.TestCase):
    def test_health_types_are_explicit_source_classes(self):
        records = [
            feature["properties"] for feature in load("facilities.geojson")["features"]
        ]
        health = [record for record in records if record["kind"] == "hospital"]
        expected = {
            "hospital": 437,
            "clinic": 173,
            "centre": 28,
            "doctor": 12,
            "rehabilitation": 12,
        }
        self.assertEqual(
            Counter(record["healthcare_class"] for record in health), expected
        )
        for summary in load("scenario_summary.json"):
            year = summary["return_period_years"]
            for category, count in expected.items():
                entry = summary["health_classes"][category]
                self.assertEqual(entry["total_mapped"], count)
                self.assertEqual(
                    entry["overlap"],
                    sum(
                        record["healthcare_class"] == category
                        and record[f"overlap_{year}yr"]
                        for record in health
                    ),
                )
        for record in records:
            self.assertNotIn("user", record)
            self.assertNotIn("uid", record)
            self.assertTrue(record.get("source_snapshot_time"))

    def test_review_status_does_not_imply_full_verification(self):
        records = [
            feature["properties"] for feature in load("facilities.geojson")["features"]
        ]
        counts = Counter(record["verification_status"] for record in records)
        self.assertEqual(
            counts,
            {
                "official_directory_match": 6,
                "official_identity_unresolved": 3,
                "not_independently_checked": 1992,
            },
        )
        review = load("metadata.json")["inventory_review"]
        self.assertFalse(review["facility_refresh_success"])
        self.assertEqual(review["quarantined"], 4)
        self.assertEqual(
            Counter(record["source_snapshot_category"] for record in records),
            {
                "fresh_school": 1339,
                "fresh_healthcare_tag_branch": 601,
                "original_hospital_tag_fallback": 61,
            },
        )

    def test_all_source_local_bodies_have_approximate_locators(self):
        locations = load("locations.geojson")["features"]
        areas = load("local_bodies.geojson")["features"]
        self.assertEqual(len(locations), 78)
        self.assertEqual(
            {feature["properties"]["id"] for feature in locations},
            {feature["properties"]["id"] for feature in areas},
        )
        self.assertEqual(
            Counter(feature["properties"]["type"] for feature in locations),
            {"gram_panchayat": 70, "municipality": 7, "corporation": 1},
        )
        for feature in locations:
            self.assertEqual(feature["geometry"]["type"], "Point")
            longitude, latitude = feature["geometry"]["coordinates"]
            self.assertTrue(75.5 < longitude < 76.2 and 11.1 < latitude < 11.9)
            self.assertEqual(
                feature["properties"]["location_kind"], "approximate_area_centre"
            )
            self.assertTrue(feature["properties"]["within_own_polygon"])

    def test_local_totals_include_the_unmatched_bucket(self):
        local = load("local_body_summary.json")
        for summary in load("scenario_summary.json"):
            year = summary["return_period_years"]
            self.assertEqual(
                sum(row["schools_total"] for row in local),
                summary["schools_total_mapped"],
            )
            self.assertEqual(
                sum(row["hospitals_total"] for row in local),
                summary["hospitals_total_mapped"],
            )
            self.assertEqual(
                sum(row[f"schools_overlap_{year}"] for row in local),
                summary["schools_overlap"],
            )
            self.assertEqual(
                sum(row[f"hospitals_overlap_{year}"] for row in local),
                summary["hospitals_overlap"],
            )
            self.assertAlmostEqual(
                sum(row[f"roads_overlap_km_{year}"] for row in local),
                summary["major_roads_overlap_km"],
                places=5,
            )


if __name__ == "__main__":
    unittest.main()
