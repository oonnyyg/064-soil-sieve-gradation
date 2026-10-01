"""Gradation curve and characteristic particle size computation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .loading import SampleInput


@dataclass
class CurvePoint:
    aperture: float
    percent_passing: float


@dataclass
class CharacteristicSize:
    name: str
    percent: float
    diameter: float | None
    note: str = ""


def build_curve(sample: SampleInput) -> tuple[list[CurvePoint], float]:
    """Return curve points sorted by ascending aperture and recovered total.

    Percent passing at an aperture equals the combined mass retained on all
    strictly smaller sieves plus the pan, divided by the recovered total.
    The pan is not emitted as a zero-aperture curve point.
    """
    ordered = sorted(sample.sieves, key=lambda s: s.aperture)
    total = sample.pan + sum(s.retained for s in ordered)
    points: list[CurvePoint] = []
    finer_mass = sample.pan
    for record in ordered:
        percent = finer_mass / total * 100.0
        points.append(CurvePoint(record.aperture, percent))
        finer_mass += record.retained
    return points, total


def characteristic_size(points: list[CurvePoint], name: str, percent: float) -> CharacteristicSize:
    """Interpolate D for a target percent passing.

    Percent passing is linear and log(aperture) is linear between adjacent
    nodes. An exact node hit returns the smallest matching aperture; without a
    bracketing interval the result is null and no extrapolation is performed.
    """
    exact = [p.aperture for p in points if math.isclose(p.percent_passing, percent, abs_tol=1e-9)]
    if exact:
        return CharacteristicSize(name, percent, min(exact))

    for lower, upper in zip(points, points[1:]):
        p_low, p_high = lower.percent_passing, upper.percent_passing
        if min(p_low, p_high) < percent < max(p_low, p_high):
            fraction = (percent - p_low) / (p_high - p_low)
            log_d = math.log(lower.aperture) + fraction * (
                math.log(upper.aperture) - math.log(lower.aperture)
            )
            return CharacteristicSize(name, percent, math.exp(log_d))

    return CharacteristicSize(
        name,
        percent,
        None,
        "target percent passing not bracketed by curve nodes; no extrapolation",
    )


def analyze_sample(sample: SampleInput) -> dict:
    """Produce the full report object for one validated sample."""
    points, total = build_curve(sample)
    d10 = characteristic_size(points, "D10", 10.0)
    d30 = characteristic_size(points, "D30", 30.0)
    d60 = characteristic_size(points, "D60", 60.0)

    cu = d60.diameter / d10.diameter if d10.diameter and d60.diameter else None
    if cu is not None and d30.diameter is not None and d10.diameter and d60.diameter:
        cc = d30.diameter**2 / (d10.diameter * d60.diameter)
    else:
        cc = None

    return {
        "sample_id": sample.sample_id,
        "dry_mass": sample.dry_mass,
        "recovered_mass": total,
        "mass_balance_error_percent": abs(total - sample.dry_mass) / sample.dry_mass * 100.0,
        "curve": [
            {"aperture_mm": p.aperture, "percent_passing": p.percent_passing} for p in points
        ],
        "characteristic_sizes": {
            "D10": _size_entry(d10),
            "D30": _size_entry(d30),
            "D60": _size_entry(d60),
        },
        "coefficients": {
            "Cu": cu,
            "Cc": cc,
            "note": "null when any required characteristic size is unavailable",
        },
    }


def _size_entry(size: CharacteristicSize) -> dict:
    entry = {"diameter_mm": size.diameter}
    if size.note:
        entry["note"] = size.note
    return entry
