"""Command line entry point: python -m sieve INPUT.json --out DIR"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import analyze_sample
from .loader import InputError, load_samples
from .report import build_report, write_curves_csv, write_report_json
from .selftest import run_selftest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sieve",
        description="Soil sieve gradation analysis: curve CSV and characteristic size report.",
    )
    parser.add_argument("input", nargs="?", help="input JSON file")
    parser.add_argument("--out", type=Path, help="output directory")
    parser.add_argument("--selftest", action="store_true", help="run built-in self tests")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if args.input is None or args.out is None:
        parser.error("input file and --out are required (or use --selftest)")

    out_dir: Path = args.out
    try:
        samples = load_samples(Path(args.input))
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results = [analyze_sample(sample) for sample in samples]
    report = build_report(results)

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.json"
    curves_path = out_dir / "curves.csv"
    write_report_json(report, report_path)
    write_curves_csv(results, curves_path)

    for result in results:
        if result.valid:
            print(f"[OK]   {result.sample_id}")
        else:
            print(f"[FAIL] {result.sample_id}: {'; '.join(result.errors)}", file=sys.stderr)

    print(f"report: {report_path}")
    print(f"curves: {curves_path}")
    return 1 if report["invalid_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
