"""Centripetal Catmull-Rom splines for open and closed centerlines.

The curve passes through every control point. Centripetal parameterization
(alpha = 0.5) avoids the cusps uniform Catmull-Rom can form on uneven spacing.
"""

from __future__ import annotations

import math

from .math2d import Vec2, resample_polyline


def _distance(a: Vec2, b: Vec2) -> float:
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


def _segment_point(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: float, alpha: float = 0.5) -> Vec2:
    """Evaluate one centripetal Catmull-Rom segment at t in [0, 1] between p1 and p2."""

    def knot(ti: float, a: Vec2, b: Vec2) -> float:
        return ti + _distance(a, b) ** alpha

    t0 = 0.0
    t1 = knot(t0, p0, p1)
    t2 = knot(t1, p1, p2)
    t3 = knot(t2, p2, p3)
    # Degenerate control spacing collapses to the straight chord.
    if (t1 - t0) < 1e-8 or (t2 - t1) < 1e-8 or (t3 - t2) < 1e-8 or (t2 - t0) < 1e-8 or (t3 - t1) < 1e-8:
        return p1.lerp(p2, t)

    param = t1 + (t2 - t1) * t

    def lerp_at(a: Vec2, b: Vec2, ta: float, tb: float) -> Vec2:
        span = tb - ta
        if abs(span) < 1e-8:
            return a
        u = (param - ta) / span
        return a.lerp(b, u)

    a1 = lerp_at(p0, p1, t0, t1)
    a2 = lerp_at(p1, p2, t1, t2)
    a3 = lerp_at(p2, p3, t2, t3)
    b1 = lerp_at(a1, a2, t0, t2)
    b2 = lerp_at(a2, a3, t1, t3)
    return lerp_at(b1, b2, t1, t2)


def sample_catmull_rom(controls: list[Vec2], spacing: float, closed: bool) -> list[Vec2]:
    """Sample a Catmull-Rom spline through `controls` at approximately `spacing` meters."""
    if len(controls) < 2:
        return list(controls)
    if len(controls) == 2 and not closed:
        return list(controls)
    if len(controls) < 4 and not closed:
        # Not enough points for a cubic. Fall back to the polyline.
        return resample_polyline(controls, spacing, closed=False)

    count = len(controls)
    dense: list[Vec2] = []
    if closed:
        segment_count = count
        for index in range(segment_count):
            p0 = controls[(index - 1) % count]
            p1 = controls[index]
            p2 = controls[(index + 1) % count]
            p3 = controls[(index + 2) % count]
            chord = p1.distance(p2)
            steps = max(1, int(math.ceil(chord / max(spacing, 1e-3))))
            for step in range(steps):
                dense.append(_segment_point(p0, p1, p2, p3, step / steps))
    else:
        # Mirror the ends so the spline reaches the first and last control points.
        extended = [controls[0] * 2.0 - controls[1], *controls, controls[-1] * 2.0 - controls[-2]]
        for index in range(1, len(extended) - 2):
            p0 = extended[index - 1]
            p1 = extended[index]
            p2 = extended[index + 1]
            p3 = extended[index + 2]
            chord = p1.distance(p2)
            steps = max(1, int(math.ceil(chord / max(spacing, 1e-3))))
            for step in range(steps):
                dense.append(_segment_point(p0, p1, p2, p3, step / steps))
        dense.append(controls[-1])
    return resample_polyline(dense, spacing, closed)
