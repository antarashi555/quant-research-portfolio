"""End-to-end and failure-path tests for the synthetic research pipeline."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "examples"))
from research_pipeline_demo import (DEFAULT_DATA, DEFAULT_SPEC, PITView,
                                    audit, load_bars, load_spec, run_pipeline, simulate)


class PipelineTests(unittest.TestCase):
    def test_happy_path_requires_human_review(self):
        report = run_pipeline()
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(report["audit"]["passed"])
        self.assertTrue(report["manual_review_required"])
        self.assertEqual(set(report["stats"]), {"train", "test", "holdout"})
        self.assertGreater(report["trade_count"], 0)
        self.assertEqual(len(report["source_hashes"]["data_sha256"]), 64)
        self.assertEqual(len(report["access_log"]), report["audit"]["reads_checked"])
        self.assertEqual(len(report["equity_curve"]), 14)

    def test_injected_leak_is_rejected(self):
        report = run_pipeline(inject_leak=True)
        self.assertEqual(report["status"], "REJECTED")
        self.assertFalse(report["audit"]["passed"])
        self.assertTrue(any("future/unpublished" in item for item in report["audit"]["findings"]))

    def test_pit_excludes_delayed_publication(self):
        bars = load_bars(DEFAULT_DATA)
        view = PITView(bars)
        observed = view.recent(bars[7].day, 20)
        self.assertNotIn(bars[7], observed)
        self.assertIn(bars[7], view.recent(bars[8].day, 20))

    def test_all_accesses_are_auditable(self):
        bars = load_bars(DEFAULT_DATA)
        spec = load_spec(DEFAULT_SPEC, bars)
        self.assertEqual(audit(bars, simulate(bars, spec), spec), [])
        self.assertGreater(len(simulate(bars, spec)["access_log"]), 0)

    def test_next_open_execution_and_cost(self):
        bars = load_bars(DEFAULT_DATA)
        spec = load_spec(DEFAULT_SPEC, bars)
        run = simulate(bars, spec)
        by_day = {bar.day.isoformat(): bar for bar in bars}
        days = list(by_day)
        for trade in run["trades"]:
            self.assertEqual(days[days.index(trade["decision_date"]) + 1], trade["execution_date"])
            self.assertEqual(trade["open_price"], by_day[trade["execution_date"]].open)
            self.assertGreater(trade["fee"], 0)

    def test_zero_cost_is_not_better_than_positive_cost(self):
        bars = load_bars(DEFAULT_DATA)
        spec = load_spec(DEFAULT_SPEC, bars)
        with_cost = simulate(bars, spec)["equity_curve"][-1]["equity"]
        spec["cost_bps"] = 0
        no_cost = simulate(bars, spec)["equity_curve"][-1]["equity"]
        self.assertGreaterEqual(no_cost, with_cost)

    def test_determinism(self):
        self.assertEqual(run_pipeline(), run_pipeline())

    def test_bad_config_rejected(self):
        bars = load_bars(DEFAULT_DATA)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            spec = json.loads(DEFAULT_SPEC.read_text(encoding="utf-8"))
            spec["lookback"] = 1
            path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_spec(path, bars)

    def test_poisoned_data_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "poisoned.csv"
            text = DEFAULT_DATA.read_text(encoding="utf-8")
            text = text.replace("2026-01-15,SYN,104,102", "2026-01-13,SYN,104,102")
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_bars(path)

    def test_audit_detects_mutated_access_record(self):
        bars = load_bars(DEFAULT_DATA)
        spec = load_spec(DEFAULT_SPEC, bars)
        run = simulate(bars, spec)
        run["access_log"][0]["available_date"] = "2029-01-01"
        self.assertTrue(audit(bars, run, spec))

    def test_cli_normal_and_failed_scenarios(self):
        program = PROJECT / "examples" / "research_pipeline_demo.py"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            normal = subprocess.run([sys.executable, str(program), "--out", str(path)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(normal.returncode, 0, normal.stderr)
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            failed = subprocess.run([sys.executable, str(program), "--out", str(path),
                                     "--inject-leak"], capture_output=True, text=True, check=False)
            self.assertEqual(failed.returncode, 2, failed.stderr)
            rejected = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(rejected["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
