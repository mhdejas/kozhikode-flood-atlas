# What was checked—and what still needs checking

The map is more useful with dates and gaps shown openly. It is not a verified list of every school, health service, road or drain.

## Included records

The screened inventory has 1,339 school records and 662 health records. Health types follow OSM tags: 437 hospital class, 173 clinic, 28 centre, 12 doctor/practice and 12 rehabilitation. A type label does not establish current use or official clinical classification.

The school and healthcare-tag source time is Schools: 19 Oct 2026, 18:52 IST. Healthcare-tag branch: 19 Oct 2026, 18:52 IST. 61 retained hospital-tagged records: 19 Oct 2026, 15:51 IST. Four parking/animal-care candidates are held out rather than silently counted as human-health records. [Held-out records](held_out_records.csv).

The amenity-only health query failed. Sixty-one earlier hospital-tagged records are retained, and amenity-only clinic/practice records may be absent. These are a partial refresh and a broader cohort, not an improvement to the flood model.

## Independent identity checks

Nine mapped records were checked against official sources. Six had a name-and-locality match; three were unresolved. The other 1,992 included facility records were not independently checked. A match does not prove current operation, coordinates, campus boundaries or flood impact. [Review sample and evidence links](identity_check_sample.csv).

## Roads and waterways

The major-road refresh succeeded; the 3,248 queried source ways had no tag or geometry changes from the earlier download. The exposure analysis retains 1,932 in-district way records and dissolves linework before measuring length. Not every road class is included.

The full-road query failed. A bounded Geofabrik fallback download also timed out; its incomplete file was deleted and no layer or statistics were invented. Smaller roads remain a coverage gap. [Fallback record](all-road-fallback.json).

The 8,364 mapped waterway segments retain their earlier 19 October source snapshot (17:17 IST). The repeat query failed. Their presence does not establish drainage capacity, and missing lines do not mean no drain exists.

## Local-body markers

All 78 polygons in the community boundary snapshot have an inside-area locator: 70 gram panchayats, seven municipalities and one corporation. These are approximate centres, not office coordinates. Count agreement with an official administrative list does not validate every name or boundary. The polygons are not presented as a current statutory survey.

## What the map cannot establish

The official KSDMA flood footprint remains about 90 m. The 30 m Copernicus surface relief is context only. The map cannot resolve every small drain, establish flood depth at a building, prove road passability or tell whether a house is safe. Exposure overlap is not a complete flood-risk assessment.
