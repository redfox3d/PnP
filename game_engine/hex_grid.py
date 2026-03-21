"""Flat-top axial hex grid utilities."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Hex:
    q: int
    r: int

    @property
    def s(self) -> int:
        return -self.q - self.r

    def distance(self, other: Hex) -> int:
        return max(abs(self.q - other.q), abs(self.r - other.r), abs(self.s - other.s))

    def neighbors(self) -> List[Hex]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
        return [Hex(self.q + dq, self.r + dr) for dq, dr in dirs]

    def in_range(self, radius: int) -> List[Hex]:
        results = []
        for dq in range(-radius, radius + 1):
            rmin = max(-radius, -dq - radius)
            rmax = min(radius, -dq + radius)
            for dr in range(rmin, rmax + 1):
                results.append(Hex(self.q + dq, self.r + dr))
        return results

    def ring(self, radius: int) -> List[Hex]:
        if radius == 0:
            return [self]
        results = []
        h = Hex(self.q + radius, self.r - radius)
        dirs = [(0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0)]
        for dq, dr in dirs:
            for _ in range(radius):
                results.append(h)
                h = Hex(h.q + dq, h.r + dr)
        return results

    def line_to(self, target: Hex) -> List[Hex]:
        """All hexes on the straight line from self to target (inclusive)."""
        n = self.distance(target)
        if n == 0:
            return [self]
        results = []
        for i in range(n + 1):
            t = i / n
            results.append(_hex_round(
                self.q * (1 - t) + target.q * t,
                self.r * (1 - t) + target.r * t,
                self.s * (1 - t) + target.s * t,
            ))
        return results

    def __iter__(self):
        yield self.q
        yield self.r


def _hex_round(q: float, r: float, s: float) -> Hex:
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return Hex(int(rq), int(rr))
