"""Centerline, width, and competition-limit tests."""

from __future__ import annotations

import unittest

from fsae_env_generator.config import GeneratorConfig
from fsae_env_generator.math2d import Vec2, polyline_length
from fsae_env_generator.rng import SeededRNG
from fsae_env_generator.track import _fillet_polygon, generate_track, trace_rounded_loop


class TrackTests(unittest.TestCase):
    def test_rounded_rectangle_closes(self) -> None:
        points, gap = trace_rounded_loop([12.0, 20.0, 12.0, 20.0], 2.0, 0.5)
        self.assertLess(gap, 1e-6)
        self.assertGreater(len(points), 10)
        # The analytic length is 2*(12+20) + 2*pi*2.
        self.assertAlmostEqual(polyline_length(points, True), 64.0 + 4.0 * 3.1415926535, delta=0.2)

    def test_square_fillet_uses_the_requested_radius(self) -> None:
        square = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)]
        samples, achieved = _fillet_polygon(square, 2.0, 0.25)
        self.assertIsNotNone(samples)
        # A 90 degree corner is opened slightly above the minimum radius.
        # Setback along each edge is r * tan(45 deg) = r, so the tangent point
        # on the bottom edge is (10 - r, 0).
        self.assertGreaterEqual(achieved, 2.0)
        nearest = min(point.distance(Vec2(10.0 - achieved, 0.0)) for point in samples)
        self.assertLess(nearest, 0.05)

    def test_procedural_tracks_meet_the_us_profile(self) -> None:
        for seed in (1, 7, 15):
            track = generate_track(GeneratorConfig(seed=seed), SeededRNG(seed))
            widths = [
                track.left_boundary[index].distance(track.right_boundary[index])
                for index in range(0, len(track.centerline), 11)
            ]
            self.assertGreaterEqual(track.length, 199.0, seed)
            self.assertLessEqual(track.length, 501.0, seed)
            self.assertGreaterEqual(track.min_radius, 4.4, seed)
            self.assertLessEqual(track.max_straight, 81.0, seed)
            self.assertTrue(all(abs(width - 3.5) < 0.02 for width in widths), seed)
            self.assertIn(track.centerline_method, {"catmull_rom", "catmull_rom_varied", "varied_polygon", "arc_line"})

    def test_same_seed_rebuilds_the_same_centerline(self) -> None:
        first = generate_track(GeneratorConfig(seed=4), SeededRNG(4))
        second = generate_track(GeneratorConfig(seed=4), SeededRNG(4))
        self.assertEqual([(round(point.x, 6), round(point.y, 6)) for point in first.centerline],
                         [(round(point.x, 6), round(point.y, 6)) for point in second.centerline])

    def test_custom_centerline_keeps_width(self) -> None:
        points, gap = trace_rounded_loop([36.0] * 6, 6.0, 1.0)
        self.assertLess(gap, 1e-4)
        config = GeneratorConfig(
            seed=2,
            track_type="custom",
            centerline=[[point.x, point.y] for point in points],
            closed_loop=True,
            smooth_centerline=False,
        )
        track = generate_track(config, SeededRNG(2))
        self.assertGreater(track.min_radius, 5.0)
        self.assertAlmostEqual(track.left_boundary[0].distance(track.right_boundary[0]), 3.5, places=3)

    def test_custom_track_without_points_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            generate_track(GeneratorConfig(track_type="custom"), SeededRNG(1))


if __name__ == "__main__":
    unittest.main()
