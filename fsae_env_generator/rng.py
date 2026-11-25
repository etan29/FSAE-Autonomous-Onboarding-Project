"""Central seeded random stream.

Every randomized decision in the generator goes through this class or through a
named child stream derived from it. Do not call `random` directly elsewhere.
Child streams are keyed by name and the parent seed, so one subsystem does not
change another subsystem's numbers if call order shifts.
"""

from __future__ import annotations

import hashlib
import random
from typing import Sequence, TypeVar

T = TypeVar("T")


class SeededRNG:
    """Deterministic wrapper around `random.Random` for one generation run."""

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._random = random.Random(self.seed)

    def child(self, name: str) -> "SeededRNG":
        """Return an independent stream for a named subsystem."""
        digest = hashlib.sha256(f"{self.seed}:{name}".encode("utf-8")).digest()
        # Stay inside the range Random accepts on every supported Python build.
        subseed = int.from_bytes(digest[:8], "big") % (2**31 - 1)
        return SeededRNG(subseed)

    def random(self) -> float:
        return self._random.random()

    def uniform(self, a: float, b: float) -> float:
        return self._random.uniform(a, b)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def choice(self, options: Sequence[T]) -> T:
        if not options:
            raise ValueError("Cannot choose from an empty sequence.")
        return self._random.choice(list(options))

    def shuffle(self, values: list[T]) -> None:
        self._random.shuffle(values)
