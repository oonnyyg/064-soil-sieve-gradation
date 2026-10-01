"""JSON/CSV serialization of analysis results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .analysis import SampleResult


def build_report(results: list[SampleResult]) -> dict:
    valid_count = sum(1 for item in results if item.valid)
    return {
        "sample_count": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "samples": [_sample_payload(item) for item in results],
    }


def _sample_payload(result: SampleResult) -> dict:
    payload = {
        "sample_id": result.sample_id,
        "valid": result.valid,
    }
    if not result.valid:
        payload["errors"] = list(result.errors)
        return payload
    payload.update(
        {
            "dry_mass": result.dry_mass,
            "recovered_mass": result.recovered_mass,
            "recovery_ratio": result.recovery_ratio,
            "curve": [
                {
                    "aperture_mm": point.aperture_mm,
                    "retained_mass": point.retained_mass,
                    "percent_passing": point.percent_passing,
                }
                for point in result.curve
            ],
            "characteristic_sizes": dict(result.characteristic_sizes),
            "size_notes": dict(result.size_notes),
            "Cu": result.cu,
            "Cc": result.cc,
        }
    )
    return payload


def write_report_json(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_curves_csv(results: list[SampleResult], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["sample_id", "aperture_mm", "retained_mass", "percent_passing"]
        )
        for result in results:
            if not result.valid:
                continue
            for point in result.curve:
                writer.writerow(
                    [
                        result.sample_id,
                        _fmt(point.aperture_mm),
                        _fmt(point.retained_mass),
                        _fmt(point.percent_passing),
                    ]
                )


def _fmt(value: float) -> str:
    text = f"{value:.10g}"
    return text
