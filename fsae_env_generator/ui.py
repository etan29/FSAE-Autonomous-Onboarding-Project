"""Sidebar controls for seed, track size, cone spacing, and the environment."""

from __future__ import annotations

import bpy

from .blender_backend import (
    build_blender_scene,
    clear_generated_scene,
    read_input_centerline,
    save_generated_blend,
)
from .config import PROFILES, GeneratorConfig, config_from_json, config_to_json
from .models import INPUT_CURVE_NAME
from .pipeline import generate_environment

_PROFILE_ITEMS = tuple(
    (profile.id, profile.name, profile.source_note) for profile in PROFILES.values()
)


class FSAESettings(bpy.types.PropertyGroup):
    """Values shown in the sidebar. Advanced limits stay on GeneratorConfig defaults."""

    seed: bpy.props.IntProperty(name="Seed", default=1, min=0, description="Integer that drives every random choice")
    track_width: bpy.props.FloatProperty(
        name="Track Width",
        default=3.5,
        min=1.0,
        soft_min=3.0,
        unit="LENGTH",
        description="Distance between the inner edges of the left and right cone bases, in meters",
    )
    cone_spacing: bpy.props.FloatProperty(
        name="Cone Spacing",
        default=5.0,
        min=1.0,
        soft_max=8.0,
        unit="LENGTH",
        description="Spacing along straights, in meters. High-curvature turns tighten toward 2 m. Formula Student caps this at 5 m",
    )
    track_type: bpy.props.EnumProperty(
        name="Track Type",
        items=(
            ("trackdrive", "Trackdrive", "Closed loop with a start/finish gate"),
            ("autocross", "Autocross", "Closed loop plus orange entry and exit lanes beside the start"),
            ("custom", "Custom", f"Use the curve object named {INPUT_CURVE_NAME}"),
        ),
        default="trackdrive",
    )
    rules_profile: bpy.props.EnumProperty(
        name="Rules Profile",
        items=_PROFILE_ITEMS,
        default="us_fsae_driverless_2025",
    )
    env_density: bpy.props.FloatProperty(
        name="Environment Density",
        default=1.0,
        min=0.0,
        max=3.0,
        description="Scales trees, tents, spectators, and barriers. Zero leaves only the track and cones",
    )
    enable_trees: bpy.props.BoolProperty(name="Trees", default=True)
    enable_tents: bpy.props.BoolProperty(name="Tents", default=True)
    enable_spectators: bpy.props.BoolProperty(name="Spectators", default=True)
    enable_barriers: bpy.props.BoolProperty(name="Barriers", default=True)
    last_status: bpy.props.StringProperty(name="Status", default="")
    last_saved_path: bpy.props.StringProperty(name="Saved File", default="")

    def to_config(self) -> GeneratorConfig:
        return GeneratorConfig(
            seed=int(self.seed),
            track_width=float(self.track_width),
            cone_spacing=float(self.cone_spacing),
            track_type=self.track_type,
            rules_profile=self.rules_profile,
            env_density=float(self.env_density),
            enable_trees=bool(self.enable_trees),
            enable_tents=bool(self.enable_tents),
            enable_spectators=bool(self.enable_spectators),
            enable_barriers=bool(self.enable_barriers),
        )


def _report_and_save(operator, settings, seed: int, report, regenerated: bool) -> set[str]:
    """Save after a finished build whose validation passed. Clear never calls this."""
    state = "PASS" if report.passed else "FAIL"
    action = "regenerated" if regenerated else "seed"
    counts = f"{report.cones_per_boundary.get('left', 0)}/{report.cones_per_boundary.get('right', 0)} cones"
    if not report.passed:
        settings.last_saved_path = ""
        settings.last_status = f"{state}  {action} {seed}  {counts}\nNot saved. Validation did not pass."
        operator.report({"WARNING"}, f"FSAE environment {state} for seed {seed}. Scene was not saved.")
        return {"FINISHED"}
    try:
        path = save_generated_blend(seed)
    except Exception as exc:
        settings.last_saved_path = ""
        settings.last_status = f"{state}  {action} {seed}  {counts}\nSave failed: {exc}"
        operator.report({"ERROR"}, str(exc))
        return {"CANCELLED"}
    settings.last_saved_path = str(path)
    settings.last_status = f"{state}  {action} {seed}  {counts}\nSaved {path.name}"
    operator.report({"INFO"}, f"Saved {path}")
    return {"FINISHED"}


class FSAE_OT_generate(bpy.types.Operator):
    """Clear the previous environment and build a new one from the sidebar."""

    bl_idname = "fsae.generate"
    bl_label = "Generate"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.fsae_settings
        config = settings.to_config()
        try:
            if config.track_type == "custom":
                points, cyclic = read_input_centerline()
                if len(points) < 4:
                    self.report(
                        {"ERROR"},
                        f"Custom tracks need a curve named {INPUT_CURVE_NAME} with at least 4 points.",
                    )
                    settings.last_status = "Custom curve missing"
                    return {"CANCELLED"}
                config.centerline = points
                if cyclic is not None:
                    config.closed_loop = cyclic
            environment, report = generate_environment(config)
            build_blender_scene(environment, report)
        except Exception as exc:
            settings.last_status = f"Error: {exc}"
            settings.last_saved_path = ""
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return _report_and_save(self, settings, config.seed, report, regenerated=False)


class FSAE_OT_regenerate(bpy.types.Operator):
    """Rebuild the last environment from the seed and settings stored on the scene."""

    bl_idname = "fsae.regenerate"
    bl_label = "Regenerate"
    bl_description = "Rebuild the stored environment. Sidebar edits are not used unless nothing has been generated yet"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.fsae_settings
        stored = context.scene.get("fsae_config")
        try:
            if stored:
                config = config_from_json(stored)
            else:
                config = settings.to_config()
                self.report({"WARNING"}, "No stored environment yet. Using the current sidebar settings.")
            environment, report = generate_environment(config)
            build_blender_scene(environment, report)
        except Exception as exc:
            settings.last_status = f"Error: {exc}"
            settings.last_saved_path = ""
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return _report_and_save(self, settings, config.seed, report, regenerated=True)


class FSAE_OT_clear(bpy.types.Operator):
    """Delete the generated track, cones, and environment."""

    bl_idname = "fsae.clear"
    bl_label = "Clear"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        clear_generated_scene()
        context.scene.fsae_settings.last_status = "Cleared"
        context.scene.fsae_settings.last_saved_path = ""
        self.report({"INFO"}, "Cleared the generated FSAE environment.")
        return {"FINISHED"}


class FSAE_PT_panel(bpy.types.Panel):
    bl_label = "FSAE Environment"
    bl_idname = "FSAE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FSAE"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fsae_settings
        layout.prop(settings, "seed")
        layout.prop(settings, "track_width")
        layout.prop(settings, "cone_spacing")
        layout.prop(settings, "track_type")
        layout.prop(settings, "rules_profile")
        layout.prop(settings, "env_density")
        column = layout.column(align=True)
        column.prop(settings, "enable_trees")
        column.prop(settings, "enable_tents")
        column.prop(settings, "enable_spectators")
        column.prop(settings, "enable_barriers")
        row = layout.row(align=True)
        row.operator("fsae.generate", text="Generate")
        row.operator("fsae.regenerate", text="Regenerate")
        row.operator("fsae.clear", text="Clear")
        if settings.last_status:
            for line in settings.last_status.split("\n"):
                layout.label(text=line)
        if settings.last_saved_path:
            layout.label(text=settings.last_saved_path)


_CLASSES = (
    FSAESettings,
    FSAE_OT_generate,
    FSAE_OT_regenerate,
    FSAE_OT_clear,
    FSAE_PT_panel,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fsae_settings = bpy.props.PointerProperty(type=FSAESettings)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "fsae_settings"):
        del bpy.types.Scene.fsae_settings
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
