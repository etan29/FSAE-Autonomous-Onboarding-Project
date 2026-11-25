"""Seeded paddock, tree line, and marshals around the open tarmac.

Every category draws from its own named random stream. Turning a category off
does not reshuffle the streams of the others. Positions still depend on what
was already placed, because a tent will not overlap a tree.
"""

from __future__ import annotations

import math

from .assets import SHIRT_COLORS, TENT_COLORS, footprint_of, quad_mesh
from .config import GeneratorConfig
from .cones import NameSequence
from .math2d import Vec2, bounding_box, min_distance_to_polyline
from .models import MeshData, PlacedObject, UniqueMesh
from .rng import SeededRNG
from .spatial import SpatialHash
from .track import TrackData


def scaled_count(explicit: int | None, default: int, density: float) -> int:
    if explicit is not None:
        return max(0, int(explicit))
    return max(0, int(round(default * max(density, 0.0))))


LOT_INSET_M = 14.0


def asphalt_lot_bounds(track: TrackData, config: GeneratorConfig) -> tuple[float, float, float, float]:
    """Asphalt rectangle inset from the grass so berms and trees remain visible."""
    min_x, min_y, max_x, max_y = terrain_bounds(track, config)
    inset = min(LOT_INSET_M, (max_x - min_x) * 0.2, (max_y - min_y) * 0.2)
    return (min_x + inset, min_y + inset, max_x - inset, max_y - inset)


def terrain_bounds(track: TrackData, config: GeneratorConfig) -> tuple[float, float, float, float]:
    """Axis-aligned ground rectangle that contains the track plus a margin.

    An explicit terrain size is expanded when it would otherwise cut the track.
    """
    min_x, min_y, max_x, max_y = bounding_box(track.centerline)
    margin = max(config.terrain_margin, track.width)
    need_w = (max_x - min_x) + 2.0 * margin
    need_d = (max_y - min_y) + 2.0 * margin
    width = need_w if config.terrain_width is None else max(float(config.terrain_width), need_w)
    depth = need_d if config.terrain_depth is None else max(float(config.terrain_depth), need_d)
    if config.terrain_size and config.terrain_size > 0.0:
        width = max(width, float(config.terrain_size))
        depth = max(depth, float(config.terrain_size))
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    return (
        center_x - width * 0.5,
        center_y - depth * 0.5,
        center_x + width * 0.5,
        center_y + depth * 0.5,
    )


def _inside(point: Vec2, bounds: tuple[float, float, float, float], padding: float) -> bool:
    min_x, min_y, max_x, max_y = bounds
    return min_x + padding <= point.x <= max_x - padding and min_y + padding <= point.y <= max_y - padding


class _Placer:
    def __init__(self, track: TrackData, config: GeneratorConfig, names: NameSequence):
        self.track = track
        self.config = config
        self.names = names
        self.bounds = terrain_bounds(track, config)
        self.hash: SpatialHash[float] = SpatialHash(4.0)
        self.objects: list[PlacedObject] = []

    def seed_with_cones(self, cones: list[PlacedObject]) -> None:
        for cone in cones:
            self.hash.insert(Vec2(cone.x, cone.y), footprint_of(cone.asset))

    def fits(self, point: Vec2, footprint: float, clearance: float, padding: float = 0.4) -> bool:
        if not _inside(point, self.bounds, footprint):
            return False
        distance = min_distance_to_polyline(point, self.track.centerline, self.track.closed)
        if distance < self.track.width * 0.5 + clearance + footprint:
            return False
        neighbors = self.hash.query_radius(point, footprint + 12.0)
        for other, other_footprint in neighbors:
            if point.distance(other) < footprint + other_footprint + padding:
                return False
        return True

    def place(
        self,
        rng: SeededRNG,
        asset: str,
        collection: str,
        role: str,
        clearance: float,
        *,
        scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
        yaw: float | None = None,
        near: Vec2 | None = None,
        near_radius: float = 0.0,
        tries: int = 50,
        metadata: dict | None = None,
        z: float = 0.0,
    ) -> PlacedObject | None:
        footprint = footprint_of(asset) * max(scale[0], scale[1])
        min_x, min_y, max_x, max_y = self.bounds
        for _ in range(tries):
            if near is None:
                point = Vec2(rng.uniform(min_x, max_x), rng.uniform(min_y, max_y))
            else:
                point = Vec2(
                    near.x + rng.uniform(-near_radius, near_radius),
                    near.y + rng.uniform(-near_radius, near_radius),
                )
            if not self.fits(point, footprint, clearance):
                continue
            placed = PlacedObject(
                asset=asset,
                name=self.names.next(role),
                collection=collection,
                x=point.x,
                y=point.y,
                z=z,
                yaw=rng.uniform(0.0, 6.28318530718) if yaw is None else yaw,
                scale=scale,
                role=role,
                metadata=metadata or {"footprint_m": footprint},
            )
            if "footprint_m" not in placed.metadata:
                placed.metadata["footprint_m"] = footprint
            self.objects.append(placed)
            self.hash.insert(point, footprint)
            return placed
        return None

    def place_exact(
        self,
        point: Vec2,
        asset: str,
        collection: str,
        role: str,
        clearance: float,
        yaw: float,
        *,
        padding: float = 0.4,
        metadata: dict | None = None,
        scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> PlacedObject | None:
        footprint = footprint_of(asset) * max(scale[0], scale[1])
        if not self.fits(point, footprint, clearance, padding):
            return None
        placed = PlacedObject(
            asset=asset,
            name=self.names.next(role),
            collection=collection,
            x=point.x,
            y=point.y,
            yaw=yaw,
            scale=scale,
            role=role,
            metadata=metadata or {"footprint_m": footprint},
        )
        if "footprint_m" not in placed.metadata:
            placed.metadata["footprint_m"] = footprint
        self.objects.append(placed)
        self.hash.insert(point, footprint)
        return placed


def _yaw_of(direction: Vec2) -> float:
    return math.atan2(direction.y, direction.x)


def _on_lot(point: Vec2, lot: tuple[float, float, float, float], pad: float) -> bool:
    min_x, min_y, max_x, max_y = lot
    return min_x + pad <= point.x <= max_x - pad and min_y + pad <= point.y <= max_y - pad


def _place_tree_line(placer: _Placer, config: GeneratorConfig, rng: SeededRNG) -> None:
    count = scaled_count(config.num_trees, 36, config.env_density)
    if count <= 0:
        return
    min_x, min_y, max_x, max_y = placer.bounds
    inset = 4.0
    corners = (
        Vec2(min_x + inset, min_y + inset),
        Vec2(max_x - inset, min_y + inset),
        Vec2(max_x - inset, max_y - inset),
        Vec2(min_x + inset, max_y - inset),
    )
    edges = [(corners[index], corners[(index + 1) % 4]) for index in range(4)]
    lengths = [start.distance(end) for start, end in edges]
    total = sum(lengths)
    if total < 1.0:
        return
    kinds = ("tree_pine", "tree_round", "tree_broad")
    for index in range(count):
        target = (index + 0.5) * total / count
        walked = 0.0
        for (start, end), length in zip(edges, lengths):
            if walked + length >= target or index == count - 1 and walked + length >= total - 1e-6:
                blend = 0.0 if length < 1e-6 else (target - walked) / length
                blend = min(max(blend, 0.0), 1.0)
                point = start + (end - start) * blend
                kind = rng.choice(kinds)
                scale_xy = rng.uniform(0.85, 1.3)
                scale_z = rng.uniform(0.9, 1.5)
                placer.place_exact(
                    point,
                    kind,
                    "Environment/Trees",
                    "tree",
                    config.tree_clearance,
                    rng.uniform(0.0, math.tau),
                    scale=(scale_xy, scale_xy, scale_z),
                    padding=0.3,
                )
                break
            walked += length


def _fence_points(origin: Vec2, tangent: Vec2, count: int, spacing: float) -> list[Vec2]:
    return [origin + tangent * (index * spacing) for index in range(count)]


def _row_fits(placer: _Placer, points: list[Vec2], lot: tuple[float, float, float, float], footprint: float, clearance: float) -> list[Vec2]:
    accepted = []
    for point in points:
        if not _on_lot(point, lot, footprint):
            continue
        if placer.fits(point, footprint, clearance, padding=0.05):
            accepted.append(point)
    return accepted


def _place_paddock(placer: _Placer, track: TrackData, config: GeneratorConfig, rng: SeededRNG) -> None:
    """One fenced paddock: canopy clusters, vans, and spectators behind the fence."""
    if len(track.centerline) < 2 or len(track.tangents) < 1:
        return
    lot = asphalt_lot_bounds(track, config)
    tangent = track.tangents[0].normalized()
    normal = track.left_normals[0].normalized()
    if track.closed:
        origin = track.centerline[0] + tangent * 12.0
    else:
        # Straights and the skidpad are small. Keep the paddock outside the course box.
        box_min_x, box_min_y, box_max_x, box_max_y = bounding_box(track.centerline)
        origin = Vec2(box_max_x + track.width + 10.0, (box_min_y + box_max_y) * 0.5)
        tangent = Vec2(0.0, 1.0)
        normal = Vec2(1.0, 0.0)
    prop_density = config.env_density * config.background_density
    fence_count = scaled_count(config.num_barriers, 16, config.env_density) if config.enable_barriers else 0
    tent_count = scaled_count(config.num_tents, 6, config.env_density) if config.enable_tents else 0
    spectator_count = scaled_count(config.num_spectators, 18, config.env_density) if config.enable_spectators else 0
    want_vehicles = config.enable_buildings and (config.enable_vans or config.enable_trailers)
    vehicle_count = scaled_count(None, 4, prop_density) if want_vehicles else 0
    if fence_count == 0 and tent_count == 0 and spectator_count == 0 and vehicle_count == 0:
        return

    best_side = None
    best_points: list[Vec2] = []
    side_order = (1.0, -1.0) if rng.random() < 0.5 else (-1.0, 1.0)
    for side in side_order:
        outward = normal * side
        fence_origin = origin + outward * (track.width * 0.5 + 3.4)
        candidates = _fence_points(fence_origin, tangent, max(fence_count, 8), 2.0)
        fitted = _row_fits(placer, candidates, lot, footprint_of("fence"), config.barrier_clearance)
        if len(fitted) > len(best_points):
            best_side = side
            best_points = fitted
    if best_side is None or len(best_points) < 4:
        return
    outward = normal * best_side
    yaw = _yaw_of(tangent)
    face_track = _yaw_of(outward * -1.0)
    placed_fence = []
    if config.enable_barriers:
        for point in best_points[:fence_count]:
            fence = placer.place_exact(
                point,
                "fence",
                "Environment/Barriers",
                "barrier",
                config.barrier_clearance,
                yaw,
                padding=0.05,
            )
            if fence is not None:
                placed_fence.append(fence)
    anchor = placed_fence[0] if placed_fence else None
    if anchor is None:
        anchor_point = best_points[0]
    else:
        anchor_point = Vec2(anchor.x, anchor.y)

    if config.enable_spectators and spectator_count > 0:
        spec_rng = rng.child("env-spectators")
        placed = 0
        group_index = 0
        while placed < spectator_count and group_index < spectator_count:
            group_size = min(spec_rng.randint(3, 5), spectator_count - placed)
            along = tangent * (2.2 * group_index)
            base = anchor_point + outward * 2.6 + along
            for member in range(group_size):
                shirt = spec_rng.choice(SHIRT_COLORS)
                asset = f"spectator_{shirt}_up" if spec_rng.random() < 0.3 else f"spectator_{shirt}"
                point = base + tangent * (member * 1.2) + outward * spec_rng.uniform(0.0, 0.6)
                person = placer.place_exact(
                    point,
                    asset,
                    "Environment/Spectators",
                    "spectator",
                    config.spectator_clearance,
                    face_track + spec_rng.uniform(-0.4, 0.4),
                    padding=0.15,
                )
                if person is not None:
                    placed += 1
            group_index += group_size

    if config.enable_tents and tent_count > 0:
        tent_rng = rng.child("env-tents")
        for index in range(tent_count):
            cluster = index // 3
            slot = index % 3
            kind = "tent_small"
            color = tent_rng.choice(TENT_COLORS)
            point = anchor_point + outward * (6.8 + cluster * 0.4) + tangent * (cluster * 16.0 + slot * 5.2)
            placer.place_exact(
                point,
                kind,
                "Environment/Tents",
                "tent",
                config.tent_clearance,
                yaw + tent_rng.uniform(-0.15, 0.15),
                metadata={"color": color, "footprint_m": footprint_of(kind)},
                padding=0.2,
            )

    if vehicle_count > 0:
        vehicle_rng = rng.child("env-buildings")
        for index in range(vehicle_count):
            if config.enable_trailers and (not config.enable_vans or index == vehicle_count - 1):
                asset = "trailer"
            else:
                asset = "van"
            point = anchor_point + outward * 12.5 + tangent * (index * 7.2)
            placer.place_exact(
                point,
                asset,
                "Environment/Buildings",
                asset,
                config.prop_clearance,
                yaw + math.pi + vehicle_rng.uniform(-0.08, 0.08),
                padding=0.3,
            )


def _place_marshals(placer: _Placer, track: TrackData, config: GeneratorConfig, rng: SeededRNG) -> None:
    count = scaled_count(None, 4, config.env_density)
    if count <= 0 or len(track.centerline) < 8:
        return
    corners: list[int] = []
    best = None
    for index, curvature in enumerate(track.curvatures):
        radius = 1.0 / abs(curvature) if abs(curvature) > 1e-6 else 1e9
        if radius < 16.0:
            if best is None or abs(curvature) > abs(track.curvatures[best]):
                best = index
        elif best is not None:
            corners.append(best)
            best = None
    if best is not None:
        corners.append(best)
    if not corners:
        return
    step = max(1, len(corners) // count)
    chosen = corners[::step][:count]
    for index, sample in enumerate(chosen):
        side = -1.0 if index % 2 else 1.0
        outward = track.left_normals[sample].normalized() * side
        point = track.centerline[sample] + outward * (track.width * 0.5 + 3.3)
        placer.place_exact(
            point,
            "marshal",
            "Environment/Props",
            "marshal",
            config.prop_clearance,
            _yaw_of(outward * -1.0),
            padding=0.2,
        )


def generate_environment(
    track: TrackData,
    cones: list[PlacedObject],
    config: GeneratorConfig,
    rng: SeededRNG,
    names: NameSequence,
) -> tuple[list[PlacedObject], list[UniqueMesh], list[str]]:
    warnings: list[str] = []
    placer = _Placer(track, config, names)
    placer.seed_with_cones(cones)
    unique: list[UniqueMesh] = []

    if config.enable_trees:
        _place_tree_line(placer, config, rng.child("env-trees"))
    _place_paddock(placer, track, config, rng.child("env-paddock"))
    _place_marshals(placer, track, config, rng.child("env-marshals"))

    prop_density = config.env_density * config.background_density
    if config.enable_extra_props:
        prop_rng = rng.child("env-props")
        for _ in range(scaled_count(None, 4, prop_density)):
            placer.place(prop_rng, "flag", "Environment/Props", "flag", config.prop_clearance, tries=20)
        for _ in range(scaled_count(None, 5, prop_density)):
            placer.place(
                prop_rng,
                "tire_stack",
                "Environment/Barriers",
                "tire_wall",
                config.barrier_clearance,
                tries=20,
            )
        if config.enable_paddock_equipment:
            for _ in range(scaled_count(None, 3, prop_density)):
                placer.place(prop_rng, "equipment", "Environment/Props", "equipment", config.prop_clearance, tries=15)
        if config.enable_background_vehicles and config.enable_vans:
            for _ in range(scaled_count(None, 2, prop_density)):
                placer.place(prop_rng, "van", "Environment/Buildings", "van", config.prop_clearance, tries=12)
        for _ in range(scaled_count(None, 4, prop_density)):
            placer.place(
                prop_rng,
                "orange_small",
                "Cones/Orange_Cones",
                "scattered_cone",
                config.prop_clearance,
                tries=15,
            )

    if config.terrain_width is not None or config.terrain_depth is not None:
        min_x, min_y, max_x, max_y = placer.bounds
        track_min_x, track_min_y, track_max_x, track_max_y = bounding_box(track.centerline)
        if config.terrain_width is not None and config.terrain_width + 1e-6 < (track_max_x - track_min_x) + 2.0 * config.terrain_margin:
            warnings.append("Terrain width was expanded so the track and its margin fit inside it.")
        if config.terrain_depth is not None and config.terrain_depth + 1e-6 < (track_max_y - track_min_y) + 2.0 * config.terrain_margin:
            warnings.append("Terrain depth was expanded so the track and its margin fit inside it.")

    return placer.objects, unique, warnings


def terrain_mesh(bounds: tuple[float, float, float, float]) -> UniqueMesh:
    min_x, min_y, max_x, max_y = bounds
    width = max_x - min_x
    depth = max_y - min_y
    mesh: MeshData = quad_mesh(width, depth, "grass", z=-0.03)
    return UniqueMesh(
        name="FSAE_Terrain",
        collection="Environment/Terrain",
        mesh=mesh,
        x=(min_x + max_x) * 0.5,
        y=(min_y + max_y) * 0.5,
        z=0.0,
    )
