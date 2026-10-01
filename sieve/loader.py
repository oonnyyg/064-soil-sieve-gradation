"""Parsing of the input JSON into SampleInput objects."""

from __future__ import annotations

import json
from pathlib import Path

from .analysis import SampleInput, SieveRecord


class InputError(ValueError):
    """Raised when the input document is structurally unusable."""


def load_samples(path: Path) -> list[SampleInput]:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise InputError(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"input file is not valid JSON: {exc}") from exc

    if isinstance(document, dict) and "samples" in document:
        raw_samples = document["samples"]
    elif isinstance(document, list):
        raw_samples = document
    else:
        raise InputError('input must be a list of samples or an object with a "samples" array')

    if not isinstance(raw_samples, list) or not raw_samples:
        raise InputError('"samples" must be a non-empty array')

    samples: list[SampleInput] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_samples):
        sample = _parse_sample(raw, index + 1)
        if isinstance(sample.sample_id, str) and sample.sample_id.strip() in seen_ids:
            raise InputError(
                f"sample #{index + 1}: duplicate sample id {sample.sample_id!r}; "
                "sample identifiers must be unique"
            )
        if isinstance(sample.sample_id, str):
            seen_ids.add(sample.sample_id.strip())
        samples.append(sample)
    return samples


def _parse_sample(raw: object, ordinal: int) -> SampleInput:
    if not isinstance(raw, dict):
        raise InputError(f"sample #{ordinal}: expected an object")
    sample_id = raw.get("id", raw.get("sample_id"))
    dry_mass = raw.get("dry_mass")
    pan_mass = raw.get("pan_mass")
    raw_sieves = raw.get("sieves")
    if not isinstance(raw_sieves, list) or not raw_sieves:
        raise InputError(f"sample #{ordinal}: \"sieves\" must be a non-empty array")

    sieves: list[SieveRecord] = []
    for sieve_index, raw_sieve in enumerate(raw_sieves):
        if not isinstance(raw_sieve, dict):
            raise InputError(
                f"sample #{ordinal} sieve #{sieve_index + 1}: expected an object"
            )
        sieves.append(
            SieveRecord(
                aperture_mm=raw_sieve.get("aperture_mm"),
                retained_mass=raw_sieve.get("retained_mass"),
            )
        )

    return SampleInput(
        sample_id=sample_id if isinstance(sample_id, str) else str(sample_id),
        dry_mass=dry_mass,
        pan_mass=pan_mass,
        sieves=sieves,
    )
