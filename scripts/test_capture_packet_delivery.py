"""Synthetic recorder fixtures only; no serial ports are opened."""
import unittest
from capture_packet_delivery import convert


class CaptureTest(unittest.TestCase):
    def fixtures(self):
        return [{"source": source, "time_us": at, "line": line} for source, at, line in [
            ("node", 0, "node trace_dropped=0"), ("gateway", 0, "pump=off trace_dropped=0"),
            ("node", 10, "TRACE tx 1 1 7 0"), ("node", 20, "TRACE tx 2 1 7 0"),
            ("gateway", 30, "TRACE rx 3 1 7 0"), ("node", 40, "TRACE tx 4 1 7 1"),
            ("gateway", 110, "TRACE rx 10 1 7 1"), ("node", 120, "TRACE tx 11 1 7 2")]]

    def test_cohort_preserves_retries_and_late_arrivals_excludes_new_samples(self):
        events = convert(self.fixtures(), 100, "SYNTHETIC", "synthetic-fixture", "synthetic.jsonl")
        self.assertEqual(len(events), 5)
        self.assertEqual(events[-1]["phase"], "recovery")
        self.assertFalse(any(event["seq"] == "2" for event in events))

    def test_trace_loss_missing_diagnostics_and_wrong_port_rejected(self):
        for extra in [[], [{"source": "node", "time_us": 50, "line": "trace_dropped=1"}],
                      [{"source": "gateway", "time_us": 50, "line": "TRACE tx 1 1 7 9"}]]:
            records = self.fixtures()[1:] if not extra else self.fixtures() + extra
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                convert(records, 100, "SYNTHETIC", "synthetic-fixture", "synthetic.jsonl")

    def test_no_transmissions_rejected(self):
        records = self.fixtures()[:2]
        with self.assertRaises(ValueError):
            convert(records, 100, "SYNTHETIC", "synthetic-fixture", "synthetic.jsonl")


if __name__ == "__main__":
    unittest.main()
