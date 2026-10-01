"""Built-in self tests, run with: python -m sieve --selftest"""

from __future__ import annotations

import math

from .analysis import SampleInput, SieveRecord, analyze_sample, interpolate_size
from .analysis import CurvePoint


def _sample(
    sample_id: str,
    dry_mass: float,
    pan_mass: float,
    pairs: list[tuple[float, float]],
) -> SampleInput:
    return SampleInput(
        sample_id=sample_id,
        dry_mass=dry_mass,
        pan_mass=pan_mass,
        sieves=[SieveRecord(aperture_mm=a, retained_mass=m) for a, m in pairs],
    )


def _assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def run_selftest() -> int:
    # 1. Valid sample, arbitrary input order; check normalization and sizes.
    result = analyze_sample(
        _sample(
            "S-valid",
            1000.0,
            0.0,
            [(2.0, 250), (0.075, 250), (0.5, 250), (0.25, 250)],
        )
    )
    assert result.valid, result.errors
    assert [point.aperture_mm for point in result.curve] == [0.075, 0.25, 0.5, 2.0]
    _assert_close(result.curve[0].percent_passing, 0.0, "passing@0.075")
    _assert_close(result.curve[1].percent_passing, 25.0, "passing@0.25")
    _assert_close(result.curve[3].percent_passing, 75.0, "passing@2.0")
    _assert_close(result.characteristic_sizes["D10"], 0.1213983437, "D10")
    _assert_close(result.characteristic_sizes["D30"], 0.2871745887, "D30")
    _assert_close(result.characteristic_sizes["D60"], 0.8705505633, "D60")
    _assert_close(result.cu, 0.8705505633 / 0.1213983437, "Cu")
    _assert_close(
        result.cc,
        0.2871745887 ** 2 / (0.1213983437 * 0.8705505633),
        "Cc",
    )

    # 2. Normalization uses recovered mass; slight recovery drift is allowed.
    drifted = analyze_sample(_sample("S-drift", 1005.0, 5.0, [(1.0, 995.0)]))
    assert drifted.valid, drifted.errors
    _assert_close(drifted.curve[0].percent_passing, 5.0 / 1000.0 * 100, "drift passing")

    # 3. Recovery beyond 1% of dry mass invalidates the sample.
    bad_recovery = analyze_sample(_sample("S-recovery", 1000.0, 0.0, [(1.0, 900.0)]))
    assert not bad_recovery.valid and bad_recovery.errors, "recovery check must fail"

    # 4. Duplicate aperture invalidates the sample.
    dup = analyze_sample(_sample("S-dup", 100.0, 0.0, [(1.0, 50.0), (1.0, 50.0)]))
    assert not dup.valid and any("duplicate" in e for e in dup.errors)

    # 5. Non-positive aperture / negative mass / non-positive dry mass.
    bad_values = analyze_sample(
        _sample("S-bad", 0.0, -1.0, [(0.0, 10.0), (1.0, -5.0)])
    )
    assert not bad_values.valid and len(bad_values.errors) >= 3

    # 6. Exact hit returns the node; ties pick the smallest aperture.
    tie = analyze_sample(
        _sample("S-tie", 1000.0, 0.0, [(0.1, 400.0), (0.5, 200.0), (2.0, 400.0), (4.0, 0.0)])
    )
    assert tie.valid, tie.errors
    _assert_close(tie.characteristic_sizes["D60"], 2.0, "D60 exact tie -> smallest")

    # 7. Target outside measured passing range: null with note, no extrapolation.
    coarse = analyze_sample(_sample("S-coarse", 1000.0, 200.0, [(2.0, 800.0)]))
    assert coarse.valid, coarse.errors
    assert coarse.characteristic_sizes["D10"] is None
    assert "D10" in coarse.size_notes
    assert coarse.characteristic_sizes["D60"] is None
    assert coarse.cu is None and coarse.cc is None

    # 8. Unit-level interpolation sanity on a two-node curve.
    d, note = interpolate_size(
        50.0,
        [CurvePoint(1.0, 0.0, 0.0), CurvePoint(10.0, 0.0, 100.0)],
    )
    assert note is None
    _assert_close(d, math.sqrt(10.0), "log midpoint")

    print("self-test passed: 8 checks")
    return 0
