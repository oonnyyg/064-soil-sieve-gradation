"""JSON report and gradation curve CSV writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def write_report(path: Path, reports: list[dict], invalid: list[dict[str, str]]) -> None:
    payload = {
        "samples": reports,
        "invalid_samples": invalid,
        "summary": {
            "valid_count": len(reports),
            "invalid_count": len(invalid),
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_curves_csv(path: Path, reports: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_id", "aperture_mm", "percent_passing"])
        for report in reports:
            for point in report["curve"]:
                writer.writerow(
                    [report["sample_id"], _fmt(point["aperture_mm"]), _fmt(point["percent_passing"])]
                )


def _fmt(value: float) -> str:
    text = f"{value:.10g}"
    return text
