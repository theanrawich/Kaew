"""Validate real CSV captures and emit descriptive metrics, never a hardware PASS.

Blank templates live in docs/testing/measurements/. No third-party dependencies required.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from collections import defaultdict

COMMON = {"test_id", "trial", "firmware_commit", "evidence"}
FIELDS = {
    "latency": COMMON | {"kind", "start_us", "end_us", "start_clock", "end_clock", "sync_uncertainty_us"},
    "packets": COMMON | {"time_us", "event", "phase", "node", "session", "seq"},
    "accuracy": COMMON | {"point_g", "reference_g", "hx711_g", "raw_counts", "calibration_id"},
    "volume": COMMON | {"target_ml", "before_g", "after_g", "density_g_per_ml", "post_stop_g", "elapsed_ms"},
}


def number(row, field, minimum=None, positive=False):
    try:
        value = float(row[field])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: finite number required") from exc
    if not math.isfinite(value) or (minimum is not None and value < minimum) or (positive and value <= 0):
        raise ValueError(f"{field}: outside allowed range")
    return value


def integer(row, field, minimum=0, maximum=None):
    value = row[field]
    if not value or not value.isascii() or not value.isdecimal():
        raise ValueError(f"{field}: unsigned decimal integer required")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{field}: outside allowed range")
    return result


def stats(values):
    values = sorted(values)
    if not values:
        raise ValueError("no measurements")
    position = (len(values) - 1) * 0.95
    lower = math.floor(position)
    p95 = values[lower] + (values[math.ceil(position)] - values[lower]) * (position - lower)
    return {"n": len(values), "mean": statistics.mean(values), "min": values[0], "max": values[-1],
            "sample_stdev": statistics.stdev(values) if len(values) > 1 else None,
            "range": values[-1] - values[0], "p95": p95}


def read_rows(mode, path):
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)) or not FIELDS[mode] <= set(reader.fieldnames):
            raise ValueError(f"missing or duplicate CSV columns; required: {sorted(FIELDS[mode])}")
        rows = []
        for line, row in enumerate(reader, 2):
            if None in row or any(row[field] is None or not row[field].strip() for field in FIELDS[mode]):
                raise ValueError(f"line {line}: blank required value or malformed CSV row")
            row = {key: value.strip() if value is not None else value for key, value in row.items()}
            row["trial"] = str(integer(row, "trial", minimum=1))
            if mode == "accuracy":
                row["point_g"] = str(number(row, "point_g", minimum=0))
            elif mode == "volume":
                row["target_ml"] = str(number(row, "target_ml", positive=True))
            rows.append(row)
    if not rows:
        raise ValueError("no measurements: header-only templates are not experimental results")
    return rows


def grouped(rows, extra=()):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in ("test_id", "firmware_commit", *extra))
        groups[key].append(row)
    return groups


def unique_trials(rows):
    trials = [row["trial"] for row in rows]
    if len(trials) != len(set(trials)):
        raise ValueError("duplicate trial in one measurement group")


def latency(rows):
    results = []
    for (test, commit, kind), group in grouped(rows, ("kind",)).items():
        unique_trials(group)
        values, uncertainties = [], []
        for row in group:
            if row["start_clock"] != row["end_clock"]:
                raise ValueError("latency endpoints need one common clock; map/synchronize captures before analysis")
            start, end = integer(row, "start_us"), integer(row, "end_us")
            if end < start:
                raise ValueError("end_us precedes start_us; unwrap hardware counters before export")
            values.append((end - start) / 1000)
            uncertainties.append(number(row, "sync_uncertainty_us", minimum=0) / 1000)
        results.append({"test_id": test, "firmware_commit": commit, "kind": kind,
                        "latency_ms": stats(values), "max_clock_uncertainty_ms": max(uncertainties)})
    return results


def packets(rows):
    results = []
    for (test, commit, trial), group in grouped(rows, ("trial",)).items():
        sent, received, in_window, acked, dropped = set(), set(), set(), set(), set()
        tx_attempts = rx_frames = 0
        window_tx = set()
        for row in group:
            integer(row, "time_us")
            key = (integer(row, "node", 1, 255), integer(row, "session", 1, 2**32-1), integer(row, "seq", 0, 2**32-1))
            if row["phase"] not in ("window", "recovery"):
                raise ValueError("packet phase must be window or recovery")
            event = row["event"]
            if event == "tx":
                tx_attempts += 1; sent.add(key)
                if row["phase"] == "window":
                    window_tx.add(key)
            elif event == "rx":
                rx_frames += 1; received.add(key)
                if row["phase"] == "window":
                    in_window.add(key)
            elif event == "ack":
                acked.add(key)
            elif event == "drop":
                dropped.add(key)
            else:
                raise ValueError("packet event must be tx, rx, ack or drop")
        if not sent or sent != window_tx:
            raise ValueError("capture every initial tx in the window; recovery may only retry those packets")
        if not (received | acked | dropped) <= sent or not acked <= received:
            raise ValueError("unmatched rx/ack/drop: incomplete or inconsistent packet captures")
        results.append({"test_id": test, "firmware_commit": commit, "trial": int(trial),
                        "tx_unique": len(sent), "tx_attempts": tx_attempts, "retry_attempts": tx_attempts-len(sent),
                        "rx_unique_window": len(in_window), "rx_unique_after_recovery": len(received),
                        "rx_frames": rx_frames, "rx_duplicates": rx_frames-len(received),
                        "pdr_window_percent": 100*len(in_window)/len(sent),
                        "pdr_after_recovery_percent": 100*len(received)/len(sent),
                        "unreceived_after_recovery": len(sent-received), "acked_unique": len(acked),
                        "sender_dropped_unique": len(dropped)})
    return results


def accuracy(rows):
    results = []
    for (test, commit, calibration, point), group in grouped(rows, ("calibration_id", "point_g")).items():
        unique_trials(group)
        errors, values = [], []
        for row in group:
            number(row, "point_g", minimum=0)
            ref, value = number(row, "reference_g", minimum=0), number(row, "hx711_g")
            try:
                raw = int(row["raw_counts"])
            except ValueError as exc:
                raise ValueError("raw_counts: signed 24-bit integer required") from exc
            if not -8388608 < raw < 8388607:
                raise ValueError("raw_counts: invalid/saturated HX711 conversion")
            values.append(value); errors.append(value-ref)
        results.append({"test_id": test, "firmware_commit": commit, "calibration_id": calibration, "point_g": float(point),
                        "hx711_g": stats(values), "signed_error_g": stats(errors),
                        "mean_absolute_error_g": statistics.mean(abs(e) for e in errors),
                        "rmse_g": math.sqrt(statistics.mean(e*e for e in errors)), "max_absolute_error_g": max(map(abs, errors))})
    return results


def volume(rows):
    results = []
    for (test, commit, target), group in grouped(rows, ("target_ml",)).items():
        unique_trials(group)
        delivered, errors, residual, elapsed = [], [], [], []
        for row in group:
            requested = number(row, "target_ml", positive=True)
            density = number(row, "density_g_per_ml", positive=True)
            gain = number(row, "after_g", minimum=0) - number(row, "before_g", minimum=0)
            post = number(row, "post_stop_g", minimum=0)
            if gain < 0 or post > gain:
                raise ValueError("volume gain must be nonnegative and include post-stop water")
            delivered.append(gain/density); errors.append(gain/density-requested)
            residual.append(post/density); elapsed.append(number(row, "elapsed_ms", minimum=0))
        results.append({"test_id": test, "firmware_commit": commit, "target_ml": float(target),
                        "delivered_ml": stats(delivered), "signed_error_ml": stats(errors),
                        "overshoot_ml": stats([max(0, e) for e in errors]), "post_stop_ml": stats(residual),
                        "elapsed_ms": stats(elapsed)})
    return results


def analyze(mode, path):
    rows = read_rows(mode, path)
    result = {"mode": mode, "input_rows": len(rows), "hardware_verdict": "NOT_ASSESSED",
              "input_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              "evidence": sorted({row["evidence"] for row in rows}),
              "groups": {"latency": latency, "packets": packets, "accuracy": accuracy, "volume": volume}[mode](rows)}
    if mode == "packets":
        summaries = defaultdict(list)
        for item in result["groups"]:
            summaries[item["test_id"], item["firmware_commit"]].append(item)
        result["trial_summary"] = [
            {"test_id": key[0], "firmware_commit": key[1],
             "pdr_window_percent": stats([item["pdr_window_percent"] for item in items]),
             "pdr_after_recovery_percent": stats([item["pdr_after_recovery_percent"] for item in items]),
             "pooled_pdr_window_percent": 100*sum(item["rx_unique_window"] for item in items)/sum(item["tx_unique"] for item in items),
             "pooled_pdr_after_recovery_percent": 100*sum(item["rx_unique_after_recovery"] for item in items)/sum(item["tx_unique"] for item in items)}
            for key, items in summaries.items()]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=FIELDS)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = json.dumps(analyze(args.mode, args.csv), ensure_ascii=False, indent=2, allow_nan=False)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"measurement analysis rejected: {exc}\n")
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
