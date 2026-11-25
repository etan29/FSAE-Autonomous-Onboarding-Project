"""2D geometry helpers. Lengths are meters and angles are radians."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Vec2:
    """A point or vector in the ground plane."""

    x: float
    y: float

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scale: float) -> "Vec2":
        return Vec2(self.x * scale, self.y * scale)

    def __rmul__(self, scale: float) -> "Vec2":
        return self.__mul__(scale)

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vec2") -> float:
        """Z component of the 3D cross product. Positive means `other` is left of self."""
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def distance(self, other: "Vec2") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def normalized(self) -> "Vec2":
        length = self.length()
        if length < 1e-12:
            return Vec2(0.0, 0.0)
        return Vec2(self.x / length, self.y / length)

    def left_normal(self) -> "Vec2":
        """Unit normal 90 degrees counter-clockwise (left of the direction of travel)."""
        return Vec2(-self.y, self.x).normalized()

    def lerp(self, other: "Vec2", t: float) -> "Vec2":
        return Vec2(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)

    def rotated(self, angle: float) -> "Vec2":
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return Vec2(self.x * cos_a - self.y * sin_a, self.x * sin_a + self.y * cos_a)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def signed_area(points: list[Vec2]) -> float:
    """Positive area means the ring is counter-clockwise."""
    area = 0.0
    count = len(points)
    for index in range(count):
        nxt = points[(index + 1) % count]
        area += points[index].x * nxt.y - nxt.x * points[index].y
    return 0.5 * area


def ensure_ccw(points: list[Vec2]) -> list[Vec2]:
    if signed_area(points) < 0.0:
        return list(reversed(points))
    return list(points)


def centroid(points: list[Vec2]) -> Vec2:
    if not points:
        return Vec2(0.0, 0.0)
    inv = 1.0 / len(points)
    return Vec2(sum(point.x for point in points) * inv, sum(point.y for point in points) * inv)


def rotate_around(points: list[Vec2], origin: Vec2, angle: float) -> list[Vec2]:
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rotated = []
    for point in points:
        offset = point - origin
        rotated.append(
            Vec2(
                origin.x + offset.x * cos_a - offset.y * sin_a,
                origin.y + offset.x * sin_a + offset.y * cos_a,
            )
        )
    return rotated


def scale_around(points: list[Vec2], origin: Vec2, factor: float) -> list[Vec2]:
    return [origin + (point - origin) * factor for point in points]


def bounding_box(points: list[Vec2]) -> tuple[float, float, float, float]:
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def is_convex_ccw(points: list[Vec2], epsilon: float = 1e-8) -> bool:
    count = len(points)
    if count < 3:
        return False
    for index in range(count):
        a = points[index]
        b = points[(index + 1) % count]
        c = points[(index + 2) % count]
        cross = (b - a).cross(c - b)
        if cross < -epsilon:
            return False
    return True


def cumulative_lengths(points: list[Vec2], closed: bool) -> list[float]:
    """Arc-length prefix sums. The final entry is the total length.

    For a closed ring the last segment returns from the last point to the first.
    `cumulative[i]` is the distance along the polyline at `points[i]`.
    """
    count = len(points)
    if count == 0:
        return [0.0]
    cumulative = [0.0]
    segments = count if closed else count - 1
    for index in range(segments):
        nxt = points[(index + 1) % count]
        cumulative.append(cumulative[-1] + points[index].distance(nxt))
    return cumulative


def polyline_length(points: list[Vec2], closed: bool) -> float:
    return cumulative_lengths(points, closed)[-1]


def point_at_distance(points: list[Vec2], cumulative: list[float], distance: float) -> tuple[Vec2, Vec2, int]:
    """Interpolate a polyline at an arc-length distance.

    Returns the point, the unit tangent of the segment that contains it, and the
    segment start index. `cumulative` must come from `cumulative_lengths`.

    A closed ring has one more cumulative entry than an open chain (`n + 1`
    versus `n`), which is how this function tells them apart. Closed distances
    wrap. Open distances clamp to the ends.
    """
    count = len(points)
    if count == 0:
        raise ValueError("Cannot sample an empty polyline.")
    total = cumulative[-1]
    if total <= 1e-12:
        return points[0], Vec2(1.0, 0.0), 0
    closed = len(cumulative) == count + 1
    if closed:
        distance = distance % total
    else:
        distance = min(max(distance, 0.0), total)
    segments = len(cumulative) - 1
    low = 0
    high = segments - 1
    while low < high:
        mid = (low + high) // 2
        if cumulative[mid + 1] < distance:
            low = mid + 1
        else:
            high = mid
    start_index = low
    seg_start = cumulative[start_index]
    seg_end = cumulative[start_index + 1]
    a = points[start_index]
    b = points[(start_index + 1) % count]
    span = seg_end - seg_start
    t = 0.0 if span < 1e-12 else (distance - seg_start) / span
    t = clamp(t, 0.0, 1.0)
    tangent = (b - a).normalized()
    if tangent.length() < 1e-12:
        tangent = Vec2(1.0, 0.0)
    return a.lerp(b, t), tangent, start_index


def resample_polyline(points: list[Vec2], spacing: float, closed: bool) -> list[Vec2]:
    """Evenly resample by arc length. Closed rings do not repeat the first point."""
    if len(points) < 2:
        return list(points)
    cumulative = cumulative_lengths(points, closed)
    total = cumulative[-1]
    if total < 1e-8:
        return [points[0]]
    if closed:
        count = max(4, int(round(total / spacing)))
        step = total / count
        return [point_at_distance(points, cumulative, index * step)[0] for index in range(count)]
    count = max(2, int(math.ceil(total / spacing)) + 1)
    step = total / (count - 1)
    return [point_at_distance(points, cumulative, index * step)[0] for index in range(count)]


def dedupe_points(points: list[Vec2], epsilon: float = 1e-8, closed: bool = True) -> list[Vec2]:
    if not points:
        return []
    unique = [points[0]]
    for point in points[1:]:
        if point.distance(unique[-1]) > epsilon:
            unique.append(point)
    if closed and len(unique) > 1 and unique[0].distance(unique[-1]) <= epsilon:
        unique.pop()
    return unique


def menger_curvature(a: Vec2, b: Vec2, c: Vec2) -> float:
    """Signed curvature of the circumcircle through three points.

    Positive curvature bends left. Radius is `1 / curvature` when curvature is non-zero.
    """
    ab = a.distance(b)
    bc = b.distance(c)
    ca = c.distance(a)
    denominator = ab * bc * ca
    if denominator < 1e-12:
        return 0.0
    # Twice the signed triangle area, which is the z component of AB × AC.
    area2 = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
    return (2.0 * area2) / denominator


def curvatures(points: list[Vec2], closed: bool) -> list[float]:
    """Local curvature from the previous and next sample.

    This is the right input for cone spacing, because a corner should tighten
    the gap even when a longer window is used for the official turning radius.
    """
    count = len(points)
    if count < 3:
        return [0.0 for _ in points]
    values = []
    for index in range(count):
        if not closed and (index == 0 or index == count - 1):
            values.append(0.0)
            continue
        previous = points[(index - 1) % count]
        nxt = points[(index + 1) % count]
        values.append(menger_curvature(previous, points[index], nxt))
    return values


def _index_offset(points: list[Vec2], start: int, signed_distance: float, closed: bool) -> int:
    """Walk `signed_distance` meters along the polyline and return that sample index."""
    direction = 1 if signed_distance >= 0.0 else -1
    remaining = abs(signed_distance)
    index = start
    count = len(points)
    for _ in range(count):
        nxt = index + direction
        if closed:
            nxt %= count
        elif nxt < 0 or nxt >= count:
            return index
        remaining -= points[index].distance(points[nxt])
        index = nxt
        if remaining <= 0.0:
            return index
    return index


def curvatures_over_window(points: list[Vec2], closed: bool, window_m: float = 2.0) -> list[float]:
    """Curvature using samples about `window_m` away on each side.

    A single fillet join can look tighter than the real arc when curvature is
    taken from the two neighboring 0.5 m samples. The competition turning
    diameter is a property of the path over a few meters, so the check uses
    this wider stencil. Points that actually lie on a circular arc still
    report that arc's radius.
    """
    count = len(points)
    if count < 3:
        return [0.0 for _ in points]
    values = []
    for index in range(count):
        if not closed and (index == 0 or index == count - 1):
            values.append(0.0)
            continue
        previous = _index_offset(points, index, -window_m, closed)
        nxt = _index_offset(points, index, window_m, closed)
        if previous == index or nxt == index or previous == nxt:
            values.append(0.0)
        else:
            values.append(menger_curvature(points[previous], points[index], points[nxt]))
    return values


def tangents_and_normals(points: list[Vec2], closed: bool) -> tuple[list[Vec2], list[Vec2]]:
    """Unit travel direction and the left normal at every sample."""
    count = len(points)
    tangents: list[Vec2] = []
    normals: list[Vec2] = []
    for index in range(count):
        if closed:
            previous = points[(index - 1) % count]
            nxt = points[(index + 1) % count]
            tangent = (nxt - previous).normalized()
        elif index == 0:
            tangent = (points[1] - points[0]).normalized()
        elif index == count - 1:
            tangent = (points[-1] - points[-2]).normalized()
        else:
            tangent = (points[index + 1] - points[index - 1]).normalized()
        if tangent.length() < 1e-12:
            tangent = Vec2(1.0, 0.0)
        tangents.append(tangent)
        normals.append(tangent.left_normal())
    return tangents, normals


def distance_to_segment(point: Vec2, a: Vec2, b: Vec2) -> float:
    ab = b - a
    length_sq = ab.dot(ab)
    if length_sq < 1e-12:
        return point.distance(a)
    t = clamp((point - a).dot(ab) / length_sq, 0.0, 1.0)
    closest = a + ab * t
    return point.distance(closest)


def min_distance_to_polyline(point: Vec2, points: list[Vec2], closed: bool) -> float:
    count = len(points)
    if count == 0:
        return float("inf")
    if count == 1:
        return point.distance(points[0])
    segments = count if closed else count - 1
    best = float("inf")
    for index in range(segments):
        dist = distance_to_segment(point, points[index], points[(index + 1) % count])
        if dist < best:
            best = dist
    return best


def segments_properly_intersect(a: Vec2, b: Vec2, c: Vec2, d: Vec2, epsilon: float = 1e-9) -> bool:
    """True when open segments AB and CD cross. Shared endpoints and overlaps do not count."""

    def orient(p: Vec2, q: Vec2, r: Vec2) -> float:
        return (q - p).cross(r - p)

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if abs(o1) <= epsilon or abs(o2) <= epsilon or abs(o3) <= epsilon or abs(o4) <= epsilon:
        return False
    return (o1 > 0.0) != (o2 > 0.0) and (o3 > 0.0) != (o4 > 0.0)


def polyline_self_intersects(points: list[Vec2], closed: bool) -> bool:
    """Proper intersection of non-adjacent segments. Neighboring segments are ignored."""
    count = len(points)
    segments = count if closed else count - 1
    if segments < 4:
        return False
    boxes = []
    for index in range(segments):
        a = points[index]
        b = points[(index + 1) % count]
        boxes.append(
            (
                a,
                b,
                min(a.x, b.x),
                max(a.x, b.x),
                min(a.y, b.y),
                max(a.y, b.y),
            )
        )
    for i in range(segments):
        a, b, ax0, ax1, ay0, ay1 = boxes[i]
        # Start at i+2 so the next segment, which shares a vertex, is skipped.
        for j in range(i + 2, segments):
            if closed and i == 0 and j == segments - 1:
                continue
            c, d, bx0, bx1, by0, by1 = boxes[j]
            if ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0:
                continue
            if segments_properly_intersect(a, b, c, d):
                return True
    return False


def straight_segment_lengths(
    points: list[Vec2],
    curvature: list[float],
    closed: bool,
    straight_radius: float,
) -> list[float]:
    """Lengths of runs whose curvature is gentler than `1 / straight_radius`."""
    count = len(points)
    if count < 2:
        return []
    threshold = 1.0 / straight_radius if straight_radius > 1e-6 else 0.0
    segments = count if closed else count - 1
    gentle = []
    for index in range(segments):
        nxt = (index + 1) % count
        gentle.append(abs(curvature[index]) <= threshold and abs(curvature[nxt]) <= threshold)

    if closed and any(gentle) and all(gentle):
        return [polyline_length(points, True)]

    # Unfold a wrapped run by rotating the start onto a non-straight segment.
    offset = 0
    if closed and gentle[0] and gentle[-1]:
        for index, flag in enumerate(gentle):
            if not flag:
                offset = (index + 1) % segments
                break
        gentle = gentle[offset:] + gentle[:offset]

    lengths: list[float] = []
    run = 0.0
    for index, flag in enumerate(gentle):
        source = (index + offset) % segments
        if flag:
            a = points[source]
            b = points[(source + 1) % count]
            run += a.distance(b)
        elif run > 0.0:
            lengths.append(run)
            run = 0.0
    if run > 0.0:
        lengths.append(run)
    return lengths


def min_radius(curvature: list[float]) -> float:
    peak = 0.0
    for value in curvature:
        peak = max(peak, abs(value))
    if peak < 1e-8:
        return float("inf")
    return 1.0 / peak


def largest_gap_index_window(sample_spacing: float, ignore_distance: float) -> int:
    if sample_spacing <= 1e-6:
        return 1
    return max(2, int(math.ceil(ignore_distance / sample_spacing)))


def has_near_approach(
    points: list[Vec2],
    min_distance: float,
    index_window: int,
    closed: bool,
) -> bool:
    """True if samples that are far apart along the path get closer than `min_distance`."""
    count = len(points)
    if count < 4:
        return False
    # Stride keeps the check inexpensive. Half-spacing still catches a ribbon overlap.
    stride = 1
    for i in range(0, count, stride):
        j = i + index_window
        end = count if not closed else count
        while j < end:
            wrap = closed and (i + count - j) < index_window
            if not wrap and points[i].distance(points[j]) < min_distance:
                return True
            j += stride
    return False
