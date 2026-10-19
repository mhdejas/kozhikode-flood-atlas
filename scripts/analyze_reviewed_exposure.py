#!/usr/bin/env python3
"""Recalculate exposure using the original KSDMA raster cells.

The school and major-road definitions are unchanged. Human-health records use the
broader documented tag cohort; the legacy hospital keys remain for compatibility.
This script reads acquired snapshots only. It never downloads or publishes data.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.windows import Window, from_bounds
from shapely import make_valid
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import polygonize, transform, unary_union
from pyproj import Transformer

SCENARIOS = (10, 25, 50)
ALLOWED_ROADS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}
WARNING_RE = re.compile(r"\b(centre|center|clinic|dispensary)\b", re.I)
QUARANTINE_NAME_RE = re.compile(r"\b(parking|vet(?:erinary|inary)?|animal)\b", re.I)
HEALTH_AMENITIES = {"hospital", "clinic", "doctors"}
HEALTHCARE_CLASSES = {
    "hospital",
    "clinic",
    "centre",
    "health_post",
    "doctor",
    "doctors",
    "community_health_worker",
    "rehabilitation",
}
PUBLIC_META = ("timestamp", "version", "changeset", "check_date")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def coords(values):
    return [(p["lon"], p["lat"]) for p in values if "lon" in p and "lat" in p]


def osmgeom(e):
    """Exact geometry construction retained from the original analysis."""
    typ = e["type"]
    if typ == "node":
        return Point(e["lon"], e["lat"])
    if typ == "way":
        xy = coords(e.get("geometry", []))
        if len(xy) < 2:
            return None
        return Polygon(xy) if len(xy) >= 4 and xy[0] == xy[-1] else LineString(xy)
    if typ == "relation":
        outer, inner = [], []
        for member in e.get("members", []):
            if member.get("type") != "way":
                continue
            xy = coords(member.get("geometry", []))
            if len(xy) < 2:
                continue
            (inner if member.get("role") == "inner" else outer).append(LineString(xy))
        if not outer:
            return None
        polys = list(polygonize(unary_union(outer)))
        if not polys:
            return None
        g = unary_union(polys)
        if inner:
            holes = list(polygonize(unary_union(inner)))
            if holes:
                g = g.difference(unary_union(holes))
        return g
    return None


def source_meta(e):
    tags = e.get("tags") or {}
    return {k: e[k] for k in PUBLIC_META if e.get(k) is not None} | (
        {"check_date": tags["check_date"]} if tags.get("check_date") else {}
    )


def display_name(tags):
    return tags.get("name:en") or tags.get("name") or ""


def norm(value):
    return re.sub(r"[^\w]+", "", value.casefold())


def health_class(tags):
    """Use an explicit healthcare tag, falling back to the amenity tag."""
    healthcare = str(tags.get("healthcare", "")).casefold()
    amenity = str(tags.get("amenity", "")).casefold()
    if healthcare in HEALTHCARE_CLASSES:
        return "doctor" if healthcare == "doctors" else healthcare
    if amenity in HEALTH_AMENITIES:
        return "doctor" if amenity == "doctors" else amenity
    return ""


def load_hazard(root: Path, period: int, boundary_ll, fwd):
    raster = next(
        (root / "raster").rglob(f"Kerala_Flood_{period}_yr_Historical.tif"), None
    )
    if raster is None:
        raise FileNotFoundError(f"missing raster for {period}-year scenario")
    with rasterio.open(raster) as src:
        if str(src.crs) != "EPSG:4326":
            raise AssertionError(f"unexpected CRS {src.crs} in {raster}")
        w = from_bounds(*boundary_ll.bounds, transform=src.transform)
        c0, r0 = int(np.floor(w.col_off)), int(np.floor(w.row_off))
        c1, r1 = int(np.ceil(w.col_off + w.width)), int(np.ceil(w.row_off + w.height))
        window = Window(c0, r0, c1 - c0, r1 - r0)
        arr = src.read(1, window=window, masked=True)
        positive = (~np.ma.getmaskarray(arr)) & (arr.filled(0) > 0)
        pieces = [
            transform(fwd, shape(g))
            for g, val in shapes(
                positive.astype("uint8"),
                mask=positive,
                transform=src.window_transform(window),
            )
            if val == 1
        ]
        hazard = unary_union(pieces).intersection(transform(fwd, boundary_ll))
        if not hazard.is_valid:
            hazard = make_valid(hazard)
        return (
            hazard,
            raster,
            {
                "sha256": sha256(raster),
                "crs": str(src.crs),
                "transform": list(src.transform),
                "positive_cells": int(positive.sum()),
                "native_resolution_degrees": [
                    abs(src.transform.a),
                    abs(src.transform.e),
                ],
            },
        )


def feature_collection(records, inv, propfn):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(transform(inv, r["geometry"])),
                "properties": propfn(r),
            }
            for r in records
        ],
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main(argv=None):
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Working folder containing the original rasters and boundary inputs",
    )
    ap.add_argument(
        "--assets", type=Path, required=True, help="fresh osm_assets_raw.json"
    )
    ap.add_argument(
        "--roads", type=Path, required=True, help="fresh osm_roads_raw.json"
    )
    ap.add_argument("--output", type=Path, default=here)
    args = ap.parse_args(argv)
    root, out = args.project_root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    boundary_ll = shape(
        json.loads((root / "Kozhikode_boundary.geojson").read_text())["features"][0][
            "geometry"
        ]
    )
    if not boundary_ll.is_valid:
        raise AssertionError("boundary is invalid")
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform
    inv = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True).transform
    boundary = transform(fwd, boundary_ll)
    assets_raw, roads_raw = json.loads(args.assets.read_text()), json.loads(
        args.roads.read_text()
    )
    qa = {
        "analysis_crs": "EPSG:32643",
        "boundary_valid": boundary.is_valid,
        "boundary_area_km2": boundary.area / 1e6,
        "input_counts": {
            "assets_raw_elements": len(assets_raw.get("elements", [])),
            "roads_raw_elements": len(roads_raw.get("elements", [])),
        },
        "missing_geometry": [],
        "repaired_geometry": [],
        "excluded_outside": Counter(),
        "duplicates": [],
        "lifecycle_ambiguous_flags": [],
        "freshness_note": "OSM retrieval metadata describes source freshness only; no physical, closure or operational validation is performed.",
        "inventory_label_warning": "Mapped OSM hospitals/health facilities are not all actual hospitals and do not establish current operational status.",
    }
    assets, raw_assets, quarantined, settlements, seen = [], [], [], [], set()
    for e in assets_raw.get("elements", []):
        oid = f"{e.get('type')}/{e.get('id')}"
        if oid in seen:
            qa["duplicates"].append(
                {"removed": oid, "reason": "duplicate OSM type/id in raw input"}
            )
            continue
        seen.add(oid)
        tags = e.get("tags") or {}
        amenity = str(tags.get("amenity", "")).casefold()
        healthcare = str(tags.get("healthcare", "")).casefold()
        if amenity == "school":
            kind = "school"
        elif amenity in HEALTH_AMENITIES or healthcare in HEALTHCARE_CLASSES:
            kind = "hospital"
        elif tags.get("place") in ["city", "town", "village", "hamlet"]:
            kind = "settlement"
        else:
            continue
        geom = osmgeom(e)
        if geom is None or geom.is_empty:
            qa["missing_geometry"].append(oid)
            continue
        if not geom.is_valid:
            geom = make_valid(geom)
            qa["repaired_geometry"].append(oid)
        geom = transform(fwd, geom)
        if not boundary.covers(geom.representative_point()):
            qa["excluded_outside"][kind] += 1
            continue
        geom = geom.intersection(boundary)
        source_amenity = amenity or None
        source_healthcare = healthcare or None
        source_snapshot = e.get("_source_snapshot") or {}
        record_health_class = health_class(tags) if kind == "hospital" else ""
        normalized_amenity = "doctor" if amenity == "doctors" else amenity
        normalized_healthcare = "doctor" if healthcare == "doctors" else healthcare
        tag_conflict = bool(
            kind == "hospital"
            and amenity in HEALTH_AMENITIES
            and healthcare in HEALTHCARE_CLASSES
            and normalized_amenity != normalized_healthcare
        )
        rec = {
            "osm_id": oid,
            "name": display_name(tags),
            "kind": kind,
            "public_label": "Health records" if kind == "hospital" else "",
            "place": tags.get("place", ""),
            "geometry": geom,
            "source_type": e["type"],
            "verification_status": "not_independently_checked",
            "source_amenity": source_amenity,
            "source_healthcare": source_healthcare,
            "source_snapshot_category": source_snapshot.get("category"),
            "source_snapshot_time": source_snapshot.get("osm_base")
            or e.get("timestamp")
            or e.get("version"),
            "healthcare_class": record_health_class or None,
            "source_class_type": (
                "osm_tag_classification_not_official_verification"
                if kind == "hospital"
                else None
            ),
            "tag_conflict": tag_conflict,
            "classification_warning": (
                "REVIEW FLAG: name suggests centre/clinic/dispensary; this is not a definitive reclassification."
                if kind == "hospital" and WARNING_RE.search(display_name(tags))
                else ""
            ),
            "source_metadata": source_meta(e),
        }
        if kind == "settlement":
            settlements.append(rec)
        else:
            ambiguous = any(
                k in tags
                for k in (
                    "disused",
                    "abandoned",
                    "demolished",
                    "construction",
                    "proposed",
                    "razed",
                    "was:amenity",
                    "was:healthcare",
                )
            )
            if ambiguous:
                rec["lifecycle_ambiguous"] = True
                qa["lifecycle_ambiguous_flags"].append(
                    {
                        "osm_id": oid,
                        "tags_present": sorted(
                            k
                            for k in tags
                            if k
                            in (
                                "disused",
                                "abandoned",
                                "demolished",
                                "construction",
                                "proposed",
                                "razed",
                                "was:amenity",
                                "was:healthcare",
                            )
                        ),
                    }
                )
            raw_assets.append(rec)
            veterinary = (
                str(tags.get("healthcare", "")).casefold() == "veterinary"
                or str(tags.get("healthcare:speciality", "")).casefold() == "veterinary"
            )
            parking_name = bool(re.search(r"\bparking\b", display_name(tags), re.I))
            quarantine_reason = (
                "name suggests parking"
                if kind == "hospital" and parking_name
                else (
                    "name or healthcare tag suggests veterinary/animal care"
                    if kind == "hospital"
                    and (QUARANTINE_NAME_RE.search(display_name(tags)) or veterinary)
                    else ""
                )
            )
            if quarantine_reason:
                quarantined.append(
                    {**rec, "quarantine_reason": quarantine_reason, "raw_tags": tags}
                )
            else:
                assets.append(rec)
    # Exact original category-aware duplicate rules.
    # Deduplicate before screening so the raw definition remains comparable.
    quarantine_by_id = {record["osm_id"]: record for record in quarantined}
    assets = list(raw_assets)
    assets.sort(
        key=lambda r: (
            r["kind"],
            0 if r["source_type"] == "relation" else 1 if r["geometry"].area > 0 else 2,
            r["osm_id"],
        )
    )
    kept = []
    for a in assets:
        duplicate = None
        why = ""
        for b in kept:
            if a["kind"] != b["kind"]:
                continue
            pa, pb = (
                a["geometry"].representative_point(),
                b["geometry"].representative_point(),
            )
            same_name = bool(
                norm(a["name"])
                and norm(b["name"])
                and norm(a["name"]) == norm(b["name"])
            )
            if same_name and pa.distance(pb) <= 100:
                duplicate, why = b, "same normalized name within 100 m"
                break
            if (
                b["geometry"].area > 0
                and b["geometry"].covers(pa)
                and (same_name or not norm(a["name"]) or not norm(b["name"]))
            ):
                duplicate, why = b, "contained point/footprint, same or missing name"
                break
        if duplicate:
            qa["duplicates"].append(
                {"removed": a["osm_id"], "kept": duplicate["osm_id"], "reason": why}
            )
        else:
            kept.append(a)
    raw_assets = kept
    quarantined = [
        quarantine_by_id[r["osm_id"]] for r in kept if r["osm_id"] in quarantine_by_id
    ]
    assets = [r for r in kept if r["osm_id"] not in quarantine_by_id]
    roads, seen = [], set()
    for e in roads_raw.get("elements", []):
        tags, oid = e.get("tags") or {}, f"{e.get('type')}/{e.get('id')}"
        if (
            e.get("type") != "way"
            or tags.get("highway") not in ALLOWED_ROADS
            or oid in seen
        ):
            continue
        seen.add(oid)
        xy = coords(e.get("geometry", []))
        if len(xy) < 2:
            qa["missing_geometry"].append(oid)
            continue
        geom = transform(fwd, LineString(xy)).intersection(boundary)
        if geom.is_empty or geom.length == 0:
            qa["excluded_outside"]["road"] += 1
            continue
        roads.append(
            {
                "osm_id": oid,
                "name": display_name(tags),
                "geometry": geom,
                "highway": tags["highway"],
                "bridge": tags.get("bridge", "no"),
                "tunnel": tags.get("tunnel", "no"),
                "source_metadata": source_meta(e),
            }
        )
    all_roads = unary_union([r["geometry"] for r in roads]) if roads else LineString()
    elevated = (
        unary_union(
            [
                r["geometry"]
                for r in roads
                if r["bridge"] not in ["no", "false", "0", ""]
                or r["tunnel"] not in ["no", "false", "0", ""]
            ]
        )
        if roads
        else LineString()
    )
    local_path = root / "expansion/local_bodies/local_bodies_web.geojson"
    local_features = json.loads(local_path.read_text())["features"]
    if len(local_features) != 78:
        raise AssertionError("expected exactly 78 local bodies")
    locals_ = [
        {**f["properties"], "geometry": transform(fwd, shape(f["geometry"]))}
        for f in local_features
    ]
    hazards, hazard_meta, summaries = {}, {}, []
    for period in SCENARIOS:
        hazards[period], raster, hazard_meta[period] = load_hazard(
            root, period, boundary_ll, fwd
        )
        h = hazards[period]
        for r in assets:
            r[f"overlap_{period}yr"] = bool(r["geometry"].intersects(h))
        for r in raw_assets:
            r[f"overlap_{period}yr_raw_definition"] = bool(r["geometry"].intersects(h))
        for r in settlements:
            r[f"point_overlap_{period}yr"] = bool(r["geometry"].intersects(h))
        for r in roads:
            r[f"overlap_{period}yr_km"] = r["geometry"].intersection(h).length / 1000
        health_classes = {}
        for record in assets:
            if record["kind"] == "hospital":
                cls = record["healthcare_class"] or "unknown"
                health_classes.setdefault(cls, {"total_mapped": 0, "overlap": 0})
                health_classes[cls]["total_mapped"] += 1
                health_classes[cls]["overlap"] += int(record[f"overlap_{period}yr"])
        summaries.append(
            {
                "return_period_years": period,
                "annual_exceedance_probability_pct": 100 / period,
                "footprint_km2": h.area / 1e6,
                "schools_total_mapped": sum(r["kind"] == "school" for r in assets),
                "schools_overlap": sum(
                    r["kind"] == "school" and r[f"overlap_{period}yr"] for r in assets
                ),
                "hospitals_total_mapped": sum(r["kind"] == "hospital" for r in assets),
                "hospitals_overlap": sum(
                    r["kind"] == "hospital" and r[f"overlap_{period}yr"] for r in assets
                ),
                "health_scope": "Human clinical health records; internal kind=hospital is retained for frontend compatibility and does not mean all records are hospitals.",
                "health_classes": health_classes,
                "health_records_total_before_screening": sum(
                    r["kind"] == "hospital" for r in raw_assets
                ),
                "health_records_overlap_before_screening": sum(
                    r["kind"] == "hospital" and r[f"overlap_{period}yr_raw_definition"]
                    for r in raw_assets
                ),
                "major_roads_total_km": all_roads.length / 1000,
                "major_roads_overlap_km": all_roads.intersection(h).length / 1000,
                "bridge_tunnel_overlap_km": elevated.intersection(h).length / 1000,
                "settlement_nodes_total": len(settlements),
                "settlement_nodes_overlap": sum(
                    r[f"point_overlap_{period}yr"] for r in settlements
                ),
            }
        )
    # Native-grid independent checks: sample original raster at representative points in overlap.
    qa["native_grid_spot_checks"] = []
    with rasterio.open(
        next((root / "raster").rglob("Kerala_Flood_50_yr_Historical.tif"))
    ) as src:
        if abs(src.transform.a - 1 / 1200) >= 1e-9:
            raise AssertionError("unexpected native raster resolution")
        for kind in ("school", "hospital"):
            for r in [x for x in assets if x["kind"] == kind and x["overlap_50yr"]][:3]:
                p = r["geometry"].intersection(hazards[50]).representative_point()
                lon, lat = inv(p.x, p.y)
                value = next(src.sample([(lon, lat)], masked=True))[0]
                qa["native_grid_spot_checks"].append(
                    {
                        "osm_id": r["osm_id"],
                        "kind": kind,
                        "native_positive_at_overlap_point": bool(
                            not np.ma.is_masked(value) and value > 0
                        ),
                        "note": "Original positive raster-cell polygons; no resampling.",
                    }
                )
    # Local-body attribution by representative point; exactly one body or explicit UNMATCHED.
    assignments = {}
    qa["local_body_multiple_matches"] = []
    for record in assets:
        point = record["geometry"].representative_point()
        hits = [body["id"] for body in locals_ if body["geometry"].covers(point)]
        assignments[record["osm_id"]] = hits[0] if hits else "UNMATCHED"
        if len(hits) > 1:
            qa["local_body_multiple_matches"].append(
                {"osm_id": record["osm_id"], "candidates": hits, "selected": hits[0]}
            )
    lb_rows = []
    for body in locals_ + [
        {
            "id": "UNMATCHED",
            "name": "UNMATCHED",
            "type": "unmatched",
            "geometry": boundary.difference(
                unary_union([x["geometry"] for x in locals_])
            ),
        }
    ]:
        row = {k: body[k] for k in ("id", "name", "type")}
        body_assets = [r for r in assets if assignments[r["osm_id"]] == body["id"]]
        body_roads = [r for r in roads if body["geometry"].intersects(r["geometry"])]
        row.update(
            schools_total=sum(r["kind"] == "school" for r in body_assets),
            hospitals_total=sum(r["kind"] == "hospital" for r in body_assets),
            roads_total_km=(
                unary_union(
                    [r["geometry"].intersection(body["geometry"]) for r in body_roads]
                ).length
                / 1000
                if body_roads
                else 0.0
            ),
        )
        for period in SCENARIOS:
            row[f"schools_overlap_{period}"] = sum(
                r["kind"] == "school" and r[f"overlap_{period}yr"] for r in body_assets
            )
            row[f"hospitals_overlap_{period}"] = sum(
                r["kind"] == "hospital" and r[f"overlap_{period}yr"]
                for r in body_assets
            )
            row[f"roads_overlap_km_{period}"] = (
                all_roads.intersection(body["geometry"])
                .intersection(hazards[period])
                .length
                / 1000
            )
        lb_rows.append(row)
    assert len(assets) + len(quarantined) == len(raw_assets)
    assert all(
        check["native_positive_at_overlap_point"]
        for check in qa["native_grid_spot_checks"]
    )
    retained_health_classes = Counter(
        r["healthcare_class"] or "unknown" for r in assets if r["kind"] == "hospital"
    )
    before_screening_health_classes = Counter(
        r["healthcare_class"] or "unknown"
        for r in raw_assets
        if r["kind"] == "hospital"
    )
    quarantined_health_classes = Counter(
        r["healthcare_class"] or "unknown"
        for r in quarantined
        if r["kind"] == "hospital"
    )
    qa["health_class_reconciliation"] = {
        "screened": dict(retained_health_classes),
        "before_screening": dict(before_screening_health_classes),
        "quarantined": dict(quarantined_health_classes),
    }
    qa["counts_by_source_snapshot"] = {
        "screened": dict(
            Counter(r.get("source_snapshot_category") or "unknown" for r in assets)
        ),
        "before_screening": dict(
            Counter(r.get("source_snapshot_category") or "unknown" for r in raw_assets)
        ),
        "quarantined": dict(
            Counter(r.get("source_snapshot_category") or "unknown" for r in quarantined)
        ),
    }
    assert (
        sum(retained_health_classes.values()) == summaries[0]["hospitals_total_mapped"]
    )
    assert (
        sum(before_screening_health_classes.values())
        == summaries[0]["health_records_total_before_screening"]
    )
    assert all(
        sum(values["total_mapped"] for values in summary["health_classes"].values())
        == summary["hospitals_total_mapped"]
        for summary in summaries
    )
    for summary in summaries:
        period = summary["return_period_years"]
        for category in ("schools", "hospitals"):
            assert (
                sum(row[f"{category}_total"] for row in lb_rows)
                == summary[f"{category}_total_mapped"]
            )
            assert (
                sum(row[f"{category}_overlap_{period}"] for row in lb_rows)
                == summary[f"{category}_overlap"]
            )
        assert (
            abs(
                sum(row[f"roads_overlap_km_{period}"] for row in lb_rows)
                - summary["major_roads_overlap_km"]
            )
            < 0.001
        )
    assigned = sum(r["schools_total"] + r["hospitals_total"] for r in lb_rows)
    qa["local_body_count"] = 78
    qa["local_body_assignment"] = {
        "facility_records": len(assets),
        "assigned": assigned,
        "unmatched": next(
            r["schools_total"] + r["hospitals_total"]
            for r in lb_rows
            if r["id"] == "UNMATCHED"
        ),
        "explicit_unmatched_row": True,
    }
    qa["excluded_outside"] = dict(qa["excluded_outside"])
    qa["retained_asset_counts"] = dict(Counter(r["kind"] for r in assets))
    qa["quarantine"] = {
        "count": len(quarantined),
        "records": [
            {"osm_id": r["osm_id"], "reason": r["quarantine_reason"]}
            for r in quarantined
        ],
        "note": "Review quarantine for public clinical-health totals; not a verified assertion about current use or operation.",
    }
    qa["major_road_ways_retained"] = len(roads)
    qa["major_road_total_km_union"] = all_roads.length / 1000
    qa["source_files"] = {
        "assets": str(args.assets),
        "roads": str(args.roads),
        "assets_sha256": sha256(args.assets),
        "roads_sha256": sha256(args.roads),
        "hazards": hazard_meta,
    }
    for p, meta_file in (
        (args.assets, args.assets.with_name("assets_acquisition.json")),
        (args.roads, args.roads.with_name("roads_acquisition.json")),
    ):
        if meta_file.exists():
            m = json.loads(meta_file.read_text())
            qa.setdefault("osm_source_metadata", {})[p.name] = {
                k: m.get(k)
                for k in (
                    "retrieved_at_utc",
                    "fetched_utc",
                    "source_osm_base_timestamp",
                    "source_osm3s_version",
                    "status",
                    "comparison",
                )
                if m.get(k) is not None
            }
    old_assets = root / "exposure/facilities_exposure.geojson"
    old_roads = root / "exposure/major_roads_exposure.geojson"
    qa["old_vs_refreshed_counts"] = {
        "old_facilities": (
            len(json.loads(old_assets.read_text()).get("features", []))
            if old_assets.exists()
            else None
        ),
        "refreshed_facilities_screened": len(assets),
        "refreshed_facilities_before_screening": len(raw_assets),
        "refreshed_quarantined": len(quarantined),
        "old_roads": (
            len(json.loads(old_roads.read_text()).get("features", []))
            if old_roads.exists()
            else None
        ),
        "refreshed_roads": len(roads),
    }
    # Public properties omit raw tags and usernames/UIDs, while retaining source edit metadata.
    public = lambda r: {
        k: v for k, v in r.items() if k not in ("geometry", "source_metadata")
    } | {f"source_{k}": v for k, v in r.get("source_metadata", {}).items()}
    write_json(
        out / "facilities_exposure.geojson", feature_collection(assets, inv, public)
    )
    write_json(
        out / "quarantined_records.geojson",
        feature_collection(
            quarantined,
            inv,
            lambda r: public(r)
            | {"quarantine_reason": r["quarantine_reason"], "raw_tags": r["raw_tags"]},
        ),
    )
    write_json(
        out / "major_roads_exposure.geojson", feature_collection(roads, inv, public)
    )
    write_json(
        out / "settlements_context.geojson",
        feature_collection(settlements, inv, public),
    )
    point_records = [
        {**r, "geometry": r["geometry"].representative_point()} for r in assets
    ]
    write_json(
        out / "facilities.geojson", feature_collection(point_records, inv, public)
    )
    write_json(out / "roads.geojson", feature_collection(roads, inv, public))
    for period in SCENARIOS:
        overlap = all_roads.intersection(hazards[period])
        write_json(
            out / f"road_overlap_{period}.geojson",
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": mapping(transform(inv, overlap)),
                        "properties": {
                            "return_period_years": period,
                            "overlap_km": overlap.length / 1000,
                            "meaning": "planar mapped-road overlap, not inundation or closure",
                        },
                    }
                ],
            },
        )
    write_json(out / "scenario_summary.json", summaries)
    write_json(out / "local_body_summary.json", lb_rows)
    with (out / "local_body_summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lb_rows[0].keys())
        w.writeheader()
        w.writerows(lb_rows)
    write_json(out / "inventory_refresh_qa.json", qa)
    print(
        json.dumps(
            {
                "output": str(out),
                "facilities": len(assets),
                "roads": len(roads),
                "local_bodies": 78,
                "scenarios": summaries,
                "qa": str(out / "inventory_refresh_qa.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
