"""Input loading and validation for sieve analysis data."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SieveRecord:
    """Mass retained on a single sieve."""

    aperture: float
    retained: float


@dataclass
class SampleInput:
    """One soil sample as read from the input file."""

    sample_id: str
    dry_mass: float
    sieves: list[SieveRecord]
    pan: float


@dataclass
class LoadResult:
    """Outcome of parsing the input file."""

    samples: list[SampleInput] = field(default_factory=list)
    invalid: list[dict[str, str]] = field(default_factory=list)


def _finite_non_negative(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(
        float(value)
    ) and float(value) >= 0.0


def load_input(path: str | Path) -> LoadResult:
    """Load and structurally validate the input JSON file.

    Expected schema::

        {
          "samples": [
            {
              "sample_id": "S1",
              "dry_mass": 1000.0,
              "sieves": [{"aperture": 4.75, "retained": 12.3}, ...],
              "pan": 5.0
            }
          ]
        }
    """
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    result = LoadResult()

    if not isinstance(data, dict) or not isinstance(data.get("samples"), list):
        raise ValueError("input JSON must be an object with a 'samples' array")

    seen_ids: set[str] = set()
    for index, raw in enumerate(data["samples"]):
        label = f"samples[{index}]"
        sample_id = raw.get("sample_id") if isinstance(raw, dict) else None
        if not isinstance(sample_id, str) or not sample_id.strip():
            result.invalid.append({"sample_id": f"<{label}>", "reason": "missing or empty sample_id"})
            continue
        sample_id = sample_id.strip()
        if sample_id in seen_ids:
            result.invalid.append({"sample_id": sample_id, "reason": "duplicate sample_id"})
            continue

        reason = _validate_sample(raw, label)
        if reason is not None:
            result.invalid.append({"sample_id": sample_id, "reason": reason})
            continue

        seen_ids.add(sample_id)
        result.samples.append(
            SampleInput(
                sample_id=sample_id,
                dry_mass=float(raw["dry_mass"]),
                sieves=[
                    SieveRecord(float(s["aperture"]), float(s["retained"]))
                    for s in raw["sieves"]
                ],
                pan=float(raw["pan"]),
            )
        )

    return result


def _validate_sample(raw: dict, label: str) -> str | None:
    dry = raw.get("dry_mass")
    if not _finite_non_negative(dry) or float(dry) <= 0.0:
        return "dry_mass must be a finite positive number"

    pan = raw.get("pan")
    if not _finite_non_negative(pan):
        return "pan mass must be a finite non-negative number"

    sieves = raw.get("sieves")
    if not isinstance(sieves, list) or not sieves:
        return "sieves must be a non-empty array"

    apertures: set[float] = set()
    for entry in sieves:
        if not isinstance(entry, dict):
            return "each sieve entry must be an object"
        aperture = entry.get("aperture")
        retained = entry.get("retained")
        if not isinstance(aperture, (int, float)) or isinstance(aperture, bool):
            return "sieve aperture must be a number"
        aperture = float(aperture)
        if not math.isfinite(aperture) or aperture <= 0.0:
            return "sieve aperture must be finite and greater than zero"
        if aperture in apertures:
            return f"duplicate aperture {aperture:g} mm within sample"
        if not _finite_non_negative(retained):
            return f"retained mass at {aperture:g} mm must be finite and non-negative"
        apertures.add(aperture)

    total_recovered = float(pan) + sum(float(s["retained"]) for s in sieves)
    if total_recovered <= 0.0:
        return "total recovered mass must be positive"
    if abs(total_recovered - float(dry)) > 0.01 * float(dry):
        return (
            f"mass balance error: |recovered {total_recovered:g} - dry {float(dry):g}| "
            "exceeds 1% of dry mass"
        )
    return None
