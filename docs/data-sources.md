# Data sources

This page lists the sources used by the companion. It does not describe datasets that were not used or downloaded for this repository.

## Flood footprints

- **Kerala State Disaster Management Authority (KSDMA), hazard maps:** <https://sdma.kerala.gov.in/hazard-maps/>. The historical 10-, 25-, and 50-year model rasters are the flood-footprint inputs. The approximately 90 m grid is retained; terrain context did not resample, expand, shrink, smooth, or replace it. KSDMA publisher terms remain separate; no explicit raster reuse licence was identified in the source review.

## Boundaries and mapped assets

- **Open Data Kerala district boundary:** <https://github.com/opendatakerala/kl_district>. An older OSM-derived district snapshot, not a cadastral survey.
- **OpenStreetMap mapped assets:** <https://www.openstreetmap.org/copyright>. Schools, selected human-health tag records, major roads and place locators use dated 19 October 2026 snapshots. The health cohort includes clinics, centres and medical practices; its refresh is partial. They are community-mapped records, not a complete official inventory.

- **Open Data Kerala, LSG Kerala Data release 1.1.0:** <https://github.com/opendatakerala/lsg-kerala-data/releases/tag/1.1.0>. OSM-derived local-body snapshot under ODbL. It supplies the 78 community-mapped local bodies: 70 gram panchayats, 7 municipalities, and 1 corporation. These are not surveyed or asserted-current statutory boundaries.
- **District administration list:** <https://kozhikode.nic.in/en/about-district/adminstration/>. Its listed local-body counts provide a comparison check, not boundary validation.
- **OpenStreetMap waterway definitions:** <https://wiki.openstreetmap.org/wiki/Key:waterway>. The map includes 8,364 mapped waterway segments. They are mapped linework, not DEM-inferred streams, and do not describe depth, capacity, or flow. OSM-derived content is © OpenStreetMap contributors, ODbL.

## Terrain context

- **Copernicus DEM public-data registry:** <https://registry.opendata.aws/copernicus-dem/>.
- **Copernicus product and licence documentation:** <https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM>.

The GLO-30 product is a digital surface model (DSM), including vegetation and buildings. It is used only for relief shading and geographic context, not as a bare-earth terrain model, flow-routing layer, or new flood simulation.

## Observed flooding gap

No district-covering observed event layer was accepted (`site/data/observed_status.json` reports `available: false`). The source review used:

- **NRSC / ISRO Bhuvan Disaster Services:** <https://bhuvan-app1.nrsc.gov.in/disaster/disaster.php>
- **Global Flood Database v1 catalog and methods:** <https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1>
- **Global Flood Database HydroShare distribution:** <https://www.hydroshare.org/resource/6461528501c14f7c9d6b10d20dd4f657/>

Five candidate Global Flood Database event rasters did not intersect Kozhikode, and the Bhuvan portal did not expose a stable event-layer download with sufficient metadata. This is a bounded data gap, not evidence that the district was dry.

## Processing notes

Exposure calculations use original positive raster cells transformed as vectors to UTM zone 43N (EPSG:32643), rather than resampling the raster. Web display uses EPSG:3857. Facility tests use full mapped geometries; map symbols use representative points. Road lengths use a geometrically dissolved network, measured in UTM 43N.

The [inventory review](inventory-review.md) records the nine-record identity sample, held-out candidates and unsuccessful broader-source requests. Source dates do not establish current operation or field accuracy.
