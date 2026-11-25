"""Seeded paddock objects placed outside the asphalt ribbon.

Every category draws from its own named random stream. Turning a category off
does not reshuffle the streams of the others. Positions still depend on what
was already placed, because a tent will not overlap a tree.
"""

from __future__ import annotations

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

    def fits(self, point: Vec2, footprint: float, clearance: float) -> bool:
        if not _inside(point, self.bounds, footprint):
            return False
        distance = min_distance_to_polyline(point, self.track.centerline, self.track.closed)
        if distance < self.track.width * 0.5 + clearance + footprint:
            return False
        neighbors = self.hash.query_radius(point, footprint + 12.0)
        for other, other_footprint in neighbors:
            if point.distance(other) < footprint + other_footprint + 0.4:
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


def _pad_is_clear(center: Vec2, track: TrackData) -> bool:
    """Keep the parking rectangle off the asphalt. The pad is 14 m by 8 m."""
    for dx, dy in ((-7.0, -4.0), (7.0, -4.0), (7.0, 4.0), (-7.0, 4.0)):
        corner = Vec2(center.x + dx, center.y + dy)
        if min_distance_to_polyline(corner, track.centerline, track.closed) < track.width * 0.5 + 0.5:
            return False
    return True


def _parking_pad(center: Vec2, yaw: float) -> UniqueMesh:
    mesh = quad_mesh(14.0, 8.0, "parking", z=0.005)
    # The quad is axis-aligned in its mesh. Yaw is applied by the builder via location only;
    # keep the pad axis-aligned so the mesh stays a simple quad. Cars sit on top of it.
    del yaw
    return UniqueMesh(
        name="FSAE_Parking_Pad",
        collection="Environment/Buildings",
        mesh=mesh,
        x=center.x,
        y=center.y,
        z=0.0,
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
        tree_rng = rng.child("env-trees")
        count = scaled_count(config.num_trees, 28, config.env_density)
        kinds = ("tree_pine", "tree_round", "tree_broad")
        for _ in range(count):
            kind = tree_rng.choice(kinds)
            scale_xy = tree_rng.uniform(0.75, 1.25)
            scale_z = tree_rng.uniform(0.8, 1.45)
            placer.place(
                tree_rng,
                kind,
                "Environment/Trees",
                "tree",
                config.tree_clearance,
                scale=(scale_xy, scale_xy, scale_z),
                tries=40,
            )

    if config.enable_tents:
        tent_rng = rng.child("env-tents")
        count = scaled_count(config.num_tents, 5, config.env_density)
        sizes = ("tent_small", "tent_medium", "tent_large")
        for _ in range(count):
            kind = tent_rng.choice(sizes)
            color = tent_rng.choice(TENT_COLORS)
            tent = placer.place(
                tent_rng,
                kind,
                "Environment/Tents",
                "tent",
                config.tent_clearance,
                metadata={"color": color, "footprint_m": footprint_of(kind)},
                tries=40,
            )
            if tent is not None:
                # A table just beside the tent. The offset is deterministic from the tent yaw.
                yaw = tent.yaw
                offset = Vec2(footprint_of(kind) + 1.0, 0.0).rotated(yaw)
                table_point = Vec2(tent.x, tent.y) + offset
                if placer.fits(table_point, footprint_of("table"), config.prop_clearance):
                    placer.place(
                        tent_rng,
                        "table",
                        "Environment/Tents",
                        "table",
                        config.prop_clearance,
                        yaw=yaw,
                        near=table_point,
                        near_radius=0.05,
                        tries=1,
                        metadata={"footprint_m": footprint_of("table"), "parent": tent.name},
                    )

    if config.enable_spectators:
        spec_rng = rng.child("env-spectators")
        count = scaled_count(config.num_spectators, 16, config.env_density)
        placed = 0
        guard = 0
        while placed < count and guard < count * 6:
            guard += 1
            group_size = min(spec_rng.randint(3, 5), count - placed)
            anchor = placer.place(
                spec_rng,
                f"spectator_{spec_rng.choice(SHIRT_COLORS)}",
                "Environment/Spectators",
                "spectator",
                config.spectator_clearance,
                tries=30,
            )
            if anchor is None:
                continue
            placed += 1
            for _ in range(group_size - 1):
                shirt = spec_rng.choice(SHIRT_COLORS)
                asset = f"spectator_{shirt}_up" if spec_rng.random() < 0.35 else f"spectator_{shirt}"
                person = placer.place(
                    spec_rng,
                    asset,
                    "Environment/Spectators",
                    "spectator",
                    config.spectator_clearance,
                    near=Vec2(anchor.x, anchor.y),
                    near_radius=2.2,
                    tries=12,
                )
                if person is not None:
                    placed += 1

    if config.enable_barriers:
        barrier_rng = rng.child("env-barriers")
        groups = scaled_count(config.num_barriers, 3, config.env_density)
        for _ in range(groups):
            yaw = barrier_rng.uniform(0.0, 6.28318530718)
            first = placer.place(
                barrier_rng,
                "barrier",
                "Environment/Barriers",
                "barrier",
                config.barrier_clearance,
                yaw=yaw,
                tries=30,
            )
            if first is None:
                continue
            direction = Vec2(1.0, 0.0).rotated(yaw)
            for step in range(1, 4):
                point = Vec2(first.x, first.y) + direction * (2.15 * step)
                if not placer.fits(point, footprint_of("barrier"), config.barrier_clearance):
                    break
                placer.place(
                    barrier_rng,
                    "barrier",
                    "Environment/Barriers",
                    "barrier",
                    config.barrier_clearance,
                    yaw=yaw,
                    near=point,
                    near_radius=0.05,
                    tries=1,
                )

    prop_density = config.env_density * config.background_density
    if config.enable_buildings:
        building_rng = rng.child("env-buildings")
        for _ in range(scaled_count(None, 2, prop_density)):
            placer.place(
                building_rng,
                "building",
                "Environment/Buildings",
                "building",
                config.prop_clearance,
                tries=30,
            )

    if config.enable_extra_props:
        prop_rng = rng.child("env-props")
        pad_anchor = placer.place(
            prop_rng,
            "car",
            "Environment/Props",
            "car",
            config.prop_clearance,
            tries=25,
        )
        if pad_anchor is not None and _pad_is_clear(Vec2(pad_anchor.x, pad_anchor.y), track):
            unique.append(_parking_pad(Vec2(pad_anchor.x, pad_anchor.y), pad_anchor.yaw))
            direction = Vec2(1.0, 0.0).rotated(pad_anchor.yaw)
            for step in range(1, scaled_count(None, 4, prop_density)):
                point = Vec2(pad_anchor.x, pad_anchor.y) + direction * (4.6 * step)
                if not placer.fits(point, footprint_of("car"), config.prop_clearance):
                    break
                placer.place(
                    prop_rng,
                    "car",
                    "Environment/Props",
                    "car",
                    config.prop_clearance,
                    yaw=pad_anchor.yaw,
                    near=point,
                    near_radius=0.05,
                    tries=1,
                )
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
        for _ in range(scaled_count(None, 1, prop_density)):
            placer.place(prop_rng, "marshall", "Environment/Props", "marshall", config.prop_clearance, tries=20)
        for _ in range(scaled_count(None, 3, prop_density)):
            placer.place(prop_rng, "equipment", "Environment/Props", "equipment", config.prop_clearance, tries=15)
        for _ in range(scaled_count(None, 5, prop_density)):
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
    mesh: MeshData = quad_mesh(width, depth, "grass", z=0.0)
    return UniqueMesh(
        name="FSAE_Terrain",
        collection="Environment/Terrain",
        mesh=mesh,
        x=(min_x + max_x) * 0.5,
        y=(min_y + max_y) * 0.5,
        z=0.0,
    )
