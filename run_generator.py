"""Run the generator from Blender, or write a validation report without Blender.

Inside Blender's Scripting workspace, open this file and press Run Script.
The same file works from a terminal:

    blender --background --python run_generator.py -- --seed 1 --self-check

Arguments belong after `--`. Without Blender, the script still builds the
geometry and writes the report; it cannot create the .blend scene.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _script_args() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    # Blender puts its own flags in sys.argv. Ignore them unless the user
    # passed arguments after `--`.
    if Path(sys.argv[0]).name.startswith("blender"):
        return []
    return sys.argv[1:]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an FSAE autonomous racing environment.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--track-width", type=float, default=3.5)
    parser.add_argument("--cone-spacing", type=float, default=5.0)
    parser.add_argument("--track-type", default="trackdrive", choices=("trackdrive", "autocross", "custom"))
    parser.add_argument("--profile", default="us_fsae_driverless_2025")
    parser.add_argument("--density", type=float, default=1.0)
    parser.add_argument("--no-trees", action="store_true")
    parser.add_argument("--no-tents", action="store_true")
    parser.add_argument("--no-spectators", action="store_true")
    parser.add_argument("--no-barriers", action="store_true")
    parser.add_argument("--report", default="", help="Path to write the text report. A .json file is written beside it.")
    parser.add_argument("--save", default="", help="Optional .blend output path.")
    parser.add_argument("--self-check", action="store_true", help="Build through the add-on operator and check the scene.")
    return parser


def _write_report(path: str, report) -> None:
    from fsae_env_generator.validation import format_report

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_report(report), encoding="utf-8")
    target.with_suffix(".json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    print(f"Wrote {target}")


def _self_check() -> None:
    import bpy

    import fsae_env_generator

    fsae_env_generator.register()
    result = bpy.ops.fsae.generate()
    if "FINISHED" not in set(result):
        raise RuntimeError(f"fsae.generate returned {result}")
    root = bpy.data.collections.get("FSAE_Environment")
    if root is None:
        raise RuntimeError("FSAE_Environment collection is missing.")
    child_names = {child.name for child in root.children}
    for required in ("Track", "Cones", "Environment", "Lighting", "Cameras"):
        if required not in child_names:
            raise RuntimeError(f"Missing collection {required}. Found {sorted(child_names)}.")
    blues = [obj for obj in bpy.data.objects if obj.name.startswith("FSAE_blue_small")]
    yellows = [obj for obj in bpy.data.objects if obj.name.startswith("FSAE_yellow_small")]
    larges = [obj for obj in bpy.data.objects if obj.name.startswith("FSAE_orange_large")]
    trees = [obj for obj in bpy.data.objects if obj.name.startswith("FSAE_tree")]
    if len(blues) < 8 or len(yellows) < 8 or len(larges) < 2 or len(trees) < 1:
        raise RuntimeError(
            f"Unexpected counts blue={len(blues)} yellow={len(yellows)} large={len(larges)} trees={len(trees)}."
        )
    mesh_users = bpy.data.meshes["FSAE_MESH_blue_small"].users
    if mesh_users < len(blues):
        raise RuntimeError("Blue cones are not sharing one mesh.")
    if bpy.data.texts.get("FSAE_Validation_Report") is None:
        raise RuntimeError("Validation report text block is missing.")
    if root.get("fsae_rules_profile") != "us_fsae_driverless_2025":
        raise RuntimeError("Rules profile was not stored on the collection.")
    if not bpy.context.scene.get("fsae_validation_passed"):
        raise RuntimeError("Validation did not pass.")
    if bpy.context.scene.unit_settings.length_unit != "METERS":
        raise RuntimeError("Scene is not set to meters.")
    before = len(blues)
    again = bpy.ops.fsae.generate()
    if "FINISHED" not in set(again):
        raise RuntimeError(f"Second generate returned {again}")
    blues_again = [obj for obj in bpy.data.objects if obj.name.startswith("FSAE_blue_small")]
    if len(blues_again) != before:
        raise RuntimeError(f"Generate accumulated objects: {before} then {len(blues_again)}.")
    bpy.ops.fsae.clear()
    if bpy.data.collections.get("FSAE_Environment") is not None:
        raise RuntimeError("Clear left FSAE_Environment behind.")
    stored = bpy.context.scene.get("fsae_config")
    if not stored:
        raise RuntimeError("Clear removed the stored config, so Regenerate cannot run.")
    regenerated = bpy.ops.fsae.regenerate()
    if "FINISHED" not in set(regenerated):
        raise RuntimeError(f"Regenerate returned {regenerated}")
    if bpy.data.collections.get("FSAE_Environment") is None:
        raise RuntimeError("Regenerate did not rebuild the environment.")
    fsae_env_generator.unregister()
    print("SELF_CHECK_OK")


def main() -> int:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    args = _parser().parse_args(_script_args())
    try:
        import bpy
    except ImportError:
        bpy = None

    if args.self_check:
        if bpy is None:
            print("Self-check needs Blender. Run: blender --background --python run_generator.py -- --self-check")
            return 1
        _self_check()
        if args.save:
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save).resolve()))
        return 0

    from fsae_env_generator.config import GeneratorConfig
    from fsae_env_generator.pipeline import generate_environment
    from fsae_env_generator.validation import format_report

    config = GeneratorConfig(
        seed=args.seed,
        track_width=args.track_width,
        cone_spacing=args.cone_spacing,
        track_type=args.track_type,
        rules_profile=args.profile,
        env_density=args.density,
        enable_trees=not args.no_trees,
        enable_tents=not args.no_tents,
        enable_spectators=not args.no_spectators,
        enable_barriers=not args.no_barriers,
    )
    environment, report = generate_environment(config)
    print(format_report(report))
    if args.report:
        _write_report(args.report, report)
    if bpy is None:
        print("Blender is not available, so no scene was created.")
        return 0 if report.passed else 1
    from fsae_env_generator.blender_backend import build_blender_scene

    build_blender_scene(environment, report)
    if report.passed:
        from fsae_env_generator.blender_backend import save_generated_blend

        save_generated_blend(config.seed)
    elif not args.save:
        print("Validation did not pass, so the track was not saved.")
    if args.save:
        destination = Path(args.save).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(
            "EXEC_DEFAULT",
            filepath=str(destination),
            check_existing=False,
        )
        print(f"Saved {destination}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
