"""Self-tests for the sieve package. Run with: python -m unittest -v"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sieve.__main__ import main
from sieve.analysis import analyze_sample
from sieve.loading import SampleInput, SieveRecord, load_input


def write_input(payload: dict, directory: Path) -> Path:
    path = directory / "input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


GOOD_SAMPLE = {
    "sample_id": "S1",
    "dry_mass": 1000.0,
    "sieves": [
        {"aperture": 2.0, "retained": 200.0},
        {"aperture": 1.0, "retained": 300.0},
        {"aperture": 0.5, "retained": 400.0},
    ],
    "pan": 100.0,
}


class LoadingTests(unittest.TestCase):
    def test_valid_sample_loaded_and_sorted_agnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_input(write_input({"samples": [GOOD_SAMPLE]}, Path(tmp)))
        self.assertEqual(loaded.invalid, [])
        self.assertEqual(len(loaded.samples), 1)
        self.assertEqual(loaded.samples[0].sample_id, "S1")

    def test_duplicate_id_and_aperture_rejected(self) -> None:
        payload = {"samples": [GOOD_SAMPLE, GOOD_SAMPLE]}
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_input(write_input(payload, Path(tmp)))
        self.assertEqual(len(loaded.samples), 1)
        self.assertEqual(loaded.invalid[0]["reason"], "duplicate sample_id")

        dup_aperture = json.loads(json.dumps(GOOD_SAMPLE))
        dup_aperture["sample_id"] = "S2"
        dup_aperture["sieves"][1]["aperture"] = 2.0
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_input(write_input({"samples": [dup_aperture]}, Path(tmp)))
        self.assertEqual(loaded.samples, [])
        self.assertIn("duplicate aperture", loaded.invalid[0]["reason"])

    def test_bad_aperture_negative_mass_and_mass_balance(self) -> None:
        cases = []
        bad_ap = json.loads(json.dumps(GOOD_SAMPLE))
        bad_ap["sample_id"] = "A"
        bad_ap["sieves"][0]["aperture"] = -1
        cases.append(bad_ap)

        bad_mass = json.loads(json.dumps(GOOD_SAMPLE))
        bad_mass["sample_id"] = "B"
        bad_mass["pan"] = -0.1
        cases.append(bad_mass)

        imbalance = json.loads(json.dumps(GOOD_SAMPLE))
        imbalance["sample_id"] = "C"
        imbalance["pan"] = 50.0
        cases.append(imbalance)

        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_input(write_input({"samples": cases}, Path(tmp)))
        self.assertEqual(loaded.samples, [])
        reasons = {item["sample_id"]: item["reason"] for item in loaded.invalid}
        self.assertIn("greater than zero", reasons["A"])
        self.assertIn("non-negative", reasons["B"])
        self.assertIn("mass balance", reasons["C"])

    def test_exactly_one_percent_tolerance_accepted(self) -> None:
        edge = json.loads(json.dumps(GOOD_SAMPLE))
        edge["dry_mass"] = 1000.0
        edge["pan"] = 110.0
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_input(write_input({"samples": [edge]}, Path(tmp)))
        self.assertEqual(len(loaded.samples), 1)


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = SampleInput(
            "S1",
            1000.0,
            [
                SieveRecord(2.0, 200.0),
                SieveRecord(1.0, 300.0),
                SieveRecord(0.5, 400.0),
            ],
            100.0,
        )

    def test_percent_passing_sorted_ascending(self) -> None:
        report = analyze_sample(self.sample)
        apertures = [p["aperture_mm"] for p in report["curve"]]
        self.assertEqual(apertures, [0.5, 1.0, 2.0])
        self.assertEqual([p["percent_passing"] for p in report["curve"]], [10.0, 50.0, 80.0])

    def test_characteristic_sizes_semilog_interpolation(self) -> None:
        report = analyze_sample(self.sample)
        sizes = report["characteristic_sizes"]
        self.assertAlmostEqual(sizes["D10"]["diameter_mm"], 0.5)
        self.assertAlmostEqual(sizes["D60"]["diameter_mm"], 2.0 ** (1.0 / 3.0))
        d30 = sizes["D30"]["diameter_mm"]
        # 30% between nodes (0.5mm,50%) and (1.0mm,10%) in aperture order:
        # nodes ordered ascending: 0.5->10%, 1.0->50%; log interpolation.
        self.assertAlmostEqual(d30, 0.5 * 2.0**0.5)

    def test_coefficients_null_when_size_missing(self) -> None:
        # Smallest node already passes 20%, so 10% is not bracketed.
        sample = SampleInput(
            "fine",
            1000.0,
            [
                SieveRecord(2.0, 200.0),
                SieveRecord(1.0, 300.0),
                SieveRecord(0.5, 300.0),
            ],
            200.0,
        )
        report = analyze_sample(sample)
        self.assertIsNone(report["characteristic_sizes"]["D10"]["diameter_mm"])
        self.assertIn("not bracketed", report["characteristic_sizes"]["D10"]["note"])
        self.assertIsNone(report["coefficients"]["Cu"])
        self.assertIsNone(report["coefficients"]["Cc"])

    def test_coefficients_complete_grading(self) -> None:
        sample = SampleInput(
            "full",
            100.0,
            [
                SieveRecord(10.0, 30.0),
                SieveRecord(2.0, 30.0),
                SieveRecord(0.5, 30.0),
            ],
            10.0,
        )
        report = analyze_sample(sample)
        sizes = report["characteristic_sizes"]
        # passing: 0.5 -> 10%, 2.0 -> 40%, 10 -> 70%
        self.assertAlmostEqual(sizes["D10"]["diameter_mm"], 0.5)
        d30 = sizes["D30"]["diameter_mm"]
        self.assertAlmostEqual(d30, 0.5 * 4.0 ** (20.0 / 30.0))
        d60 = sizes["D60"]["diameter_mm"]
        self.assertAlmostEqual(d60, 2.0 * 5.0 ** (20.0 / 30.0))
        cu = report["coefficients"]["Cu"]
        cc = report["coefficients"]["Cc"]
        self.assertAlmostEqual(cu, d60 / 0.5)
        self.assertAlmostEqual(cc, d30**2 / (0.5 * d60))


class CliTests(unittest.TestCase):
    def test_cli_writes_outputs_and_nonzero_on_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_path = write_input({"samples": [GOOD_SAMPLE, {"sample_id": "bad"}]}, tmp_path)
            out_dir = tmp_path / "out"
            code = main([str(in_path), "--out", str(out_dir)])
            self.assertEqual(code, 1)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"], {"valid_count": 1, "invalid_count": 1})
            self.assertEqual(report["invalid_samples"][0]["sample_id"], "bad")
            csv_text = (out_dir / "curves.csv").read_text(encoding="utf-8")
            self.assertIn("sample_id,aperture_mm,percent_passing", csv_text)
            self.assertIn("S1,0.5,10", csv_text)
            self.assertNotIn("bad", csv_text)

    def test_cli_zero_exit_when_all_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_path = write_input({"samples": [GOOD_SAMPLE]}, tmp_path)
            code = main([str(in_path), "--out", str(tmp_path / "out")])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
