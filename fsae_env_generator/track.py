"""Closed-loop centerlines, offset boundaries, and the asphalt ribbon.

Procedural tracks are built from straight segments and circular fillets so the
minimum turning diameter and maximum straight length are controlled directly.
A centripetal Catmull-Rom spline then resamples that loop when the spline still
meets the same limits. Supplied centerlines are smoothed with the same spline.

Track width is the distance between the inner edges of the cone bases. Those
edges are the left and right boundary polylines, each offset from the
centerline by half the requested width along the local normal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import GeneratorConfig, ResolvedLimits, resolve_limits
from .math2d import (
    Vec2,
    centroid,
    cumulative_lengths,
    curvatures,
    curvatures_over_window,
    dedupe_points,
    ensure_ccw,
    has_near_approach,
    is_convex_ccw,
    min_radius,
    polyline_length,
    polyline_self_intersects,
    resample_polyline,
    rotate_around,
    scale_around,
    signed_area,
    straight_segment_lengths,
    tangents_and_normals,
)
from .rng import SeededRNG
from .splines import sample_catmull_rom


@dataclass
class TrackData:
    """Pure-Python description of one track. Blender objects are built later."""

    centerline: list[Vec2]
    tangents: list[Vec2]
    left_normals: list[Vec2]
    curvatures: list[float]
    left_boundary: list[Vec2]
    right_boundary: list[Vec2]
    closed: bool
    width: float
    length: float
    min_radius: float
    max_straight: float
    straight_lengths: list[float]
    surface_vertices: list[tuple[float, float, float]]
    surface_faces: list[tuple[int, int, int]]
    centerline_method: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class PathMetrics:
    length: float
    min_radius: float
    max_straight: float
    straight_lengths: list[float]
    self_intersects: bool
    near_approach: bool
    max_segment: float


def measure_path(
    points: list[Vec2],
    closed: bool,
    straight_radius: float,
    approach_distance: float,
    approach_window_m: float,
    sample_spacing: float,
) -> PathMetrics:
    # Wider stencil: a G1 fillet join is not a tighter corner than the arc itself.
    curvature = curvatures_over_window(points, closed, window_m=2.0)
    straights = straight_segment_lengths(points, curvature, closed, straight_radius)
    count = len(points)
    segments = count if closed else max(0, count - 1)
    max_segment = 0.0
    for index in range(segments):
        max_segment = max(max_segment, points[index].distance(points[(index + 1) % count]))
    window = max(2, int(math.ceil(approach_window_m / max(sample_spacing, 1e-3))))
    return PathMetrics(
        length=polyline_length(points, closed),
        min_radius=min_radius(curvature),
        max_straight=max(straights) if straights else 0.0,
        straight_lengths=straights,
        self_intersects=polyline_self_intersects(points, closed),
        near_approach=has_near_approach(points, approach_distance, window, closed),
        max_segment=max_segment,
    )


def _required_radius(config: GeneratorConfig, limits: ResolvedLimits) -> float:
    """Tightest centerline radius that still satisfies the profile and the offset.

    The inner boundary cusps when the centerline radius drops to half the track
    width, so the centerline is kept at least `width/2 + 0.6 m` even when the
    competition minimum turning radius is smaller.
    """
    return max(limits.min_turning_diameter * 0.5, config.track_width * 0.5 + 0.6)


def _path_is_acceptable(
    points: list[Vec2],
    config: GeneratorConfig,
    limits: ResolvedLimits,
    *,
    check_length: bool,
) -> bool:
    if len(points) < 8:
        return False
    metrics = measure_path(
        points,
        True,
        config.straight_curvature_radius,
        config.track_width * 0.98,
        max(8.0, config.track_width * 3.0),
        config.sample_spacing,
    )
    required = _required_radius(config, limits)
    if metrics.self_intersects and not config.allow_self_intersection:
        return False
    if metrics.near_approach and not config.allow_self_intersection:
        return False
    # Generation is stricter than the validation tolerance so a sampled curve
    # cannot drift below the competition minimum turning radius.
    if metrics.min_radius < required - 0.05:
        return False
    if metrics.max_straight > limits.max_straight + config.straight_length_tolerance:
        return False
    if check_length:
        if metrics.length < limits.length_min - config.length_tolerance:
            return False
        if metrics.length > limits.length_max + config.length_tolerance:
            return False
    if metrics.max_segment > config.sample_spacing * 2.5:
        return False
    return True


def _sample_line(start: Vec2, end: Vec2, spacing: float) -> list[Vec2]:
    """Samples from `start` up to but not including `end`."""
    length = start.distance(end)
    if length < 1e-8:
        return []
    steps = max(1, int(math.ceil(length / spacing)))
    return [start.lerp(end, index / steps) for index in range(steps)]


def _sample_arc(center: Vec2, radius: float, angle0: float, sweep: float, spacing: float) -> list[Vec2]:
    """Samples a circular arc, excluding the endpoint so the next piece can own it.

    `sweep` is signed. Positive sweep turns counter-clockwise, which is a left turn.
    """
    arc_length = abs(radius * sweep)
    if arc_length < 1e-8:
        return []
    steps = max(1, int(math.ceil(arc_length / spacing)))
    points = []
    for index in range(steps):
        angle = angle0 + sweep * (index / steps)
        points.append(Vec2(center.x + radius * math.cos(angle), center.y + radius * math.sin(angle)))
    return points


def trace_rounded_loop(
    straight_lengths: list[float],
    radius: float,
    spacing: float,
    heading0: float = 0.0,
) -> tuple[list[Vec2], float]:
    """Trace straights joined by equal left-hand fillets.

    Every corner changes heading by `2π / n`. A regular polygon (equal straights)
    and a rounded rectangle (opposite straights equal) both return to the start.
    The second value is the gap between the analytic endpoint and the origin.
    """
    count = len(straight_lengths)
    if count < 3:
        raise ValueError("A closed loop needs at least 3 corners.")
    if radius <= 0.0:
        raise ValueError("Fillet radius must be positive.")
    turn = 2.0 * math.pi / count
    heading = heading0
    position = Vec2(0.0, 0.0)
    points: list[Vec2] = []
    for length in straight_lengths:
        direction = Vec2(math.cos(heading), math.sin(heading))
        straight_end = position + direction * max(length, 0.0)
        points.extend(_sample_line(position, straight_end, spacing))
        # The fillet center sits one radius to the left of the travel direction.
        left = Vec2(-direction.y, direction.x)
        center = straight_end + left * radius
        angle0 = math.atan2(straight_end.y - center.y, straight_end.x - center.x)
        points.extend(_sample_arc(center, radius, angle0, turn, spacing))
        angle1 = angle0 + turn
        position = Vec2(center.x + radius * math.cos(angle1), center.y + radius * math.sin(angle1))
        heading += turn
    gap = position.distance(Vec2(0.0, 0.0))
    return dedupe_points(points, closed=True), gap


def _straight_budget(target_length: float, radius: float) -> float:
    return target_length - 2.0 * math.pi * radius


def _regular_lengths(
    rng: SeededRNG,
    target_length: float,
    radius: float,
    max_straight: float,
    min_straight: float,
    num_corners: int | None,
    num_straights: int | None,
    warnings: list[str],
) -> list[float]:
    budget = _straight_budget(target_length, radius)
    if budget <= 1.0:
        raise ValueError(
            f"Target length {target_length:.1f} m is too short for a turning radius of {radius:.2f} m."
        )
    cap = max_straight / 1.03
    minimum_n = max(4, int(math.ceil(budget / cap - 1e-9)))
    requested = num_corners if num_corners is not None else num_straights
    if num_corners is not None and num_straights is not None and num_corners != num_straights:
        warnings.append(
            "num_corners and num_straights differ. A single closed loop uses one straight "
            f"per corner, so num_corners ({num_corners}) is used and then increased if the "
            "maximum straight length requires it."
        )
    if requested is not None:
        count = max(int(requested), minimum_n)
        if count != int(requested):
            warnings.append(
                f"Corner count was increased from {int(requested)} to {count} so no straight "
                f"exceeds {max_straight:.1f} m at the target length."
            )
    else:
        longest_ok = max(minimum_n, int(math.floor(budget / max(min_straight, 0.5))))
        upper = max(minimum_n, min(longest_ok, minimum_n + 3, 12))
        count = rng.randint(minimum_n, upper)
    length = budget / count
    if length > cap:
        count = int(math.ceil(budget / cap))
        length = budget / count
    if length + 1e-6 < min_straight:
        warnings.append(
            f"Straights are {length:.1f} m, below the requested minimum of {min_straight:.1f} m. "
            "Maximum straight length and lap length were given priority."
        )
    return [length] * count


def _rectangle_lengths(
    rng: SeededRNG,
    target_length: float,
    radius: float,
    max_straight: float,
    min_straight: float,
) -> list[float] | None:
    """Opposite-side rounded rectangle, or None when it cannot hit the target."""
    half = _straight_budget(target_length, radius) / 2.0
    cap = max_straight / 1.03
    if half < min_straight * 2.0 or half > cap * 2.0:
        return None
    low = max(min_straight, half - cap)
    high = min(cap, half - min_straight)
    if high < low:
        return None
    long_side = rng.uniform(low, high)
    short_side = half - long_side
    return [long_side, short_side, long_side, short_side]


def _scale_to_length(points: list[Vec2], target_length: float) -> list[Vec2]:
    current = polyline_length(points, True)
    if current < 1e-6:
        return points
    return scale_around(points, centroid(points), target_length / current)


def _build_analytic_loop(
    rng: SeededRNG,
    config: GeneratorConfig,
    limits: ResolvedLimits,
    target_length: float,
    radius: float,
    warnings: list[str],
) -> list[Vec2]:
    shape_rng = rng.child("shape")
    rectangle = _rectangle_lengths(
        shape_rng,
        target_length,
        radius,
        limits.max_straight,
        config.min_straight_length,
    )
    if rectangle is not None and shape_rng.random() < 0.45:
        lengths = rectangle
        warnings.append("Centerline base shape: rounded rectangle.")
    else:
        lengths = _regular_lengths(
            shape_rng,
            target_length,
            radius,
            limits.max_straight,
            config.min_straight_length,
            config.num_corners,
            config.num_straights,
            warnings,
        )
        warnings.append(f"Centerline base shape: rounded regular loop with {len(lengths)} corners.")
    points, gap = trace_rounded_loop(lengths, radius, config.sample_spacing)
    if gap > 1e-3:
        raise RuntimeError(f"Analytic loop failed to close (gap {gap:.4f} m).")
    points = resample_polyline(points, config.sample_spacing, True)
    return _scale_to_length(points, target_length)


def _rotate(points: list[Vec2], angle: float) -> list[Vec2]:
    return rotate_around(points, centroid(points), angle)


def _straight_runs(points: list[Vec2], config: GeneratorConfig) -> list[tuple[int, int, float]]:
    """Return non-wrapping `(start, end, length)` runs that count as straights.

    `end` is the last point index of the run. The run does not include the
    closing segment of the loop.
    """
    curvature = curvatures(points, True)
    threshold = 1.0 / config.straight_curvature_radius
    count = len(points)
    gentle = [abs(curvature[index]) <= threshold for index in range(count)]
    runs: list[tuple[int, int, float]] = []
    start = None
    for index, flag in enumerate(gentle):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append(_run_tuple(points, start, index - 1))
            start = None
    if start is not None:
        runs.append(_run_tuple(points, start, count - 1))
    return [run for run in runs if run[2] >= 12.0]


def _run_tuple(points: list[Vec2], start: int, end: int) -> tuple[int, int, float]:
    length = 0.0
    for index in range(start, end):
        length += points[index].distance(points[index + 1])
    return start, end, length


def _feature_shape(u: float, waves: int) -> float:
    """Smooth lateral profile. Value and derivative are zero at both ends."""
    return math.sin(waves * math.pi * u) * math.sin(math.pi * u) ** 2


def apply_lateral_feature(
    points: list[Vec2],
    start: int,
    end: int,
    amplitude: float,
    waves: int,
) -> list[Vec2]:
    """Push a non-wrapping index range sideways and return to the same tangents.

    `waves=2` is one S (left then right). `waves=4` is a tighter chicane.
    Endpoints do not move, and the lateral derivative is zero there, so the
    join back onto the straight stays G1.
    """
    if end - start < 4 or amplitude == 0.0:
        return list(points)
    peak = max(abs(_feature_shape(index / 200.0, waves)) for index in range(201))
    if peak < 1e-8:
        return list(points)
    tangent = (points[end] - points[start]).normalized()
    left = tangent.left_normal()
    updated = list(points)
    span = end - start
    for step in range(span + 1):
        u = step / span
        offset = amplitude * _feature_shape(u, waves) / peak
        updated[start + step] = points[start + step] + left * offset
    return updated


def _try_feature(
    points: list[Vec2],
    start: int,
    end: int,
    amplitude: float,
    waves: int,
    config: GeneratorConfig,
    limits: ResolvedLimits,
) -> list[Vec2] | None:
    candidate = apply_lateral_feature(points, start, end, amplitude, waves)
    candidate = resample_polyline(dedupe_points(candidate, closed=True), config.sample_spacing, True)
    if _path_is_acceptable(candidate, config, limits, check_length=True):
        return candidate
    return None


def _apply_features(
    points: list[Vec2],
    rng: SeededRNG,
    config: GeneratorConfig,
    limits: ResolvedLimits,
    warnings: list[str],
) -> list[Vec2]:
    """Add an S-curve and a chicane when they still meet the geometric limits."""
    feature_rng = rng.child("features")
    want_s = feature_rng.random() < 0.9
    want_chicane = feature_rng.random() < 0.75
    current = points
    if want_s:
        runs = sorted(_straight_runs(current, config), key=lambda run: run[2], reverse=True)
        if runs:
            start, end, length = runs[0]
            amplitude = min(2.4, length * 0.045)
            updated = _try_feature(current, start, end, amplitude, 2, config, limits)
            if updated is not None:
                current = updated
                warnings.append("Added an S-curve on the longest straight.")
            else:
                warnings.append("Skipped the S-curve because it violated a geometric limit.")
    if want_chicane:
        runs = sorted(_straight_runs(current, config), key=lambda run: run[2], reverse=True)
        # Prefer a different straight than the one the S-curve just consumed.
        chosen = runs[1] if len(runs) > 1 else (runs[0] if runs else None)
        if chosen is not None and chosen[2] >= 16.0:
            start, end, length = chosen
            amplitude = min(1.6, length * 0.03)
            updated = _try_feature(current, start, end, amplitude, 4, config, limits)
            if updated is not None:
                current = updated
                warnings.append("Added a chicane on a straight.")
            else:
                warnings.append("Skipped the chicane because it violated a geometric limit.")
    return current


def _spline_resample(points: list[Vec2], spacing: float) -> list[Vec2]:
    controls = resample_polyline(points, max(spacing * 4.0, 2.0), True)
    return sample_catmull_rom(controls, spacing, True)


def _split_long_edges(points: list[Vec2], max_len: float) -> list[Vec2] | None:
    """Insert an outward kink so a later fillet can break an over-long straight."""
    current = list(points)
    for _ in range(12):
        count = len(current)
        center = centroid(current)
        rebuilt: list[Vec2] = []
        changed = False
        for index in range(count):
            start = current[index]
            end = current[(index + 1) % count]
            rebuilt.append(start)
            length = start.distance(end)
            if length > max_len:
                mid = start.lerp(end, 0.5)
                outward = (mid - center).normalized()
                if outward.length() < 1e-8:
                    outward = Vec2(0.0, 1.0)
                rebuilt.append(mid + outward * min(2.0, length * 0.025))
                changed = True
        if not is_convex_ccw(rebuilt):
            return current if is_convex_ccw(current) else None
        current = rebuilt
        if not changed:
            return current
    return current


def _fillet_polygon(points: list[Vec2], min_radius: float, spacing: float) -> tuple[list[Vec2], float] | None:
    """Fillet a CCW convex polygon. Returns samples and the smallest radius used.

    Setback along each edge is `r * tan(δ / 2)`, where δ is the heading change.
    That places the arc tangent to both edges. If the edges are too short for
    `min_radius`, the radius is reduced and the caller can scale the polygon up.
    """
    count = len(points)
    if count < 3 or not is_convex_ccw(points):
        return None
    corners = []
    achieved = float("inf")
    for index in range(count):
        previous = points[(index - 1) % count]
        vertex = points[index]
        nxt = points[(index + 1) % count]
        arrive = (vertex - previous).normalized()
        leave = (nxt - vertex).normalized()
        turn = math.atan2(arrive.cross(leave), max(-1.0, min(1.0, arrive.dot(leave))))
        if turn <= math.radians(1.0):
            corners.append({"radius": 0.0, "vertex": vertex, "turn": turn})
            continue
        edge_prev = vertex.distance(previous)
        edge_next = nxt.distance(vertex)
        max_setback = 0.45 * min(edge_prev, edge_next)
        # Sharp corners stay at the minimum legal radius. Gentle corners open up.
        sharpness = min(1.0, turn / math.radians(110.0))
        desired = min_radius + (1.0 - sharpness) * min_radius
        setback = desired * math.tan(turn * 0.5)
        if setback > max_setback:
            setback = max_setback
            radius = setback / math.tan(turn * 0.5)
        else:
            radius = desired
        achieved = min(achieved, radius)
        tangent_in = vertex - arrive * setback
        tangent_out = vertex + leave * setback
        left = Vec2(-arrive.y, arrive.x)
        center = tangent_in + left * radius
        angle0 = math.atan2(tangent_in.y - center.y, tangent_in.x - center.x)
        corners.append(
            {
                "radius": radius,
                "turn": turn,
                "tangent_in": tangent_in,
                "tangent_out": tangent_out,
                "center": center,
                "angle0": angle0,
                "vertex": vertex,
            }
        )
    samples: list[Vec2] = []
    for index, corner in enumerate(corners):
        if corner["radius"] > 1e-4:
            samples.extend(
                _sample_arc(corner["center"], corner["radius"], corner["angle0"], corner["turn"], spacing)
            )
            start = corner["tangent_out"]
        else:
            start = corner["vertex"]
        nxt = corners[(index + 1) % count]
        end = nxt["tangent_in"] if nxt["radius"] > 1e-4 else nxt["vertex"]
        samples.extend(_sample_line(start, end, spacing))
    samples = dedupe_points(samples, closed=True)
    if len(samples) < 8:
        return None
    return samples, achieved if math.isfinite(achieved) else 0.0


def _try_varied_polygon(
    rng: SeededRNG,
    config: GeneratorConfig,
    limits: ResolvedLimits,
    target_length: float,
    radius: float,
) -> list[Vec2] | None:
    """Convex control polygon with one sharper corner. Accepted only if it validates."""
    shape_rng = rng.child("varied")
    count = max(5, int(round(target_length / max(limits.max_straight * 0.65, 20.0))))
    count = min(count, 12)
    weights = [shape_rng.uniform(0.85, 1.15) for _ in range(count)]
    total = sum(weights)
    angle = 0.0
    angles = []
    for weight in weights:
        angles.append(2.0 * math.pi * angle / total)
        angle += weight
    mean_radius = max(target_length / (2.0 * math.pi), radius + config.track_width)
    radii = [mean_radius * shape_rng.uniform(0.88, 1.12) for _ in range(count)]
    # Pull one vertex out so its interior angle becomes the hairpin-style corner.
    radii[0] *= 1.45
    points = ensure_ccw(
        [Vec2(radii[index] * math.cos(angles[index]), radii[index] * math.sin(angles[index])) for index in range(count)]
    )
    points = _split_long_edges(points, limits.max_straight * 0.75)
    if points is None:
        return None
    filleted = _fillet_polygon(points, radius, config.sample_spacing)
    if filleted is None:
        return None
    samples, achieved = filleted
    if achieved < radius * 0.98:
        scale = (radius / max(achieved, 0.1)) * 1.04
        points = scale_around(points, centroid(points), scale)
        points = _split_long_edges(points, limits.max_straight * 0.75)
        if points is None:
            return None
        filleted = _fillet_polygon(points, radius, config.sample_spacing)
        if filleted is None:
            return None
        samples, achieved = filleted
        if achieved < radius - 0.05:
            return None
    samples = resample_polyline(samples, config.sample_spacing, True)
    length = polyline_length(samples, True)
    if length < 1e-3:
        return None
    scaled = _scale_to_length(samples, target_length)
    if _path_is_acceptable(scaled, config, limits, check_length=True):
        return scaled
    return None


def _roll_to_longest_straight(points: list[Vec2], config: GeneratorConfig) -> list[Vec2]:
    """Put the start/finish line at the beginning of the longest straight.

    Entry and exit lanes are drawn along the opening tangent, so the gate needs
    to sit on a straight rather than in the sharpened corner.
    """
    runs = _straight_runs(points, config)
    if not runs:
        return points
    start, _end, _length = max(runs, key=lambda run: run[2])
    if start <= 0:
        return points
    return points[start:] + points[:start]


def generate_procedural_centerline(
    config: GeneratorConfig,
    limits: ResolvedLimits,
    rng: SeededRNG,
) -> tuple[list[Vec2], str, list[str]]:
    warnings: list[str] = []
    target = rng.child("target").uniform(limits.length_min, limits.length_max)
    # A little extra radius absorbs the chord approximation and later spline fit.
    radius = _required_radius(config, limits) + 0.35
    rotation = rng.child("rotation").uniform(0.0, 2.0 * math.pi)
    varied = _try_varied_polygon(rng, config, limits, target, radius)
    if varied is not None:
        points = varied
        method = "varied_polygon"
        warnings.append("Centerline base shape: varied convex polygon with a sharpened corner.")
    else:
        points = _build_analytic_loop(rng, config, limits, target, radius, warnings)
        method = "arc_line"
    points = _rotate(points, rotation)
    points = resample_polyline(points, config.sample_spacing, True)
    if not _path_is_acceptable(points, config, limits, check_length=True):
        # Rotation and resampling should not break the analytic loop. Rebuild it plainly.
        warnings.append("Procedural variation was discarded because it missed a geometric limit.")
        points = _build_analytic_loop(rng, config, limits, target, radius, warnings)
        points = _rotate(points, rotation)
        points = resample_polyline(points, config.sample_spacing, True)
        method = "arc_line"
    points = _apply_features(points, rng, config, limits, warnings)
    splined = _spline_resample(points, config.sample_spacing)
    if _path_is_acceptable(splined, config, limits, check_length=True):
        chosen = splined
        method = "catmull_rom" if method == "arc_line" else "catmull_rom_varied"
    else:
        warnings.append("Catmull-Rom resample missed a limit, so the arc-line centerline was kept.")
        chosen = points
    chosen = _roll_to_longest_straight(chosen, config)
    return chosen, method, warnings


def centerline_from_input(config: GeneratorConfig) -> tuple[list[Vec2], str, list[str]]:
    """Smooth or resample a user centerline. The z coordinate is ignored."""
    if not config.centerline or len(config.centerline) < 2:
        raise ValueError("A custom centerline needs at least two points.")
    raw = [Vec2(float(point[0]), float(point[1])) for point in config.centerline]
    closed = config.wants_closed_loop()
    warnings: list[str] = []
    if closed and raw[0].distance(raw[-1]) < max(0.5, config.sample_spacing):
        raw = raw[:-1]
        warnings.append("Dropped a duplicate closing point from the supplied centerline.")
    if len(raw) < 3 and closed:
        raise ValueError("A closed custom centerline needs at least three distinct points.")
    if config.smooth_centerline and len(raw) >= 4:
        points = sample_catmull_rom(raw, config.sample_spacing, closed)
        method = "catmull_rom"
    else:
        points = resample_polyline(raw, config.sample_spacing, closed)
        method = "polyline"
        if config.smooth_centerline:
            warnings.append("Centerline has fewer than 4 points, so it was resampled without a spline.")
    return points, method, warnings


def build_surface(
    left: list[Vec2],
    right: list[Vec2],
    closed: bool,
    z: float = 0.02,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Triangle ribbon between the inner-edge boundaries. Normals point up."""
    count = len(left)
    if count != len(right) or count < 2:
        raise ValueError("Boundary polylines must match and contain at least two points.")
    vertices = [(point.x, point.y, z) for point in left] + [(point.x, point.y, z) for point in right]
    faces: list[tuple[int, int, int]] = []
    segments = count if closed else count - 1
    for index in range(segments):
        nxt = (index + 1) % count
        left_i, left_j = index, nxt
        right_i, right_j = count + index, count + nxt
        faces.append((left_i, right_i, right_j))
        faces.append((left_i, right_j, left_j))
    ax, ay, _az = vertices[faces[0][0]]
    bx, by, _bz = vertices[faces[0][1]]
    cx, cy, _cz = vertices[faces[0][2]]
    # Positive z component of AB × AC means the face is counter-clockwise from above.
    if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) < 0.0:
        faces = [tuple(reversed(face)) for face in faces]
    return vertices, faces


def build_track(
    centerline: list[Vec2],
    config: GeneratorConfig,
    method: str,
    warnings: list[str] | None = None,
) -> TrackData:
    """Offset `centerline` into boundaries and a mesh. Width is constant by construction.

    At each sample the left boundary is `center + left_normal * width/2` and the
    right boundary is the opposite offset. Left is the blue-cone side when the
    centerline is traveled in its stored direction.
    """
    closed = config.wants_closed_loop()
    if len(centerline) < 2:
        raise ValueError("Centerline is too short to build a track.")
    points = dedupe_points(centerline, closed=closed)
    tangents, normals = tangents_and_normals(points, closed)
    # Local curvature drives cone spacing. The stored minimum radius uses a
    # 2 m window so a fillet join is not reported as a tighter corner.
    curvature = curvatures(points, closed)
    windowed = curvatures_over_window(points, closed, window_m=2.0)
    half = config.track_width * 0.5
    left = [points[index] + normals[index] * half for index in range(len(points))]
    right = [points[index] - normals[index] * half for index in range(len(points))]
    straights = straight_segment_lengths(points, windowed, closed, config.straight_curvature_radius)
    vertices, faces = build_surface(left, right, closed)
    area = signed_area(points)
    direction_note = []
    if closed and area < 0.0:
        direction_note.append(
            "Supplied centerline is clockwise. Blue cones still follow the left side of travel."
        )
    return TrackData(
        centerline=points,
        tangents=tangents,
        left_normals=normals,
        curvatures=curvature,
        left_boundary=left,
        right_boundary=right,
        closed=closed,
        width=config.track_width,
        length=polyline_length(points, closed),
        min_radius=min_radius(windowed),
        max_straight=max(straights) if straights else 0.0,
        straight_lengths=straights,
        surface_vertices=vertices,
        surface_faces=faces,
        centerline_method=method,
        warnings=[*(warnings or []), *direction_note],
    )


def generate_track(config: GeneratorConfig, rng: SeededRNG, limits: ResolvedLimits | None = None) -> TrackData:
    """Build a track from a supplied centerline, or create a closed loop from the seed."""
    limits = limits or resolve_limits(config)
    # Profile warnings are attached by the validator so they are not listed twice.
    notes: list[str] = []
    if config.centerline:
        if config.track_type != "custom":
            notes.append("A centerline was supplied, so it was used instead of a procedural loop.")
        points, method, extra = centerline_from_input(config)
        notes.extend(extra)
    else:
        if config.track_type == "custom":
            raise ValueError(
                "Track type 'custom' needs a centerline. Provide coordinates or, in Blender, "
                "a curve object named FSAE_Input_Centerline."
            )
        points, method, extra = generate_procedural_centerline(config, limits, rng)
        notes.extend(extra)
    track = build_track(points, config, method, notes)
    if math.isfinite(track.min_radius):
        track.warnings.append(f"Sharpest centerline radius over a 2 m window is {track.min_radius:.2f} m.")
    return track
