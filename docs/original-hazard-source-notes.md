# Kozhikode flood-hazard screening map

The PNG and PDF compare the official historical-climate **10-, 25- and 50-year model footprints** across Kozhikode district. This is the hazard component of a first-pass flood-risk assessment, not a completed exposure, vulnerability or damage estimate.

## What it shows

Blue means a positive, non-NoData cell in the corresponding KSDMA historical raster. Grey means no inundation shown or NoData; **it does not establish safety**. The three scenarios have annual exceedance probabilities of approximately 10%, 4% and 2%. Return periods are not fixed schedules.

On the displayed 90 m projected grid, mapped footprints are approximately **144, 154 and 163 km²**, respectively. These are model-support areas inside the selected district boundary, including any river/water cells; not additional dry land flooded, affected built-up area, or verified event extents. Native-grid geodesic checks give about 145, 155 and 164 km² (under 1% difference). Differences reflect reprojection and boundary-cell selection, not measured uncertainty.

The maps show a branching river-corridor pattern, with broad clusters in the north-central/western part of the district and corridors in the south. The 50-year scenario shows a larger footprint than the 10-year scenario. No local-government or property risk rankings were calculated.

## Sources

- **Flood rasters:** [KSDMA Hazard Maps](https://sdma.kerala.gov.in/hazard-maps/), historical 10/25/50-year [ZIP](https://sdma.kerala.gov.in/wp-content/uploads/2026/06/1.-Flood-Return-Probability-Historical-10-25-50-years.zip). Downloaded 19 October 2026. Portal attribution: UNEP, UN GRID, CIMA Italy, KSDMA (2020); flood-return-probability assessment and RMSI/National Insurance Academy (2024). The files were uploaded in June 2026; this is not their climate baseline or observation date. No explicit reuse license identified on the portal; retain attribution and consult KSDMA for redistribution conditions.
- **Context and interpretation:** [KSDMA technical report](https://sdma.kerala.gov.in/wp-content/uploads/2022/06/Flood-Probability-Report-2022_Final.pdf) and [official Kozhikode historical atlas](https://sdma.kerala.gov.in/wp-content/uploads/2022/05/Kozhikode_Hist.pdf). The linked report describes approximately 1.4 km hydrology rescaled to 90 m and river-network inundation. It should not be read as parcel-scale validation of the newly uploaded rasters.
- **Boundary and city locator:** [Open Data Kerala district snapshot](https://github.com/opendatakerala/kl_district), `Kerala_districts.geojson`, retrieved 19 October 2026; an older community-maintained OSM snapshot, not a surveyed statutory boundary. © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). Filtered 845 mixed features to one valid Kozhikode district MultiPolygon; city location is the source's Kozhikode point. Source GeoJSON uses WGS84 longitude/latitude.

## How it was made

`make_flood_map.py` extracts positive raster support, reprojects by nearest neighbour to WGS 84 / UTM zone 43N (EPSG:32643), masks to the district using pixel centres, computes footprint area, and exports PNG/PDF and three COG GeoTIFFs. Source resolution is 0.000833333 degrees (3 arc-seconds, approximately 90 m). Display resolution is 90 m; it is not an accuracy claim. Raw raster values lack unit metadata and were **not interpreted as flood depths**. No new hydraulic simulation, weighting, hazard severity classification, flood observations or asset overlay was performed.

COG codes: `0` = outside district/NoData; `1` = no inundation shown (not safe); `2` = positive official model footprint. See `qa_summary.json` for numerical checks and package versions. To reproduce, download the linked inputs into the same structure and run `python3 make_flood_map.py` (requires numpy, rasterio, shapely, pyproj, matplotlib).

## Limits

This is primarily river-flood screening. Urban drainage failures, flash flooding below model resolution, coastal surge/tides, defences, recent works and dam-break scenarios are not comprehensively assessed. No current rainfall or river gauges were used. Areas outside blue cannot be declared safe. For evacuation, construction, insurance or property decisions, use official warnings and a site-specific study.
