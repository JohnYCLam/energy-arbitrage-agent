"""
Generate 5 Victoria sub-region polygons from location points.

This script:
1) downloads the Australia states GeoJSON,
2) extracts Victoria,
3) builds Voronoi cells from the 5 representative weather points,
4) clips each cell to Victoria, and
5) writes a GeoJSON for frontend map rendering.

Dependencies:
    pip install shapely scipy
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from urllib.request import urlopen

from scipy.spatial import Voronoi
from shapely.geometry import MultiPolygon, Polygon, shape, mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.locations import VICTORIA_WEATHER_LOCATIONS

STATES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/rowanhogan/australian-states/master/states.geojson"
)
OUTPUT_PATH = (
    PROJECT_ROOT
    / "frontend"
    / "v1_observability"
    / "src"
    / "assets"
    / "vic_regions.geojson"
)


def _voronoi_finite_polygons_2d(vor: Voronoi, radius: float = 1000):
    """
    Reconstruct finite Voronoi regions from scipy output.

    Adapted from scipy cookbook recipe.
    """
    new_regions = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)
    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    for p1, region_idx in enumerate(vor.point_region):
        vertices = vor.regions[region_idx]
        if all(v >= 0 for v in vertices):
            new_regions.append(vertices)
            continue

        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]
        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                continue
            tangent = vor.points[p2] - vor.points[p1]
            tangent /= (tangent**2).sum() ** 0.5
            normal = [-tangent[1], tangent[0]]

            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = normal if ((midpoint - center) @ normal) > 0 else [-normal[0], -normal[1]]
            far_point = vor.vertices[v2] + direction * radius
            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        vs = [new_vertices[v] for v in new_region]
        centroid = [sum(v[0] for v in vs) / len(vs), sum(v[1] for v in vs) / len(vs)]
        new_region = sorted(
            new_region,
            key=lambda v: __import__("math").atan2(
                new_vertices[v][1] - centroid[1],
                new_vertices[v][0] - centroid[0],
            ),
        )
        new_regions.append(new_region)

    return new_regions, new_vertices


def _load_victoria_geometry():
    with urlopen(STATES_GEOJSON_URL) as response:  # nosec B310
        geo = json.loads(response.read().decode("utf-8"))
    features = geo.get("features", [])
    for feature in features:
        props = feature.get("properties", {})
        if props.get("STATE_NAME") == "Victoria":
            geom = shape(feature.get("geometry"))
            if isinstance(geom, Polygon):
                return geom
            if isinstance(geom, MultiPolygon):
                return max(geom.geoms, key=lambda g: g.area)
    raise RuntimeError("Victoria boundary not found in source GeoJSON")


def generate_vic_regions_geojson():
    vic_geom = _load_victoria_geometry()
    points = [
        (location["longitude"], location["latitude"])
        for location in VICTORIA_WEATHER_LOCATIONS
    ]
    vor = Voronoi(points)
    regions, vertices = _voronoi_finite_polygons_2d(vor, radius=20)

    features = []
    for idx, region in enumerate(regions):
        polygon = Polygon([vertices[v] for v in region]).intersection(vic_geom)
        if polygon.is_empty:
            continue
        name = VICTORIA_WEATHER_LOCATIONS[idx]["name"]
        features.append(
            {
                "type": "Feature",
                "properties": {"region": name},
                "geometry": mapping(polygon),
            }
        )

    feature_collection = {"type": "FeatureCollection", "features": features}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(feature_collection, indent=2), encoding="utf-8")
    print(f"Wrote {len(features)} region polygons to {OUTPUT_PATH}")


if __name__ == "__main__":
    generate_vic_regions_geojson()
