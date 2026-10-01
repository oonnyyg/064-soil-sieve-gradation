"""Command line entry point: python -m sieve input.json --out output_dir."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import analyze_sample
from .loading import load_input
from .report import write_curves_csv, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sieve",
        description="Batch soil sieve gradation analysis.",
    )
    parser.add_argument("input", help="path to the input JSON file")
    parser.add_argument("--out", required=True, help="output directory for report and curves")
    args = parser.parse_args(argv)

    try:
        loaded = load_input(args.input)
    except (OSError, ValueError) as exc:
        print(f"error: failed to load input: {exc}", file=sys.stderr)
        return 2

    reports = [analyze_sample(sample) for sample in loaded.samples]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_report(out_dir / "report.json", reports, loaded.invalid)
    write_curves_csv(out_dir / "curves.csv", reports)

    for item in loaded.invalid:
        print(f"invalid sample {item['sample_id']}: {item['reason']}", file=sys.stderr)
    print(
        f"processed {len(reports)} valid sample(s), {len(loaded.invalid)} invalid; "
        f"outputs in {out_dir}"
    )
    return 1 if loaded.invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
