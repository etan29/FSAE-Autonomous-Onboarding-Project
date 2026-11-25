"""2026 event geometry, cone counts, and ground truth."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fsae_env_generator.config import GeneratorConfig
from fsae_env_generator.ground_truth import write_ground_truth_files
from fsae_env_generator.pipeline import assemble_environment, generate_environment
from fsae_env_generator.rng import SeededRNG
from fsae_env_generator.track import generate_track


def _failed(report) -> list[str]:
    return [f"{check.name}: {check.detail}" for check in report.checks if not check.passed]


class EventGeometryTests(unittest.TestCase):
    def test_acceleration_timed_section_is_75_m(self) -> None:
        environment, report = generate_environment(
            GeneratorConfig(seed=4, track_type="acceleration", env_density=0.0, background_density=0.0)
        )
        self.assertTrue(report.passed, _failed(report))
        self.assertAlmostEqual(environment.track.timed_length, 75.0, places=2)
        self.assertAlmostEqual(environment.track.length, 150.0, delta=1.0)
        self.assertGreater(environment.track.length, environment.track.timed_length + 70.0)
        gates = [obj for obj in environment.objects if obj.metadata.get("marking") == "start_finish"]
        self.assertGreaterEqual(len(gates), 2)
        self.assertTrue(all(obj.asset == "orange_large" for obj in gates))
        self.assertEqual(environment.ground_truth["event"], "acceleration")
        self.assertIn("D.9.1.1", " ".join(environment.ground_truth["official"]))

    def test_skidpad_is_one_figure_eight(self) -> None:
        environment, report = generate_environment(
            GeneratorConfig(seed=6, track_type="skidpad", env_density=0.0, background_density=0.0)
        )
        self.assertTrue(report.passed, _failed(report))
        xs = [point.x for point in environment.track.centerline]
        self.assertLess(min(xs), -8.0)
        self.assertGreater(max(xs), 8.0)
        near_origin = [point for point in environment.track.centerline if point.length() < 1.0]
        self.assertGreaterEqual(len(near_origin), 2)
        counts = {}
        for ring in ("right-inner", "left-inner", "right-outer", "left-outer"):
            counts[ring] = sum(1 for obj in environment.objects if obj.metadata.get("ring") == ring)
        self.assertEqual(counts["right-inner"], 17)
        self.assertEqual(counts["left-inner"], 17)
        self.assertEqual(counts["right-outer"], 13)
        self.assertEqual(counts["left-outer"], 13)
        self.assertEqual(environment.track.event_metrics["lap_sequence"], ["right", "right", "left", "left"])
        self.assertAlmostEqual(environment.track.width, 3.0, places=2)
        lanes = [obj for obj in environment.objects if obj.role == "lane_cone"]
        self.assertGreaterEqual(len(lanes), 4)
        self.assertTrue(all(obj.asset == "orange_small" for obj in lanes))

    def test_autocross_arc_length_stays_in_range_for_several_seeds(self) -> None:
        for seed in (1, 8, 12):
            track = generate_track(GeneratorConfig(seed=seed, track_type="autocross"), SeededRNG(seed))
            self.assertGreaterEqual(track.length, 200.0, seed)
            self.assertLessEqual(track.length, 500.0, seed)
            self.assertLessEqual(track.stopping_zone["length_m"], 30.0)
            self.assertTrue(track.stopping_zone["on_track"])
        environment, report = generate_environment(
            GeneratorConfig(seed=8, track_type="autocross", env_density=0.0, background_density=0.0)
        )
        self.assertTrue(report.passed, _failed(report))
        self.assertEqual(sum(1 for obj in environment.objects if obj.role == "lane_cone"), 0)
        again = generate_track(GeneratorConfig(seed=8, track_type="autocross"), SeededRNG(8))
        self.assertEqual(
            [(point.x, point.y) for point in environment.track.centerline],
            [(point.x, point.y) for point in again.centerline],
        )

    def test_different_autocross_seeds_differ(self) -> None:
        first = generate_track(GeneratorConfig(seed=2, track_type="autocross"), SeededRNG(2))
        second = generate_track(GeneratorConfig(seed=3, track_type="autocross"), SeededRNG(3))
        self.assertNotEqual(
            [(round(point.x, 3), round(point.y, 3)) for point in first.centerline],
            [(round(point.x, 3), round(point.y, 3)) for point in second.centerline],
        )

    def test_ebs_is_a_labeled_supplementary_straight(self) -> None:
        environment, report = generate_environment(
            GeneratorConfig(seed=5, track_type="ebs", env_density=0.0, background_density=0.0)
        )
        self.assertTrue(report.passed, _failed(report))
        info = environment.track.event_metrics
        self.assertFalse(info["scored_event"])
        self.assertAlmostEqual(info["accel_length_m"], 20.0, places=2)
        self.assertAlmostEqual(info["emergency_stop_length_m"], 8.5, places=2)
        self.assertTrue(any("assumption" in note.lower() for note in environment.track.assumptions))
        self.assertLess(environment.track.length, 80.0)
        self.assertGreater(environment.track.length, 40.0)

    def test_same_seed_exports_the_same_ground_truth(self) -> None:
        config = GeneratorConfig(seed=4, track_type="acceleration", env_density=0.0, background_density=0.0)
        first = assemble_environment(config)
        second = assemble_environment(config)
        self.assertEqual(first.ground_truth["centerline"], second.ground_truth["centerline"])
        self.assertEqual(first.ground_truth["cones"], second.ground_truth["cones"])
        cone = first.ground_truth["cones"][0]
        for key in ("id", "x", "y", "z", "color", "side", "base_m", "yaw_rad"):
            self.assertIn(key, cone)
        with tempfile.TemporaryDirectory() as directory:
            paths = write_ground_truth_files(first.ground_truth, Path(directory), 4)
            self.assertTrue(all(path.is_file() for path in paths))
            self.assertTrue(paths[0].name.endswith("_ground_truth.json"))
            self.assertTrue(paths[2].name.endswith("_cones.csv"))


if __name__ == "__main__":
    unittest.main()
