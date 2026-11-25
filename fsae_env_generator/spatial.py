"""Uniform grid used to reject overlapping placements without an all-pairs loop."""

from __future__ import annotations

import math
from typing import Generic, TypeVar

from .math2d import Vec2

T = TypeVar("T")


class SpatialHash(Generic[T]):
    """2D spatial hash. Query order is sorted so results do not depend on dict order."""

    def __init__(self, cell_size: float):
        if cell_size <= 0.0:
            raise ValueError("Spatial hash cell size must be positive.")
        self.cell_size = float(cell_size)
        self._cells: dict[tuple[int, int], list[tuple[Vec2, T]]] = {}

    def _key(self, point: Vec2) -> tuple[int, int]:
        return (
            math.floor(point.x / self.cell_size),
            math.floor(point.y / self.cell_size),
        )

    def insert(self, point: Vec2, item: T) -> None:
        self._cells.setdefault(self._key(point), []).append((point, item))

    def query_radius(self, point: Vec2, radius: float) -> list[tuple[Vec2, T]]:
        if radius < 0.0:
            return []
        reach = int(math.ceil(radius / self.cell_size))
        cx, cy = self._key(point)
        found: list[tuple[Vec2, T]] = []
        radius_sq = radius * radius
        for iy in range(cy - reach, cy + reach + 1):
            for ix in range(cx - reach, cx + reach + 1):
                bucket = self._cells.get((ix, iy))
                if not bucket:
                    continue
                for other, item in bucket:
                    dx = other.x - point.x
                    dy = other.y - point.y
                    if dx * dx + dy * dy <= radius_sq:
                        found.append((other, item))
        found.sort(key=lambda pair: (pair[0].x, pair[0].y, repr(pair[1])))
        return found

    def nearest_distance(self, point: Vec2, radius: float) -> float | None:
        neighbors = self.query_radius(point, radius)
        if not neighbors:
            return None
        return min(point.distance(other) for other, _item in neighbors)

    def conflicts(self, point: Vec2, min_distance: float) -> bool:
        """True when a stored point is strictly closer than `min_distance`."""
        nearest = self.nearest_distance(point, min_distance)
        return nearest is not None and nearest < min_distance - 1e-6

    def __len__(self) -> int:
        return sum(len(bucket) for bucket in self._cells.values())
