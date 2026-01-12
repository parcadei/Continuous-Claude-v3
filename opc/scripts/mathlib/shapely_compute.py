#!/usr/bin/env python3
"""Computational geometry script - Cognitive prosthetics for Claude.

USAGE:
    # Create geometries
    uv run python -m runtime.harness scripts/shapely_compute.py \
        create point --coords "1,2"

    uv run python -m runtime.harness scripts/shapely_compute.py \
        create line --coords "0,0 1,1 2,0"

    uv run python -m runtime.harness scripts/shapely_compute.py \
        create polygon --coords "0,0 1,0 1,1 0,1"

    # Geometric operations
    uv run python -m runtime.harness scripts/shapely_compute.py \
        op intersection --g1 "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))" \
                        --g2 "POLYGON ((1 1, 3 1, 3 3, 1 3, 1 1))"

    uv run python -m runtime.harness scripts/shapely_compute.py \
        op buffer --g1 "POINT (0 0)" --g2 "1.5"

    # Predicates
    uv run python -m runtime.harness scripts/shapely_compute.py \
        pred contains --g1 "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))" \
                      --g2 "POINT (1 1)"

    # Measurements
    uv run python -m runtime.harness scripts/shapely_compute.py \
        measure area --geom "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"

    uv run python -m runtime.harness scripts/shapely_compute.py \
        measure centroid --geom "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))"

    # Transformations
    uv run python -m runtime.harness scripts/shapely_compute.py \
        transform translate --geom "POINT (0 0)" --params "1,2"

    uv run python -m runtime.harness scripts/shapely_compute.py \
        transform rotate --geom "POINT (1 0)" --params "90"

    # Validation
    uv run python -m runtime.harness scripts/shapely_compute.py \
        validate --geom "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"

    # Distance
    uv run python -m runtime.harness scripts/shapely_compute.py \
        distance --g1 "POINT (0 0)" --g2 "POINT (3 4)"

Requires: shapely (pip install shapely)
"""

import argparse
import asyncio
import json
import sys
from typing import Any, Tuple


def get_shapely():
    """Lazy import Shapely - only load when needed."""
    import shapely

    return shapely


def parse_coords(coords_str: str) -> list[tuple[float, ...]]:
    """Parse coordinate string into list of tuples.

    Accepts:
        - "1,2" -> [(1.0, 2.0)]
        - "0,0 1,1 2,0" -> [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
        - "1,2,3" -> [(1.0, 2.0, 3.0)] (3D point)

    Args:
        coords_str: Coordinate string with space-separated points

    Returns:
        List of coordinate tuples

    Raises:
        ValueError: If coordinates cannot be parsed
    """
    coords_str = coords_str.strip()
    if not coords_str:
        raise ValueError("Empty coordinate string")

    points = []
    # Split by space to get individual points
    point_strs = coords_str.split()

    for point_str in point_strs:
        parts = point_str.split(",")
        try:
            coords = tuple(float(p.strip()) for p in parts)
            if len(coords) < 2:
                raise ValueError(f"Point must have at least 2 coordinates: {point_str}")
            points.append(coords)
        except ValueError as e:
            raise ValueError(f"Cannot parse coordinates '{point_str}': {e}")

    return points


def _parse_wkt(wkt_str: str) -> Any:
    """Parse WKT string to Shapely geometry.

    Args:
        wkt_str: Well-Known Text representation

    Returns:
        Shapely geometry object

    Raises:
        ValueError: If WKT is invalid
    """
    get_shapely()
    from shapely import wkt

    try:
        return wkt.loads(wkt_str)
    except Exception as e:
        raise ValueError(f"Invalid WKT: {wkt_str}: {e}")


def create_geometry(geom_type: str, coords: str, holes: str | None = None) -> dict:
    """Create a geometry from coordinates.

    Args:
        geom_type: Type of geometry (point, line, polygon, multipoint, etc.)
        coords: Coordinate string like "0,0 1,1 2,0"
        holes: For polygons, optional hole coordinates

    Returns:
        {
            "wkt": "POINT (1 2)",
            "type": "Point",
            "bounds": (minx, miny, maxx, maxy)
        }
    """
    get_shapely()
    from shapely import geometry

    geom_type = geom_type.lower()

    try:
        coord_list = parse_coords(coords)

        if geom_type == "point":
            if len(coord_list) != 1:
                return {"error": "Point requires exactly one coordinate"}
            geom = geometry.Point(coord_list[0])

        elif geom_type == "line" or geom_type == "linestring":
            if len(coord_list) < 2:
                return {"error": "Line requires at least 2 coordinates"}
            geom = geometry.LineString(coord_list)

        elif geom_type == "polygon":
            if len(coord_list) < 3:
                return {"error": "Polygon requires at least 3 coordinates"}
            # Check if polygon needs to be closed
            if coord_list[0] != coord_list[-1]:
                coord_list.append(coord_list[0])

            if holes:
                hole_coords = parse_coords(holes)
                if hole_coords[0] != hole_coords[-1]:
                    hole_coords.append(hole_coords[0])
                geom = geometry.Polygon(coord_list, [hole_coords])
            else:
                geom = geometry.Polygon(coord_list)

        elif geom_type == "multipoint":
            geom = geometry.MultiPoint(coord_list)

        elif geom_type == "multilinestring":
            # Expect format like "0,0 1,1|2,2 3,3" for multiple lines
            lines = coords.split("|")
            line_coords = [parse_coords(line) for line in lines]
            geom = geometry.MultiLineString(line_coords)

        elif geom_type == "multipolygon":
            # Expect format like "0,0 1,0 1,1 0,1|2,2 3,2 3,3 2,3"
            polys = coords.split("|")
            poly_coords = []
            for poly in polys:
                pc = parse_coords(poly)
                if pc[0] != pc[-1]:
                    pc.append(pc[0])
                poly_coords.append(pc)
            geom = geometry.MultiPolygon([geometry.Polygon(p) for p in poly_coords])

        else:
            return {"error": f"Unsupported geometry type: {geom_type}"}

        return {
            "wkt": geom.wkt,
            "type": geom.geom_type,
            "bounds": geom.bounds,
            "is_valid": geom.is_valid,
            "is_empty": geom.is_empty,
        }

    except Exception as e:
        return {"error": str(e)}


def geometry_operation(op: str, g1_wkt: str, g2_wkt: str | None) -> dict:
    """Perform geometric set operation.

    Args:
        op: Operation (intersection, union, difference, symmetric_difference,
            buffer, convex_hull)
        g1_wkt: First geometry as WKT
        g2_wkt: Second geometry as WKT (or buffer distance for buffer op)

    Returns:
        {
            "wkt": "...",
            "type": "...",
            "area": float (if polygon),
            "is_empty": bool
        }
    """
    get_shapely()

    try:
        geom1 = _parse_wkt(g1_wkt)

        op = op.lower()

        if op == "buffer":
            try:
                distance = float(g2_wkt)
            except (TypeError, ValueError):
                return {"error": f"Buffer requires numeric distance, got: {g2_wkt}"}
            result = geom1.buffer(distance)

        elif op == "convex_hull":
            result = geom1.convex_hull

        elif op == "envelope":
            result = geom1.envelope

        elif op == "simplify":
            try:
                tolerance = float(g2_wkt) if g2_wkt else 0.0
            except (TypeError, ValueError):
                tolerance = 0.0
            result = geom1.simplify(tolerance)

        else:
            if not g2_wkt:
                return {"error": f"Operation '{op}' requires two geometries"}

            geom2 = _parse_wkt(g2_wkt)

            if op == "intersection":
                result = geom1.intersection(geom2)
            elif op == "union":
                result = geom1.union(geom2)
            elif op == "difference":
                result = geom1.difference(geom2)
            elif op == "symmetric_difference":
                result = geom1.symmetric_difference(geom2)
            else:
                return {"error": f"Unknown operation: {op}"}

        output = {
            "wkt": result.wkt,
            "type": result.geom_type,
            "is_empty": result.is_empty,
            "is_valid": result.is_valid,
            "bounds": result.bounds,
        }

        # Add area for polygons
        if hasattr(result, "area"):
            output["area"] = result.area

        # Add length for lines
        if hasattr(result, "length"):
            output["length"] = result.length

        return output

    except Exception as e:
        return {"error": str(e)}


def geometry_predicate(pred: str, g1_wkt: str, g2_wkt: str) -> dict:
    """Check geometric predicate between two geometries.

    Args:
        pred: Predicate (contains, intersects, within, touches, crosses,
              disjoint, overlaps, equals)
        g1_wkt: First geometry as WKT
        g2_wkt: Second geometry as WKT

    Returns:
        {
            "result": bool,
            "predicate": str,
            "g1_type": str,
            "g2_type": str
        }
    """
    try:
        geom1 = _parse_wkt(g1_wkt)
        geom2 = _parse_wkt(g2_wkt)

        pred = pred.lower()

        predicate_map = {
            "contains": geom1.contains,
            "intersects": geom1.intersects,
            "within": geom1.within,
            "touches": geom1.touches,
            "crosses": geom1.crosses,
            "disjoint": geom1.disjoint,
            "overlaps": geom1.overlaps,
            "equals": geom1.equals,
            "covers": geom1.covers,
            "covered_by": geom1.covered_by,
        }

        if pred not in predicate_map:
            return {"error": f"Unknown predicate: {pred}"}

        result = predicate_map[pred](geom2)

        return {
            "result": result,
            "predicate": pred,
            "g1_type": geom1.geom_type,
            "g2_type": geom2.geom_type,
        }

    except Exception as e:
        return {"error": str(e)}


def measure_geometry(what: str, geom_wkt: str) -> dict:
    """Measure geometric properties.

    Args:
        what: What to measure (area, length, centroid, bounds, exterior_ring)
        geom_wkt: Geometry as WKT

    Returns:
        Measurement result dictionary
    """
    try:
        geom = _parse_wkt(geom_wkt)

        what = what.lower()

        if what == "area":
            return {"area": geom.area, "type": geom.geom_type}

        elif what == "length":
            return {"length": geom.length, "type": geom.geom_type}

        elif what == "centroid":
            centroid = geom.centroid
            return {
                "centroid": {"x": centroid.x, "y": centroid.y},
                "wkt": centroid.wkt,
                "type": geom.geom_type,
            }

        elif what == "bounds":
            return {"bounds": geom.bounds, "type": geom.geom_type}

        elif what == "exterior_ring":
            if hasattr(geom, "exterior"):
                return {"wkt": geom.exterior.wkt, "coords": list(geom.exterior.coords)}
            else:
                return {"error": "Geometry has no exterior ring"}

        elif what == "all":
            result = {
                "type": geom.geom_type,
                "bounds": geom.bounds,
                "is_valid": geom.is_valid,
                "is_empty": geom.is_empty,
            }
            if hasattr(geom, "area"):
                result["area"] = geom.area
            if hasattr(geom, "length"):
                result["length"] = geom.length
            centroid = geom.centroid
            result["centroid"] = {"x": centroid.x, "y": centroid.y}
            return result

        else:
            return {"error": f"Unknown measurement: {what}"}

    except Exception as e:
        return {"error": str(e)}


def distance_geometry(g1_wkt: str, g2_wkt: str) -> dict:
    """Compute distance between two geometries.

    Args:
        g1_wkt: First geometry as WKT
        g2_wkt: Second geometry as WKT

    Returns:
        {
            "distance": float,
            "g1_type": str,
            "g2_type": str
        }
    """
    try:
        geom1 = _parse_wkt(g1_wkt)
        geom2 = _parse_wkt(g2_wkt)

        return {
            "distance": geom1.distance(geom2),
            "g1_type": geom1.geom_type,
            "g2_type": geom2.geom_type,
        }

    except Exception as e:
        return {"error": str(e)}


def get_coords(geom_wkt: str) -> dict:
    """Extract coordinates from a geometry.

    Args:
        geom_wkt: Geometry as WKT

    Returns:
        {
            "coords": [...],
            "type": str
        }
    """
    try:
        geom = _parse_wkt(geom_wkt)

        if hasattr(geom, "exterior"):
            # Polygon - get exterior ring
            coords = list(geom.exterior.coords)
        elif hasattr(geom, "coords"):
            # Point, LineString
            coords = list(geom.coords)
        elif hasattr(geom, "geoms"):
            # Multi-geometry
            coords = []
            for g in geom.geoms:
                if hasattr(g, "coords"):
                    coords.extend(list(g.coords))
                elif hasattr(g, "exterior"):
                    coords.extend(list(g.exterior.coords))
        else:
            return {"error": f"Cannot extract coords from {geom.geom_type}"}

        return {"coords": coords, "type": geom.geom_type}

    except Exception as e:
        return {"error": str(e)}


def transform_geometry(transform: str, geom_wkt: str, params: str) -> dict:
    """Transform a geometry.

    Args:
        transform: Type of transform (translate, rotate, scale)
        geom_wkt: Geometry as WKT
        params: Transform parameters:
            - translate: "dx,dy" or "dx,dy,dz"
            - rotate: "angle" or "angle,origin_x,origin_y"
            - scale: "sx,sy" or "sx,sy,origin_x,origin_y"

    Returns:
        {
            "wkt": "...",
            "type": "...",
            "transform": str
        }
    """
    get_shapely()
    from shapely import affinity

    try:
        geom = _parse_wkt(geom_wkt)
        transform = transform.lower()

        param_parts = [float(p.strip()) for p in params.split(",")]

        if transform == "translate":
            if len(param_parts) == 2:
                dx, dy = param_parts
                result = affinity.translate(geom, xoff=dx, yoff=dy)
            elif len(param_parts) == 3:
                dx, dy, dz = param_parts
                result = affinity.translate(geom, xoff=dx, yoff=dy, zoff=dz)
            else:
                return {"error": "translate requires 2 or 3 parameters (dx,dy[,dz])"}

        elif transform == "rotate":
            if len(param_parts) == 1:
                angle = param_parts[0]
                result = affinity.rotate(geom, angle, origin="centroid")
            elif len(param_parts) == 3:
                angle, ox, oy = param_parts
                result = affinity.rotate(geom, angle, origin=(ox, oy))
            else:
                return {"error": "rotate requires 1 or 3 parameters (angle[,origin_x,origin_y])"}

        elif transform == "scale":
            if len(param_parts) == 2:
                sx, sy = param_parts
                result = affinity.scale(geom, xfact=sx, yfact=sy, origin="centroid")
            elif len(param_parts) == 4:
                sx, sy, ox, oy = param_parts
                result = affinity.scale(geom, xfact=sx, yfact=sy, origin=(ox, oy))
            else:
                return {"error": "scale requires 2 or 4 parameters (sx,sy[,origin_x,origin_y])"}

        elif transform == "skew":
            if len(param_parts) == 2:
                xs, ys = param_parts
                result = affinity.skew(geom, xs=xs, ys=ys, origin="centroid")
            else:
                return {"error": "skew requires 2 parameters (xs,ys)"}

        else:
            return {"error": f"Unknown transform: {transform}"}

        return {
            "wkt": result.wkt,
            "type": result.geom_type,
            "transform": transform,
            "bounds": result.bounds,
        }

    except Exception as e:
        return {"error": str(e)}


def validate_geometry(geom_wkt: str) -> dict:
    """Validate a geometry.

    Args:
        geom_wkt: Geometry as WKT

    Returns:
        {
            "is_valid": bool,
            "reason": str (if invalid)
        }
    """
    get_shapely()
    from shapely.validation import explain_validity

    try:
        geom = _parse_wkt(geom_wkt)

        is_valid = geom.is_valid
        result = {"is_valid": is_valid, "type": geom.geom_type, "wkt": geom.wkt}

        if not is_valid:
            result["reason"] = explain_validity(geom)

        return result

    except Exception as e:
        return {"error": str(e), "is_valid": False}


def make_valid_geometry(geom_wkt: str) -> dict:
    """Make an invalid geometry valid.

    Args:
        geom_wkt: Geometry as WKT

    Returns:
        {
            "wkt": "...",
            "is_valid": True,
            "was_valid": bool
        }
    """
    get_shapely()
    from shapely.validation import make_valid

    try:
        geom = _parse_wkt(geom_wkt)
        was_valid = geom.is_valid

        if was_valid:
            return {"wkt": geom.wkt, "is_valid": True, "was_valid": True, "type": geom.geom_type}

        valid_geom = make_valid(geom)

        return {
            "wkt": valid_geom.wkt,
            "is_valid": valid_geom.is_valid,
            "was_valid": was_valid,
            "type": valid_geom.geom_type,
            "original_type": geom.geom_type,
        }

    except Exception as e:
        return {"error": str(e)}


def from_wkt(wkt_str: str) -> dict:
    """Parse WKT and return geometry information.

    Args:
        wkt_str: Well-Known Text string

    Returns:
        {
            "type": str,
            "coords": [...],
            "bounds": tuple,
            "area": float (if polygon),
            "length": float (if line)
        }
    """
    try:
        geom = _parse_wkt(wkt_str)

        result = {
            "type": geom.geom_type,
            "bounds": geom.bounds,
            "is_valid": geom.is_valid,
            "is_empty": geom.is_empty,
        }

        # Get coordinates
        if hasattr(geom, "exterior"):
            result["coords"] = list(geom.exterior.coords)
        elif hasattr(geom, "coords"):
            result["coords"] = list(geom.coords)

        # Add measurements
        if hasattr(geom, "area") and geom.area > 0:
            result["area"] = geom.area
        if hasattr(geom, "length") and geom.length > 0:
            result["length"] = geom.length

        return result

    except Exception as e:
        return {"error": str(e)}


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Computational geometry - cognitive prosthetics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create command
    create_p = subparsers.add_parser("create", help="Create geometry")
    create_p.add_argument(
        "geom_type",
        choices=[
            "point",
            "line",
            "linestring",
            "polygon",
            "multipoint",
            "multilinestring",
            "multipolygon",
        ],
        help="Type of geometry to create",
    )
    create_p.add_argument("--coords", required=True, help="Coordinates (e.g., '0,0 1,1 2,0')")
    create_p.add_argument("--holes", help="Hole coordinates for polygons")

    # Operation command
    op_p = subparsers.add_parser("op", help="Geometric operation")
    op_p.add_argument(
        "operation",
        choices=[
            "intersection",
            "union",
            "difference",
            "symmetric_difference",
            "buffer",
            "convex_hull",
            "envelope",
            "simplify",
        ],
        help="Operation to perform",
    )
    op_p.add_argument("--g1", required=True, help="First geometry (WKT)")
    op_p.add_argument("--g2", help="Second geometry (WKT) or buffer distance")

    # Predicate command
    pred_p = subparsers.add_parser("pred", help="Geometric predicate")
    pred_p.add_argument(
        "predicate",
        choices=[
            "contains",
            "intersects",
            "within",
            "touches",
            "crosses",
            "disjoint",
            "overlaps",
            "equals",
            "covers",
            "covered_by",
        ],
        help="Predicate to check",
    )
    pred_p.add_argument("--g1", required=True, help="First geometry (WKT)")
    pred_p.add_argument("--g2", required=True, help="Second geometry (WKT)")

    # Measure command
    measure_p = subparsers.add_parser("measure", help="Measure geometry")
    measure_p.add_argument(
        "what",
        choices=["area", "length", "centroid", "bounds", "exterior_ring", "all"],
        help="What to measure",
    )
    measure_p.add_argument("--geom", required=True, help="Geometry (WKT)")

    # Distance command
    distance_p = subparsers.add_parser("distance", help="Distance between geometries")
    distance_p.add_argument("--g1", required=True, help="First geometry (WKT)")
    distance_p.add_argument("--g2", required=True, help="Second geometry (WKT)")

    # Transform command
    transform_p = subparsers.add_parser("transform", help="Transform geometry")
    transform_p.add_argument(
        "transform_type", choices=["translate", "rotate", "scale", "skew"], help="Type of transform"
    )
    transform_p.add_argument("--geom", required=True, help="Geometry (WKT)")
    transform_p.add_argument("--params", required=True, help="Transform parameters")

    # Validate command
    validate_p = subparsers.add_parser("validate", help="Validate geometry")
    validate_p.add_argument("--geom", required=True, help="Geometry (WKT)")

    # Make valid command
    make_valid_p = subparsers.add_parser("makevalid", help="Make geometry valid")
    make_valid_p.add_argument("--geom", required=True, help="Geometry (WKT)")

    # Coords command
    coords_p = subparsers.add_parser("coords", help="Extract coordinates")
    coords_p.add_argument("--geom", required=True, help="Geometry (WKT)")

    # From WKT command
    fromwkt_p = subparsers.add_parser("fromwkt", help="Parse WKT")
    fromwkt_p.add_argument("wkt", help="WKT string")

    # Common options
    for p in [
        create_p,
        op_p,
        pred_p,
        measure_p,
        distance_p,
        transform_p,
        validate_p,
        make_valid_p,
        coords_p,
        fromwkt_p,
    ]:
        p.add_argument("--json", action="store_true", help="Output as JSON")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    args = parse_args()

    try:
        if args.command == "create":
            result = create_geometry(args.geom_type, args.coords, getattr(args, "holes", None))

        elif args.command == "op":
            result = geometry_operation(args.operation, args.g1, args.g2)

        elif args.command == "pred":
            result = geometry_predicate(args.predicate, args.g1, args.g2)

        elif args.command == "measure":
            result = measure_geometry(args.what, args.geom)

        elif args.command == "distance":
            result = distance_geometry(args.g1, args.g2)

        elif args.command == "transform":
            result = transform_geometry(args.transform_type, args.geom, args.params)

        elif args.command == "validate":
            result = validate_geometry(args.geom)

        elif args.command == "makevalid":
            result = make_valid_geometry(args.geom)

        elif args.command == "coords":
            result = get_coords(args.geom)

        elif args.command == "fromwkt":
            result = from_wkt(args.wkt)

        else:
            result = {"error": f"Unknown command: {args.command}"}

        # Output
        print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
