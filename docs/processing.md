# Processing the map data

The checked-in website works without running these scripts. Its tables and flags are a dated release, not live updates.

## Download new OSM snapshots

Run requests one at a time and respect the public Overpass service. Each command records the query, source timestamp and checksum. A failed request is not a refresh. Raw responses can include OSM editor metadata; keep `.local-data/` out of the public repository.

```sh
python3 scripts/fetch_osm_snapshot.py schools
python3 scripts/fetch_osm_snapshot.py healthcare
python3 scripts/fetch_osm_snapshot.py health-amenity
python3 scripts/fetch_osm_snapshot.py major-roads
python3 scripts/merge_osm_snapshots.py .local-data/schools.json .local-data/healthcare.json .local-data/health-amenity.json --output .local-data/assets.json
```

The two health requests are separate on purpose. Both must succeed to cover both selected tag branches. They still do not establish a complete real-world register. This release could not refresh the amenity-only branch, so it retains some earlier hospital-tag records and documents the remaining gaps.

## Prepare the flood-analysis inputs

Install the geospatial packages listed in `scripts/requirements.txt`. The analysis command needs a working folder containing:

- `Kozhikode_boundary.geojson`: the supplied district polygon, copied from `site/data/district.geojson`.
- `expansion/local_bodies/local_bodies_web.geojson`: the community boundary snapshot, copied from `site/data/local_bodies.geojson`.
- `raster/`: the original KSDMA historical rasters named `Kerala_Flood_10_yr_Historical.tif`, `Kerala_Flood_25_yr_Historical.tif` and `Kerala_Flood_50_yr_Historical.tif`. Download them from the [publisher's hazard-map page](https://sdma.kerala.gov.in/hazard-maps/); they are not bundled or relicensed here.

Then run:

```sh
python3 scripts/analyze_reviewed_exposure.py --project-root /path/to/working-folder --assets .local-data/assets.json --roads .local-data/major-roads.json --output .local-data/analysis
```

The script tests full mapped facility geometry against original positive flood cells. It measures dissolved major-road linework in UTM 43N and assigns each facility once to a local body, retaining an unmatched bucket. Record symbols remain locators, not full campus outlines. Parking and animal-care name flags are held out for review rather than silently accepted as human-health records.

## Review before replacing the website data

Read the QA file, source dates, excluded records and class totals. Check changed identities and geometry; an OSM edit date is not a field-inspection date. Reconcile district and local totals and update the regression fixtures deliberately. Do not treat this as an unattended publishing pipeline.

The current source window is recorded in `source-snapshots.json`. New downloads can differ from this release. The raw source responses, original KSDMA rasters and private deployment ownership links are not included.

The optional context-preparation scripts require their separately documented terrain/waterway inputs. They do not create a new flood simulation or improve the approximately 90 m hazard grid.

## Rebuild the optional relief and waterway context

The website already includes these assets. To rebuild them, install the separate context dependencies and supply the original input tree:

```sh
python3 -m pip install -r scripts/requirements-context.txt
python3 scripts/prepare_context.py --input-root /path/to/kozhikode_flood
```

`--input-root` must contain `Kozhikode_boundary.geojson` and the supplied inputs under `expansion/improved_context/terrain/` and `expansion/improved_context/waterways/`. Raw source grids are not included in this repository.

By default, this command writes the four context files under `site/assets/` and `site/data/`. Its QA report goes to `tests/context_qa.generated.json`, outside the website. This rebuild covers the context assets only, not the full upstream analysis or a new flood simulation.
