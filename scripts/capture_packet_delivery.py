"""Capture optional firmware TRACE logs from two serial ports (pump disconnected).

Requires pyserial only for live capture. --from-log reprocesses a saved JSONL
without serial access. PC monotonic receipt timestamps define the cohort window;
they are NOT measurements of MCU-to-MCU latency.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import threading
import time
from analyze_measurements import FIELDS, analyze

TRACE = re.compile(r"^TRACE (tx|rx|ack|drop) (\d+) (\d+) (\d+) (\d+)$")
DROPPED = re.compile(r"\btrace_dropped=(\d+)\b")


def convert(records, window_us, test_id, commit, evidence, *, recovery_us):
    events = []
    closing_diagnostics = set()
    measured_until_us = window_us + recovery_us
    for record in records:
        source, line = record["source"], record["line"].strip()
        if source not in ("node", "gateway") or record["time_us"] < 0:
            raise ValueError("invalid recorder source/time")
        counter = DROPPED.search(line)
        if counter:
            if int(counter[1]):
                raise ValueError("trace loss reported; repeat capture with complete logs")
            if record["time_us"] >= measured_until_us:
                closing_diagnostics.add(source)
        match = TRACE.fullmatch(line)
        if match:
            event, board_ms, node, session, seq = match.groups()
            if (source == "gateway") != (event == "rx"):
                raise ValueError("TRACE event came from the wrong serial port")
            if record["time_us"] >= measured_until_us:
                continue # Closing-tail traffic must not inflate recovery PDR.
            events.append(dict(test_id=test_id, trial="1", time_us=str(record["time_us"]), event=event,
                               phase="window" if record["time_us"] < window_us else "recovery",
                               node=node, session=session, seq=seq, firmware_commit=commit, evidence=evidence))
    if closing_diagnostics != {"node", "gateway"}:
        raise ValueError("capture lacks closing trace_dropped diagnostics from both boards after window + recovery")
    key = lambda event: (event["node"], event["session"], event["seq"])
    cohort = {key(event) for event in events if event["event"] == "tx" and event["phase"] == "window"}
    if not cohort:
        raise ValueError("no transmitted cohort in the measurement window")
    # Boards keep sampling during recovery. Exclude NEW packets from that phase;
    # retain every retry/rx/ack/drop belonging to the original cohort.
    return [event for event in events if key(event) in cohort]


def capture(node_port, gateway_port, duration_s, closing_grace_s=3):
    try:
        import serial
    except ImportError as exc:
        raise ValueError("live capture needs pyserial (available in the local PlatformIO venv)") from exc
    ports = []
    records, errors = [], []
    try:
        for name in (node_port, gateway_port):
            port = serial.Serial(port=None, baudrate=115200, timeout=0.1)
            port.dtr = False; port.rts = False; port.port = name
            port.open(); ports.append(port)
        for port in ports:
            port.reset_input_buffer() # Exclude pre-capture USB/driver backlog.
        start = time.perf_counter_ns()
        def reader(source, port):
            try:
                while time.perf_counter_ns() - start < (duration_s + closing_grace_s) * 1e9:
                    line = port.read_until(b"\n", 2048)
                    if line:
                        if not line.endswith(b"\n"):
                            raise ValueError(f"{source}: incomplete serial line")
                        record = {"source": source, "time_us": (time.perf_counter_ns()-start)//1000,
                                  "line": line.decode("utf-8", errors="strict").rstrip()}
                        records.append(record)
                        if record["time_us"] >= duration_s * 1e6 and DROPPED.search(record["line"]):
                            return # Each port closes only after its own final counter.
                errors.append(f"{source}: missing closing trace_dropped counter after measurement")
            except Exception as exc:
                errors.append(str(exc))
        threads = [threading.Thread(target=reader, args=(source, port)) for source, port in zip(("node", "gateway"), ports)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        for port in ports:
            port.close()
    return sorted(records, key=lambda item: item["time_us"]), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node")
    parser.add_argument("--gateway")
    parser.add_argument("--from-log", type=Path)
    parser.add_argument("--window-s", type=float, default=60)
    parser.add_argument("--recovery-s", type=float, default=10)
    parser.add_argument("--closing-grace-s", type=float, default=3, help="extra seconds to obtain final counters; excluded from PDR")
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--firmware-commit", required=True)
    parser.add_argument("--output", type=Path, required=True, help="new CSV path; matching .jsonl stores raw logs")
    args = parser.parse_args()
    if not 1 <= args.window_s <= 3600 or not 1 <= args.recovery_s <= 3600:
        parser.error("window/recovery durations must be 1..3600 seconds")
    if not 1 <= args.closing_grace_s <= 60:
        parser.error("closing grace must be 1..60 seconds")
    if not args.from_log and (not args.node or not args.gateway or args.node == args.gateway):
        parser.error("specify two distinct ports or --from-log")
    try:
        if args.output.exists():
            raise ValueError("output exists; choose a new evidence file")
        if args.from_log:
            raw_path = args.from_log
            records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            raw_path = args.output.with_suffix(".jsonl")
            if raw_path.exists():
                raise ValueError("raw log exists; choose a new output name")
            records, errors = capture(args.node, args.gateway, args.window_s + args.recovery_s, args.closing_grace_s)
            raw_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")
            if errors:
                raise ValueError("; ".join(errors))
        events = convert(records, args.window_s*1e6, args.test_id, args.firmware_commit, str(raw_path), recovery_us=args.recovery_s*1e6)
        with args.output.open("x", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=sorted(FIELDS["packets"]))
            writer.writeheader(); writer.writerows(events)
        print(json.dumps(analyze("packets", args.output), indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError, UnicodeError) as exc:
        parser.exit(2, f"capture rejected (inspect raw evidence): {exc}\n")


if __name__ == "__main__":
    main()
