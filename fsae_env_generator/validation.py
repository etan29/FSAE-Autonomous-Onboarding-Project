"""Geometry checks and the validation report.

Checks use the same limits the generator resolved, and each limit's source is
printed so a Formula Student run is not described as if it enforced U.S. Formula
SAE track dimensions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .assets import footprint_of, mesh_aabb
from .config import GeneratorConfig, ResolvedLimits, resolve_limits
from .math2d import Vec2, min_distance_to_polyline, polyline_self_intersects
from .models import PlacedObject
from .spatial import SpatialHash
from .track import PathMetrics, TrackData, measure_path


@dataclass
class CheckResult:
    name: str
    category: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    seed: int
    rules_profile: str
    rules_revision: str
    rules_note: str
    track_length_m: float
    track_width_mean_m: float
    track_width_min_m: float
    track_width_max_m: float
    minimum_radius_m: float
    maximum_straight_m: float
    cones_per_boundary: dict[str, int]
    average_cone_spacing_m: dict[str, float]
    minimum_cone_spacing_m: dict[str, float]
    maximum_cone_spacing_m: dict[str, float]
    collision_violations: int
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "rules_profile": self.rules_profile,
            "rules_revision": self.rules_revision,
            "rules_note": self.rules_note,
            "track_length_m": self.track_length_m,
            "track_width_mean_m": self.track_width_mean_m,
            "track_width_min_m": self.track_width_min_m,
            "track_width_max_m": self.track_width_max_m,
            "minimum_radius_m": self.minimum_radius_m,
            "maximum_straight_m": self.maximum_straight_m,
            "cones_per_boundary": self.cones_per_boundary,
            "average_cone_spacing_m": self.average_cone_spacing_m,
            "minimum_cone_spacing_m": self.minimum_cone_spacing_m,
            "maximum_cone_spacing_m": self.maximum_cone_spacing_m,
            "collision_violations": self.collision_violations,
            "passed": self.passed,
            "warnings": list(self.warnings),
            "checks": [
                {"name": check.name, "category": check.category, "passed": check.passed, "detail": check.detail}
                for check in self.checks
            ],
        }


def format_report(report: ValidationReport) -> str:
    lines = [
        "FSAE Environment Validation Report",
        "==================================",
        f"Seed: {report.seed}",
        f"Rules profile: {report.rules_profile}",
        f"Revision: {report.rules_revision}",
        f"Note: {report.rules_note}",
        "",
        f"Track length: {report.track_length_m:.3f} m",
        (
            "Track width mean / min / max: "
            f"{report.track_width_mean_m:.3f} / {report.track_width_min_m:.3f} / {report.track_width_max_m:.3f} m"
        ),
        f"Minimum centerline radius: {report.minimum_radius_m:.3f} m",
        f"Maximum straight: {report.maximum_straight_m:.3f} m",
        "",
        "Cones",
    ]
    for side in ("left", "right"):
        count = report.cones_per_boundary.get(side, 0)
        average = report.average_cone_spacing_m.get(side, 0.0)
        low = report.minimum_cone_spacing_m.get(side, 0.0)
        high = report.maximum_cone_spacing_m.get(side, 0.0)
        lines.append(
            f"  {side}: {count} cones, spacing avg/min/max {average:.3f} / {low:.3f} / {high:.3f} m"
        )
    lines.append(f"Collision violations: {report.collision_violations}")
    if report.warnings:
        lines.append("")
        lines.append("Warnings")
        for warning in report.warnings:
            lines.append(f"  - {warning}")
    lines.append("")
    lines.append("Checks")
    for check in report.checks:
        state = "PASS" if check.passed else "FAIL"
        lines.append(f"  [{state}] {check.category}: {check.name} - {check.detail}")
    lines.append("")
    lines.append(f"Overall: {'PASS' if report.passed else 'FAIL'}")
    return "\n".join(lines) + "\n"


def scene_signature(track: TrackData, objects: list[PlacedObject]) -> list[tuple]:
    """Rounded geometry used to compare two runs. Order is generation order."""
    rows: list[tuple] = []
    for point in track.centerline:
        rows.append(("c", round(point.x, 6), round(point.y, 6)))
    for obj in objects:
        rows.append(
            (
                obj.role,
                obj.asset,
                round(obj.x, 6),
                round(obj.y, 6),
                round(obj.z, 6),
                round(obj.yaw, 6),
                round(obj.pitch, 6),
                round(obj.roll, 6),
                tuple(round(value, 6) for value in obj.scale),
            )
        )
    return rows


def _widths(track: TrackData) -> list[float]:
    return [
        track.left_boundary[index].distance(track.right_boundary[index])
        for index in range(len(track.centerline))
    ]


def _one_ring_gaps(cones: list[PlacedObject]) -> list[float]:
    if len(cones) < 2:
        return []
    cones.sort(key=lambda obj: float(obj.metadata.get("station_m", 0.0)))
    total = float(cones[0].metadata.get("boundary_length_m", 0.0))
    stations = [float(obj.metadata["station_m"]) for obj in cones]
    gaps = [stations[index + 1] - stations[index] for index in range(len(stations) - 1)]
    if total > stations[-1] + 1e-6:
        gaps.append(total - stations[-1] + stations[0])
    return gaps


def _boundary_gaps(objects: list[PlacedObject], side: str) -> list[float]:
    cones = [
        obj
        for obj in objects
        if obj.role == "boundary_cone" and obj.metadata.get("side") == side
    ]
    groups: dict[str, list[PlacedObject]] = {}
    for obj in cones:
        groups.setdefault(str(obj.metadata.get("ring", "main")), []).append(obj)
    gaps: list[float] = []
    for group in groups.values():
        gaps.extend(_one_ring_gaps(group))
    return gaps


def _summarize_gaps(gaps: list[float]) -> tuple[float, float, float]:
    if not gaps:
        return 0.0, 0.0, 0.0
    return sum(gaps) / len(gaps), min(gaps), max(gaps)


def _cone_overlap_count(objects: list[PlacedObject]) -> int:
    cones = [obj for obj in objects if obj.role in {"boundary_cone", "lane_cone", "scattered_cone"}]
    occupied: SpatialHash[int] = SpatialHash(1.0)
    violations = 0
    for index, cone in enumerate(cones):
        point = Vec2(cone.x, cone.y)
        radius = footprint_of(cone.asset)
        for other, other_index in occupied.query_radius(point, radius + 0.4):
            other_cone = cones[other_index]
            required = radius + footprint_of(other_cone.asset) - 1e-3
            if point.distance(other) < required:
                violations += 1
        occupied.insert(point, index)
    return violations


def _cone_environment_overlap_count(objects: list[PlacedObject]) -> int:
    """Count cones that intersect a non-cone object. The spatial hash avoids an all-pairs loop."""
    cones = [obj for obj in objects if obj.role in {"boundary_cone", "lane_cone", "scattered_cone"}]
    others = [obj for obj in objects if obj.role not in {"boundary_cone", "lane_cone", "scattered_cone"}]
    occupied: SpatialHash[int] = SpatialHash(2.0)
    for index, cone in enumerate(cones):
        occupied.insert(Vec2(cone.x, cone.y), index)
    violations = 0
    for obj in others:
        footprint = float(obj.metadata.get("footprint_m", footprint_of(obj.asset)))
        point = Vec2(obj.x, obj.y)
        for other, index in occupied.query_radius(point, footprint + 0.5):
            required = footprint + footprint_of(cones[index].asset) - 0.05
            if point.distance(other) < required:
                violations += 1
    return violations


def _environment_collision_count(track: TrackData, objects: list[PlacedObject]) -> int:
    violations = 0
    half = track.width * 0.5
    for obj in objects:
        if obj.role in {"boundary_cone", "lane_cone", "scattered_cone"}:
            continue
        footprint = float(obj.metadata.get("footprint_m", footprint_of(obj.asset)))
        distance = min_distance_to_polyline(Vec2(obj.x, obj.y), track.centerline, track.closed)
        if distance - footprint < half - 0.05:
            violations += 1
    return violations


def _event_checks(add, track: TrackData, objects: list[PlacedObject], config: GeneratorConfig, metrics: PathMetrics) -> None:
    """Rule checks that the generic lap-length test does not cover."""
    kind = config.track_type
    if kind == "acceleration":
        add(
            "event",
            "Acceleration timed length is 75 m",
            abs(track.timed_length - 75.0) <= 0.05,
            f"Timed length {track.timed_length:.2f} m (D.9.1.1). Total centerline {metrics.length:.2f} m includes the exit lane.",
        )
        target = 75.0 + config.stopping_zone_length
        add(
            "event",
            "Acceleration exit lane follows the finish",
            abs(metrics.length - target) <= max(1.0, config.sample_spacing * 2.0),
            f"Expected {target:.2f} m (75 m timed plus {config.stopping_zone_length:.2f} m exit, DD.4.2.4).",
        )
    elif kind == "skidpad":
        xs = [point.x for point in track.centerline]
        near = sum(1 for point in track.centerline if point.length() < 1.0)
        add(
            "event",
            "Skidpad is one figure eight",
            bool(xs) and min(xs) < -8.0 and max(xs) > 8.0 and near >= 2,
            "The centerline reaches both circles and passes through the shared crossover.",
        )
        rings = {
            "right-inner": 17,
            "left-inner": 17,
            "right-outer": 13,
            "left-outer": 13,
        }
        counts = {ring: sum(1 for obj in objects if obj.metadata.get("ring") == ring) for ring in rings}
        count_ok = all(counts[ring] == expected for ring, expected in rings.items())
        add(
            "event",
            "Skidpad cone counts match 2026",
            count_ok,
            f"Inner 17 and outer 13 per circle (DD.4.3.1, D.10.1.2). Counts: {counts}.",
        )
        add(
            "event",
            "Skidpad timed length is two timed laps",
            abs(track.timed_length - 2.0 * 2.0 * math.pi * 9.125) < 0.05,
            f"Timed length {track.timed_length:.2f} m is the second right lap plus the second left lap.",
        )
    elif kind == "ebs":
        info = track.event_metrics or {}
        stop = float(info.get("emergency_stop_length_m", 0.0))
        accel = float(info.get("accel_length_m", 0.0))
        add(
            "event",
            "EBS emergency stop is at most 8.5 m",
            0.5 < stop <= 8.5 + 1e-6,
            f"Emergency region {stop:.2f} m (DI.2.2.2).",
        )
        add(
            "event",
            "EBS acceleration zone is at most 20 m",
            0.5 < accel <= 20.0 + 1e-6,
            f"Acceleration zone {accel:.2f} m (DI.2.2.2, distance to reach 40 km/h).",
        )
        text = " ".join(track.assumptions).lower()
        add(
            "event",
            "EBS unpublished lengths are labeled assumptions",
            "assumption" in text and info.get("scored_event") is False,
            "Approach length, trigger coordinate, rest corridor, and width are assumptions. EBS is not a scored event.",
        )
    elif kind == "autocross":
        arc_ok = 200.0 - config.length_tolerance <= metrics.length <= 500.0 + config.length_tolerance
        add(
            "event",
            "Autocross centerline arc length is 200-500 m",
            arc_ok,
            f"Arc length {metrics.length:.2f} m (DD.4.4.1). This is the polyline length, not the bounding box.",
        )
        zone = track.stopping_zone or {}
        add(
            "event",
            "Autocross stopping zone stays on the track",
            bool(zone.get("on_track")) and float(zone.get("length_m", 0.0)) <= 30.0 + 1e-6,
            "DD.4.4.4: stop in 30 m or less on the track after the finish.",
        )


def validate_environment(
    track: TrackData,
    objects: list[PlacedObject],
    assets: dict,
    config: GeneratorConfig,
    limits: ResolvedLimits | None = None,
    reproducible: bool | None = None,
    extra_warnings: list[str] | None = None,
    terrain_bounds: tuple[float, float, float, float] | None = None,
) -> ValidationReport:
    limits = limits or resolve_limits(config)
    profile = config.profile()
    checks: list[CheckResult] = []
    warnings = list(limits.warnings)
    warnings.extend(track.warnings)
    if extra_warnings:
        warnings.extend(extra_warnings)

    metrics: PathMetrics = measure_path(
        track.centerline,
        track.closed,
        config.straight_curvature_radius,
        config.track_width * 0.98,
        max(8.0, config.track_width * 3.0),
        config.sample_spacing,
    )
    widths = _widths(track)
    if config.track_type == "skidpad" and widths:
        # The figure-eight crossover is a single shared point. Width samples on top of it are not the 3 m path.
        kept = [widths[index] for index, point in enumerate(track.centerline) if point.length() > 2.5]
        if kept:
            widths = kept
    width_mean = sum(widths) / len(widths) if widths else 0.0
    width_min = min(widths) if widths else 0.0
    width_max = max(widths) if widths else 0.0

    def add(category: str, name: str, passed: bool, detail: str) -> None:
        checks.append(CheckResult(name=name, category=category, passed=passed, detail=detail))

    add(
        "track",
        "Track is continuous",
        metrics.max_segment <= config.sample_spacing * 2.5,
        f"Largest sample gap is {metrics.max_segment:.3f} m.",
    )
    if config.wants_closed_loop():
        closing = track.centerline[-1].distance(track.centerline[0]) if len(track.centerline) > 1 else 0.0
        add(
            "track",
            "Track is closed",
            track.closed and closing <= config.sample_spacing * 2.5,
            f"Closing segment is {closing:.3f} m.",
        )
    else:
        add("track", "Track is closed", True, "Closed-loop mode is off, so this check does not apply.")
    if config.allow_self_intersection:
        intersection_detail = "Self-intersection is enabled for this run."
    elif metrics.self_intersects:
        intersection_detail = "Centerline segments cross."
    else:
        intersection_detail = "Centerline segments do not cross."
    add(
        "track",
        "No unintended self-intersection",
        config.allow_self_intersection or not metrics.self_intersects,
        intersection_detail,
    )
    if not config.allow_self_intersection and (
        polyline_self_intersects(track.left_boundary, track.closed)
        or polyline_self_intersects(track.right_boundary, track.closed)
    ):
        add("track", "Boundaries do not self-intersect", False, "An offset boundary crosses itself.")
    else:
        add("track", "Boundaries do not self-intersect", True, "Left and right boundaries do not cross themselves.")
    width_tolerance = config.track_width_tolerance
    if config.track_width_variation > 0.0:
        width_tolerance = max(width_tolerance, config.track_width * config.track_width_variation * 1.25)
    width_ok = abs(width_mean - config.track_width) <= width_tolerance and (
        width_max - width_min
    ) <= width_tolerance
    add(
        "track",
        "Track width matches the request",
        width_ok,
        f"Requested {config.track_width:.3f} m, measured mean {width_mean:.3f} m.",
    )
    if profile.min_track_width_m is not None:
        add(
            "track",
            "Track width meets the selected profile",
            width_min + 1e-6 >= profile.min_track_width_m,
            f"{limits.min_track_width_source}. Minimum {profile.min_track_width_m:.2f} m, measured {width_min:.3f} m.",
        )
    else:
        add(
            "track",
            "Track width meets the selected profile",
            True,
            f"{profile.name} does not define a minimum track width. Generator width is {config.track_width:.2f} m.",
        )
    radius_limit = limits.min_turning_diameter * 0.5
    add(
        "track",
        "Minimum turning diameter is respected",
        metrics.min_radius + config.min_radius_tolerance >= radius_limit,
        (
            f"{limits.min_turning_diameter_source}. "
            f"Required radius {radius_limit:.2f} m, measured {metrics.min_radius:.2f} m "
            f"(tolerance {config.min_radius_tolerance:.2f} m)."
        ),
    )
    if config.track_type in {"acceleration", "ebs"}:
        add(
            "track",
            "Straight sections respect the maximum length",
            True,
            "The 80 m straight cap is DD.4.4.1 (driverless autocross). It is not applied to this straight-line event.",
        )
    else:
        add(
            "track",
            "Straight sections respect the maximum length",
            metrics.max_straight <= limits.max_straight + config.straight_length_tolerance,
            f"{limits.max_straight_source}. Maximum {limits.max_straight:.1f} m, measured {metrics.max_straight:.2f} m.",
        )
    length_applies = config.centerline is None and config.track_type not in {"acceleration", "skidpad", "ebs"}
    length_ok = limits.length_min - config.length_tolerance <= metrics.length <= limits.length_max + config.length_tolerance
    if config.track_type in {"acceleration", "skidpad", "ebs"}:
        add(
            "track",
            "Track length is within the target range",
            True,
            f"This event is not a 200–500 m autocross lap. Centerline arc length is {metrics.length:.2f} m.",
        )
    elif length_applies:
        add(
            "track",
            "Track length is within the target range",
            length_ok,
            f"{limits.length_source}. Range {limits.length_min:.0f}–{limits.length_max:.0f} m, measured {metrics.length:.2f} m.",
        )
    else:
        add(
            "track",
            "Track length is within the target range",
            length_ok,
            f"Custom centerline length is {metrics.length:.2f} m. Target range is {limits.length_min:.0f}–{limits.length_max:.0f} m.",
        )

    left = [obj for obj in objects if obj.role == "boundary_cone" and obj.metadata.get("side") == "left"]
    right = [obj for obj in objects if obj.role == "boundary_cone" and obj.metadata.get("side") == "right"]
    left_gaps = _boundary_gaps(objects, "left")
    right_gaps = _boundary_gaps(objects, "right")
    left_avg, left_min, left_max = _summarize_gaps(left_gaps)
    right_avg, right_min, right_max = _summarize_gaps(right_gaps)
    cones_per_boundary = {"left": len(left), "right": len(right)}
    average_spacing = {"left": left_avg, "right": right_avg}
    min_spacing = {"left": left_min, "right": right_min}
    max_spacing = {"left": left_max, "right": right_max}

    add(
        "cones",
        "Both boundaries have cones",
        len(left) >= 2 and len(right) >= 2,
        f"Left {len(left)}, right {len(right)}.",
    )

    def _allowed(obj: PlacedObject, regular: str) -> bool:
        kind = obj.asset
        if kind == regular:
            return True
        if config.enable_start_finish and kind == profile.start_finish_cone and obj.metadata.get("marking") == "start_finish":
            return True
        return False

    left_colors_ok = all(_allowed(obj, profile.left_cone) for obj in left)
    right_colors_ok = all(_allowed(obj, profile.right_cone) for obj in right)
    add(
        "cones",
        "Left boundary cones are blue",
        left_colors_ok and all(obj.asset != profile.right_cone for obj in left),
        f"Left asset is {profile.left_cone}, with {profile.start_finish_cone} allowed at the start/finish gate.",
    )
    add(
        "cones",
        "Right boundary cones are yellow",
        right_colors_ok and all(obj.asset != profile.left_cone for obj in right),
        f"Right asset is {profile.right_cone}, with {profile.start_finish_cone} allowed at the start/finish gate.",
    )

    def _dimension_ok(kind: str) -> bool:
        mesh = assets[kind]
        low, high = mesh_aabb(mesh)
        base, height = profile.cone_size(kind)
        return abs((high[0] - low[0]) - base) < 1e-4 and abs((high[2] - low[2]) - height) < 1e-4 and low[2] >= -1e-6

    dimension_ok = all(_dimension_ok(kind) for kind in ("blue_small", "yellow_small", "orange_small", "orange_large"))
    add(
        "cones",
        "Cone dimensions match the profile",
        dimension_ok,
        (
            f"Small {profile.small_cone_base_m:.3f} x {profile.small_cone_height_m:.3f} m, "
            f"large {profile.large_cone_base_m:.3f} x {profile.large_cone_height_m:.3f} m."
        ),
    )
    tolerance = config.cone_spacing_tolerance
    spacing_ok = True
    spacing_detail = []
    for side, gaps in (("left", left_gaps), ("right", right_gaps)):
        if not gaps:
            spacing_ok = False
            spacing_detail.append(f"{side} has no gaps")
            continue
        low = min(gaps)
        high = max(gaps)
        if low < limits.min_cone_spacing - tolerance or high > limits.max_cone_spacing + tolerance:
            spacing_ok = False
        spacing_detail.append(f"{side} {low:.2f}–{high:.2f} m")
    add(
        "cones",
        "Cone spacing is within the configured tolerance",
        spacing_ok,
        (
            f"{limits.cone_spacing_source}. Allowed {limits.min_cone_spacing:.2f}–{limits.max_cone_spacing:.2f} m "
            f"(tolerance {tolerance:.2f}). " + "; ".join(spacing_detail)
        ),
    )
    overlap_count = _cone_overlap_count(objects)
    cone_object_hits = _cone_environment_overlap_count(objects)
    add("cones", "Cones do not overlap", overlap_count == 0, f"{overlap_count} overlapping pair(s).")
    add(
        "cones",
        "Cones do not intersect other objects",
        cone_object_hits == 0,
        f"{cone_object_hits} cone/object intersection(s).",
    )

    def _on_correct_side(obj: PlacedObject, sign: float) -> bool:
        best_distance = float("inf")
        best_index = 0
        for index, sample in enumerate(track.centerline):
            distance = sample.distance(Vec2(obj.x, obj.y))
            if distance < best_distance:
                best_distance = distance
                best_index = index
        outward = track.left_normals[best_index] * sign
        offset = Vec2(obj.x, obj.y) - track.centerline[best_index]
        return offset.dot(outward) > 0.0

    sides_ok = all(_on_correct_side(obj, 1.0) for obj in left) and all(_on_correct_side(obj, -1.0) for obj in right)
    add("cones", "Cones sit on the correct side of the centerline", sides_ok, "Left cones are left of travel and right cones are right of travel.")

    gates = [obj for obj in objects if obj.metadata.get("marking") == "start_finish"]
    if config.enable_start_finish:
        gate_ok = len(gates) >= 2 and all(obj.asset == profile.start_finish_cone for obj in gates)
        add(
            "cones",
            "Special orange cones are identified",
            gate_ok,
            f"{len(gates)} start/finish cone(s) using {profile.start_finish_cone}.",
        )
    else:
        add("cones", "Special orange cones are identified", True, "Start/finish cones are disabled.")
    lanes = [obj for obj in objects if obj.role == "lane_cone"]
    if lanes:
        lane_ok = all(obj.asset == profile.entry_exit_cone for obj in lanes)
        add("cones", "Entry and exit cones are small orange", lane_ok, f"{len(lanes)} lane cone(s).")

    env_hits = _environment_collision_count(track, objects)
    collision_violations = overlap_count + env_hits + cone_object_hits
    add(
        "environment",
        "Environmental objects do not obstruct the track",
        env_hits == 0,
        f"{env_hits} object(s) intersect the drivable ribbon.",
    )
    if terrain_bounds is not None:
        min_x, min_y, max_x, max_y = terrain_bounds
        outside = 0
        for obj in objects:
            footprint = float(obj.metadata.get("footprint_m", 0.0))
            if obj.x - footprint < min_x - 0.05 or obj.x + footprint > max_x + 0.05:
                outside += 1
            elif obj.y - footprint < min_y - 0.05 or obj.y + footprint > max_y + 0.05:
                outside += 1
        add(
            "environment",
            "Objects stay inside the terrain",
            outside == 0,
            f"{outside} object(s) extend past the terrain rectangle.",
        )
    spectators = [obj for obj in objects if obj.role == "spectator"]
    spectator_bad = 0
    for obj in spectators:
        footprint = float(obj.metadata.get("footprint_m", 0.45))
        distance = min_distance_to_polyline(Vec2(obj.x, obj.y), track.centerline, track.closed)
        if distance - footprint < track.width * 0.5 + 2.0:
            spectator_bad += 1
    add(
        "environment",
        "Spectators are outside the restricted area",
        spectator_bad == 0,
        f"{spectator_bad} spectator(s) are within 2 m of the asphalt.",
    )
    trees_tents = [obj for obj in objects if obj.role in {"tree", "tent"}]
    plant_bad = 0
    for obj in trees_tents:
        footprint = float(obj.metadata.get("footprint_m", footprint_of(obj.asset)))
        distance = min_distance_to_polyline(Vec2(obj.x, obj.y), track.centerline, track.closed)
        if distance - footprint < track.width * 0.5 - 0.05:
            plant_bad += 1
    add(
        "environment",
        "Trees and tents stay off the drivable surface",
        plant_bad == 0,
        f"{plant_bad} tree or tent intersection(s).",
    )
    below_ground = [obj for obj in objects if obj.z < -1e-4]
    add(
        "environment",
        "Objects sit on the ground",
        len(below_ground) == 0,
        f"{len(below_ground)} object(s) have a negative height.",
    )
    _event_checks(add, track, objects, config, metrics)
    if reproducible is None:
        add("reproducibility", "Identical inputs repeat", True, "Reproducibility was not compared on this call.")
    else:
        add(
            "reproducibility",
            "Identical inputs repeat",
            reproducible,
            "A second build with the same seed matched the first." if reproducible else "The second build differed.",
        )

    passed = all(check.passed for check in checks)
    return ValidationReport(
        seed=config.seed,
        rules_profile=f"{profile.name} [{profile.id}]",
        rules_revision=profile.revision,
        rules_note=profile.source_note,
        track_length_m=metrics.length,
        track_width_mean_m=width_mean,
        track_width_min_m=width_min,
        track_width_max_m=width_max,
        minimum_radius_m=metrics.min_radius,
        maximum_straight_m=metrics.max_straight,
        cones_per_boundary=cones_per_boundary,
        average_cone_spacing_m=average_spacing,
        minimum_cone_spacing_m=min_spacing,
        maximum_cone_spacing_m=max_spacing,
        collision_violations=collision_violations,
        checks=checks,
        warnings=warnings,
        passed=passed,
    )
