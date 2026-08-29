"""
Shared core for Frontier X live ECG capture.

Protocol details were taken from the webapp's own bundle
(https://liveecg.frontierxapp.com/js/1.js, src/views/Livecg.vue):

  * socket   wss://liveecgwsapi.<domain>/server<1..N>?Authorization=token
  * subscribe {"action":"sendmessage","data":{userid,role:"USER",
               type:"STREAMING",server:"server<N>"}}
  * scaling  volts = raw_count * 0.0000038146972

Measured against the live stream: 125 samples per packet, one packet per
second (125 Hz). "Timestamp" is the session start and stays constant for the
whole stream; "packetNo" counts seconds from it. The server re-sends each
packet roughly three times, so duplicates must be discarded.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import numpy as np
import pandas as pd

SCALE_VOLTS_PER_COUNT = 0.0000038146972
SAMPLES_PER_PACKET = 125
SAMPLE_RATE_HZ = 125.0

# Number of WebSocket servers per domain, as hardcoded in the webapp.
SERVER_COUNT = {"frontierxapp.com": 5, "frontierxs.com": 5, "frontierxd.in": 1}

# Packet fields that describe the subject/session rather than the waveform.
META_FIELDS = (
    "userID", "userName", "age", "gender", "macID", "env",
    "activity_type", "stream", "MobileInternet", "isFromFDA",
)


def parse_stream_link(link_or_userid: str, domain_override: str | None = None) -> tuple[str, str]:
    """Return (userid, domain) from either a full liveecg link or a bare userid."""
    text = (link_or_userid or "").strip()
    if not text:
        raise ValueError("Enter a live ECG link or a numeric user id.")

    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            raise ValueError(f"Could not find a user id in the link path: {text}")
        # host is "liveecg.<domain>" -> strip the prefix to get the API domain
        domain = domain_override or re.sub(r"^liveecg\.", "", parsed.netloc)
        return parts[0], domain

    if not text.isdigit():
        raise ValueError(f"Expected a liveecg link or a numeric user id, got: {text}")
    return text, (domain_override or "frontierxapp.com")


def build_socket_url(domain: str) -> tuple[str, int]:
    server_n = random.randint(1, SERVER_COUNT.get(domain, 1))
    return f"wss://liveecgwsapi.{domain}/server{server_n}?Authorization=token", server_n


def subscribe_payload(userid: str, server_n: int) -> str:
    return json.dumps(
        {
            "action": "sendmessage",
            "data": {
                "userid": str(userid),
                "role": "USER",
                "type": "STREAMING",
                "server": f"server{server_n}",
            },
        }
    )


@dataclass
class PacketStore:
    """Thread-safe accumulator for deduplicated ECG packets."""

    packets: list[dict] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    received: int = 0       # frames seen on the wire, including repeats
    duplicates: int = 0     # repeats and out-of-order frames discarded
    missed: int = 0         # gaps in packetNo, i.e. data we never received
    last_packet_no: int | None = None
    session_timestamp: int | None = None
    last_heartrate: int | None = None
    last_packet_at: float | None = None   # monotonic clock of last accepted packet
    meta: dict = field(default_factory=dict)
    events: list[tuple[float, str]] = field(default_factory=list)

    def log(self, message: str) -> None:
        with self.lock:
            self.events.append((time.time(), message))
            del self.events[:-200]

    def add(self, pkt: dict) -> bool:
        """Ingest one packet. Returns True if it was new waveform data."""
        msg_type = pkt.get("type")
        if msg_type == "connection":
            self.log("Connection established.")
            return False
        if msg_type == "livecg-begin":
            self.log("Device started streaming.")
            with self.lock:
                self.last_packet_no = None
            return False
        if msg_type == "livecg-end":
            self.log("Device stopped streaming.")
            return False

        data = pkt.get("data")
        if not isinstance(data, list) or not data:
            return False

        packet_no = pkt.get("packetNo")
        timestamp = pkt.get("Timestamp")

        with self.lock:
            self.received += 1

            # A changed session timestamp means the device restarted the stream.
            if self.session_timestamp is not None and timestamp != self.session_timestamp:
                self.events.append((time.time(), "New streaming session detected."))
                self.last_packet_no = None
            self.session_timestamp = timestamp

            if isinstance(packet_no, int) and self.last_packet_no is not None:
                if packet_no <= self.last_packet_no:
                    self.duplicates += 1
                    return False
                if packet_no > self.last_packet_no + 1:
                    self.missed += packet_no - self.last_packet_no - 1
            if isinstance(packet_no, int):
                self.last_packet_no = packet_no

            self.packets.append(pkt)
            self.last_packet_at = time.monotonic()
            hr = pkt.get("heartrate")
            self.last_heartrate = int(hr) if isinstance(hr, (int, float)) else None
            if not self.meta:
                self.meta = {k: pkt.get(k) for k in META_FIELDS if k in pkt}
        return True

    def snapshot(self) -> list[dict]:
        with self.lock:
            return list(self.packets)

    def stats(self) -> dict:
        with self.lock:
            stale = None
            if self.last_packet_at is not None:
                stale = time.monotonic() - self.last_packet_at
            return {
                "packets": len(self.packets),
                "samples": sum(len(p["data"]) for p in self.packets),
                "received": self.received,
                "duplicates": self.duplicates,
                "missed": self.missed,
                "heartrate": self.last_heartrate,
                "session_timestamp": self.session_timestamp,
                "seconds_since_packet": stale,
                "meta": dict(self.meta),
                "events": list(self.events[-12:]),
            }

    def clear(self) -> None:
        with self.lock:
            self.packets.clear()
            self.received = self.duplicates = self.missed = 0
            self.last_packet_no = None
            self.session_timestamp = None
            self.last_heartrate = None
            self.last_packet_at = None
            self.meta.clear()
            self.events.clear()


class LiveCapture(threading.Thread):
    """Background WebSocket reader. Touches no Streamlit APIs, only PacketStore."""

    def __init__(self, userid: str, domain: str, store: PacketStore, retries: int = 20):
        super().__init__(daemon=True)
        self.userid = str(userid)
        self.domain = domain
        self.store = store
        self.retries = retries
        self._stop = threading.Event()
        self.connected = False
        self.error: str | None = None

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def run(self) -> None:
        import websocket  # imported here so the module loads without it

        attempt = 0
        while not self._stop.is_set():
            url, server_n = build_socket_url(self.domain)
            ws = None
            try:
                self.store.log(f"Connecting to server{server_n}...")
                ws = websocket.create_connection(url, timeout=20)
                ws.send(subscribe_payload(self.userid, server_n))
                self.connected = True
                self.error = None
                attempt = 0
                self.store.log(f"Subscribed as user {self.userid} on {self.domain}.")

                while not self._stop.is_set():
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise ConnectionError("socket closed by server")
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    for pkt in (msg if isinstance(msg, list) else [msg]):
                        if isinstance(pkt, dict):
                            self.store.add(pkt)
            except Exception as exc:  # noqa: BLE001 - surface anything to the UI
                self.connected = False
                if self._stop.is_set():
                    break
                attempt += 1
                self.error = str(exc)
                if attempt > self.retries:
                    self.store.log(f"Giving up after {self.retries} retries: {exc}")
                    break
                self.store.log(f"Disconnected ({exc}); reconnecting in 3s...")
                self._stop.wait(3)
            finally:
                self.connected = False
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

        self.store.log("Capture stopped.")


def packets_to_frame(packets: list[dict]) -> pd.DataFrame:
    """Flatten packets into one row per sample."""
    cols = ["packetNo", "session_start_ms", "sample_time_ms", "sample_index",
            "raw_count", "volts", "heartrate"]
    if not packets:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in cols})

    counts, packet_nos, sample_idx, sample_ms, hrs, session_ms = [], [], [], [], [], []
    step_ms = 1000.0 / SAMPLE_RATE_HZ
    for pkt in packets:
        data = pkt["data"]
        n = len(data)
        pno = pkt.get("packetNo")
        ts = pkt.get("Timestamp")
        hr = pkt.get("heartrate")
        base = (ts + pno * 1000) if isinstance(ts, int) and isinstance(pno, int) else np.nan

        counts.append(np.asarray(data, dtype="float64"))
        packet_nos.append(np.full(n, pno if pno is not None else np.nan, dtype="float64"))
        sample_idx.append(np.arange(n, dtype="int32"))
        sample_ms.append(base + np.arange(n, dtype="float64") * step_ms)
        session_ms.append(np.full(n, ts if ts is not None else np.nan, dtype="float64"))
        hrs.append(np.full(n, hr if isinstance(hr, (int, float)) else np.nan, dtype="float64"))

    raw = np.concatenate(counts)
    return pd.DataFrame(
        {
            "packetNo": np.concatenate(packet_nos),
            "session_start_ms": np.concatenate(session_ms),
            "sample_time_ms": np.concatenate(sample_ms),
            "sample_index": np.concatenate(sample_idx),
            "raw_count": raw,
            "volts": raw * SCALE_VOLTS_PER_COUNT,
            "heartrate": np.concatenate(hrs),
        }
    )


def frame_from_jsonl(text: str) -> tuple[pd.DataFrame, list[dict]]:
    """Parse a .jsonl archive back into a sample frame plus its packets."""
    packets = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pkt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(pkt, dict) and isinstance(pkt.get("data"), list) and pkt["data"]:
            packets.append(pkt)
    return packets_to_frame(packets), packets


def elapsed_seconds(df: pd.DataFrame) -> np.ndarray:
    """Seconds from the start of the recording, for plotting."""
    if df.empty:
        return np.zeros(0)
    t = df["sample_time_ms"].to_numpy(dtype="float64")
    if np.all(np.isnan(t)):
        return np.arange(len(df)) / SAMPLE_RATE_HZ
    return (t - np.nanmin(t)) / 1000.0
