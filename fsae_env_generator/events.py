"""2026 Formula SAE driverless event geometry.

Official numbers come from the Formula SAE Rules 2026 v1.0 and the Driverless
Cup Supplement 2026. Anything the rulebooks do not publish is stored on the
track as an assumption and is not presented as a rule.
"""

from __future__ import annotations

import math

from .config import GeneratorConfig, ResolvedLimits
from .math2d import Vec2, cumulative_lengths, dedupe_points, point_at_distance, resample_polyline

# D.9.1 Acceleration.
ACCEL_TIMED_M = 75.0
ACCEL_MIN_WIDTH_M = 4.9
ACCEL_SPACING_M = 6.0
ACCEL_STOP_MAX_M = 75.0  # DD.4.2.4

# D.10.1 Skidpad. Centerline radius is halfway between the 15.25 m and 21.25 m diameters.
SKID_CENTER_SEPARATION_M = 18.25
SKID_INNER_DIAMETER_M = 15.25
SKID_OUTER_DIAMETER_M = 21.25
SKID_PATH_WIDTH_M = 3.0
SKID_CENTERLINE_RADIUS_M = 9.125
SKID_ENTRY_M = 15.0  # DD.4.3.2, staging distance used as the entry straight
SKID_EXIT_M = 25.0  # DD.4.3.4
SKID_INNER_CONES = 17  # DD.4.3.1.b
SKID_OUTER_CONES = 13  # D.10.1.2

# DD.4.4 Autocross / trackdrive layout.
AUTOX_LENGTH = (200.0, 500.0)
AUTOX_MIN_WIDTH_M = 3.0
AUTOX_MIN_DIAMETER_M = 9.0
AUTOX_MAX_STRAIGHT_M = 80.0
AUTOX_STOP_MAX_M = 30.0  # DD.4.4.4

# DI.2.2 EBS brake test. Not a scored dynamic event.
EBS_ACCEL_MAX_M = 20.0
EBS_STOP_MAX_M = 8.5


def apply_event_defaults(config: GeneratorConfig) -> list[str]:
    """Fill official defaults and record anything the rules do not specify.

    Calling this twice is safe. A value the user already set is left alone,
    except where a rule fixes the number (the 75 m acceleration and the 3.0 m
    skidpad path).
    """
    notes: list[str] = []
    kind = config.track_type
    if kind == "acceleration":
        if abs(config.acceleration_length - ACCEL_TIMED_M) > 1e-6:
            notes.append(
                "Acceleration length was reset to 75 m. D.9.1.1 fixes the timed distance; "
                "a different length is not the 2026 event."
            )
        config.acceleration_length = ACCEL_TIMED_M
        if config.track_width < ACCEL_MIN_WIDTH_M - 1e-6:
            notes.append(
                f"Track width raised from {config.track_width:.2f} m to {ACCEL_MIN_WIDTH_M:.1f} m "
                "(D.9.1.2, minimum between the inner edges of the cone bases)."
            )
            config.track_width = ACCEL_MIN_WIDTH_M
        if abs(config.cone_spacing - 5.0) < 1e-9:
            config.cone_spacing = ACCEL_SPACING_M
            notes.append(
                "Straight cone spacing set to 6 m. D.9.1.3 says cones are spaced at intervals of approximately 6 m."
            )
        if config.stopping_zone_length <= 0.0:
            config.stopping_zone_length = ACCEL_STOP_MAX_M
    elif kind == "skidpad":
        if abs(config.track_width - SKID_PATH_WIDTH_M) > 1e-6:
            notes.append(
                f"Skidpad path width set to {SKID_PATH_WIDTH_M:.1f} m (D.10.1.1). "
                f"The requested {config.track_width:.2f} m was not used."
            )
        config.track_width = SKID_PATH_WIDTH_M
        config.allow_self_intersection = True
        if config.skidpad_entry_length <= 0.0:
            config.skidpad_entry_length = SKID_ENTRY_M
        if config.skidpad_exit_length <= 0.0:
            config.skidpad_exit_length = SKID_EXIT_M
        if config.stopping_zone_length <= 0.0:
            config.stopping_zone_length = config.skidpad_exit_length
        config.skidpad_inner_count = max(16, min(17, int(config.skidpad_inner_count or SKID_INNER_CONES)))
        if config.skidpad_inner_count != 17:
            notes.append("Driverless skidpad uses 17 inner pylons per circle (DD.4.3.1.b). The count was kept in the 16–17 range from D.10.1.2.")
        config.skidpad_inner_count = 17
        config.skidpad_outer_count = 13
    elif kind == "ebs":
        if config.track_width < ACCEL_MIN_WIDTH_M - 1e-6:
            notes.append(
                "EBS width raised to 4.9 m. DI.2.2.1 says the line is marked like Acceleration, "
                "whose minimum width is 4.9 m (D.9.1.2). The supplement does not publish a separate EBS width. "
                "This is a simulation assumption."
            )
            config.track_width = ACCEL_MIN_WIDTH_M
        if abs(config.cone_spacing - 5.0) < 1e-9:
            config.cone_spacing = ACCEL_SPACING_M
            notes.append(
                "EBS cone spacing set to about 6 m so the line matches Acceleration (D.9.1.3). DI.2.2 does not publish a separate spacing."
            )
        config.ebs_accel_length = min(max(config.ebs_accel_length, 5.0), EBS_ACCEL_MAX_M)
        config.ebs_stop_length = min(max(config.ebs_stop_length, 2.0), EBS_STOP_MAX_M)
        if config.ebs_approach_length <= 0.0:
            config.ebs_approach_length = 15.0
        if config.ebs_rest_length <= 0.0:
            config.ebs_rest_length = 10.0
        if config.stopping_zone_length <= 0.0:
            config.stopping_zone_length = config.ebs_rest_length
    elif kind in {"autocross", "trackdrive"}:
        if config.stopping_zone_length <= 0.0:
            config.stopping_zone_length = AUTOX_STOP_MAX_M
        if kind == "autocross" and config.complexity is not None:
            config.num_corners = max(6, min(24, int(round(8 + float(config.complexity) * 14))))
    return notes


def prepare_limits(config: GeneratorConfig, limits: ResolvedLimits, notes: list[str]) -> ResolvedLimits:
    """Keep an autocross lap inside the 200–500 m rule while honoring a tighter request."""
    if config.track_type != "autocross":
        return limits
    low = float(config.autocross_min_length)
    high = float(config.autocross_max_length)
    if low > high:
        low, high = high, low
    clamped_low = min(max(low, AUTOX_LENGTH[0]), AUTOX_LENGTH[1])
    clamped_high = min(max(high, clamped_low), AUTOX_LENGTH[1])
    if abs(clamped_low - low) > 1e-6 or abs(clamped_high - high) > 1e-6:
        notes.append(
            "Autocross lap length was kept inside 200–500 m (DD.4.4.1). "
            f"Requested {low:.0f}–{high:.0f} m, used {clamped_low:.0f}–{clamped_high:.0f} m."
        )
    limits.length_min = clamped_low
    limits.length_max = clamped_high
    limits.length_source = "DD.4.4.1 one-lap length, narrowed by the autocross length controls when those sit inside 200–500 m"
    return limits


def _open_line(length: float, spacing: float) -> list[Vec2]:
    raw = [Vec2(0.0, 0.0), Vec2(0.0, max(length, spacing))]
    return resample_polyline(dedupe_points(raw, closed=False), spacing, False)


def _append(path: list[Vec2], points: list[Vec2]) -> None:
    for point in points:
        if path and path[-1].distance(point) < 1e-3:
            continue
        path.append(point)


def _arc(center: Vec2, radius: float, start: float, sweep: float, steps: int) -> list[Vec2]:
    points: list[Vec2] = []
    for index in range(steps + 1):
        angle = start + sweep * (index / steps)
        points.append(Vec2(center.x + radius * math.cos(angle), center.y + radius * math.sin(angle)))
    return points


def acceleration_centerline(config: GeneratorConfig) -> tuple[list[Vec2], str, list[str]]:
    total = ACCEL_TIMED_M + max(config.stopping_zone_length, 1.0)
    points = _open_line(total, config.sample_spacing)
    notes = [
        "Timed acceleration is the first 75 m (D.9.1.1). The rest is the exit lane.",
        "Cone positions are not painted on the course (D.9.1.4). The white lines in this scene are simulation markings.",
    ]
    return points, "acceleration_straight", notes


def ebs_centerline(config: GeneratorConfig) -> tuple[list[Vec2], str, list[str]]:
    total = (
        config.ebs_approach_length
        + config.ebs_accel_length
        + config.ebs_stop_length
        + max(config.ebs_rest_length, 0.0)
    )
    points = _open_line(total, config.sample_spacing)
    notes = [
        "EBS is an inspection test (DI.2), not a scored dynamic event.",
        "The car must reach at least 40 km/h within 20 m and then stop within 8.5 m (DI.2.2.2).",
    ]
    return points, "ebs_straight", notes


def skidpad_centerline(config: GeneratorConfig) -> tuple[list[Vec2], str, list[str]]:
    """Figure eight: entry from the south, right circle clockwise, left circle counter-clockwise, exit north.

    Both circles pass through the origin. Centers are 18.25 m apart, so the
    centerline radius is 9.125 m. The procedure in D.10.2.3 is two laps on the
    right, then two on the left. The curve stores one lap of each so the cones
    are not stacked. The timed length is the second right lap plus the second left lap.
    """
    radius = SKID_CENTERLINE_RADIUS_M
    right = Vec2(radius, 0.0)
    left = Vec2(-radius, 0.0)
    entry = max(config.skidpad_entry_length, 1.0)
    exit_length = max(config.skidpad_exit_length, 1.0)
    path: list[Vec2] = []
    _append(path, [Vec2(0.0, -entry + index * 0.5) for index in range(int(entry / 0.5) + 1)])
    _append(path, [Vec2(0.0, 0.0)])
    _append(path, _arc(right, radius, math.pi, -2.0 * math.pi, 96))
    _append(path, _arc(left, radius, 0.0, 2.0 * math.pi, 96))
    _append(path, [Vec2(0.0, index * 0.5) for index in range(int(exit_length / 0.5) + 1)])
    points = resample_polyline(dedupe_points(path, closed=False), config.sample_spacing, False)
    notes = [
        "Skidpad centers are 18.25 m apart. Inner diameter 15.25 m, outer diameter 21.25 m, path width 3.0 m (D.10.1.1).",
        "Travel is one clockwise lap on the right circle, then one counter-clockwise lap on the left. "
        "D.10.2.3 drives two laps on each circle; the second of each is timed. Those extra laps retrace this curve.",
    ]
    return points, "skidpad_figure_eight", notes


def _sample_zone(track, start: float, end: float) -> list[list[float]]:
    cumulative = cumulative_lengths(track.centerline, track.closed)
    total = cumulative[-1]
    start = min(max(start, 0.0), total)
    end = min(max(end, start), total)
    if end <= start + 1e-6:
        point, _tangent, _index = point_at_distance(track.centerline, cumulative, start)
        return [[point.x, point.y, 0.0]]
    count = max(2, int((end - start) / 1.0) + 1)
    samples: list[list[float]] = []
    for index in range(count):
        station = start + (end - start) * (index / (count - 1))
        point, _tangent, _index = point_at_distance(track.centerline, cumulative, station)
        samples.append([point.x, point.y, 0.0])
    return samples


def describe_event(track, config: GeneratorConfig, notes: list[str]) -> None:
    """Attach rule citations, assumptions, gates, and the stopping zone. Does not move the centerline."""
    kind = config.track_type
    track.event_type = kind
    track.assumptions = []
    track.official_notes = list(notes)
    stop_width = config.stopping_zone_width if config.stopping_zone_width > 0.0 else config.track_width

    if kind == "acceleration":
        timed = ACCEL_TIMED_M
        stop = max(config.stopping_zone_length, 1.0)
        track.timed_length = timed
        track.gate_stations = [0.0, timed]
        track.official_notes.extend(
            [
                "D.9.1.1 timed distance is 75 m from start to finish.",
                "D.9.1.2 minimum width is 4.9 m between the inner edges of the cone bases.",
                "D.9.1.3 edge cones are spaced at approximately 6 m.",
                "DD.4.2.4 the car stops in the marked exit lane within 75 m of the finish.",
                "DD.4.2.2 staging places the foremost point of the vehicle 0.30 m behind the start. That is a vehicle position, not extra track.",
            ]
        )
        track.assumptions.append(
            "The exit lane is drawn at the 75 m maximum from DD.4.2.4. A shorter stop is legal. "
            "Large orange cones mark the start and the finish. Blue cones are on the left of travel and yellow cones on the right (DD.1.1)."
        )
        track.stopping_zone = {
            "name": "acceleration_exit",
            "start_station_m": timed,
            "end_station_m": min(timed + stop, track.length),
            "length_m": stop,
            "width_m": stop_width,
            "on_track": True,
            "rule": "DD.4.2.4",
            "samples_xyz": _sample_zone(track, timed, timed + stop),
        }
        track.event_metrics = {"timed_length_m": timed, "exit_length_m": stop, "width_m": config.track_width}
    elif kind == "skidpad":
        circumference = 2.0 * math.pi * SKID_CENTERLINE_RADIUS_M
        track.timed_length = 2.0 * circumference
        track.gate_stations = [config.skidpad_entry_length]
        track.official_notes.extend(
            [
                "D.10.1.1 two pairs of concentric circles in a figure eight. Centers 18.25 m apart.",
                "Inner diameter 15.25 m, outer diameter 21.25 m, driving path 3.0 m.",
                "D.10.1.2 and DD.4.3.1: 17 pylons inside each inner circle and 13 outside each outer circle.",
                "D.10.2.3: enter perpendicular to the figure eight, two laps on the right circle (second lap timed), "
                "then two laps on the left circle (second lap timed), then exit through the intersection in the entry direction.",
                "DD.4.3.2 staging is 15 m before the start line. DD.4.3.4 stop within 25 m after the finish in the exit lane.",
                "The start/stop line is the line between the circle centers (D.10.1.3.b).",
            ]
        )
        track.assumptions.extend(
            [
                "Assumption: cone centers are offset by half a base width so the inner face of each cone sits on the official placement circle.",
                "Assumption: pylons that would stand in the 3 m entry/exit opening are packed onto the rest of the same circle, and the count stays 17 and 13.",
                "Assumption: the right circle is clockwise and the left circle is counter-clockwise, so a car arriving from the south continues forward into the right lap.",
                "The drawn centerline contains one lap of each circle. The lap sequence right, right, left, left retraces those laps.",
            ]
        )
        exit_start = config.skidpad_entry_length + 2.0 * circumference
        track.stopping_zone = {
            "name": "skidpad_exit",
            "start_station_m": exit_start,
            "end_station_m": track.length,
            "length_m": config.skidpad_exit_length,
            "width_m": SKID_PATH_WIDTH_M,
            "on_track": True,
            "rule": "DD.4.3.4",
            "samples_xyz": _sample_zone(track, max(track.length - config.skidpad_exit_length, 0.0), track.length),
        }
        track.event_metrics = {
            "center_separation_m": SKID_CENTER_SEPARATION_M,
            "inner_diameter_m": SKID_INNER_DIAMETER_M,
            "outer_diameter_m": SKID_OUTER_DIAMETER_M,
            "centerline_radius_m": SKID_CENTERLINE_RADIUS_M,
            "path_width_m": SKID_PATH_WIDTH_M,
            "entry_length_m": config.skidpad_entry_length,
            "exit_length_m": config.skidpad_exit_length,
            "inner_cones_per_circle": 17,
            "outer_cones_per_circle": 13,
            "lap_sequence": ["right", "right", "left", "left"],
            "laps_drawn": ["right", "left"],
            "timed_length_m": track.timed_length,
            "right_center_xy": [SKID_CENTERLINE_RADIUS_M, 0.0],
            "left_center_xy": [-SKID_CENTERLINE_RADIUS_M, 0.0],
        }
    elif kind == "ebs":
        approach = config.ebs_approach_length
        accel = config.ebs_accel_length
        stop = config.ebs_stop_length
        rest = config.ebs_rest_length
        trigger = approach + accel
        track.timed_length = stop
        track.gate_stations = [approach, trigger]
        track.official_notes.extend(
            [
                "DI.2.2.1 the EBS test is a straight line marked with cones, similar to Acceleration.",
                "DI.2.2.2 accelerate in Driverless Mode to at least 40 km/h in 20 m or less.",
                "DI.2.2.2 a Remote Stop is triggered at a specific point, then the car stops safely in 8.5 m or less.",
                "EBS is technical inspection (DI.2), not a scored dynamic event.",
            ]
        )
        track.assumptions.extend(
            [
                f"Assumption: the approach before the measured {accel:.1f} m acceleration zone is {approach:.1f} m. The rules do not publish this length.",
                "Assumption: the Remote Stop 'specific point' is the end of the acceleration zone. The rules require a specific point but do not publish its coordinate.",
                f"Assumption: an extra {rest:.1f} m rest corridor is drawn after the {stop:.1f} m emergency-stop region. The rules stop at 8.5 m.",
                "Assumption: the corridor width matches the Acceleration minimum of 4.9 m because DI.2.2.1 says the line is similar and does not give another width.",
            ]
        )
        track.stopping_zone = {
            "name": "ebs_emergency_stop",
            "start_station_m": trigger,
            "end_station_m": trigger + stop,
            "length_m": stop,
            "width_m": stop_width,
            "on_track": True,
            "rule": "DI.2.2.2 maximum 8.5 m",
            "samples_xyz": _sample_zone(track, trigger, trigger + stop),
        }
        track.event_metrics = {
            "approach_length_m": approach,
            "accel_length_m": accel,
            "trigger_station_m": trigger,
            "emergency_stop_length_m": stop,
            "rest_length_m": rest,
            "supplementary": True,
            "scored_event": False,
        }
    else:
        stop = min(max(config.stopping_zone_length, 1.0), AUTOX_STOP_MAX_M, track.length)
        track.timed_length = track.length
        track.gate_stations = [0.0]
        track.official_notes.extend(
            [
                "DD.4.4.1 driverless autocross: straights no longer than 80 m, minimum width 3 m, "
                "minimum turning diameter 9 m, one lap 200–500 m. The length is the centerline arc length.",
                "DD.4.4.3 staging places the front wheels 6 m behind the start. That is a vehicle position, not extra track.",
                "DD.4.4.4 the car stops in 30 m or less on the track after the finish.",
                "IC autocross D.11 is not used. Its 0.80 km lap and 3.5 m width belong to the combustion event.",
            ]
        )
        track.assumptions.extend(
            [
                "Assumption: corner count, S-curve, chicane, hairpin, and slalom frequencies are simulation controls. DD.4.4.1 allows those features but does not set their rates.",
                "Assumption: the stopping zone is the first meters of the lap after the finish line, on the same centerline, because DD.4.4.4 says the stop is on the track.",
                "Assumption: large orange cones mark the combined start/finish line. A closed lap has one timing line.",
            ]
        )
        if config.track_width_variation > 0.0:
            track.assumptions.append(
                "Assumption: track width varies along the lap. DD.4.4.1 sets a 3 m minimum and does not require a constant width."
            )
        track.stopping_zone = {
            "name": "autocross_stop_on_track",
            "start_station_m": 0.0,
            "end_station_m": stop,
            "length_m": stop,
            "width_m": stop_width,
            "on_track": True,
            "rule": "DD.4.4.4",
            "samples_xyz": _sample_zone(track, 0.0, stop),
        }
        track.event_metrics = {
            "lap_length_m": track.length,
            "length_is_arc": True,
            "stopping_zone_length_m": stop,
            "min_width_m": AUTOX_MIN_WIDTH_M,
            "min_turning_diameter_m": AUTOX_MIN_DIAMETER_M,
            "max_straight_m": AUTOX_MAX_STRAIGHT_M,
        }
