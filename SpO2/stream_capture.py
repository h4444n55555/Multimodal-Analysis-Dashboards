"""
Contec CMS50E pulse-oximeter capture (SpO2, pulse rate, finger status).

The CMS50E enumerates as a virtual COM port via its Silicon Labs CP210x
bridge. This tool auto-detects that port and records either the live feed or a
stored on-device session to disk, the same way the ECG folder's
stream_capture.py records the Frontier X stream.

Two files are written per run:
  <out>.csv    one decoded row per sample: timestamp, elapsed seconds,
               SpO2 (%), pulse rate (bpm), finger-out flag, validity, and the
               raw frame as hex (so nothing decoded-away is lost)
  <out>.raw    the exact bytes read from the serial port, verbatim
               (lossless archive, in case a frame layout needs reworking)

Usage:
    pip install -r requirements.txt

    python stream_capture.py ports                 # list serial ports
    python stream_capture.py selftest              # check decoders, no device
    python stream_capture.py live [-o out] [-d secs] [--port COMx] [--protocol cms50e|cms50d+]
    python stream_capture.py download [-o out] [--port COMx] [--start "2026-08-27 22:30"]

Examples:
    python stream_capture.py live
    python stream_capture.py live -d 600 -o morning
    python stream_capture.py download -o last_night --start "2026-08-27 22:30"
"""
import argparse
import csv
import sys
import time
from datetime import datetime, timedelta

import spo2_core as core

# Columns written to the CSV, per protocol. Defined once in spo2_core so the
# CLI and the dashboard always agree on the layout.
COLUMNS = core.CSV_COLUMNS


def resolve_port(args) -> str:
    if args.port:
        return args.port
    port = core.autodetect_port()   # raises with guidance if 0 or >1 CP210x
    print(f"Auto-detected CP210x port: {port}")
    return port


def make_writer(csv_file, columns):
    writer = csv.DictWriter(csv_file, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    return writer


def cmd_ports(args) -> int:
    ports = core.list_serial_ports()
    if not ports:
        print("No serial ports found (install pyserial and plug in the device).")
        return 1
    print("Serial ports:")
    for p in ports:
        vid = f"{p['vid']:04x}" if p["vid"] is not None else "----"
        pid = f"{p['pid']:04x}" if p["pid"] is not None else "----"
        tag = "  <- CP210x (likely the CMS50E)" if p["is_cp210x"] else ""
        print(f"  {p['device']:<10} [{vid}:{pid}] {p['description']}{tag}")
    return 0


def cmd_selftest(args) -> int:
    core.run_selftest()
    return 0


def cmd_live(args) -> int:
    port = resolve_port(args)
    out = args.output or f"spo2_live_{int(time.time())}"
    if out.endswith(".csv"):
        out = out[:-4]
    cols = COLUMNS["cms50e"] if args.protocol == "cms50e" else COLUMNS["cms50d+_live"]

    deadline = (time.monotonic() + args.duration) if args.duration else None
    stop_flag = (lambda: deadline is not None and time.monotonic() >= deadline)

    raw_file = open(f"{out}.raw", "wb")
    csv_file = open(f"{out}.csv", "w", newline="")
    writer = make_writer(csv_file, cols)
    dev = core.CMS50(port, protocol=args.protocol, raw_sink=raw_file)

    print(f"Connecting to {port} ({args.protocol}) ...")
    print(f"Writing {out}.csv / {out}.raw   (Ctrl+C to stop)")
    n = 0
    start = None
    try:
        dev.connect()
        for sample in dev.stream_live(stop_flag=stop_flag):
            now = time.time()
            if start is None:
                start = now
            sample["sample_index"] = n
            sample["elapsed_s"] = round(now - start, 3)
            sample["time_iso"] = datetime.fromtimestamp(now).isoformat(timespec="milliseconds")
            writer.writerow(sample)
            csv_file.flush()
            n += 1
            if n % 25 == 0:
                s = dev.stats
                print(f"\r{n} samples  SpO2={s.last_spo2}%  Pulse={s.last_pulse} bpm  "
                      f"(valid {s.valid}/{s.frames})", end="")
                sys.stdout.flush()
            if stop_flag():
                break
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as exc:  # surface connection/parse errors plainly
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    finally:
        dev.close()
        csv_file.close()
        raw_file.close()
    print(f"\nDone. {n} samples, {dev.stats.bytes_read} raw bytes -> {out}.csv / {out}.raw")
    return 0


def cmd_download(args) -> int:
    port = resolve_port(args)
    out = args.output or f"spo2_session_{int(time.time())}"
    if out.endswith(".csv"):
        out = out[:-4]
    key = "cms50e" if args.protocol == "cms50e" else "cms50d+_recorded"
    cols = COLUMNS[key]

    start_dt = None
    if args.start:
        try:
            start_dt = _parse_datetime(args.start)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    raw_file = open(f"{out}.raw", "wb")
    csv_file = open(f"{out}.csv", "w", newline="")
    writer = make_writer(csv_file, cols)
    dev = core.CMS50(port, protocol=args.protocol, raw_sink=raw_file)

    print(f"Connecting to {port} ({args.protocol}) ...")
    print("Requesting stored session (please wait) ...")
    n = 0
    try:
        dev.connect()
        for sample in dev.download():
            if start_dt is not None:
                t = start_dt + timedelta(seconds=sample["elapsed_s"])
                sample["time_iso"] = t.isoformat(timespec="seconds")
            writer.writerow(sample)
            csv_file.flush()
            n += 1
            expected = getattr(dev, "expected_points", None)
            tail = f" of ~{expected}" if expected else ""
            if n % 20 == 0:
                print(f"\rDownloaded {n}{tail} points", end="")
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    finally:
        dev.close()
        csv_file.close()
        raw_file.close()
    print(f"\nDone. {n} points -> {out}.csv / {out}.raw")
    return 0


def _parse_datetime(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date/time: {s!r} (try 'YYYY-MM-DD HH:MM')")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture SpO2/pulse data from a Contec CMS50E pulse oximeter."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--port", help="Serial port (default: auto-detect the CP210x)")
        p.add_argument("--protocol", choices=["cms50e", "cms50d+"], default="cms50e",
                       help="Device protocol (default: cms50e, matches SpO2 Assistant)")

    p_live = sub.add_parser("live", help="Record the live feed")
    add_common(p_live)
    p_live.add_argument("-o", "--output", help="Output prefix (default: spo2_live_<epoch>)")
    p_live.add_argument("-d", "--duration", type=float, default=None,
                        help="Stop after N seconds (default: until Ctrl+C)")
    p_live.set_defaults(func=cmd_live)

    p_dl = sub.add_parser("download", help="Download the stored on-device session")
    add_common(p_dl)
    p_dl.add_argument("-o", "--output", help="Output prefix (default: spo2_session_<epoch>)")
    p_dl.add_argument("--start", help="Recording start time for absolute timestamps, "
                                      "e.g. '2026-08-27 22:30'")
    p_dl.set_defaults(func=cmd_download)

    sub.add_parser("ports", help="List serial ports").set_defaults(func=cmd_ports)
    sub.add_parser("selftest", help="Validate decoders without a device").set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
