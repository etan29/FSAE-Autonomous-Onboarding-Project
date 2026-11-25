"""Cones, environment, profiles, and the validation report."""

from __future__ import annotations

import unittest

from fsae_env_generator.assets import build_cone_library, mesh_aabb
from fsae_env_generator.config import GeneratorConfig, config_from_json, config_to_json, resolve_limits
from fsae_env_generator.pipeline import assemble_environment, generate_environment


class SceneTests(unittest.TestCase):
    def test_cone_meshes_have_the_specified_size_and_stripes(self) -> None:
        profile = GeneratorConfig().profile()
        library = build_cone_library(profile)
        for kind, base, height in (
            ("blue_small", 0.228, 0.325),
            ("yellow_small", 0.228, 0.325),
            ("orange_large", 0.285, 0.505),
        ):
            low, high = mesh_aabb(library[kind])
            self.assertAlmostEqual(high[0] - low[0], base, places=4)
            self.assertAlmostEqual(high[1] - low[1], base, places=4)
            self.assertAlmostEqual(high[2] - low[2], height, places=4)
            self.assertAlmostEqual(low[2], 0.0, places=6)
        self.assertIn("cone_white", library["blue_small"].material_slots)
        self.assertIn("cone_black", library["yellow_small"].material_slots)
        self.assertEqual(library["orange_large"].material_slots.count("cone_white"), 1)
        white_faces = [
            slot
            for slot, material in zip(library["orange_large"].face_materials, library["orange_large"].face_materials)
            if library["orange_large"].material_slots[material] == "cone_white"
        ]
        self.assertGreaterEqual(len(white_faces), 8)

    def test_formula_student_caps_spacing_and_us_profile_does_not(self) -> None:
        capped = resolve_limits(GeneratorConfig(rules_profile="formula_student_2026", cone_spacing=6.0))
        self.assertAlmostEqual(capped.max_cone_spacing, 5.0)
        self.assertAlmostEqual(capped.nominal_cone_spacing, 5.0)
        self.assertTrue(any("5.00" in warning for warning in capped.warnings))
        open_limit = resolve_limits(GeneratorConfig(cone_spacing=6.0))
        self.assertAlmostEqual(open_limit.max_cone_spacing, 6.0)
        fs_profile = GeneratorConfig(rules_profile="formula_student_2026").profile()
        self.assertIsNone(fs_profile.min_track_width_m)
        self.assertIsNone(fs_profile.max_straight_length_m)

    def test_config_round_trip(self) -> None:
        config = GeneratorConfig(seed=9, track_width=4.0, cone_spacing=3.0, track_type="autocross")
        restored = config_from_json(config_to_json(config))
        self.assertEqual(restored.seed, 9)
        self.assertEqual(restored.track_type, "autocross")
        self.assertAlmostEqual(restored.track_width, 4.0)

    def test_full_environment_passes_and_repeats(self) -> None:
        environment, report = generate_environment(GeneratorConfig(seed=1))
        self.assertTrue(report.passed, [check.detail for check in report.checks if not check.passed])
        self.assertGreater(report.cones_per_boundary["left"], 10)
        self.assertGreater(report.cones_per_boundary["right"], 10)
        self.assertEqual(report.collision_violations, 0)
        self.assertIn("us_fsae_driverless_2025", report.rules_profile)
        left = [obj for obj in environment.objects if obj.role == "boundary_cone" and obj.metadata["side"] == "left"]
        self.assertTrue(all(obj.asset in {"blue_small", "orange_large"} for obj in left))
        self.assertTrue(any(obj.asset == "orange_large" for obj in left))
        self.assertGreater(sum(1 for obj in environment.objects if obj.role == "tree"), 0)
        self.assertGreater(sum(1 for obj in environment.objects if obj.role == "tent"), 0)
        self.assertGreater(sum(1 for obj in environment.objects if obj.role == "spectator"), 0)
        self.assertEqual(environment.objects[0].z, 0.0)

    def test_different_seeds_differ_and_trackdrive_has_no_lanes(self) -> None:
        first = assemble_environment(GeneratorConfig(seed=1))
        second = assemble_environment(GeneratorConfig(seed=2))
        self.assertNotEqual(first.signature(), second.signature())
        self.assertEqual(sum(1 for obj in first.objects if obj.role == "lane_cone"), 0)

    def test_autocross_adds_orange_lanes_and_density_zero_skips_props(self) -> None:
        autocross = assemble_environment(GeneratorConfig(seed=5, track_type="autocross"))
        lanes = [obj for obj in autocross.objects if obj.role == "lane_cone"]
        self.assertGreaterEqual(len(lanes), 4)
        self.assertTrue(all(obj.asset == "orange_small" for obj in lanes))
        empty = assemble_environment(GeneratorConfig(seed=5, env_density=0.0, background_density=0.0))
        self.assertEqual(sum(1 for obj in empty.objects if obj.role == "tree"), 0)
        self.assertEqual(sum(1 for obj in empty.objects if obj.role == "spectator"), 0)
        self.assertGreater(sum(1 for obj in empty.objects if obj.role == "boundary_cone"), 0)

    def test_us_six_meter_spacing_is_allowed_and_formula_student_is_not(self) -> None:
        us_scene, us_report = generate_environment(GeneratorConfig(seed=4, cone_spacing=6.0))
        self.assertTrue(us_report.passed, [check.name for check in us_report.checks if not check.passed])
        self.assertGreater(us_report.maximum_cone_spacing_m["left"], 5.0)
        fs_scene, fs_report = generate_environment(
            GeneratorConfig(seed=4, rules_profile="formula_student_2026", cone_spacing=6.0)
        )
        self.assertTrue(fs_report.passed, [check.name for check in fs_report.checks if not check.passed])
        self.assertLessEqual(fs_report.maximum_cone_spacing_m["left"], 5.0 + 0.25)
        self.assertLessEqual(fs_report.maximum_cone_spacing_m["right"], 5.0 + 0.25)
        width_check = next(check for check in fs_report.checks if check.name == "Track width meets the selected profile")
        self.assertIn("does not define", width_check.detail)
        self.assertTrue(us_scene.seed == fs_scene.seed)

    def test_track_narrower_than_the_profile_fails_validation(self) -> None:
        _scene, report = generate_environment(GeneratorConfig(seed=3, track_width=2.2))
        width_check = next(check for check in report.checks if check.name == "Track width meets the selected profile")
        self.assertFalse(width_check.passed)
        self.assertFalse(report.passed)

    def test_collections_are_assigned_on_every_object(self) -> None:
        environment = assemble_environment(GeneratorConfig(seed=2, track_type="autocross"))
        collections = {obj.collection for obj in environment.objects}
        self.assertIn("Cones/Blue_Cones", collections)
        self.assertIn("Cones/Yellow_Cones", collections)
        self.assertIn("Cones/Large_Orange_Cones", collections)
        self.assertIn("Cones/Orange_Cones", collections)
        self.assertIn("Environment/Trees", collections)
        self.assertTrue(all(obj.collection for obj in environment.objects))


if __name__ == "__main__":
    unittest.main()
