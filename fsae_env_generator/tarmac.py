"""Open asphalt lot, grass berms, tire marks, and distractor paint.

The racing line is still defined by the centerline and the cones. These meshes
replace the old narrow road ribbon. Nothing here is a painted highway centerline.
"""

from __future__ import annotations

import math

from .config import GeneratorConfig
from .environment import asphalt_lot_bounds, terrain_bounds
from .math2d import Vec2, cumulative_lengths, min_distance_to_polyline, point_at_distance
from .models import MeshData, UniqueMesh
from .rng import SeededRNG
from .track import TrackData


def _add_poly(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[int],
    corners: list[tuple[float, float, float]],
    slot: int,
) -> None:
    base = len(vertices)
    vertices.extend(corners)
    if len(corners) == 3:
        faces.append((base, base + 1, base + 2))
    else:
        faces.append(tuple(range(base, base + len(corners))))
    materials.append(slot)


def _quad_strip(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[int],
    start: Vec2,
    end: Vec2,
    width: float,
    z: float,
    slot: int,
) -> None:
    direction = end - start
    if direction.length() < 1e-4:
        return
    side = direction.left_normal().normalized() * (width * 0.5)
    _add_poly(
        vertices,
        faces,
        materials,
        [
            (start.x - side.x, start.y - side.y, z),
            (start.x + side.x, start.y + side.y, z),
            (end.x + side.x, end.y + side.y, z),
            (end.x - side.x, end.y - side.y, z),
        ],
        slot,
    )


def _box_world(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[int],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    z0: float,
    z1: float,
    slot: int,
) -> None:
    corners = (
        (min_x, min_y, z0),
        (max_x, min_y, z0),
        (max_x, max_y, z0),
        (min_x, max_y, z0),
        (min_x, min_y, z1),
        (max_x, min_y, z1),
        (max_x, max_y, z1),
        (min_x, max_y, z1),
    )
    base = len(vertices)
    vertices.extend(corners)
    quads = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    for quad in quads:
        faces.append(tuple(base + index for index in quad))
        materials.append(slot)


def _mesh(vertices, faces, materials, slots: list[str]) -> MeshData:
    return MeshData(vertices=vertices, faces=faces, material_slots=slots, face_materials=materials)


def _asphalt_mesh(lot: tuple[float, float, float, float]) -> UniqueMesh:
    min_x, min_y, max_x, max_y = lot
    # One millimeter under the cone bases so the sheet does not flicker against them.
    mesh = _mesh(
        [
            (min_x, min_y, -0.001),
            (max_x, min_y, -0.001),
            (max_x, max_y, -0.001),
            (min_x, max_y, -0.001),
        ],
        [(0, 1, 2, 3)],
        [0],
        ["asphalt"],
    )
    return UniqueMesh(name="FSAE_Track_Surface", collection="Track/Track_Surface", mesh=mesh)


def _berm_mesh(track_bounds: tuple[float, float, float, float], lot: tuple[float, float, float, float]) -> UniqueMesh:
    """Raised grass ring between the tarmac edge and the outer tree line."""
    tmin_x, tmin_y, tmax_x, tmax_y = track_bounds
    lmin_x, lmin_y, lmax_x, lmax_y = lot
    outer = 6.0
    gap = 1.5
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    bands = (
        (tmin_x + outer, tmin_y + outer, tmax_x - outer, lmin_y - gap),
        (tmin_x + outer, lmax_y + gap, tmax_x - outer, tmax_y - outer),
        (tmin_x + outer, lmin_y - gap, lmin_x - gap, lmax_y + gap),
        (lmax_x + gap, lmin_y - gap, tmax_x - outer, lmax_y + gap),
    )
    for min_x, min_y, max_x, max_y in bands:
        if max_x - min_x < 1.0 or max_y - min_y < 1.0:
            continue
        _box_world(vertices, faces, materials, min_x, min_y, max_x, max_y, 0.0, 0.55, 0)
    return UniqueMesh(
        name="FSAE_Grass_Berms",
        collection="Environment/Terrain",
        mesh=_mesh(vertices, faces, materials, ["grass"]),
    )


def _off_the_racing_line(point: Vec2, track: TrackData, margin: float) -> bool:
    return min_distance_to_polyline(point, track.centerline, track.closed) > track.width * 0.5 + margin


def _clear_patch(lot: tuple[float, float, float, float], track: TrackData, rng: SeededRNG, radius: float) -> Vec2 | None:
    min_x, min_y, max_x, max_y = lot
    if max_x - min_x < radius * 2.0 or max_y - min_y < radius * 2.0:
        return None
    for _ in range(48):
        point = Vec2(rng.uniform(min_x + radius, max_x - radius), rng.uniform(min_y + radius, max_y - radius))
        if _off_the_racing_line(point, track, radius):
            return point
    return None


def _skid_mesh(track: TrackData, rng: SeededRNG) -> UniqueMesh:
    """Broken tire streaks beside the driven line, not a continuous center stripe."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    cumulative = cumulative_lengths(track.centerline, track.closed)
    total = cumulative[-1]
    distance = rng.uniform(2.0, 8.0)
    while distance < total - 2.0:
        if rng.random() < 0.62:
            length = rng.uniform(1.4, 4.2)
            end_distance = min(total - 0.5, distance + length)
            start, _tangent, _index = point_at_distance(track.centerline, cumulative, distance)
            end, _end_tangent, _end_index = point_at_distance(track.centerline, cumulative, end_distance)
            direction = end - start
            if direction.length() > 0.4:
                normal = direction.left_normal().normalized()
                offset = rng.choice((-1.0, 1.0)) * rng.uniform(0.35, 1.05)
                width = rng.uniform(0.12, 0.28)
                _quad_strip(vertices, faces, materials, start + normal * offset, end + normal * offset, width, 0.004, 0)
        distance += rng.uniform(2.5, 7.0)
    return UniqueMesh(
        name="FSAE_Skid_Marks",
        collection="Track/Markings",
        mesh=_mesh(vertices, faces, materials, ["skid"]),
    )


def _parking_lines(origin: Vec2, yaw: float, stalls: int) -> tuple[list, list, list]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    forward = Vec2(math.cos(yaw), math.sin(yaw))
    side = forward.left_normal()
    stall_w = 2.5
    stall_d = 5.0
    for index in range(stalls + 1):
        start = origin + side * (index * stall_w)
        _quad_strip(vertices, faces, materials, start, start + forward * stall_d, 0.1, 0.005, 0)
    back = origin + forward * stall_d
    _quad_strip(vertices, faces, materials, origin, origin + side * (stalls * stall_w), 0.1, 0.005, 0)
    _quad_strip(vertices, faces, materials, back, back + side * (stalls * stall_w), 0.1, 0.005, 0)
    return vertices, faces, materials


def _arc_lines(center: Vec2, radius: float, start: float, sweep: float, width: float, slot: int) -> tuple[list, list, list]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    steps = max(12, int(abs(sweep) * radius / 0.8))
    previous = None
    for step in range(steps + 1):
        angle = start + sweep * step / steps
        point = center + Vec2(math.cos(angle), math.sin(angle)) * radius
        if previous is not None:
            _quad_strip(vertices, faces, materials, previous, point, width, 0.005, slot)
        previous = point
    return vertices, faces, materials


def _paint_mesh(lot: tuple[float, float, float, float], track: TrackData, rng: SeededRNG) -> UniqueMesh:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    parking = _clear_patch(lot, track, rng, 8.0)
    if parking is not None:
        yaw = rng.uniform(0.0, math.tau)
        extra_v, extra_f, extra_m = _parking_lines(parking, yaw, 6)
        shift = len(vertices)
        vertices.extend(extra_v)
        faces.extend(tuple(index + shift for index in face) for face in extra_f)
        materials.extend(extra_m)
    pad = _clear_patch(lot, track, rng, 12.0)
    if pad is not None:
        for radius, width in ((8.5, 0.14), (6.2, 0.12)):
            extra_v, extra_f, extra_m = _arc_lines(pad, radius, rng.uniform(0.0, 0.4), math.radians(300.0), width, 1)
            shift = len(vertices)
            vertices.extend(extra_v)
            faces.extend(tuple(index + shift for index in face) for face in extra_f)
            materials.extend(extra_m)
    return UniqueMesh(
        name="FSAE_Distractor_Paint",
        collection="Track/Markings",
        mesh=_mesh(vertices, faces, materials, ["paint_white", "paint_yellow"]),
    )


def _timing_arch(track: TrackData) -> UniqueMesh:
    """Posts outside the cone line and a beam across the start straight."""
    tangent = track.tangents[0].normalized()
    left_normal = track.left_normals[0].normalized()
    left = track.left_boundary[0] + left_normal * 1.1
    right = track.right_boundary[0] - left_normal * 1.1
    across = right - left
    beam_z = 3.15
    post = 0.18
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []

    def post_at(base: Vec2) -> None:
        _box_world(
            vertices,
            faces,
            materials,
            base.x - post,
            base.y - post,
            base.x + post,
            base.y + post,
            0.0,
            beam_z,
            0,
        )

    post_at(left)
    post_at(right)
    mid = (left + right) * 0.5
    half_across = across.length() * 0.5 + 0.2
    side = tangent * 0.14
    depth = across.normalized() * half_across
    z0 = beam_z - 0.16
    z1 = beam_z + 0.16
    corners_low = (mid - depth - side, mid + depth - side, mid + depth + side, mid - depth + side)
    # The beam is a box in the plane of the start line. Build it from the four ground corners extruded up.
    extruded = [(x, y, z0) for x, y in ((point.x, point.y) for point in corners_low)]
    extruded += [(x, y, z1) for x, y in ((point.x, point.y) for point in corners_low)]
    base = len(vertices)
    vertices.extend(extruded)
    for quad in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        faces.append(tuple(base + index for index in quad))
        materials.append(1)
    return UniqueMesh(
        name="FSAE_Timing_Arch",
        collection="Track/Markings",
        mesh=_mesh(vertices, faces, materials, ["pole", "hi_vis"]),
    )


def _lerp_color(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float, float]:
    t = max(0.0, min(1.0, t))
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, 1.0)


def _continuous_ground(track: TrackData, bounds: tuple[float, float, float, float], rng: SeededRNG) -> UniqueMesh:
    """One mesh: flat asphalt on the course, then gravel, then grass. Relief stays off the driving line."""
    min_x, min_y, max_x, max_y = bounds
    span = max(max_x - min_x, max_y - min_y)
    step = 4.0 if span < 220.0 else 6.0
    xs: list[float] = []
    x = min_x
    while x < max_x - 1e-6:
        xs.append(x)
        x += step
    xs.append(max_x)
    ys: list[float] = []
    y = min_y
    while y < max_y - 1e-6:
        ys.append(y)
        y += step
    ys.append(max_y)
    samples = track.centerline[::2] or track.centerline
    phase = rng.child("terrain-relief").uniform(0.0, 20.0)
    asphalt = (0.07, 0.07, 0.075)
    gravel = (0.34, 0.31, 0.26)
    grass = (0.16, 0.38, 0.12)
    flat_limit = track.width * 0.5 + 3.0
    vertices: list[tuple[float, float, float]] = []
    colors: list[tuple[float, float, float, float]] = []
    for y_value in ys:
        for x_value in xs:
            point = Vec2(x_value, y_value)
            distance = min(point.distance(sample) for sample in samples) if samples else 0.0
            noise = 0.5 + 0.5 * math.sin(x_value * 0.23 + phase) * math.cos(y_value * 0.19 + phase * 0.3)
            if distance <= flat_limit:
                z = 0.0
                color = (asphalt[0], asphalt[1], asphalt[2], 1.0)
            elif distance <= flat_limit + 6.0:
                blend = (distance - flat_limit) / 6.0
                z = (0.03 + 0.05 * noise) * blend
                color = _lerp_color(asphalt, gravel, blend)
            else:
                blend = min(1.0, (distance - flat_limit - 6.0) / 12.0)
                z = 0.08 + 0.22 * noise * (0.35 + 0.65 * blend)
                color = _lerp_color(gravel, grass, blend)
            vertices.append((x_value, y_value, z))
            colors.append(color)
    columns = len(xs)
    faces: list[tuple[int, ...]] = []
    for row in range(len(ys) - 1):
        for column in range(columns - 1):
            base = row * columns + column
            faces.append((base, base + 1, base + columns + 1, base + columns))
    mesh = MeshData(
        vertices=vertices,
        faces=faces,
        material_slots=["ground_blend"],
        face_materials=[0] * len(faces),
        vertex_colors=colors,
    )
    return UniqueMesh(name="FSAE_Terrain", collection="Environment/Terrain", mesh=mesh)


def build_tarmac(
    track: TrackData,
    config: GeneratorConfig,
    rng: SeededRNG,
) -> list[UniqueMesh]:
    """Continuous ground, skid marks, distractor paint, and the timing arch.

    The driving surface is the flat part of the ground mesh. Blue and yellow
    boundary curves are not created; the cones are the visible boundaries.
    """
    bounds = terrain_bounds(track, config)
    lot = asphalt_lot_bounds(track, config)
    meshes = [
        _continuous_ground(track, bounds, rng),
        _skid_mesh(track, rng.child("skid-marks")),
        _paint_mesh(lot, track, rng.child("distractor-paint")),
    ]
    if config.enable_start_finish and config.enable_timing_structures and track.centerline:
        meshes.append(_timing_arch(track))
    return meshes
