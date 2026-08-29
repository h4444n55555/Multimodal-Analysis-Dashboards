"""
Frontier X2 live ECG capture.

Connects to the same WebSocket the liveecg.frontierxapp.com webapp uses and
saves the raw ECG samples to disk for as long as the stream link stays live.

The stream is 125 Hz: one packet per second carrying 125 samples. The server
sends each packet about three times over, so duplicates and out-of-order
packets are discarded the same way the webapp discards them.

Two files are written:
  <out>.csv    one row per sample: packet no, session start, derived sample
               wall-clock (ms), sample index, raw ADC count, volts, heart rate
  <out>.jsonl  one line per unique packet, exactly as the server sent it
               (lossless archive, in case the CSV layout needs reworking later)

Usage:
    pip install -r requirements.txt
    python stream_capture.py <stream_link_or_userid> [-o out_prefix] [-d seconds]

Examples:
    python stream_capture.py https://liveecg.frontierxapp.com/6005748/Hans
    python stream_capture.py 6005748 --domain frontierxapp.com
    python stream_capture.py https://liveecg.frontierxapp.com/6005748/Hans -d 600
"""
import argparse
import csv
import json
import random
import re
import sys
import time
from urllib.parse import urlparse

import websocket

# Matches the webapp's ADC -> volts conversion (src/views/Livecg.vue).
SCALE_VOLTS_PER_COUNT = 0.0000038146972

# Measured against the live stream: 125 samples per packet, one packet per second.
# "Timestamp" is the session start (constant for the whole stream) and packetNo
# counts seconds from it, so a sample's wall clock is derivable from both.
SAMPLES_PER_PACKET = 125
SAMPLE_RATE_HZ = 125

# Number of WebSocket servers per domain, as hardcoded in the webapp.
SERVER_COUNT = {"frontierxapp.com": 5, "frontierxs.com": 5, "frontierxd.in": 1}


def parse_stream_link(link_or_userid, domain_override):
    """Return (userid, domain) from either a full liveecg link or a bare userid."""
    if link_or_userid.startswith("http://") or link_or_userid.startswith("https://"):
        parsed = urlparse(link_or_userid)
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            raise ValueError(f"Could not find a user id in the link path: {link_or_userid}")
        # host is "liveecg.<domain>" -> strip the "liveecg." prefix to get the API domain
        domain = domain_override or re.sub(r"^liveecg\.", "", parsed.netloc)
        return parts[0], domain

    return link_or_userid, (domain_override or "frontierxapp.com")


def build_socket_url(domain):
    server_n = random.randint(1, SERVER_COUNT.get(domain, 1))
    return f"wss://liveecgwsapi.{domain}/server{server_n}?Authorization=token", server_n


class Capture:
    """Writes ECG packets to a CSV of samples plus a raw JSONL archive."""

    def __init__(self, csv_path, jsonl_path):
        self.csv_file = open(csv_path, "w", newline="")
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow(
            [
                "packetNo",
                "session_start_ms",
                "sample_time_ms",
                "sample_index",
                "raw_count",
                "volts",
                "heartrate",
            ]
        )
        self.jsonl_file = open(jsonl_path, "w", encoding="utf-8")

        self.packets = 0
        self.samples = 0
        self.dropped = 0  # gaps in packetNo, i.e. samples we never received
        self.last_packet_no = None
        self.last_timestamp = None

    def handle(self, pkt):
        """Process one decoded packet. Returns False when the stream has ended."""
        if not isinstance(pkt, dict):
            return True

        msg_type = pkt.get("type")
        if msg_type == "connection":
            print("Connection established.")
            return True
        if msg_type == "livecg-begin":
            print("Streaming started.")
            self.last_packet_no = None
            return True
        if msg_type == "livecg-end":
            print("Streaming stopped by the device.")
            return False

        if "data" not in pkt or not isinstance(pkt["data"], list) or not pkt["data"]:
            return True

        packet_no = pkt.get("packetNo")
        timestamp = pkt.get("Timestamp")

        # A changed session timestamp means the device restarted the stream.
        if self.last_timestamp is not None and timestamp != self.last_timestamp:
            print(f"New streaming session detected (timestamp {timestamp}).")
            self.last_packet_no = None
        self.last_timestamp = timestamp

        # Drop replays / out-of-order packets the way the webapp does.
        if (
            self.last_packet_no is not None
            and isinstance(packet_no, int)
            and packet_no <= self.last_packet_no
        ):
            return True
        if (
            self.last_packet_no is not None
            and isinstance(packet_no, int)
            and packet_no > self.last_packet_no + 1
        ):
            self.dropped += packet_no - self.last_packet_no - 1
        if isinstance(packet_no, int):
            self.last_packet_no = packet_no

        # Past the dedupe check, so this packet is new: archive it verbatim.
        self.jsonl_file.write(json.dumps(pkt, separators=(",", ":")) + "\n")

        hr = pkt.get("heartrate")
        self.packets += 1
        # packetNo counts seconds since session start; samples are evenly spaced.
        base_ms = None
        if isinstance(timestamp, int) and isinstance(packet_no, int):
            base_ms = timestamp + packet_no * 1000
        for i, count in enumerate(pkt["data"]):
            sample_ms = "" if base_ms is None else round(base_ms + i * 1000 / SAMPLE_RATE_HZ)
            self.writer.writerow(
                [
                    packet_no,
                    timestamp,
                    sample_ms,
                    i,
                    count,
                    count * SCALE_VOLTS_PER_COUNT,
                    hr,
                ]
            )
            self.samples += 1
        self.csv_file.flush()
        self.jsonl_file.flush()

        if self.packets % 20 == 0:
            print(
                f"{self.packets} packets / {self.samples} samples logged, "
                f"last HR={hr}, missed packets={self.dropped}"
            )
        return True

    def close(self):
        self.csv_file.close()
        self.jsonl_file.close()


def capture(userid, domain, out_prefix, duration, retries):
    cap = Capture(f"{out_prefix}.csv", f"{out_prefix}.jsonl")
    start = time.monotonic()
    attempt = 0
    stop = False

    try:
        while not stop:
            url, server_n = build_socket_url(domain)
            print(f"Connecting to {url}")
            try:
                ws = websocket.create_connection(url, timeout=30)
            except Exception as e:
                attempt += 1
                if attempt > retries:
                    print(f"Could not connect after {retries} retries: {e}", file=sys.stderr)
                    break
                print(f"Connect failed ({e}); retrying in 3s...")
                time.sleep(3)
                continue

            attempt = 0
            ws.send(
                json.dumps(
                    {
                        "action": "sendmessage",
                        "data": {
                            "userid": userid,
                            "role": "USER",
                            "type": "STREAMING",
                            "server": f"server{server_n}",
                        },
                    }
                )
            )
            print(f"Subscribed as user {userid} on {domain}. Writing {out_prefix}.csv / .jsonl")
            print("Press Ctrl+C to stop.")

            try:
                while True:
                    if duration is not None and (time.monotonic() - start) >= duration:
                        print(f"Reached duration limit of {duration}s.")
                        stop = True
                        break
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        break  # socket closed
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    for pkt in (msg if isinstance(msg, list) else [msg]):
                        if not cap.handle(pkt):
                            stop = True
                    if stop:
                        break
            except (websocket.WebSocketConnectionClosedException, ConnectionError) as e:
                print(f"Socket closed ({e}); reconnecting...")
            finally:
                try:
                    ws.close()
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        cap.close()

    print(
        f"Done. {cap.packets} packets, {cap.samples} samples, {cap.dropped} missed packets "
        f"-> {out_prefix}.csv"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Capture raw ECG data from a Frontier X2 live stream link."
    )
    parser.add_argument(
        "stream",
        help="Live ECG share link (e.g. https://liveecg.frontierxapp.com/6005748/Hans) or a bare userid",
    )
    parser.add_argument("-o", "--output", help="Output path prefix (default: ecg_<userid>_<epoch>)")
    parser.add_argument(
        "-d", "--duration", type=float, default=None,
        help="Stop after N seconds (default: run until Ctrl+C or the stream ends)",
    )
    parser.add_argument("--domain", help="Override the API domain (default: inferred from the link)")
    parser.add_argument(
        "--retries", type=int, default=5, help="Reconnect attempts before giving up (default: 5)"
    )
    args = parser.parse_args()

    try:
        userid, domain = parse_stream_link(args.stream, args.domain)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_prefix = args.output or f"ecg_{userid}_{int(time.time())}"
    if out_prefix.endswith(".csv"):
        out_prefix = out_prefix[:-4]
    capture(userid, domain, out_prefix, args.duration, args.retries)


if __name__ == "__main__":
    main()
