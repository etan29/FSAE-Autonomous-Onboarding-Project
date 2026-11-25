"""Place boundary cones, start/finish gates, and optional entry/exit lanes.

Spacing is measured along the boundary polyline, not by centerline sample count.
Cone centers sit outside the inner-edge boundary by half the base width, so the
inner face of the base lies on the boundary. That makes the configured track
width the distance between the inner edges of the cone bases.

A spatial hash rejects a cone that would overlap one already accepted. On a
closed loop the gap that wraps from the last cone back to the first is repaired
so it stays inside the spacing limits.
"""

from __future__ import annotations

import math

from .assets import footprint_of
from .config import GeneratorConfig, ResolvedLimits, RuleProfile
from .math2d import Vec2, cumulative_lengths, min_distance_to_polyline, point_at_distance
from .models import MeshData, PlacedObject, UniqueMesh
from .rng import SeededRNG
from .spatial import SpatialHash
from .track import TrackData

CONE_COLLECTIONS = {
    "blue_small": "Cones/Blue_Cones",
    "yellow_small": "Cones/Yellow_Cones",
    "orange_small": "Cones/Orange_Cones",
    "orange_large": "Cones/Large_Orange_Cones",
}


class NameSequence:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"FSAE_{prefix}_{self._counts[prefix]:04d}"


def spacing_for_curvature(curvature: float, config: GeneratorConfig, limits: ResolvedLimits) -> float:
    """Straights use the nominal gap. High curvature closes the gap toward 2 m.

    The default nominal gap is 5 m. A radius at or above ``corner_radius_threshold``
    keeps that gap. By a 6 m radius the gap has reached ``min_cone_spacing`` (2 m
    unless the user asked for an even smaller straight spacing).
    """
    nominal = limits.nominal_cone_spacing
    if not limits.tighten_corners:
        return nominal
    radius = 1.0 / abs(curvature) if abs(curvature) > 1e-6 else 1e9
    if radius >= config.corner_radius_threshold:
        return nominal
    tight_radius = 6.0
    span = max(config.corner_radius_threshold - tight_radius, 1.0)
    blend = max(0.0, min(1.0, (radius - tight_radius) / span))
    floor = min(max(config.corner_cone_spacing, 0.5), nominal)
    spacing = floor + blend * (nominal - floor)
    return max(floor, min(limits.max_cone_spacing, spacing))


def _nearest_curvature(point: Vec2, track: TrackData) -> float:
    best = 0.0
    best_distance = float("inf")
    for index, sample in enumerate(track.centerline):
        distance = sample.distance(point)
        if distance < best_distance:
            best_distance = distance
            best = track.curvatures[index]
    return best


def _repair_stations(stations: list[float], total: float, min_gap: float, max_gap: float) -> list[float]:
    """Insert or drop stations until every gap, including the wrap, fits the limits."""
    if total <= min_gap:
        return [0.0]
    current = [0.0]
    for station in stations:
        if min_gap * 0.5 < station < total - min_gap * 0.25:
            current.append(station)
    current = sorted(set(round(station, 4) for station in current))
    if not current or current[0] != 0.0:
        current = [0.0, *current]

    for _ in range(24):
        changed = False
        sequence = current + [current[0] + total]
        rebuilt = [current[0]]
        for index in range(len(sequence) - 1):
            gap = sequence[index + 1] - sequence[index]
            if gap > max_gap + 1e-4:
                intervals = max(2, int(math.ceil(gap / max_gap - 1e-9)))
                step = gap / intervals
                if step + 1e-6 < min_gap:
                    intervals = max(1, int(math.floor(gap / min_gap)))
                    step = gap / max(intervals, 1)
                for step_index in range(1, intervals):
                    rebuilt.append(sequence[index] + step * step_index)
                changed = True
            end = sequence[index + 1]
            if end < total - 1e-4:
                rebuilt.append(end)
        cleaned = [rebuilt[0]]
        for station in rebuilt[1:]:
            if station - cleaned[-1] < min_gap - 1e-4:
                changed = True
                continue
            if station < total - 1e-4:
                cleaned.append(station)
        if len(cleaned) > 1 and (total - cleaned[-1]) < min_gap - 1e-4:
            cleaned.pop()
            changed = True
        current = cleaned or [0.0]
        if not changed:
            break
    return current


def _stations_along(
    boundary: list[Vec2],
    track: TrackData,
    config: GeneratorConfig,
    limits: ResolvedLimits,
) -> tuple[list[float], float]:
    cumulative = cumulative_lengths(boundary, track.closed)
    total = cumulative[-1]
    if total <= 1e-6:
        return [0.0], total
    stations = [0.0]
    distance = 0.0
    for _ in range(10000):
        point, _tangent, _index = point_at_distance(boundary, cumulative, distance)
        step = spacing_for_curvature(_nearest_curvature(point, track), config, limits)
        nxt = distance + step
        if track.closed:
            if nxt >= total - min(step, limits.min_cone_spacing) * 0.35:
                break
        elif nxt > total + 1e-6:
            break
        else:
            nxt = min(nxt, total)
        if nxt <= distance + 1e-6:
            break
        if not track.closed and abs(nxt - total) < 1e-4:
            stations.append(total)
            break
        stations.append(nxt)
        distance = nxt
        if not track.closed and distance >= total - 1e-4:
            break
    minimum_gap = max(limits.min_cone_spacing, 0.5)
    for gate in getattr(track, "gate_stations", None) or []:
        gate = float(gate)
        if gate < 0.0 or gate > total:
            continue
        nearest = min(stations, key=lambda station: abs(station - gate))
        if abs(nearest - gate) < minimum_gap:
            stations = [gate if abs(station - nearest) < 1e-4 else station for station in stations]
        elif not any(abs(station - gate) < 0.2 for station in stations):
            stations.append(gate)
    stations.sort()
    if track.closed:
        stations = _repair_stations(stations, total, limits.min_cone_spacing, limits.max_cone_spacing)
    else:
        stations = _fill_large_gaps(stations, limits.max_cone_spacing)
    return stations, total


def _fill_large_gaps(stations: list[float], max_gap: float) -> list[float]:
    """Split open-track gaps that grew when a timing gate replaced a regular station."""
    current = sorted(stations)
    for _ in range(12):
        rebuilt = [current[0]]
        changed = False
        for index in range(len(current) - 1):
            start = current[index]
            end = current[index + 1]
            gap = end - start
            if gap > max_gap + 1e-4:
                intervals = max(2, int(math.ceil(gap / max_gap - 1e-9)))
                step = gap / intervals
                for step_index in range(1, intervals):
                    rebuilt.append(start + step * step_index)
                changed = True
            rebuilt.append(end)
        current = rebuilt
        if not changed:
            break
    return current


def _yaw(tangent: Vec2) -> float:
    if tangent.length() < 1e-8:
        return 0.0
    return math.atan2(tangent.y, tangent.x)


def _pose_cone(position: Vec2, yaw: float, pose_rng: SeededRNG, jitter: float) -> tuple[Vec2, float, float, float]:
    """Keep the boundary heading. Jitter is optional and defaults to zero. Tilt stays under 1.5 degrees."""
    if jitter > 0.0:
        position = position + Vec2(pose_rng.uniform(-jitter, jitter), pose_rng.uniform(-jitter, jitter))
    tilt = math.radians(1.5)
    pitch = pose_rng.uniform(-tilt, tilt)
    roll = pose_rng.uniform(-tilt, tilt)
    return position, yaw, pitch, roll


def _append_cone(
    objects: list[PlacedObject],
    occupied: SpatialHash[float],
    names: NameSequence,
    position: Vec2,
    yaw: float,
    kind: str,
    role: str,
    metadata: dict,
    min_distance: float,
    pose_rng: SeededRNG | None = None,
    jitter: float = 0.0,
) -> bool:
    del min_distance  # Separation is the sum of the two base radii, looked up per neighbor.
    pitch = 0.0
    roll = 0.0
    if pose_rng is not None:
        position, yaw, pitch, roll = _pose_cone(position, yaw, pose_rng, jitter)
    footprint = footprint_of(kind)
    for other, other_footprint in occupied.query_radius(position, footprint + 0.35):
        if position.distance(other) < footprint + other_footprint - 1e-4:
            return False
    meta = dict(metadata)
    color, size_name, base, height = {
        "blue_small": ("blue", "small", 0.228, 0.325),
        "yellow_small": ("yellow", "small", 0.228, 0.325),
        "orange_small": ("orange", "small", 0.228, 0.325),
        "orange_large": ("orange", "large", 0.285, 0.505),
    }.get(kind, ("unknown", "unknown", 0.0, 0.0))
    meta.setdefault("color", color)
    meta.setdefault("size", size_name)
    meta.setdefault("base_m", base)
    meta.setdefault("height_m", height)
    meta.setdefault("boundary", meta.get("side", ""))
    placed = PlacedObject(
        asset=kind,
        name=names.next(kind),
        collection=CONE_COLLECTIONS[kind],
        x=position.x,
        y=position.y,
        z=0.0,
        yaw=yaw,
        pitch=pitch,
        roll=roll,
        role=role,
        metadata=meta,
    )
    objects.append(placed)
    occupied.insert(position, footprint)
    return True


def _boundary_cones(
    boundary: list[Vec2],
    outward_sign: float,
    side: str,
    regular_kind: str,
    track: TrackData,
    profile: RuleProfile,
    config: GeneratorConfig,
    limits: ResolvedLimits,
    names: NameSequence,
    occupied: SpatialHash[float],
    variation_rng: SeededRNG | None,
    objects: list[PlacedObject],
    pose_rng: SeededRNG | None = None,
) -> None:
    stations, total = _stations_along(boundary, track, config, limits)
    cumulative = cumulative_lengths(boundary, track.closed)
    base_width, _height = profile.cone_size(regular_kind)
    special_width, _height = profile.cone_size(profile.start_finish_cone)
    for station in stations:
        point, tangent, _index = point_at_distance(boundary, cumulative, station)
        outward = tangent.left_normal() * outward_sign
        gates = [float(gate) for gate in (getattr(track, "gate_stations", None) or [])]
        if gates:
            is_gate = config.enable_start_finish and any(abs(station - gate) <= 0.45 for gate in gates)
        else:
            is_gate = config.enable_start_finish and station <= 1e-3 and (track.closed or side in {"left", "right"})
            if not track.closed and config.enable_start_finish and abs(station - total) <= 1e-3:
                is_gate = True
        kind = profile.start_finish_cone if is_gate else regular_kind
        half_base = (special_width if is_gate else base_width) * 0.5
        center = point + outward * half_base
        yaw = _yaw(tangent)
        if variation_rng is not None and not is_gate and config.cone_placement_variation > 0.0:
            amount = config.cone_placement_variation
            shifted = center + tangent * variation_rng.uniform(-amount, amount) + outward * variation_rng.uniform(0.0, amount)
            # Extra along-track variation stays outside the inner edge. The ±5 cm
            # pose jitter below is applied later, on every cone.
            if min_distance_to_polyline(shifted, track.centerline, track.closed) >= track.width * 0.5 + half_base * 0.9:
                center = shifted
        required = footprint_of(kind) + 0.16
        role = "boundary_cone"
        metadata = {
            "side": side,
            "station_m": station,
            "boundary_length_m": total,
            "marking": "start_finish" if is_gate else "boundary",
        }
        if is_gate:
            metadata["timing_gate"] = True
        placed = _append_cone(
            objects, occupied, names, center, yaw, kind, role, metadata, required, pose_rng, config.cone_jitter_m
        )
        if not placed and not is_gate:
            # Slide along the boundary a short distance before giving up.
            for delta in (0.3, -0.3, 0.6, -0.6):
                alt_station = min(max(station + delta, 0.0), max(total - 1e-3, 0.0))
                alt_point, alt_tangent, _index = point_at_distance(boundary, cumulative, alt_station)
                alt_out = alt_tangent.left_normal() * outward_sign
                alt_center = alt_point + alt_out * half_base
                metadata = dict(metadata)
                metadata["station_m"] = alt_station
                if _append_cone(
                    objects,
                    occupied,
                    names,
                    alt_center,
                    _yaw(alt_tangent),
                    kind,
                    role,
                    metadata,
                    required,
                    pose_rng,
                    config.cone_jitter_m,
                ):
                    break


def _lane_cones(
    track: TrackData,
    profile: RuleProfile,
    config: GeneratorConfig,
    limits: ResolvedLimits,
    names: NameSequence,
    occupied: SpatialHash[float],
    objects: list[PlacedObject],
    warnings: list[str],
    pose_rng: SeededRNG | None = None,
) -> None:
    """Orange corridor beside the start straight.

    The racing line stays the closed loop. Entry and exit are one straight
    corridor parallel to the opening tangent, offset outside the right boundary.
    Negative stations are the entry half and positive stations are the exit half.
    """
    if not config.wants_entry_exit() or len(track.centerline) < 4:
        return
    tangent = track.tangents[0]
    right = track.left_normals[0] * -1.0
    origin = track.centerline[0]
    straight = 0.0
    for index in range(len(track.centerline) - (0 if track.closed else 1)):
        if abs(track.curvatures[index]) > 1.0 / config.straight_curvature_radius:
            break
        nxt = track.centerline[(index + 1) % len(track.centerline)]
        straight += track.centerline[index].distance(nxt)
        if straight > 18.0:
            break
    length = min(12.0, straight * 0.8)
    if length < 6.0:
        warnings.append("Entry and exit lanes were skipped because the start is not on a long enough straight.")
        return
    lateral = track.width + 2.5
    kind = profile.entry_exit_cone
    half_base = profile.cone_size(kind)[0] * 0.5
    lane_half = track.width * 0.5
    step = limits.nominal_cone_spacing
    accepted = 0
    rejected = 0
    distance = step
    while distance <= length + 1e-6:
        for sign, marking in ((-1.0, "entry"), (1.0, "exit")):
            center = origin + right * lateral + tangent * (sign * distance)
            if min_distance_to_polyline(center, track.centerline, track.closed) < track.width * 0.5 + lane_half:
                rejected += 1
                continue
            for side_sign, side_name in ((1.0, "lane_left"), (-1.0, "lane_right")):
                cone_center = center + right * side_sign * (lane_half + half_base)
                if min_distance_to_polyline(cone_center, track.centerline, track.closed) < track.width * 0.5 + 0.4:
                    rejected += 1
                    continue
                metadata = {
                    "side": side_name,
                    "station_m": sign * distance,
                    "marking": marking,
                    "boundary_length_m": length * 2.0,
                }
                if _append_cone(
                    objects,
                    occupied,
                    names,
                    cone_center,
                    _yaw(tangent),
                    kind,
                    "lane_cone",
                    metadata,
                    footprint_of(kind) + 0.16,
                    pose_rng,
                ):
                    accepted += 1
                else:
                    rejected += 1
        distance += step
    if accepted == 0 or rejected > accepted:
        # Drop a lane that mostly intersects the circuit.
        if accepted:
            lane_names = {obj.name for obj in objects if obj.role == "lane_cone"}
            objects[:] = [obj for obj in objects if obj.name not in lane_names]
            warnings.append("Entry and exit lanes were removed because they intersected the track.")
        else:
            warnings.append("Entry and exit lanes were skipped because they would intersect the track.")


def _line_at(track: TrackData, station: float, name: str) -> UniqueMesh:
    """A short white bar across the inner edges at one station. Painted a few millimeters up."""
    cumulative = cumulative_lengths(track.centerline, track.closed)
    total = max(cumulative[-1], 1e-6)
    station = min(max(station, 0.0), total)
    _point, tangent, index = point_at_distance(track.centerline, cumulative, station)
    fraction = station / total
    left_cum = cumulative_lengths(track.left_boundary, track.closed)
    right_cum = cumulative_lengths(track.right_boundary, track.closed)
    left, _left_tangent, _left_index = point_at_distance(track.left_boundary, left_cum, fraction * left_cum[-1])
    right, _right_tangent, _right_index = point_at_distance(track.right_boundary, right_cum, fraction * right_cum[-1])
    if tangent.length() < 1e-8:
        tangent = track.tangents[min(index, len(track.tangents) - 1)]
    thickness = 0.08
    z = 0.006
    corners = (
        left - tangent * thickness,
        right - tangent * thickness,
        right + tangent * thickness,
        left + tangent * thickness,
    )
    mesh = MeshData(
        vertices=[(point.x, point.y, z) for point in corners],
        faces=[(0, 1, 2, 3)],
        material_slots=["start_line"],
        face_materials=[0],
    )
    return UniqueMesh(name=name, collection="Track/Markings", mesh=mesh)


def start_line_mesh(track: TrackData) -> UniqueMesh:
    """A short white bar across the inner edges at the start station."""
    return _line_at(track, 0.0, "FSAE_Start_Line")


def marking_lines(track: TrackData) -> list[UniqueMesh]:
    gates = list(getattr(track, "gate_stations", None) or [0.0])
    lines: list[UniqueMesh] = []
    for index, station in enumerate(gates):
        name = "FSAE_Start_Line" if index == 0 else f"FSAE_Timing_Line_{index}"
        lines.append(_line_at(track, float(station), name))
    return lines


def _ring_angles(gate_angle: float, count: int, gap: float) -> list[float]:
    """Even angles around a circle, leaving an opening of `2 * gap` at `gate_angle`."""
    span = 2.0 * math.pi - 2.0 * gap
    start = gate_angle + gap
    return [start + span * ((index + 0.5) / count) for index in range(count)]


def _place_skidpad_cones(
    track: TrackData,
    profile: RuleProfile,
    config: GeneratorConfig,
    names: NameSequence,
    occupied: SpatialHash[float],
    objects: list[PlacedObject],
    pose_rng: SeededRNG | None,
) -> None:
    """17 inner and 13 outer cones on each official circle, plus orange entry and exit cones.

    Right circle is clockwise, so the center is on the driver's right: inner cones are yellow
    and outer cones are blue. Left circle is counter-clockwise, so inner cones are blue
    and outer cones are yellow. Entry and exit cones are small orange (DD.1.1.c).
    """
    from .events import SKID_CENTERLINE_RADIUS_M

    radius = SKID_CENTERLINE_RADIUS_M
    inner_radius = 15.25 * 0.5
    outer_radius = 21.25 * 0.5
    small_base, _small_height = profile.cone_size(profile.left_cone)
    large_base, _large_height = profile.cone_size(profile.start_finish_cone)
    half_small = small_base * 0.5
    half_large = large_base * 0.5
    gap = 0.62
    jitter = config.cone_jitter_m

    def place_ring(center: Vec2, circle_radius: float, inward: bool, kind: str, side: str, ring: str, gate: float, count: int, travel_sign: float) -> None:
        for index, angle in enumerate(_ring_angles(gate, count, gap)):
            radial = Vec2(math.cos(angle), math.sin(angle))
            offset = -half_small if inward else half_small
            position = center + radial * (circle_radius + offset)
            tangent = Vec2(travel_sign * math.sin(angle), -travel_sign * math.cos(angle))
            arc = circle_radius * (2.0 * math.pi - 2.0 * gap)
            step = arc / count
            metadata = {
                "side": side,
                "station_m": index * step,
                "boundary_length_m": index * step,
                "marking": "boundary",
                "ring": ring,
            }
            _append_cone(
                objects,
                occupied,
                names,
                position,
                _yaw(tangent),
                kind,
                "boundary_cone",
                metadata,
                footprint_of(kind) + 0.16,
                pose_rng,
                jitter,
            )

    right = Vec2(radius, 0.0)
    left = Vec2(-radius, 0.0)
    # Clockwise travel_sign = 1 uses tangent (sin, -cos). Counter-clockwise uses the opposite.
    place_ring(right, inner_radius, True, profile.right_cone, "right", "right-inner", math.pi, config.skidpad_inner_count, 1.0)
    place_ring(right, outer_radius, False, profile.left_cone, "left", "right-outer", math.pi, config.skidpad_outer_count, 1.0)
    place_ring(left, inner_radius, True, profile.left_cone, "left", "left-inner", 0.0, config.skidpad_inner_count, -1.0)
    place_ring(left, outer_radius, False, profile.right_cone, "right", "left-outer", 0.0, config.skidpad_outer_count, -1.0)

    half_path = config.track_width * 0.5
    left_normal = Vec2(-1.0, 0.0)

    def place_orange(y: float, marking: str) -> None:
        for sign, side_name in ((1.0, "lane_left"), (-1.0, "lane_right")):
            center = Vec2(0.0, y) + left_normal * sign * (half_path + half_small)
            _append_cone(
                objects,
                occupied,
                names,
                center,
                _yaw(Vec2(0.0, 1.0)),
                profile.entry_exit_cone,
                "lane_cone",
                {"side": side_name, "station_m": y, "marking": marking, "ring": marking},
                footprint_of(profile.entry_exit_cone) + 0.16,
                pose_rng,
                jitter,
            )

    y = -config.skidpad_entry_length
    while y <= -3.6:
        place_orange(y, "entry")
        y += 5.0
    y = 4.0
    while y <= config.skidpad_exit_length + 1e-6:
        place_orange(y, "exit")
        y += 5.0

    for sign, side_name in ((1.0, "left"), (-1.0, "right")):
        center = Vec2(0.0, 0.0) + left_normal * sign * (half_path + half_large)
        _append_cone(
            objects,
            occupied,
            names,
            center,
            _yaw(Vec2(0.0, 1.0)),
            profile.start_finish_cone,
            "boundary_cone",
            {
                "side": side_name,
                "station_m": 0.0,
                "boundary_length_m": 0.0,
                "marking": "start_finish",
                "timing_gate": True,
                "ring": "gate",
            },
            footprint_of(profile.start_finish_cone) + 0.16,
            pose_rng,
            jitter,
        )


def generate_cones(
    track: TrackData,
    profile: RuleProfile,
    config: GeneratorConfig,
    limits: ResolvedLimits,
    rng: SeededRNG,
    names: NameSequence,
) -> tuple[list[PlacedObject], list[UniqueMesh], list[str]]:
    """Return cone instances, marking meshes, and warnings."""
    warnings: list[str] = []
    objects: list[PlacedObject] = []
    occupied: SpatialHash[float] = SpatialHash(1.0)
    variation = rng.child("cones") if config.cone_placement_variation > 0.0 else None
    pose_rng = rng.child("cone-pose")
    if track.event_type == "skidpad":
        _place_skidpad_cones(track, profile, config, names, occupied, objects, pose_rng)
        markings = marking_lines(track) if config.enable_start_finish and track.centerline else []
        return objects, markings, warnings
    # Left of the direction of travel uses the positive left normal. Right uses the opposite.
    _boundary_cones(
        track.left_boundary,
        1.0,
        "left",
        profile.left_cone,
        track,
        profile,
        config,
        limits,
        names,
        occupied,
        variation,
        objects,
        pose_rng,
    )
    _boundary_cones(
        track.right_boundary,
        -1.0,
        "right",
        profile.right_cone,
        track,
        profile,
        config,
        limits,
        names,
        occupied,
        variation,
        objects,
        pose_rng,
    )
    _lane_cones(track, profile, config, limits, names, occupied, objects, warnings, pose_rng)
    markings: list[UniqueMesh] = []
    if config.enable_start_finish and track.centerline:
        markings.extend(marking_lines(track))
    return objects, markings, warnings
