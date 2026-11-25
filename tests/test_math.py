"""Geometry helpers that the track and cone code depend on."""

from __future__ import annotations

import math
import unittest

from fsae_env_generator.math2d import (
    Vec2,
    curvatures,
    menger_curvature,
    point_at_distance,
    cumulative_lengths,
    polyline_self_intersects,
    segments_properly_intersect,
)
from fsae_env_generator.rng import SeededRNG
from fsae_env_generator.spatial import SpatialHash
from fsae_env_generator.splines import sample_catmull_rom


class MathTests(unittest.TestCase):
    def test_segments_cross_only_when_they_properly_intersect(self) -> None:
        self.assertTrue(
            segments_properly_intersect(Vec2(0, 0), Vec2(1, 1), Vec2(0, 1), Vec2(1, 0))
        )
        self.assertFalse(
            segments_properly_intersect(Vec2(0, 0), Vec2(1, 0), Vec2(2, 0), Vec2(3, 0))
        )

    def test_closed_square_does_not_self_intersect(self) -> None:
        square = [Vec2(0, 0), Vec2(4, 0), Vec2(4, 4), Vec2(0, 4)]
        self.assertFalse(polyline_self_intersects(square, True))

    def test_circle_curvature_matches_radius(self) -> None:
        radius = 10.0
        points = [
            Vec2(radius * math.cos(index * 0.2), radius * math.sin(index * 0.2))
            for index in range(32)
        ]
        curvature = curvatures(points, True)
        measured = 1.0 / abs(curvature[8])
        self.assertAlmostEqual(measured, radius, delta=0.15)
        self.assertGreater(menger_curvature(points[0], points[1], points[2]), 0.0)

    def test_point_at_distance_walks_a_straight_line(self) -> None:
        points = [Vec2(0, 0), Vec2(10, 0)]
        cumulative = cumulative_lengths(points, False)
        point, tangent, _index = point_at_distance(points, cumulative, 4.0)
        self.assertAlmostEqual(point.x, 4.0, places=6)
        self.assertAlmostEqual(tangent.x, 1.0, places=6)

    def test_closed_spline_passes_near_its_controls(self) -> None:
        controls = [Vec2(0, 0), Vec2(10, 0), Vec2(12, 8), Vec2(4, 10), Vec2(-2, 5)]
        samples = sample_catmull_rom(controls, 0.25, True)
        self.assertGreater(len(samples), 20)
        for control in controls:
            nearest = min(control.distance(sample) for sample in samples)
            self.assertLess(nearest, 0.2)

    def test_spatial_hash_finds_neighbors_and_ignores_distant_points(self) -> None:
        grid: SpatialHash[str] = SpatialHash(1.0)
        grid.insert(Vec2(0, 0), "a")
        grid.insert(Vec2(0.4, 0.1), "b")
        grid.insert(Vec2(10, 10), "c")
        found = [item for _point, item in grid.query_radius(Vec2(0, 0), 1.0)]
        self.assertEqual(found, ["a", "b"])
        self.assertTrue(grid.conflicts(Vec2(0.2, 0.0), 0.5))
        self.assertFalse(grid.conflicts(Vec2(3, 0), 0.5))

    def test_child_streams_do_not_depend_on_each_other(self) -> None:
        first = SeededRNG(11)
        second = SeededRNG(11)
        self.assertEqual(first.child("cones").uniform(0, 1), second.child("cones").uniform(0, 1))
        # Drawing from another child must not change the cones stream.
        first.child("trees").uniform(0, 1)
        self.assertEqual(first.child("cones").uniform(0, 1), second.child("cones").uniform(0, 1))
        self.assertNotEqual(SeededRNG(11).uniform(0, 1), SeededRNG(12).uniform(0, 1))


if __name__ == "__main__":
    unittest.main()
