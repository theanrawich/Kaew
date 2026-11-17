"""Synthetic fixtures test arithmetic/validation ONLY; no hardware measurements."""
import csv
from pathlib import Path
import tempfile
import unittest
from analyze_measurements import analyze, FIELDS


class MeasurementsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic-unit-test.csv"
        self.base = {"test_id": "SYNTHETIC", "trial": "1", "firmware_commit": "synthetic-fixture",
                     "evidence": "synthetic-unit-test-only"}

    def write(self, mode, rows):
        with self.path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=sorted(FIELDS[mode]))
            writer.writeheader()
            writer.writerows(dict(self.base, **row) for row in rows)
        return analyze(mode, self.path)

    def latency(self, **extra):
        return dict(kind="event_to_control", start_us="1000", end_us="4000", start_clock="capture-1",
                    end_clock="capture-1", sync_uncertainty_us="10", **extra)

    def packet(self, event="tx", seq="0", phase="window", **extra):
        return dict(time_us="1000", event=event, phase=phase, node="1", session="9", seq=seq, **extra)

    def accuracy(self, **extra):
        row = dict(point_g="50", reference_g="50", hx711_g="51", raw_counts="5100", calibration_id="synthetic")
        return dict(row, **extra)

    def volume(self, **extra):
        row = dict(target_ml="50", before_g="100", after_g="151", density_g_per_ml="1", post_stop_g="2", elapsed_ms="10000")
        return dict(row, **extra)

    def test_latency_mean_range_sample_variation_and_units(self):
        result = self.write("latency", [self.latency(), dict(self.latency(), trial="2", end_us="6000")])
        summary = result["groups"][0]["latency_ms"]
        self.assertEqual((summary["mean"], summary["min"], summary["max"], summary["range"]), (4, 3, 5, 2))
        self.assertAlmostEqual(summary["sample_stdev"], 2**0.5)
        self.assertAlmostEqual(summary["p95"], 4.9)
        self.assertEqual(result["hardware_verdict"], "NOT_ASSESSED")
        self.assertEqual(len(result["input_sha256"]), 64)

    def test_clock_mismatch_and_backwards_time_rejected(self):
        for row in [dict(self.latency(), end_clock="other"), dict(self.latency(), end_us="999")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.write("latency", [row])

    def test_duplicate_trials_rejected_including_leading_zero(self):
        with self.assertRaisesRegex(ValueError, "duplicate trial"):
            self.write("latency", [self.latency(), dict(self.latency(), trial="01")])

    def test_packet_retries_duplicates_window_and_recovery(self):
        result = self.write("packets", [self.packet(), self.packet(), self.packet("rx"), self.packet("rx"),
                    self.packet(seq="1"), self.packet("drop", "1"), self.packet("rx", "1", "recovery"), self.packet("ack", "0")])
        group = result["groups"][0]
        self.assertEqual((group["tx_unique"], group["tx_attempts"], group["retry_attempts"], group["rx_duplicates"]), (2, 3, 1, 1))
        self.assertEqual((group["pdr_window_percent"], group["pdr_after_recovery_percent"]), (50, 100))
        self.assertEqual(group["sender_dropped_unique"], 1) # ACK loss != packet loss

    def test_packet_reboot_sequence_wrap_and_missing_packets(self):
        rows = [self.packet(seq="4294967295"), self.packet("rx", "4294967295"), self.packet(seq="0"),
                dict(self.packet(), session="10"), dict(self.packet("rx"), session="10")]
        group = self.write("packets", rows)["groups"][0]
        self.assertEqual(group["tx_unique"], 3)
        self.assertEqual(group["unreceived_after_recovery"], 1)
        self.assertAlmostEqual(group["pdr_after_recovery_percent"], 200/3)

    def test_packet_repeated_trials_have_variation_and_pooled_rate(self):
        result = self.write("packets", [self.packet(), self.packet("rx"),
                   self.packet(trial="2"), self.packet(seq="1", trial="2"), self.packet("rx", trial="2")])
        summary = result["trial_summary"][0]
        self.assertEqual(summary["pdr_window_percent"]["mean"], 75)
        self.assertAlmostEqual(summary["pooled_pdr_window_percent"], 200/3)

    def test_incomplete_capture_bad_phase_and_bad_ids_rejected(self):
        for rows in [[self.packet("rx")], [self.packet(phase="recovery")],
                     [self.packet(), self.packet("rx", "1")], [dict(self.packet(), session="0")],
                     [dict(self.packet(), seq="4294967296")], [self.packet(phase="other")],
                     [self.packet(), self.packet("ack")], [self.packet(event="cloud")]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.write("packets", rows)

    def test_accuracy_signed_error_mae_rmse_and_repeatability(self):
        summary = self.write("accuracy", [self.accuracy(), self.accuracy(trial="2", hx711_g="49", point_g="50.0")])["groups"][0]
        self.assertEqual(summary["signed_error_g"]["mean"], 0)
        self.assertEqual(summary["mean_absolute_error_g"], 1)
        self.assertEqual(summary["rmse_g"], 1)
        self.assertAlmostEqual(summary["hx711_g"]["sample_stdev"], 2**0.5)

    def test_saturated_raw_and_nonfinite_values_rejected(self):
        for row in [self.accuracy(raw_counts="8388607"), self.accuracy(raw_counts="-8388608"),
                    self.accuracy(hx711_g="nan"), self.accuracy(reference_g="inf")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.write("accuracy", [row])

    def test_volume_overshoot_density_and_post_stop(self):
        summary = self.write("volume", [self.volume()])["groups"][0]
        self.assertEqual(summary["delivered_ml"]["mean"], 51)
        self.assertEqual(summary["overshoot_ml"]["mean"], 1)
        self.assertEqual(summary["post_stop_ml"]["mean"], 2)
        self.assertIsNone(summary["delivered_ml"]["sample_stdev"])

    def test_impossible_volume_and_zero_density_rejected(self):
        for row in [self.volume(density_g_per_ml="0"), self.volume(after_g="99"), self.volume(post_stop_g="60")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.write("volume", [row])

    def test_header_only_template_and_missing_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, "no measurements"):
            self.write("latency", [])
        with self.assertRaisesRegex(ValueError, "blank required"):
            self.write("latency", [dict(self.latency(), evidence="")])

    def test_malformed_schema_rejected(self):
        self.path.write_text("test_id,test_id\na,b\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            analyze("latency", self.path)

    def test_versions_are_never_averaged_together(self):
        result = self.write("accuracy", [self.accuracy(), self.accuracy(firmware_commit="other")])
        self.assertEqual(len(result["groups"]), 2)


if __name__ == "__main__":
    unittest.main()
