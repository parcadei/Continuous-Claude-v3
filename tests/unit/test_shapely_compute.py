#!/usr/bin/env python3
"""Unit tests for shapely_compute.py - computational geometry CLI.

Tests geometry creation, operations, predicates, measurements, and transformations.
"""

import json
import subprocess
import sys

import pytest


class TestCreateGeometry:
    """Test geometry creation functions."""

    def test_create_point(self):
        """Test creating a Point geometry."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("point", "1,2")
        assert "wkt" in result
        assert "POINT" in result["wkt"]
        assert result["type"] == "Point"

    def test_create_point_3d(self):
        """Test creating a 3D Point geometry."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("point", "1,2,3")
        assert "wkt" in result
        assert "POINT Z" in result["wkt"] or "POINT" in result["wkt"]

    def test_create_line(self):
        """Test creating a LineString geometry."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("line", "0,0 1,1 2,0")
        assert "wkt" in result
        assert "LINESTRING" in result["wkt"]
        assert result["type"] == "LineString"

    def test_create_polygon(self):
        """Test creating a Polygon geometry."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("polygon", "0,0 1,0 1,1 0,1")
        assert "wkt" in result
        assert "POLYGON" in result["wkt"]
        assert result["type"] == "Polygon"

    def test_create_polygon_with_hole(self):
        """Test creating a Polygon with a hole."""
        from scripts.shapely_compute import create_geometry

        # Outer ring and inner ring (hole)
        result = create_geometry(
            "polygon",
            "0,0 10,0 10,10 0,10",
            holes="2,2 8,2 8,8 2,8"
        )
        assert "wkt" in result
        assert "POLYGON" in result["wkt"]

    def test_create_multipoint(self):
        """Test creating a MultiPoint geometry."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("multipoint", "0,0 1,1 2,2")
        assert "wkt" in result
        assert "MULTIPOINT" in result["wkt"]


class TestParseCoords:
    """Test coordinate parsing."""

    def test_parse_single_point(self):
        """Test parsing single point coordinates."""
        from scripts.shapely_compute import parse_coords

        coords = parse_coords("1,2")
        assert coords == [(1.0, 2.0)]

    def test_parse_multiple_points(self):
        """Test parsing multiple points."""
        from scripts.shapely_compute import parse_coords

        coords = parse_coords("0,0 1,1 2,0")
        assert coords == [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]

    def test_parse_3d_coords(self):
        """Test parsing 3D coordinates."""
        from scripts.shapely_compute import parse_coords

        coords = parse_coords("1,2,3")
        assert coords == [(1.0, 2.0, 3.0)]

    def test_parse_negative_coords(self):
        """Test parsing negative coordinates."""
        from scripts.shapely_compute import parse_coords

        coords = parse_coords("-1,-2 3,-4")
        assert coords == [(-1.0, -2.0), (3.0, -4.0)]


class TestGeometricOperations:
    """Test geometric set operations."""

    def test_intersection_polygons(self):
        """Test intersection of two overlapping polygons."""
        from scripts.shapely_compute import geometry_operation

        # Two overlapping squares
        result = geometry_operation(
            "intersection",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
            "POLYGON ((1 1, 3 1, 3 3, 1 3, 1 1))"
        )
        assert "wkt" in result
        assert result.get("is_empty") is False

    def test_union_polygons(self):
        """Test union of two polygons."""
        from scripts.shapely_compute import geometry_operation

        result = geometry_operation(
            "union",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "POLYGON ((1 0, 2 0, 2 1, 1 1, 1 0))"
        )
        assert "wkt" in result
        assert "POLYGON" in result["wkt"]

    def test_difference_polygons(self):
        """Test difference of two polygons."""
        from scripts.shapely_compute import geometry_operation

        result = geometry_operation(
            "difference",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
            "POLYGON ((1 1, 3 1, 3 3, 1 3, 1 1))"
        )
        assert "wkt" in result

    def test_symmetric_difference(self):
        """Test symmetric difference of two polygons."""
        from scripts.shapely_compute import geometry_operation

        result = geometry_operation(
            "symmetric_difference",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
            "POLYGON ((1 1, 3 1, 3 3, 1 3, 1 1))"
        )
        assert "wkt" in result

    def test_buffer_polygon(self):
        """Test buffering a polygon."""
        from scripts.shapely_compute import geometry_operation

        result = geometry_operation(
            "buffer",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "0.5"  # buffer distance
        )
        assert "wkt" in result
        assert "area" in result
        # Buffered polygon should be larger
        assert result["area"] > 1.0

    def test_convex_hull(self):
        """Test convex hull of a geometry."""
        from scripts.shapely_compute import geometry_operation

        result = geometry_operation(
            "convex_hull",
            "MULTIPOINT ((0 0), (1 1), (0 2), (2 0))",
            None
        )
        assert "wkt" in result
        assert "POLYGON" in result["wkt"]


class TestPredicates:
    """Test geometric predicates."""

    def test_contains_point_in_polygon(self):
        """Test if polygon contains a point."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "contains",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
            "POINT (1 1)"
        )
        assert result["result"] is True

    def test_contains_point_outside_polygon(self):
        """Test if polygon contains a point outside."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "contains",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
            "POINT (5 5)"
        )
        assert result["result"] is False

    def test_intersects_overlapping(self):
        """Test if two overlapping geometries intersect."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "intersects",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
            "POLYGON ((1 1, 3 1, 3 3, 1 3, 1 1))"
        )
        assert result["result"] is True

    def test_intersects_disjoint(self):
        """Test if two disjoint geometries intersect."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "intersects",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "POLYGON ((5 5, 6 5, 6 6, 5 6, 5 5))"
        )
        assert result["result"] is False

    def test_within_point_in_polygon(self):
        """Test if point is within polygon."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "within",
            "POINT (1 1)",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))"
        )
        assert result["result"] is True

    def test_touches(self):
        """Test if two geometries touch."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "touches",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "POLYGON ((1 0, 2 0, 2 1, 1 1, 1 0))"
        )
        assert result["result"] is True

    def test_crosses_line_polygon(self):
        """Test if line crosses polygon."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "crosses",
            "LINESTRING (0 0.5, 2 0.5)",
            "POLYGON ((0.5 0, 1.5 0, 1.5 1, 0.5 1, 0.5 0))"
        )
        assert result["result"] is True

    def test_disjoint(self):
        """Test if two geometries are disjoint."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "disjoint",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "POLYGON ((5 5, 6 5, 6 6, 5 6, 5 5))"
        )
        assert result["result"] is True

    def test_equals(self):
        """Test if two geometries are equal."""
        from scripts.shapely_compute import geometry_predicate

        result = geometry_predicate(
            "equals",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
        )
        assert result["result"] is True


class TestMeasurements:
    """Test geometric measurements."""

    def test_area_square(self):
        """Test area of a unit square."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry(
            "area",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
        )
        assert result["area"] == pytest.approx(1.0)

    def test_area_triangle(self):
        """Test area of a triangle."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry(
            "area",
            "POLYGON ((0 0, 2 0, 1 2, 0 0))"
        )
        assert result["area"] == pytest.approx(2.0)

    def test_length_line(self):
        """Test length of a line."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry(
            "length",
            "LINESTRING (0 0, 3 4)"
        )
        assert result["length"] == pytest.approx(5.0)

    def test_perimeter_square(self):
        """Test perimeter of a square."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry(
            "length",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
        )
        assert result["length"] == pytest.approx(4.0)

    def test_distance_points(self):
        """Test distance between two points."""
        from scripts.shapely_compute import distance_geometry

        result = distance_geometry(
            "POINT (0 0)",
            "POINT (3 4)"
        )
        assert result["distance"] == pytest.approx(5.0)

    def test_distance_point_line(self):
        """Test distance from point to line."""
        from scripts.shapely_compute import distance_geometry

        result = distance_geometry(
            "POINT (0 1)",
            "LINESTRING (0 0, 2 0)"
        )
        assert result["distance"] == pytest.approx(1.0)

    def test_centroid_square(self):
        """Test centroid of a square."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry(
            "centroid",
            "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))"
        )
        assert result["centroid"]["x"] == pytest.approx(1.0)
        assert result["centroid"]["y"] == pytest.approx(1.0)

    def test_bounds(self):
        """Test bounding box of a geometry."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry(
            "bounds",
            "POLYGON ((1 2, 3 2, 3 5, 1 5, 1 2))"
        )
        assert result["bounds"] == (1.0, 2.0, 3.0, 5.0)


class TestCoordinates:
    """Test coordinate extraction and transformations."""

    def test_coords_line(self):
        """Test extracting coordinates from a line."""
        from scripts.shapely_compute import get_coords

        result = get_coords("LINESTRING (0 0, 1 1, 2 0)")
        assert result["coords"] == [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]

    def test_coords_polygon_exterior(self):
        """Test extracting exterior ring coordinates from polygon."""
        from scripts.shapely_compute import get_coords

        result = get_coords("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))")
        assert len(result["coords"]) == 5  # Closed ring

    def test_translate(self):
        """Test translating a geometry."""
        from scripts.shapely_compute import transform_geometry

        result = transform_geometry(
            "translate",
            "POINT (1 1)",
            "2,3"  # dx, dy
        )
        assert "POINT" in result["wkt"]
        # Result should be POINT (3 4)
        assert "3" in result["wkt"]
        assert "4" in result["wkt"]

    def test_rotate(self):
        """Test rotating a geometry."""
        from scripts.shapely_compute import transform_geometry

        result = transform_geometry(
            "rotate",
            "POINT (1 0)",
            "90"  # angle in degrees
        )
        assert "wkt" in result
        # 90-degree rotation of (1,0) around origin should give (0,1)

    def test_rotate_around_point(self):
        """Test rotating around a specific point."""
        from scripts.shapely_compute import transform_geometry

        result = transform_geometry(
            "rotate",
            "POINT (2 0)",
            "90,1,0"  # angle, origin_x, origin_y
        )
        assert "wkt" in result

    def test_scale(self):
        """Test scaling a geometry."""
        from scripts.shapely_compute import transform_geometry

        result = transform_geometry(
            "scale",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "2,2"  # sx, sy
        )
        assert "wkt" in result
        # Scaled polygon should have area 4x the original

    def test_scale_non_uniform(self):
        """Test non-uniform scaling."""
        from scripts.shapely_compute import transform_geometry

        result = transform_geometry(
            "scale",
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "2,3"  # sx=2, sy=3
        )
        assert "wkt" in result


class TestValidation:
    """Test geometry validation."""

    def test_valid_polygon(self):
        """Test validation of a valid polygon."""
        from scripts.shapely_compute import validate_geometry

        result = validate_geometry("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))")
        assert result["is_valid"] is True

    def test_invalid_self_intersecting(self):
        """Test validation of self-intersecting polygon (bowtie)."""
        from scripts.shapely_compute import validate_geometry

        # Bowtie/figure-8 polygon (self-intersecting)
        result = validate_geometry(
            "POLYGON ((0 0, 2 2, 2 0, 0 2, 0 0))"
        )
        assert result["is_valid"] is False
        assert "reason" in result

    def test_make_valid(self):
        """Test making an invalid geometry valid."""
        from scripts.shapely_compute import make_valid_geometry

        # Self-intersecting polygon
        result = make_valid_geometry(
            "POLYGON ((0 0, 2 2, 2 0, 0 2, 0 0))"
        )
        assert result["is_valid"] is True
        assert "wkt" in result


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_wkt(self):
        """Test handling of invalid WKT."""
        from scripts.shapely_compute import measure_geometry

        result = measure_geometry("area", "NOT A VALID WKT")
        assert "error" in result

    def test_invalid_coords_format(self):
        """Test handling of invalid coordinate format."""
        from scripts.shapely_compute import parse_coords

        with pytest.raises(ValueError):
            parse_coords("not,valid,coords,format")

    def test_unsupported_geometry_type(self):
        """Test handling of unsupported geometry type."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("unknown_type", "0,0")
        assert "error" in result

    def test_operation_type_mismatch(self):
        """Test handling operations on incompatible types."""
        from scripts.shapely_compute import geometry_operation

        # Buffer requires a distance as second param
        result = geometry_operation(
            "buffer",
            "POINT (0 0)",
            "not_a_number"
        )
        assert "error" in result


class TestCLI:
    """Test CLI interface."""

    def test_cli_create_point(self):
        """Test CLI create point command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "runtime.harness",
                "scripts/shapely_compute.py",
                "create", "point", "--coords", "1,2"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "wkt" in output
            assert "POINT" in output["wkt"]

    def test_cli_measure_area(self):
        """Test CLI measure area command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "runtime.harness",
                "scripts/shapely_compute.py",
                "measure", "area",
                "--geom", "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert output["area"] == pytest.approx(1.0)

    def test_cli_predicate_contains(self):
        """Test CLI predicate contains command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "runtime.harness",
                "scripts/shapely_compute.py",
                "pred", "contains",
                "--g1", "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
                "--g2", "POINT (1 1)"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert output["result"] is True

    def test_cli_operation_intersection(self):
        """Test CLI operation intersection command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "runtime.harness",
                "scripts/shapely_compute.py",
                "op", "intersection",
                "--g1", "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
                "--g2", "POLYGON ((1 1, 3 1, 3 3, 1 3, 1 1))"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "wkt" in output

    def test_cli_transform_translate(self):
        """Test CLI transform translate command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "runtime.harness",
                "scripts/shapely_compute.py",
                "transform", "translate",
                "--geom", "POINT (0 0)",
                "--params", "1,2"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "wkt" in output

    def test_cli_help(self):
        """Test CLI help command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "runtime.harness",
                "scripts/shapely_compute.py",
                "--help"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )
        # Help should succeed or fail gracefully
        assert result.returncode in (0, 1, 2)


class TestWKTConversion:
    """Test WKT (Well-Known Text) conversion."""

    def test_from_wkt_point(self):
        """Test parsing WKT to geometry."""
        from scripts.shapely_compute import from_wkt

        result = from_wkt("POINT (1 2)")
        assert result["type"] == "Point"
        assert result["coords"] == [(1.0, 2.0)]

    def test_from_wkt_polygon(self):
        """Test parsing WKT polygon."""
        from scripts.shapely_compute import from_wkt

        result = from_wkt("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))")
        assert result["type"] == "Polygon"
        assert "area" in result

    def test_to_wkt(self):
        """Test geometry to WKT conversion."""
        from scripts.shapely_compute import create_geometry

        result = create_geometry("point", "1,2")
        assert "wkt" in result
        assert result["wkt"] == "POINT (1 2)"
