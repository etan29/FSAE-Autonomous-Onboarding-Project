"""Shared scene records. These stay free of Blender so they can be tested directly."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MeshData:
    """A triangle or quad mesh with material slots. Units are meters."""

    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, ...]]
    material_slots: list[str]
    face_materials: list[int]
    vertex_colors: list[tuple[float, float, float, float]] | None = None


@dataclass
class PlacedObject:
    """One instanced object. `asset` refers to a shared mesh in the library."""

    asset: str
    name: str
    collection: str
    x: float
    y: float
    z: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    role: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class UniqueMesh:
    """A one-off mesh such as the asphalt ribbon or the start line."""

    name: str
    collection: str
    mesh: MeshData
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


COLLECTION_PATHS = (
    "Track/Track_Surface",
    "Track/Track_Centerline",
    "Track/Track_Boundaries",
    "Track/Markings",
    "Cones/Blue_Cones",
    "Cones/Yellow_Cones",
    "Cones/Orange_Cones",
    "Cones/Large_Orange_Cones",
    "Environment/Trees",
    "Environment/Tents",
    "Environment/Spectators",
    "Environment/Barriers",
    "Environment/Buildings",
    "Environment/Terrain",
    "Environment/Props",
    "Lighting",
    "Cameras",
)

ROOT_COLLECTION = "FSAE_Environment"
INPUT_CURVE_NAME = "FSAE_Input_Centerline"
REPORT_TEXT_NAME = "FSAE_Validation_Report"
