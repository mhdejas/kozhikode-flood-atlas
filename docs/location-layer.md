# Kozhikode location layer source notes

## Method

- Input: `site/data/local_bodies.geojson`; the existing site boundary layer has 78 polygons (70 `gram_panchayat`, 7 `municipality`, 1 `corporation`) and is the reusable OSM-derived/Open Data Kerala boundary snapshot already used by the site. No Google Maps coordinates or listings were copied.
- Each polygon was transformed from EPSG:4326 to projected **EPSG:32643**. The projected polygon centroid was used when covered by its own polygon; otherwise `representative_point()` was used to guarantee an interior point. Output points are transformed back to EPSG:4326 for web GeoJSON.
- Every point is labelled **Approximate area centre — not the local-body office** through `location_kind`, `method`, and the source/coverage fields. These are not official coordinates, precise centres, actual offices, or flood-safe locations.

## Official verification

- [Kozhikode District Administration — Administrative Setup](https://kozhikode.nic.in/en/about-district/adminstration/) (page last updated 2018-05-30) states 70 panchayats, 7 municipalities (Vatakara, Koyilandy, Ramanattukara, Feroke, Payyoli, Koduvally, Mukkam), and 1 corporation (Kozhikode).
- [Kozhikode District Administration — Panchayaths](https://kozhikode.nic.in/en/about-district/adminstration/panchayaths/) lists 70 panchayat names (page last updated 2023-03-17).
- [Kerala LSGD Localbody Websites](https://lsgkerala.gov.in/en/website/web) provides names/codes/websites and filters, but the fetched directory exposes no comprehensive reusable office-coordinate download. No verified reusable full office-coordinate set was found or used.
- **Important identity caveat:** the official totals match 70/7/1, but exact name identity is **not claimed as verified**; spelling/transliteration variants exist between the official list and boundary attributes. See `location-quality.json` → `official_name_mismatches`.

## License/provenance

The boundary provenance is inherited from the existing site metadata: Open Data Kerala LSG boundary snapshot release 1.1.0, OSM-derived and ODbL. This output is a derived point layer; retain that attribution and ODbL notice when redistributing.
