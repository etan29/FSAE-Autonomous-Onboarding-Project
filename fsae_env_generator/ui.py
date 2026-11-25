"""Sidebar controls for the 2026 driverless events, cone spacing, and the environment."""

from __future__ import annotations

import json

import bpy

from .blender_backend import (
    build_blender_scene,
    clear_generated_scene,
    generated_tracks_directory,
    read_input_centerline,
    save_generated_blend,
)
from .config import PROFILES, GeneratorConfig, config_from_json, config_to_json, event_defaults, event_description
from .ground_truth import write_ground_truth_files
from .models import INPUT_CURVE_NAME
from .pipeline import generate_environment


def _on_track_type(self, context):
    """Apply event defaults only after the user changes the dropdown."""
    del context
    current = self.track_type
    previous = self.get("fsae_last_event")
    self["fsae_last_event"] = current
    if previous is None or previous == current:
        return
    for key, value in event_defaults(current).items():
        if key in self.bl_rna.properties:
            setattr(self, key, value)

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
        description="Spacing along straights, in meters. Formula Student caps this at 5 m",
    )
    corner_cone_spacing: bpy.props.FloatProperty(
        name="Corner Cone Spacing",
        default=2.0,
        min=1.0,
        soft_max=6.0,
        unit="LENGTH",
        description="Gap used in tight corners, in meters. Straights keep the straight spacing",
    )
    cone_jitter_m: bpy.props.FloatProperty(
        name="Cone Jitter",
        default=0.0,
        min=0.0,
        soft_max=0.15,
        unit="LENGTH",
        description="Random lateral offset. Zero keeps every cone on the boundary and aligned with it",
    )
    terrain_size: bpy.props.FloatProperty(
        name="Terrain Size",
        default=0.0,
        min=0.0,
        soft_max=400.0,
        unit="LENGTH",
        description="Minimum ground size in meters. Zero fits the track plus the margin",
    )
    track_type: bpy.props.EnumProperty(
        name="Event",
        items=(
            ("autocross", "Autocross", "Closed lap, 200–500 m centerline arc length"),
            ("acceleration", "Acceleration", "75 m timed straight plus an exit lane"),
            ("skidpad", "Skidpad", "Figure eight with a real crossover"),
            ("ebs", "EBS Brake Test", "Inspection straight. Not a scored event"),
            ("trackdrive", "Trackdrive", "Same layout limits as autocross"),
            ("custom", "Custom", f"Use the curve object named {INPUT_CURVE_NAME}"),
        ),
        default="autocross",
        update=_on_track_type,
    )
    stopping_zone_length: bpy.props.FloatProperty(
        name="Stopping Zone Length",
        default=30.0,
        min=0.0,
        soft_max=75.0,
        unit="LENGTH",
        description="0 uses the event default. Acceleration max 75 m, autocross max 30 m, skidpad exit 25 m",
    )
    stopping_zone_width: bpy.props.FloatProperty(
        name="Stopping Zone Width",
        default=3.5,
        min=0.0,
        soft_max=12.0,
        unit="LENGTH",
        description="0 uses the track width",
    )
    acceleration_length: bpy.props.FloatProperty(
        name="Acceleration Length",
        default=75.0,
        min=75.0,
        max=75.0,
        unit="LENGTH",
        description="Fixed at 75 m by D.9.1.1",
    )
    skidpad_entry_length: bpy.props.FloatProperty(name="Skidpad Entry", default=15.0, min=5.0, soft_max=30.0, unit="LENGTH")
    skidpad_exit_length: bpy.props.FloatProperty(name="Skidpad Exit", default=25.0, min=5.0, soft_max=40.0, unit="LENGTH")
    autocross_min_length: bpy.props.FloatProperty(name="Autocross Min Length", default=200.0, min=200.0, max=500.0, unit="LENGTH")
    autocross_max_length: bpy.props.FloatProperty(name="Autocross Max Length", default=500.0, min=200.0, max=500.0, unit="LENGTH")
    max_corner_radius: bpy.props.FloatProperty(name="Max Corner Radius", default=30.0, min=4.5, soft_max=40.0, unit="LENGTH")
    s_curve_frequency: bpy.props.FloatProperty(name="S-Curve Frequency", default=0.9, min=0.0, max=1.0)
    chicane_frequency: bpy.props.FloatProperty(name="Chicane Frequency", default=0.75, min=0.0, max=1.0)
    hairpin_frequency: bpy.props.FloatProperty(name="Hairpin Frequency", default=0.0, min=0.0, max=1.0)
    slalom_frequency: bpy.props.FloatProperty(name="Slalom Frequency", default=0.0, min=0.0, max=1.0)
    track_width_variation: bpy.props.FloatProperty(name="Width Variation", default=0.0, min=0.0, max=0.2)
    complexity: bpy.props.FloatProperty(name="Complexity", default=0.55, min=0.0, max=1.0)
    ebs_approach_length: bpy.props.FloatProperty(
        name="EBS Approach",
        default=15.0,
        min=0.0,
        soft_max=40.0,
        unit="LENGTH",
        description="Simulation assumption. The rules do not publish an approach length",
    )
    ebs_accel_length: bpy.props.FloatProperty(
        name="EBS Accel Zone",
        default=20.0,
        min=5.0,
        max=20.0,
        unit="LENGTH",
        description="Distance allowed to reach 40 km/h. Maximum 20 m (DI.2.2.2)",
    )
    ebs_stop_length: bpy.props.FloatProperty(
        name="EBS Stop Length",
        default=8.5,
        min=2.0,
        max=8.5,
        unit="LENGTH",
        description="Emergency stop region. Maximum 8.5 m (DI.2.2.2)",
    )
    ebs_rest_length: bpy.props.FloatProperty(
        name="EBS Rest Corridor",
        default=10.0,
        min=0.0,
        soft_max=30.0,
        unit="LENGTH",
        description="Simulation assumption past the 8.5 m stop",
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
    enable_vans: bpy.props.BoolProperty(name="Vans", default=True)
    enable_trailers: bpy.props.BoolProperty(name="Trailers", default=True)
    enable_timing_structures: bpy.props.BoolProperty(name="Timing Structures", default=True)
    enable_background_vehicles: bpy.props.BoolProperty(name="Background Vehicles", default=True)
    enable_paddock_equipment: bpy.props.BoolProperty(name="Paddock Equipment", default=True)
    last_status: bpy.props.StringProperty(name="Status", default="")
    last_saved_path: bpy.props.StringProperty(name="Saved File", default="")

    def to_config(self) -> GeneratorConfig:
        return GeneratorConfig(
            seed=int(self.seed),
            track_width=float(self.track_width),
            cone_spacing=float(self.cone_spacing),
            corner_cone_spacing=float(self.corner_cone_spacing),
            cone_jitter_m=float(self.cone_jitter_m),
            terrain_size=float(self.terrain_size),
            track_type=self.track_type,
            rules_profile=self.rules_profile,
            env_density=float(self.env_density),
            stopping_zone_length=float(self.stopping_zone_length),
            stopping_zone_width=float(self.stopping_zone_width),
            acceleration_length=float(self.acceleration_length),
            skidpad_entry_length=float(self.skidpad_entry_length),
            skidpad_exit_length=float(self.skidpad_exit_length),
            autocross_min_length=float(self.autocross_min_length),
            autocross_max_length=float(self.autocross_max_length),
            max_corner_radius=float(self.max_corner_radius),
            s_curve_frequency=float(self.s_curve_frequency),
            chicane_frequency=float(self.chicane_frequency),
            hairpin_frequency=float(self.hairpin_frequency),
            slalom_frequency=float(self.slalom_frequency),
            track_width_variation=float(self.track_width_variation),
            complexity=float(self.complexity) if self.track_type == "autocross" else None,
            ebs_approach_length=float(self.ebs_approach_length),
            ebs_accel_length=float(self.ebs_accel_length),
            ebs_stop_length=float(self.ebs_stop_length),
            ebs_rest_length=float(self.ebs_rest_length),
            enable_trees=bool(self.enable_trees),
            enable_tents=bool(self.enable_tents),
            enable_spectators=bool(self.enable_spectators),
            enable_barriers=bool(self.enable_barriers),
            enable_vans=bool(self.enable_vans),
            enable_trailers=bool(self.enable_trailers),
            enable_timing_structures=bool(self.enable_timing_structures),
            enable_background_vehicles=bool(self.enable_background_vehicles),
            enable_paddock_equipment=bool(self.enable_paddock_equipment),
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


class FSAE_OT_export_ground_truth(bpy.types.Operator):
    """Write the ground-truth JSON and CSV next to the saved tracks."""

    bl_idname = "fsae.export_ground_truth"
    bl_label = "Export Ground Truth"
    bl_options = {"REGISTER"}

    def execute(self, context):
        text = bpy.data.texts.get("FSAE_Ground_Truth")
        if text is None:
            self.report({"ERROR"}, "Generate a track before exporting ground truth.")
            return {"CANCELLED"}
        payload = json.loads(text.as_string())
        paths = write_ground_truth_files(payload, generated_tracks_directory(), int(payload.get("seed", 0)))
        context.scene.fsae_settings.last_saved_path = str(paths[0])
        self.report({"INFO"}, f"Exported {paths[0].name}")
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
        layout.prop(settings, "track_type")
        layout.label(text=event_description(settings.track_type))
        layout.prop(settings, "track_width")
        layout.prop(settings, "cone_spacing")
        layout.prop(settings, "corner_cone_spacing")
        layout.prop(settings, "cone_jitter_m")
        layout.prop(settings, "terrain_size")
        layout.prop(settings, "env_density")
        layout.prop(settings, "rules_profile")
        event = settings.track_type
        box = layout.box()
        if event == "acceleration":
            box.prop(settings, "acceleration_length")
            box.prop(settings, "stopping_zone_length")
            box.prop(settings, "stopping_zone_width")
        elif event == "skidpad":
            box.prop(settings, "skidpad_entry_length")
            box.prop(settings, "skidpad_exit_length")
            box.prop(settings, "stopping_zone_length")
            box.prop(settings, "stopping_zone_width")
        elif event == "ebs":
            box.prop(settings, "ebs_approach_length")
            box.prop(settings, "ebs_accel_length")
            box.prop(settings, "ebs_stop_length")
            box.prop(settings, "ebs_rest_length")
            box.prop(settings, "stopping_zone_width")
        elif event == "autocross":
            box.prop(settings, "autocross_min_length")
            box.prop(settings, "autocross_max_length")
            box.prop(settings, "max_corner_radius")
            box.prop(settings, "complexity")
            box.prop(settings, "s_curve_frequency")
            box.prop(settings, "chicane_frequency")
            box.prop(settings, "hairpin_frequency")
            box.prop(settings, "slalom_frequency")
            box.prop(settings, "track_width_variation")
            box.prop(settings, "stopping_zone_length")
            box.prop(settings, "stopping_zone_width")
        column = layout.column(align=True)
        column.prop(settings, "enable_trees")
        column.prop(settings, "enable_tents")
        column.prop(settings, "enable_spectators")
        column.prop(settings, "enable_barriers")
        column.prop(settings, "enable_vans")
        column.prop(settings, "enable_trailers")
        column.prop(settings, "enable_timing_structures")
        column.prop(settings, "enable_background_vehicles")
        column.prop(settings, "enable_paddock_equipment")
        row = layout.row(align=True)
        row.operator("fsae.generate", text="Generate")
        row.operator("fsae.regenerate", text="Regenerate")
        row.operator("fsae.clear", text="Clear")
        layout.operator("fsae.export_ground_truth", text="Export Ground Truth")
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
    FSAE_OT_export_ground_truth,
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
