#!/usr/bin/env python3
"""Build optional terrain and waterway context assets for the local site.

This script does not create or alter flood analysis. It prepares cartographic
context from supplied local inputs only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import array_bounds
from rasterio.warp import (
    Resampling,
    calculate_default_transform,
    reproject,
    transform_bounds,
)
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry

WEB_CRS = "EPSG:3857"
WGS84_CRS = "EPSG:4326"
UTM_CRS = "EPSG:32643"
ATTRIBUTION = (
    "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus "
    "Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European "
    "Union and ESA; all rights reserved"
)
OSM_LICENSE = (
    "OpenStreetMap data © OpenStreetMap contributors, available under the Open "
    "Data Commons Open Database License (ODbL)."
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded_coordinates(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [rounded_coordinates(item) for item in value]
    if isinstance(value, (float, int)):
        return round(float(value), 6)
    return value


def paths(input_root: Path, site_dir: Path, qa_file: Path) -> dict[str, Path]:
    return {
        "boundary": input_root / "Kozhikode_boundary.geojson",
        "raster": input_root / "expansion/improved_context/terrain/hillshade_utm43.tif",
        "terrain_metadata": input_root
        / "expansion/improved_context/terrain/terrain_metadata.json",
        "waterways": input_root
        / "expansion/improved_context/waterways/waterways_context.geojson",
        "waterways_metadata": input_root
        / "expansion/improved_context/waterways/waterways_metadata.json",
        "relief": site_dir / "assets/terrain-relief.webp",
        "district_mark": site_dir / "assets/district-mark.svg",
        "waterways_output": site_dir / "data/waterways.geojson",
        "metadata_output": site_dir / "data/context_metadata.json",
        "qa": qa_file,
    }


def boundary_geometry(path: Path) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return shape(payload["features"][0]["geometry"])


def make_relief(source: Path, boundary_path: Path, output: Path) -> dict[str, Any]:
    with rasterio.open(source) as raster:
        source_array = raster.read(1).astype("float32")
        destination_transform, width, height = calculate_default_transform(
            raster.crs,
            WEB_CRS,
            raster.width,
            raster.height,
            *raster.bounds,
            resolution=(30, 30),
        )
        destination = np.full((height, width), np.nan, dtype="float32")
        reproject(
            source_array,
            destination,
            src_transform=raster.transform,
            src_crs=raster.crs,
            src_nodata=raster.nodata,
            dst_transform=destination_transform,
            dst_crs=WEB_CRS,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    boundary = boundary_geometry(boundary_path)
    boundary_web = transform_geometry(
        Transformer.from_crs(WGS84_CRS, WEB_CRS, always_xy=True).transform,
        boundary,
    )
    inside = geometry_mask(
        [mapping(boundary_web)],
        out_shape=destination.shape,
        transform=destination_transform,
        invert=True,
    )
    valid = np.isfinite(destination) & inside
    clipped = np.clip(destination, 0, 1)
    gray = np.clip(
        248 + (np.nan_to_num(clipped, nan=0.5) - 0.5) * 42,
        214,
        255,
    ).astype("uint8")
    rgba = np.zeros((height, width, 4), dtype="uint8")
    rgba[:, :, :3] = gray[:, :, None]
    rgba[:, :, 3] = np.where(valid, 255, 0).astype("uint8")
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(output, "WEBP", lossless=True, method=6)
    bounds_wgs84 = list(
        transform_bounds(
            WEB_CRS,
            WGS84_CRS,
            *array_bounds(height, width, destination_transform),
            densify_pts=21,
        )
    )
    return {
        "bounds": [
            [bounds_wgs84[1], bounds_wgs84[0]],
            [bounds_wgs84[3], bounds_wgs84[2]],
        ],
        "width": width,
        "height": height,
        "display_grid_m": 30.0,
        "valid_pixels": int(valid.sum()),
        "nodata_pixels": int((~valid).sum()),
        "transform": list(destination_transform)[:6],
    }


def make_waterways(source: Path, output: Path) -> dict[str, Any]:
    waterways = gpd.read_file(source)
    if waterways.crs is None:
        raise ValueError("waterways input CRS is missing")
    before = len(waterways)
    simplified = waterways.to_crs(UTM_CRS)
    simplified["geometry"] = simplified.geometry.simplify(10.0, preserve_topology=False)
    simplified = simplified.to_crs(WGS84_CRS)
    fields = ["osm_id", "waterway", "name", "name:en", "intermittent", "tunnel"]
    features = []
    for _, row in simplified.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        properties = {}
        for field in fields:
            value = row.get(field)
            properties[field] = (
                None if isinstance(value, float) and math.isnan(value) else value
            )
        features.append(
            {
                "type": "Feature",
                "geometry": rounded_coordinates(mapping(geometry)),
                "properties": properties,
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features}, separators=(",", ":")
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "input_feature_count": before,
        "feature_count": len(features),
        "geometry_types": sorted({feature["geometry"]["type"] for feature in features}),
    }


def make_district_mark(boundary_path: Path, output: Path) -> dict[str, Any]:
    geometry = boundary_geometry(boundary_path)
    if geometry.geom_type == "MultiPolygon":
        geometry = max(geometry.geoms, key=lambda polygon: polygon.area)
    ring = list(geometry.exterior.coords)
    min_x, min_y, max_x, max_y = geometry.bounds
    scale_x = 180 / (max_x - min_x)
    scale_y = 180 / (max_y - min_y)
    points = [
        (10 + (x - min_x) * scale_x, 190 - (y - min_y) * scale_y) for x, y in ring
    ]
    path_data = "M " + " ".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
        f'<path d="{path_data}" fill="currentColor" fill-rule="evenodd"/></svg>\n'
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    return {"vertex_count": len(ring), "viewBox": "0 0 200 200"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root", required=True, type=Path, help="Original kozhikode_flood root"
    )
    parser.add_argument(
        "--site-dir", type=Path, help="Website directory (default: repository/site)"
    )
    parser.add_argument(
        "--qa-file",
        type=Path,
        help="QA JSON path (default: repository/tests/context_qa.generated.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = Path(__file__).resolve().parents[1]
    site_dir = args.site_dir or repository / "site"
    qa_file = args.qa_file or repository / "tests/context_qa.generated.json"
    input_root = args.input_root.resolve()
    output_paths = paths(input_root, site_dir, qa_file)
    required = [
        output_paths["boundary"],
        output_paths["raster"],
        output_paths["terrain_metadata"],
        output_paths["waterways"],
        output_paths["waterways_metadata"],
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing required input files:\n- " + "\n- ".join(missing))

    relief = make_relief(
        output_paths["raster"], output_paths["boundary"], output_paths["relief"]
    )
    waterways = make_waterways(
        output_paths["waterways"], output_paths["waterways_output"]
    )
    district_mark = make_district_mark(
        output_paths["boundary"], output_paths["district_mark"]
    )
    source_files = [
        output_paths["raster"],
        output_paths["terrain_metadata"],
        output_paths["waterways"],
        output_paths["waterways_metadata"],
        output_paths["boundary"],
    ]
    source_hashes = {
        str(path.relative_to(input_root)): sha256(path) for path in source_files
    }
    terrain_metadata = json.loads(
        output_paths["terrain_metadata"].read_text(encoding="utf-8")
    )
    waterways_metadata = json.loads(
        output_paths["waterways_metadata"].read_text(encoding="utf-8")
    )
    contract = {
        "terrain": {
            "bounds": relief["bounds"],
            "image_url": "assets/terrain-relief.webp",
            "source_grid_m": 30,
            "display_grid_m": relief["display_grid_m"],
            "source": {
                "raster": str(output_paths["raster"].relative_to(input_root)),
                "crs": "EPSG:32643",
                "warped_crs": WEB_CRS,
                "attribution": terrain_metadata.get("source", {}).get(
                    "attribution", ATTRIBUTION
                ),
                "source_metadata": str(
                    output_paths["terrain_metadata"].relative_to(input_root)
                ),
            },
            "limits": [
                "Cartographic DSM hillshade context only; not bare-earth terrain or a hydrological model.",
                "Strict district mask; alpha 0 is nodata. Does not improve the ~90 m flood footprint or establish house safety.",
            ],
        },
        "waterways": {
            "file": "data/waterways.geojson",
            "feature_count": waterways["feature_count"],
            "source": {
                "file": str(output_paths["waterways"].relative_to(input_root)),
                "license": waterways_metadata.get("license", OSM_LICENSE),
                "metadata": str(
                    output_paths["waterways_metadata"].relative_to(input_root)
                ),
                "simplification": "10 m tolerance in EPSG:32643 for context display; output EPSG:4326 rounded to 6 decimals",
            },
            "limits": [
                "OSM mapped centerlines are not drainage capacity, culvert conveyance, bankfull width, or a hydraulic model."
            ],
        },
        "flood_grid_m_approx": 90,
        "terrain_grid_m": 30,
        "source_notes": [
            ATTRIBUTION,
            OSM_LICENSE,
            "No new flood analysis is performed by this script.",
        ],
        "source_hashes_sha256": source_hashes,
    }
    output_paths["metadata_output"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["metadata_output"].write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    qa = {
        "terrain": {
            **relief,
            "output_sha256": sha256(output_paths["relief"]),
            "crs": WEB_CRS,
            "source_crs": UTM_CRS,
        },
        "waterways": {
            **waterways,
            "output_sha256": sha256(output_paths["waterways_output"]),
        },
        "district_mark": {
            **district_mark,
            "output_sha256": sha256(output_paths["district_mark"]),
        },
        "source_hashes_sha256": source_hashes,
    }
    qa_file.parent.mkdir(parents=True, exist_ok=True)
    qa_file.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "site": str(site_dir),
                "qa": str(qa_file),
                "outputs": [
                    str(output_paths[key])
                    for key in (
                        "relief",
                        "district_mark",
                        "waterways_output",
                        "metadata_output",
                    )
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
