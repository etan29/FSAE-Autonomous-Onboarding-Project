"""Export the track the simulator should trust.

Rendered cones are not the ground truth. This module writes the centerline,
boundaries, and every cone from the generator records.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import PlacedObject
from .track import TrackData

CONE_SIZE = {
    "blue_small": ("blue", "small", 0.228, 0.325),
    "yellow_small": ("yellow", "small", 0.228, 0.325),
    "orange_small": ("orange", "small", 0.228, 0.325),
    "orange_large": ("orange", "large", 0.285, 0.505),
}

CONE_ROLES = {"boundary_cone", "lane_cone", "scattered_cone"}


def _cone_record(obj: PlacedObject) -> dict:
    color, size_name, base, height = CONE_SIZE.get(obj.asset, ("unknown", "unknown", 0.0, 0.0))
    meta = obj.metadata or {}
    return {
        "id": obj.name,
        "x": obj.x,
        "y": obj.y,
        "z": obj.z,
        "color": meta.get("color", color),
        "size": meta.get("size", size_name),
        "base_m": float(meta.get("base_m", base)),
        "height_m": float(meta.get("height_m", height)),
        "side": meta.get("side", ""),
        "role": obj.role,
        "boundary": meta.get("boundary", meta.get("side", "")),
        "ring": meta.get("ring", ""),
        "marking": meta.get("marking", ""),
        "station_m": meta.get("station_m"),
        "yaw_rad": obj.yaw,
        "pitch_rad": obj.pitch,
        "roll_rad": obj.roll,
        "asset": obj.asset,
    }


def build_ground_truth(track: TrackData, objects: list[PlacedObject], config: dict) -> dict:
    """JSON-ready ground truth. Positions are meters in the scene frame. Z is up."""
    centerline = []
    for index, point in enumerate(track.centerline):
        tangent = track.tangents[index]
        normal = track.left_normals[index]
        curvature = track.curvatures[index] if index < len(track.curvatures) else 0.0
        if track.width_profile and index < len(track.width_profile):
            width = track.width_profile[index]
        elif index < len(track.left_boundary):
            width = track.left_boundary[index].distance(track.right_boundary[index])
        else:
            width = track.width
        centerline.append(
            {
                "index": index,
                "x": point.x,
                "y": point.y,
                "z": 0.0,
                "tangent_x": tangent.x,
                "tangent_y": tangent.y,
                "normal_x": normal.x,
                "normal_y": normal.y,
                "curvature_inv_m": curvature,
                "width_m": width,
            }
        )
    left = [[point.x, point.y, 0.0] for point in track.left_boundary]
    right = [[point.x, point.y, 0.0] for point in track.right_boundary]
    cones = [_cone_record(obj) for obj in objects if obj.role in CONE_ROLES]
    cones.sort(key=lambda row: row["id"])
    start = centerline[0] if centerline else None
    finish_station = track.gate_stations[-1] if track.gate_stations else 0.0
    return {
        "event": track.event_type or config.get("track_type", ""),
        "seed": int(config.get("seed", 0)),
        "units": "meters",
        "frame": "scene XY, Z up, origin at the generator origin",
        "rules_profile": config.get("rules_profile", ""),
        "parameters": config,
        "length_m": track.length,
        "timed_length_m": track.timed_length if track.timed_length else track.length,
        "closed": track.closed,
        "width_m": track.width,
        "start_xyz": [start["x"], start["y"], 0.0] if start else None,
        "finish_station_m": finish_station,
        "gate_stations_m": list(track.gate_stations),
        "stopping_zone": track.stopping_zone,
        "centerline": centerline,
        "left_boundary_xyz": left,
        "right_boundary_xyz": right,
        "cones": cones,
        "event_metrics": track.event_metrics,
        "official": list(track.official_notes),
        "assumptions": list(track.assumptions),
        "note": (
            "Use this file as ground truth. Do not infer the racing line, cone positions, "
            "or the stopping zone from the rendered meshes."
        ),
    }


def write_ground_truth_files(payload: dict, directory: Path, seed: int) -> list[Path]:
    """Write JSON plus centerline and cone CSV files. Same seed overwrites."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"FSAE_Track_Seed_{seed}"
    json_path = directory / f"{stem}_ground_truth.json"
    centerline_path = directory / f"{stem}_centerline.csv"
    cones_path = directory / f"{stem}_cones.csv"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with centerline_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "x",
                "y",
                "z",
                "tangent_x",
                "tangent_y",
                "normal_x",
                "normal_y",
                "curvature_inv_m",
                "width_m",
            ],
        )
        writer.writeheader()
        writer.writerows(payload.get("centerline", []))
    with cones_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "id",
            "x",
            "y",
            "z",
            "color",
            "size",
            "base_m",
            "height_m",
            "side",
            "role",
            "boundary",
            "ring",
            "marking",
            "station_m",
            "yaw_rad",
            "pitch_rad",
            "roll_rad",
            "asset",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(payload.get("cones", []))
    return [json_path, centerline_path, cones_path]
