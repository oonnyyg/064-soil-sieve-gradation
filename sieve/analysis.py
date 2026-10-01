"""Core validation and gradation calculations for one sample.

Percent passing uses the recovered total mass for normalization. For a
given sieve (sorted by ascending aperture) the passing mass is the sum
of masses retained on all smaller sieves plus the pan.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

RECOVERY_TOLERANCE = 0.01  # |recovered - dry| must not exceed 1% of dry


@dataclass
class SieveRecord:
    aperture_mm: float
    retained_mass: float


@dataclass
class SampleInput:
    sample_id: str
    dry_mass: float
    pan_mass: float
    sieves: list[SieveRecord]


@dataclass
class CurvePoint:
    aperture_mm: float
    retained_mass: float
    percent_passing: float


@dataclass
class SampleResult:
    sample_id: str
    valid: bool = False
    errors: list[str] = field(default_factory=list)
    dry_mass: float | None = None
    recovered_mass: float | None = None
    recovery_ratio: float | None = None
    curve: list[CurvePoint] = field(default_factory=list)
    characteristic_sizes: dict[str, float | None] = field(
        default_factory=lambda: {"D10": None, "D30": None, "D60": None}
    )
    size_notes: dict[str, str] = field(default_factory=dict)
    cu: float | None = None
    cc: float | None = None


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def interpolate_size(
    target_percent: float,
    curve: list[CurvePoint],
) -> tuple[float | None, str | None]:
    """Return (aperture, note).

    Interpolation is linear in percent passing (linear axis) against the
    logarithm of aperture (log axis), between adjacent curve nodes.
    An exact hit returns the smallest matching aperture. No extrapolation
    is performed outside the bracketing node range.
    """
    if not curve:
        return None, "no sieve data"

    # curve is ascending in aperture -> percent passing is non-decreasing.
    for point in curve:  # ascending: first hit is the smallest aperture
        if math.isclose(point.percent_passing, target_percent, rel_tol=0.0, abs_tol=1e-12):
            return point.aperture_mm, "exact node"

    passing_values = [point.percent_passing for point in curve]
    min_passing = passing_values[0]
    max_passing = passing_values[-1]
    if target_percent > max_passing or target_percent < min_passing:
        return None, (
            f"target {target_percent:g}% lies outside the measured passing "
            f"range ({min_passing:.6g}% to {max_passing:.6g}%); no extrapolation"
        )

    # Find the adjacent pair that brackets the target.
    for smaller, larger in zip(curve, curve[1:]):
        p_small = smaller.percent_passing
        p_large = larger.percent_passing
        if p_small < target_percent < p_large:
            fraction = (target_percent - p_small) / (p_large - p_small)
            log_d = math.log(smaller.aperture_mm) + fraction * (
                math.log(larger.aperture_mm) - math.log(smaller.aperture_mm)
            )
            return math.exp(log_d), None
    return None, "no bracketing interval found"


def analyze_sample(sample: SampleInput) -> SampleResult:
    """Validate one sample and compute its gradation curve and sizes."""
    result = SampleResult(sample_id=sample.sample_id)
    errors: list[str] = []

    if not isinstance(sample.sample_id, str) or not sample.sample_id.strip():
        errors.append("sample id must be a non-empty string")
    if not _finite_number(sample.dry_mass) or sample.dry_mass <= 0:
        errors.append("dry mass (送样干质量) must be a finite positive number")
    if not _finite_number(sample.pan_mass) or sample.pan_mass < 0:
        errors.append("pan mass (底盘质量) must be a finite non-negative number")

    if not isinstance(sample.sieves, list) or not sample.sieves:
        errors.append("at least one sieve record is required")
        sample.sieves = []

    seen_apertures: set[float] = set()
    valid_sieves: list[SieveRecord] = []
    for index, record in enumerate(sample.sieves):
        if not isinstance(record, SieveRecord):
            errors.append(f"sieve #{index + 1}: malformed record")
            continue
        if not _finite_number(record.aperture_mm) or record.aperture_mm <= 0:
            errors.append(
                f"sieve #{index + 1}: aperture {record.aperture_mm!r} must be finite and > 0 mm"
            )
            continue
        if not _finite_number(record.retained_mass) or record.retained_mass < 0:
            errors.append(
                f"sieve #{index + 1} ({record.aperture_mm:g} mm): retained mass "
                f"{record.retained_mass!r} must be finite and non-negative"
            )
            continue
        if record.aperture_mm in seen_apertures:
            errors.append(f"duplicate aperture {record.aperture_mm:g} mm in sample")
            continue
        seen_apertures.add(record.aperture_mm)
        valid_sieves.append(record)

    if errors:
        result.errors = errors
        return result

    ordered = sorted(valid_sieves, key=lambda item: item.aperture_mm)
    recovered = sample.pan_mass + sum(item.retained_mass for item in ordered)
    result.dry_mass = sample.dry_mass
    result.recovered_mass = recovered

    if recovered <= 0:
        result.errors = ["recovered total mass (回收总质量) must be positive"]
        return result

    recovery_ratio = recovered / sample.dry_mass
    result.recovery_ratio = recovery_ratio
    if abs(recovered - sample.dry_mass) > RECOVERY_TOLERANCE * sample.dry_mass:
        result.errors = [
            f"mass recovery check failed: |{recovered:g} - {sample.dry_mass:g}| "
            f"exceeds 1% of dry mass (recovery ratio {recovery_ratio:.6g})"
        ]
        return result

    # Passing mass at each sieve = pan + all smaller sieve retained masses.
    curve: list[CurvePoint] = []
    smaller_mass = sample.pan_mass
    for record in ordered:
        percent_passing = smaller_mass / recovered * 100.0
        curve.append(
            CurvePoint(
                aperture_mm=record.aperture_mm,
                retained_mass=record.retained_mass,
                percent_passing=percent_passing,
            )
        )
        smaller_mass += record.retained_mass
    result.curve = curve

    for name, target in (("D10", 10.0), ("D30", 30.0), ("D60", 60.0)):
        size, note = interpolate_size(target, curve)
        result.characteristic_sizes[name] = size
        if note:
            result.size_notes[name] = note

    d10 = result.characteristic_sizes["D10"]
    d30 = result.characteristic_sizes["D30"]
    d60 = result.characteristic_sizes["D60"]
    if d10 is not None and d60 is not None and d10 > 0:
        result.cu = d60 / d10
    else:
        result.size_notes["Cu"] = "Cu not computed: D10 or D60 is missing"
    if d10 is not None and d30 is not None and d60 is not None and d10 > 0 and d60 > 0:
        result.cc = d30 * d30 / (d10 * d60)
    else:
        result.size_notes["Cc"] = "Cc not computed: D10, D30 or D60 is missing"

    result.valid = True
    return result
