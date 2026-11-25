"""Build a complete environment description from a config and a seed.

`assemble_environment` is pure: the same config produces the same scene.
`generate_environment` builds twice and records whether the two results match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .assets import SURFACE_MATERIALS, build_asset_library
from .config import GeneratorConfig, config_to_dict, resolve_limits
from .cones import NameSequence, generate_cones
from .environment import generate_environment as generate_surroundings
from .environment import terrain_bounds, terrain_mesh
from .math2d import Vec2, bounding_box
from .models import MeshData, PlacedObject, UniqueMesh
from .rng import SeededRNG
from .track import TrackData, generate_track
from .validation import ValidationReport, scene_signature, validate_environment

_LIGHTING = {
    "noon": {
        "elevation": 68.0,
        "azimuth": 35.0,
        "energy": 4.5,
        "sun_color": (1.0, 0.96, 0.9),
        "world_color": (0.42, 0.62, 0.92),
        "world_energy": 0.9,
    },
    "overcast": {
        "elevation": 55.0,
        "azimuth": 20.0,
        "energy": 1.6,
        "sun_color": (0.82, 0.85, 0.9),
        "world_color": (0.62, 0.66, 0.7),
        "world_energy": 1.1,
    },
    "sunset": {
        "elevation": 12.0,
        "azimuth": 80.0,
        "energy": 3.0,
        "sun_color": (1.0, 0.42, 0.16),
        "world_color": (0.78, 0.38, 0.22),
        "world_energy": 0.35,
    },
    "night": {
        "elevation": -8.0,
        "azimuth": 10.0,
        "energy": 0.05,
        "sun_color": (0.55, 0.65, 0.9),
        "world_color": (0.01, 0.015, 0.04),
        "world_energy": 0.04,
    },
}


@dataclass
class GeneratedEnvironment:
    """Everything the Blender backend needs, with no Blender types attached."""

    config: dict
    seed: int
    profile_id: str
    profile_name: str
    profile_revision: str
    profile_note: str
    track: TrackData
    objects: list[PlacedObject]
    assets: dict[str, MeshData]
    unique_meshes: list[UniqueMesh]
    lighting: dict
    camera: dict
    label_text: str
    label_position: tuple[float, float, float]
    terrain_bounds: tuple[float, float, float, float]
    warnings: list[str] = field(default_factory=list)

    def signature(self) -> list[tuple]:
        rows = scene_signature(self.track, self.objects)
        rows.append(
            (
                "camera",
                round(self.camera["x"], 6),
                round(self.camera["y"], 6),
                round(self.camera["z"], 6),
            )
        )
        rows.append(("sun", round(self.lighting["azimuth"], 6), round(self.lighting["elevation"], 6)))
        for mesh in self.unique_meshes:
            rows.append((mesh.name, round(mesh.x, 6), round(mesh.y, 6), len(mesh.mesh.vertices)))
        return rows


def _lighting(config: GeneratorConfig, rng: SeededRNG) -> tuple[dict, str]:
    weather = config.weather if config.weather in {"clear", "overcast", "rain", "fog"} else "clear"
    preset_name = config.lighting if config.lighting in _LIGHTING else "noon"
    note = ""
    if weather == "rain":
        preset_name = "overcast"
        note = "Rain is represented by dim overcast light. Particle rain is not simulated."
    elif weather == "fog":
        note = "Fog is represented by a dimmer gray background. Volumetric fog is not simulated."
    elif weather == "overcast" and preset_name == "noon":
        preset_name = "overcast"
    preset = _LIGHTING[preset_name]
    azimuth = preset["azimuth"] + rng.child("lighting").uniform(-18.0, 18.0)
    energy = preset["energy"]
    world_energy = preset["world_energy"]
    if weather == "fog":
        energy *= 0.55
        world_energy *= 0.6
    return (
        {
            "preset": preset_name,
            "weather": weather,
            "azimuth": azimuth,
            "elevation": preset["elevation"],
            "energy": energy,
            "sun_color": preset["sun_color"],
            "world_color": preset["world_color"],
            "world_energy": world_energy,
            "note": note,
        },
        note,
    )


def _camera(track: TrackData, rng: SeededRNG) -> dict:
    min_x, min_y, max_x, max_y = bounding_box(track.centerline)
    center = Vec2((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
    span = max(max_x - min_x, max_y - min_y, 30.0)
    yaw = rng.child("camera").uniform(0.0, 2.0 * math.pi)
    distance = span * 0.95
    return {
        "x": center.x + math.cos(yaw) * distance,
        "y": center.y + math.sin(yaw) * distance,
        "z": span * 0.62,
        "target_x": center.x,
        "target_y": center.y,
        "target_z": 0.0,
    }


def assemble_environment(config: GeneratorConfig) -> GeneratedEnvironment:
    """Create one environment. Callers that need a report should use `generate_environment`."""
    profile = config.profile()
    limits = resolve_limits(config)
    rng = SeededRNG(int(config.seed))
    track = generate_track(config, rng, limits)
    names = NameSequence()
    cones, markings, cone_warnings = generate_cones(track, profile, config, limits, rng, names)
    surroundings, prop_meshes, env_warnings = generate_surroundings(track, cones, config, rng, names)
    assets = build_asset_library(profile)
    bounds = terrain_bounds(track, config)
    surface_material = SURFACE_MATERIALS.get(config.surface_appearance, "asphalt")
    surface = UniqueMesh(
        name="FSAE_Track_Surface",
        collection="Track/Track_Surface",
        mesh=MeshData(
            vertices=track.surface_vertices,
            faces=track.surface_faces,
            material_slots=[surface_material],
            face_materials=[0] * len(track.surface_faces),
        ),
    )
    unique = [terrain_mesh(bounds), surface, *markings, *prop_meshes]
    lighting, light_note = _lighting(config, rng)
    warnings = [*cone_warnings, *env_warnings]
    if light_note:
        warnings.append(light_note)
    min_x, min_y, max_x, max_y = bounds
    label = f"{profile.name}\n{profile.revision}"
    return GeneratedEnvironment(
        config=config_to_dict(config),
        seed=int(config.seed),
        profile_id=profile.id,
        profile_name=profile.name,
        profile_revision=profile.revision,
        profile_note=profile.source_note,
        track=track,
        objects=[*cones, *surroundings],
        assets=assets,
        unique_meshes=unique,
        lighting=lighting,
        camera=_camera(track, rng),
        label_text=label,
        label_position=(min_x + 1.0, max_y - 1.0, 0.2),
        terrain_bounds=bounds,
        warnings=warnings,
    )


def generate_environment(config: GeneratorConfig) -> tuple[GeneratedEnvironment, ValidationReport]:
    """Build the environment, repeat the build, and validate both the geometry and the repeat."""
    first = assemble_environment(config)
    second = assemble_environment(config)
    reproducible = first.signature() == second.signature()
    report = validate_environment(
        first.track,
        first.objects,
        first.assets,
        config,
        reproducible=reproducible,
        extra_warnings=first.warnings,
        terrain_bounds=first.terrain_bounds,
    )
    return first, report
