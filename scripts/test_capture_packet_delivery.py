"""Synthetic recorder fixtures only; no serial ports are opened."""
import unittest
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from capture_packet_delivery import convert, main


class CaptureTest(unittest.TestCase):
    def fixtures(self):
        return [{"source": source, "time_us": at, "line": line} for source, at, line in [
            ("node", 0, "node trace_dropped=0"), ("gateway", 0, "pump=off trace_dropped=0"),
            ("node", 10, "TRACE tx 1 1 7 0"), ("node", 20, "TRACE tx 2 1 7 0"),
            ("gateway", 30, "TRACE rx 3 1 7 0"), ("node", 40, "TRACE tx 4 1 7 1"),
            ("gateway", 110, "TRACE rx 10 1 7 1"), ("node", 120, "TRACE tx 11 1 7 2"),
            ("node", 210, "node trace_dropped=0"), ("gateway", 220, "pump=off trace_dropped=0")]]

    def convert(self, records):
        return convert(records, 100, "SYNTHETIC", "synthetic-fixture", "synthetic.jsonl", recovery_us=100)

    def test_cohort_preserves_retries_and_late_arrivals_excludes_new_samples(self):
        events = self.convert(self.fixtures())
        self.assertEqual(len(events), 5)
        self.assertEqual(events[-1]["phase"], "recovery")
        self.assertFalse(any(event["seq"] == "2" for event in events))

    def test_trace_loss_missing_diagnostics_and_wrong_port_rejected(self):
        for extra in [[], [{"source": "node", "time_us": 50, "line": "trace_dropped=1"}],
                      [{"source": "gateway", "time_us": 50, "line": "TRACE tx 1 1 7 9"}]]:
            records = self.fixtures()[:-1] if not extra else self.fixtures() + extra
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.convert(records)

    def test_opening_zero_counters_do_not_prove_completeness(self):
        with self.assertRaisesRegex(ValueError, "closing trace_dropped"):
            self.convert(self.fixtures()[:-2])

    def test_counters_after_window_must_also_cover_recovery(self):
        records = self.fixtures()
        records[-2]["time_us"] = 150
        records[-1]["time_us"] = 160
        with self.assertRaisesRegex(ValueError, "after window \\+ recovery"):
            self.convert(records)

    def test_late_trace_loss_on_either_board_invalidates_the_run(self):
        for source in ("node", "gateway"):
            records = self.fixtures()
            for record in records[-2:]:
                if record["source"] == source:
                    record["line"] = "trace_dropped=1"
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "trace loss"):
                self.convert(records)

    def test_closing_tail_does_not_extend_measured_recovery(self):
        records = self.fixtures()
        records.insert(-2, {"source": "gateway", "time_us": 205, "line": "TRACE rx 20 1 7 0"})
        events = self.convert(records)
        self.assertEqual(len(events), 5) # tail duplicate excluded
        self.assertTrue(all(int(event["time_us"]) < 200 for event in events))

    def test_counter_at_measurement_end_is_a_valid_closing_counter(self):
        records = self.fixtures()
        for record in records[-2:]:
            record["time_us"] = 200
        self.assertEqual(len(self.convert(records)), 5)

    def test_saved_log_without_final_counter_cannot_create_result_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "synthetic.jsonl"
            output = Path(directory) / "result.csv"
            records = self.fixtures()[:-2]
            for record in records:
                record["time_us"] *= 10000 # 100 fixture units = CLI's 1-second window.
            raw.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
            args = ["capture_packet_delivery.py", "--from-log", str(raw), "--window-s", "1", "--recovery-s", "1",
                    "--test-id", "SYNTHETIC", "--firmware-commit", "synthetic-fixture", "--output", str(output)]
            with patch("sys.argv", args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(output.exists())
            self.assertTrue(raw.exists())

    def test_saved_log_with_final_counters_creates_bounded_results(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "synthetic.jsonl"
            output = Path(directory) / "result.csv"
            records = self.fixtures()
            for record in records:
                record["time_us"] *= 10000
            raw.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
            args = ["capture_packet_delivery.py", "--from-log", str(raw), "--window-s", "1", "--recovery-s", "1",
                    "--test-id", "SYNTHETIC", "--firmware-commit", "synthetic-fixture", "--output", str(output)]
            result = io.StringIO()
            with patch("sys.argv", args), redirect_stdout(result):
                main()
            group = json.loads(result.getvalue())["groups"][0]
            self.assertEqual(group["pdr_window_percent"], 50)
            self.assertEqual(group["pdr_after_recovery_percent"], 100)
            self.assertTrue(output.exists())

    def test_no_transmissions_rejected(self):
        records = [item for item in self.fixtures() if not item["line"].startswith("TRACE")]
        with self.assertRaises(ValueError):
            self.convert(records)


if __name__ == "__main__":
    unittest.main()
