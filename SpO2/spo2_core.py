"""
Shared core for Contec CMS50E (CMS50E/W family) pulse-oximeter capture.

The CMS50E shows up as a virtual COM port through its Silicon Labs CP210x
USB-to-serial bridge (the same driver SpO2 Assistant uses). Two protocol
generations exist across the CMS50 range; both are supported here:

  * "cms50e"  (default) - the CMS50E/W protocol, as used by SpO2 Assistant.
        115200 baud, 8N1, software flow control (xonxoff). The host sends
        9-byte 0x7d-prefixed commands; the device answers with frames that
        start on a 0x01 sync byte. Payload bytes carry bit 7 set, so 0x01
        never appears inside a frame and is a safe delimiter. Yields
        SpO2 + pulse rate + finger status at ~1 Hz. Same frame is used for
        the live feed and for downloading a stored session.
  * "cms50d+" (fallback) - the older CMS50D+ protocol.
        19200 baud, 8 data bits, ODD parity, xonxoff. Live frames are 5 bytes
        delimited by bit 7 on the first byte and DO carry the ~60 Hz
        plethysmograph waveform. Recorded download uses a 0xf5/0xf2 handshake
        and 3-byte samples at 1 Hz.

Protocol details were read out of two established reverse-engineered clients
rather than guessed, and the decoders are checked against their documented
byte->value vectors in run_selftest():
  * tobac/cms50ew        (CMS50E/W: serial params, command set, frame layout)
  * atbrask/CMS50Dplus   (CMS50D+: live 5-byte + recorded 3-byte layout)

pyserial is imported lazily (inside connect()), so this module and the
self-test import fine on a machine without pyserial or without a device.
"""
from __future__ import annotations

import csv
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

# Silicon Labs CP210x USB-to-UART bridge (the CMS50E's USB id).
CP210X_VID = 0x10C4
CP210X_PID = 0xEA60

# --- CMS50E/W protocol (default) ------------------------------------------
# 9-byte, 0x7d-prefixed, 0x80-padded commands.
CMD_HELLO1 = b"\x7d\x81\xa7\x80\x80\x80\x80\x80\x80"
CMD_HELLO2 = b"\x7d\x81\xa2\x80\x80\x80\x80\x80\x80"
CMD_HELLO3 = b"\x7d\x81\xa0\x80\x80\x80\x80\x80\x80"
CMD_GET_LIVE_DATA = b"\x7d\x81\xa1\x80\x80\x80\x80\x80\x80"
CMD_GET_SESSION_COUNT = b"\x7d\x81\xa3\x80\x80\x80\x80\x80\x80"
CMD_GET_SESSION_DURATION = b"\x7d\x81\xa4\x80\x80\x80\x80\x80\x80"
CMD_GET_SESSION_DATA = b"\x7d\x81\xa6\x80\x80\x80\x80\x80\x80"

FRAME_LEN_B = 9          # bytes per CMS50E/W frame, including the 0x01 sync
SYNC_B = 0x01
RECORDED_INTERVAL_B = 3.0  # a stored CMS50E/W sample covers 3 seconds

# --- CMS50D+ protocol (fallback) ------------------------------------------
FRAME_LEN_DPLUS = 5
RECORDED_INTERVAL_DPLUS = 1.0

# SpO2 / pulse "no reading" sentinels the CMS50 devices emit when a finger is
# out or the signal is lost. Left in the data (never dropped) but flagged.
SPO2_INVALID = 127
PULSE_INVALID = 255

# Canonical CSV column order per protocol, shared by the CLI and the dashboard
# so the two never drift. "recorded" is the stored-session download layout.
CSV_COLUMNS = {
    "cms50e": ["time_iso", "elapsed_s", "sample_index", "spo2", "pulse_rate",
               "pleth", "pleth2", "finger_out", "valid", "status1", "status2",
               "frame_hex"],
    "cms50d+_live": ["time_iso", "elapsed_s", "sample_index", "spo2", "pulse_rate",
                     "pleth", "signal_strength", "searching", "probe_error",
                     "bar_graph", "finger_out", "valid", "frame_hex"],
    "cms50d+_recorded": ["time_iso", "elapsed_s", "sample_index", "spo2",
                         "pulse_rate", "finger_out", "valid", "frame_hex"],
}


def live_columns(protocol: str) -> list[str]:
    """CSV columns for a *live* capture in the given protocol."""
    return CSV_COLUMNS["cms50e"] if protocol == "cms50e" else CSV_COLUMNS["cms50d+_live"]


# ==========================================================================
# Port discovery
# ==========================================================================
def list_serial_ports() -> list[dict]:
    """Return every serial port with its USB ids. Empty list if none/pyserial missing."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    ports = []
    for p in list_ports.comports():
        ports.append(
            {
                "device": p.device,
                "description": p.description or "",
                "vid": p.vid,
                "pid": p.pid,
                "is_cp210x": p.vid == CP210X_VID and p.pid == CP210X_PID,
            }
        )
    return ports


def find_cp210x_ports() -> list[str]:
    """Devices whose USB id matches the CP210x bridge, most likely the oximeter."""
    return [p["device"] for p in list_serial_ports() if p["is_cp210x"]]


def autodetect_port() -> str:
    """Return the single CP210x port, or raise with guidance if 0 or >1 match."""
    cp = find_cp210x_ports()
    if len(cp) == 1:
        return cp[0]
    all_ports = list_serial_ports()
    if not all_ports:
        raise RuntimeError(
            "No serial ports found. Is the CMS50E plugged in and the CP210x "
            "driver installed? (pip install pyserial to enable detection.)"
        )
    listing = "\n".join(
        f"  {p['device']}  {p['description']}"
        f"{'  <- CP210x' if p['is_cp210x'] else ''}"
        for p in all_ports
    )
    if not cp:
        raise RuntimeError(
            "Could not find a CP210x port automatically. Pass --port explicitly.\n"
            f"Available ports:\n{listing}"
        )
    raise RuntimeError(
        "Multiple CP210x ports found; pass --port to pick one.\n" f"Available ports:\n{listing}"
    )


# ==========================================================================
# Pure decoders (no I/O) - validated in run_selftest()
# ==========================================================================
def decode_frame_cms50e(frame: list[int]) -> dict:
    """Decode one 9-byte CMS50E/W frame (frame[0] is the 0x01 sync byte).

    Byte layout confirmed against a real CMS50E capture (2026-08-27, firmware
    as shipped, ~58 Hz live feed):
      [0] 0x01 sync
      [1] status/flags   (bit 7 always set; 0xE0 with a finger in)
      [2] status/flags   (one bit toggles once per heartbeat)
      [3] plethysmograph waveform sample, 7-bit (0..127) -- the ~58 Hz PPG,
          a clean systolic-upstroke / diastolic-decay pulse wave
      [4] secondary pulsatile byte, 7-bit (small-amplitude, tracks the beat;
          semantics unconfirmed -- see README, preserved as `pleth2`)
      [5] pulse rate, bpm  (low 7 bits)
      [6] SpO2, %          (low 7 bits; 127 = no reading / finger out)
      [7],[8] 0xFF padding with a finger in

    NOTE: the tobac/cms50ew reference treats byte 3 as a finger flag
    (== 0xC0 -> finger out). On this unit byte 3 is the waveform, and 0xC0
    (192) is simply one waveform level, so that test produces false finger-out
    flags. Finger-out is instead taken from the SpO2 sentinel (127), which is
    the value CMS50 devices emit when no reading is available.
    """
    if len(frame) != FRAME_LEN_B or frame[0] != SYNC_B:
        raise ValueError(f"Invalid CMS50E frame: {frame}")
    spo2 = frame[6] & 0x7F
    pulse = frame[5] & 0x7F
    finger_out = spo2 == SPO2_INVALID
    return {
        "spo2": spo2,
        "pulse_rate": pulse,
        "pleth": frame[3] & 0x7F,      # ~58 Hz plethysmograph waveform, 0..127
        "pleth2": frame[4] & 0x7F,     # secondary pulsatile byte (see docstring)
        "finger_out": finger_out,
        "status1": frame[1],           # raw status/flag bytes, kept for analysis
        "status2": frame[2],
        "valid": not finger_out,
        # Full frame kept as hex so any byte we don't decode is never lost.
        "frame_hex": bytes(frame).hex(),
    }


def decode_live_cms50dplus(frame: list[int]) -> dict:
    """Decode one 5-byte CMS50D+ live frame (frame[0] has bit 7 set)."""
    if len(frame) != FRAME_LEN_DPLUS or not (frame[0] & 0x80):
        raise ValueError(f"Invalid CMS50D+ live frame: {frame}")
    pulse = ((frame[2] & 0x40) << 1) | (frame[3] & 0x7F)
    spo2 = frame[4] & 0x7F
    return {
        "spo2": spo2,
        "pulse_rate": pulse,
        "pleth": frame[1] & 0x7F,          # plethysmograph waveform, 0..127
        "signal_strength": frame[0] & 0x0F,
        "finger_out": bool(frame[0] & 0x10),
        "dropping_spo2": bool(frame[0] & 0x20),
        "searching": bool(frame[2] & 0x20),
        "probe_error": bool(frame[2] & 0x10),
        "bar_graph": frame[2] & 0x0F,
        "valid": spo2 != SPO2_INVALID and not (frame[0] & 0x10),
        "frame_hex": bytes(frame).hex(),
    }


def decode_recorded_cms50dplus(frame: list[int]) -> dict:
    """Decode one 3-byte CMS50D+ recorded sample."""
    if len(frame) != 3 or frame[0] & 0xFE != 0xF0 or not (frame[1] & 0x80) or (frame[2] & 0x80):
        raise ValueError(f"Invalid CMS50D+ recorded frame: {frame}")
    pulse = ((frame[0] & 0x01) << 7) | (frame[1] & 0x7F)
    spo2 = frame[2] & 0x7F
    return {
        "spo2": spo2,
        "pulse_rate": pulse,
        "finger_out": spo2 == SPO2_INVALID,
        "valid": spo2 != SPO2_INVALID,
        "frame_hex": bytes(frame).hex(),
    }


# ==========================================================================
# Stateful frame parsers - fed one raw byte at a time
# ==========================================================================
class _ParserCMS50E:
    """Reassembles the CMS50E/W byte stream into 9-byte frames."""

    def __init__(self):
        self.buf: list[int] = []

    def push(self, byte: int) -> dict | None:
        if byte == SYNC_B:
            self.buf = [SYNC_B]          # (re)start of a frame
            return None
        if self.buf:                     # only collect once synced
            self.buf.append(byte)
            if len(self.buf) == FRAME_LEN_B:
                frame, self.buf = self.buf, []
                return decode_frame_cms50e(frame)
        return None


class _ParserCMS50Dplus:
    """Reassembles the CMS50D+ byte stream into 5-byte live frames."""

    def __init__(self):
        self.buf: list[int] = []

    def push(self, byte: int) -> dict | None:
        result = None
        if byte & 0x80:                  # bit 7 marks a new frame
            if len(self.buf) == FRAME_LEN_DPLUS and (self.buf[0] & 0x80):
                result = decode_live_cms50dplus(self.buf)
            self.buf = []
        if len(self.buf) < FRAME_LEN_DPLUS:
            self.buf.append(byte)
        return result


# ==========================================================================
# Device
# ==========================================================================
@dataclass
class CaptureStats:
    frames: int = 0
    valid: int = 0
    invalid: int = 0
    bytes_read: int = 0
    last_spo2: int | None = None
    last_pulse: int | None = None
    started_at: float | None = None


class CMS50:
    """A CMS50E/CMS50D+ over a serial (COM) port. Serial I/O only, no UI."""

    def __init__(self, port: str, protocol: str = "cms50e", raw_sink=None):
        if protocol not in ("cms50e", "cms50d+"):
            raise ValueError("protocol must be 'cms50e' or 'cms50d+'")
        self.port = port
        self.protocol = protocol
        self.raw_sink = raw_sink          # optional binary file for lossless raw bytes
        self.conn = None
        self.stats = CaptureStats()

    # -- connection --------------------------------------------------------
    def connect(self) -> None:
        import serial  # lazy: module imports fine without pyserial installed

        if self.protocol == "cms50e":
            self.conn = serial.Serial(
                port=self.port, baudrate=115200, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                timeout=0.1, xonxoff=True,
            )
        else:
            self.conn = serial.Serial(
                port=self.port, baudrate=19200, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_ODD, stopbits=serial.STOPBITS_ONE,
                timeout=5, xonxoff=True,
            )

    def close(self) -> None:
        if self.conn is not None and self.conn.is_open:
            self.conn.close()

    def _send(self, cmd: bytes) -> None:
        self.conn.write(cmd)
        self.conn.flush()

    def _read_byte(self) -> int | None:
        """Read one byte; tee it to the raw sink. None on timeout (no data)."""
        char = self.conn.read(1)
        if not char:
            return None
        if self.raw_sink is not None:
            self.raw_sink.write(char)
        self.stats.bytes_read += 1
        return char[0]

    def _drain(self) -> list[int]:
        """Read whatever the device has queued right now (until a read times out)."""
        out = []
        while True:
            b = self._read_byte()
            if b is None:
                break
            out.append(b)
        return out

    # -- CMS50E/W handshake ------------------------------------------------
    def _initiate(self) -> bool:
        self._send(CMD_HELLO1)
        if not self._drain():
            return False
        self._send(CMD_HELLO2)
        self._send(CMD_HELLO3)
        self._drain()
        return True

    def has_stored_session(self) -> bool:
        self._send(CMD_GET_SESSION_COUNT)
        resp = self._drain()
        return len(resp) > 3 and (resp[3] & 0x7F) == 1

    def stored_duration_seconds(self) -> float | None:
        """Recording length in seconds (SleepyHead decode), or None if unknown."""
        self._send(CMD_GET_SESSION_DURATION)
        r = [b & 0x7F for b in self._drain()]
        if len(r) < 7:
            return None
        duration = (r[1] & 0x04) << 5
        duration |= r[4]
        duration |= (r[5] | ((r[1] & 0x08) << 4)) << 8
        duration |= (r[6] | ((r[1] & 0x10) << 3)) << 16
        return duration / 2.0

    # -- live streaming ----------------------------------------------------
    def stream_live(self, stop_flag=None):
        """
        Yield decoded live samples until stop_flag() is true (or forever).

        stop_flag: optional zero-arg callable returning True to stop cleanly.
        The CMS50E stream occasionally stalls (~every 30 s); we re-issue the
        handshake and keep going, matching the reference client's behaviour.
        """
        self.stats.started_at = time.monotonic()
        parser = _ParserCMS50E() if self.protocol == "cms50e" else _ParserCMS50Dplus()

        def stopping() -> bool:
            return bool(stop_flag and stop_flag())

        while not stopping():
            if self.protocol == "cms50e":
                if not self._initiate():
                    time.sleep(0.5)
                    continue
                self._send(CMD_GET_LIVE_DATA)

            stall = 0
            while not stopping():
                byte = self._read_byte()
                if byte is None:
                    stall += 1
                    # ~3 s of silence -> re-handshake (cms50e) or bail (cms50d+)
                    if stall > 30:
                        if self.protocol == "cms50e":
                            break
                        return
                    continue
                stall = 0
                sample = parser.push(byte)
                if sample is not None:
                    self._record(sample)
                    yield sample

    def _record(self, sample: dict) -> None:
        self.stats.frames += 1
        if sample.get("valid"):
            self.stats.valid += 1
            self.stats.last_spo2 = sample["spo2"]
            self.stats.last_pulse = sample["pulse_rate"]
        else:
            self.stats.invalid += 1

    # -- stored-session download ------------------------------------------
    def download(self):
        """Yield decoded samples from the stored on-device recording."""
        if self.protocol == "cms50e":
            yield from self._download_cms50e()
        else:
            yield from self._download_cms50dplus()

    def _download_cms50e(self):
        if not self._initiate():
            raise RuntimeError("Device did not respond to the wake-up handshake.")
        if not self.has_stored_session():
            raise RuntimeError("No stored session on the device.")
        self.duration_s = self.stored_duration_seconds()
        self.expected_points = round(self.duration_s / RECORDED_INTERVAL_B) if self.duration_s else None
        self._send(CMD_GET_SESSION_DATA)

        parser = _ParserCMS50E()
        idx = 0
        empty = 0
        while True:
            byte = self._read_byte()
            if byte is None:
                empty += 1
                if empty > 20:            # sustained silence -> end of session
                    return
                continue
            empty = 0
            sample = parser.push(byte)
            if sample is not None:
                sample["sample_index"] = idx
                sample["elapsed_s"] = idx * RECORDED_INTERVAL_B
                idx += 1
                self._record(sample)
                yield sample

    def _download_cms50dplus(self):
        # Confirm the stream is alive, then request the recorded buffer.
        for _ in range(10):
            if self._read_byte() is None:
                break
        self.conn.reset_input_buffer()
        self._send(b"\xf5\xf5")
        self.conn.flush()

        def expect(val: int) -> bool:
            while True:
                b = self._read_byte()
                if b is None:
                    return False
                if b == val:
                    return True

        for _ in range(3):
            if not (expect(0xF2) and expect(0x80) and expect(0x00)):
                raise RuntimeError("No valid preamble from device during download.")
        la, lb, lc = self._read_byte(), self._read_byte(), self._read_byte()
        if None in (la, lb, lc) or not (la & 0x80) or not (lb & 0x80) or (lc & 0x80):
            raise RuntimeError("Corrupted length header during download.")
        length = (((la & 0x7F) << 14) | ((lb & 0x7F) << 7) | lc) + 1
        self.expected_points = length // 3
        try:
            frame, idx = [], 0
            for i in range(length):
                b = self._read_byte()
                if b is None:
                    raise RuntimeError("Timeout during download.")
                frame.append(b)
                if len(frame) == 3:
                    sample = decode_recorded_cms50dplus(frame)
                    sample["sample_index"] = idx
                    sample["elapsed_s"] = idx * RECORDED_INTERVAL_DPLUS
                    idx += 1
                    self._record(sample)
                    yield sample
                    frame = []
        finally:
            self._send(b"\xf6\xf6\xf6")   # tell the device to stop


# ==========================================================================
# Dashboard support: threaded capture, live store, device probe, storage
# ==========================================================================
class SpO2Store:
    """Thread-safe accumulator for a live capture.

    Holds every decoded sample (the on-disk CSV is the real archive) plus
    incrementally-maintained running stats, so the dashboard's status strip can
    read a cheap summary every second without touching the full sample list.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.rows: list[dict] = []
        self.frames = 0
        self.valid = 0
        self.finger_out_frames = 0
        self.sum_spo2 = 0
        self.sum_pulse = 0
        self.min_spo2: int | None = None
        self.max_spo2: int | None = None
        self.min_pulse: int | None = None
        self.max_pulse: int | None = None
        self.last: dict | None = None
        self.last_valid: dict | None = None
        self.started_at: float | None = None
        self.last_at: float | None = None
        self.events: list[tuple[float, str]] = []

    def log(self, message: str) -> None:
        with self.lock:
            self.events.append((time.time(), message))
            del self.events[:-200]

    def add(self, s: dict) -> None:
        with self.lock:
            self.rows.append(s)
            self.frames += 1
            now = time.monotonic()
            if self.started_at is None:
                self.started_at = now
            self.last_at = now
            self.last = s
            if s.get("valid"):
                self.valid += 1
                self.last_valid = s
                sp, pu = s["spo2"], s["pulse_rate"]
                self.sum_spo2 += sp
                self.sum_pulse += pu
                self.min_spo2 = sp if self.min_spo2 is None else min(self.min_spo2, sp)
                self.max_spo2 = sp if self.max_spo2 is None else max(self.max_spo2, sp)
                self.min_pulse = pu if self.min_pulse is None else min(self.min_pulse, pu)
                self.max_pulse = pu if self.max_pulse is None else max(self.max_pulse, pu)
            else:
                self.finger_out_frames += 1

    def recent(self, n: int) -> list[dict]:
        """The last n samples, for the optional live waveform view."""
        with self.lock:
            return self.rows[-n:]

    def snapshot(self) -> list[dict]:
        with self.lock:
            return list(self.rows)

    def stats(self) -> dict:
        with self.lock:
            stale = None if self.last_at is None else time.monotonic() - self.last_at
            last = self.last or {}
            # "Finger in" means the most recent sample is a real reading and
            # fresh: with a finger out this unit stops streaming, so a stale
            # last-sample is itself the finger-out/disconnect signal.
            finger_in = bool(last.get("valid")) and (stale is not None and stale < 2.0)
            return {
                "frames": self.frames,
                "valid": self.valid,
                "finger_out_frames": self.finger_out_frames,
                "valid_pct": (100.0 * self.valid / self.frames) if self.frames else None,
                "last_spo2": (self.last_valid or {}).get("spo2"),
                "last_pulse": (self.last_valid or {}).get("pulse_rate"),
                "last_pleth": last.get("pleth"),
                "mean_spo2": (self.sum_spo2 / self.valid) if self.valid else None,
                "min_spo2": self.min_spo2,
                "mean_pulse": (self.sum_pulse / self.valid) if self.valid else None,
                "min_pulse": self.min_pulse,
                "max_pulse": self.max_pulse,
                "duration_s": (self.last_at - self.started_at) if self.started_at else 0.0,
                "seconds_since_sample": stale,
                "finger_in": finger_in,
                "events": list(self.events[-12:]),
            }

    def clear(self) -> None:
        with self.lock:
            self.__init__()


class SpO2LiveCapture(threading.Thread):
    """Background reader: streams the device into a SpO2Store and to disk.

    Touches no UI. Writes the decoded CSV and the verbatim raw archive as it
    goes (crash-safe), so a session is preserved even if the app is killed.
    """

    def __init__(self, port: str, protocol: str, store: SpO2Store,
                 csv_path: str, raw_path: str):
        super().__init__(daemon=True)
        self.port = port
        self.protocol = protocol
        self.store = store
        self.csv_path = csv_path
        self.raw_path = raw_path
        self._stop = threading.Event()
        self.connected = False
        self.error: str | None = None
        self.samples = 0

    def stop(self) -> None:
        self._stop.set()

    def stopping(self) -> bool:
        return self._stop.is_set()

    def run(self) -> None:
        columns = live_columns(self.protocol)
        raw_file = open(self.raw_path, "wb")
        csv_file = open(self.csv_path, "w", newline="")
        writer = csv.DictWriter(csv_file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        dev = CMS50(self.port, protocol=self.protocol, raw_sink=raw_file)
        start = None
        try:
            dev.connect()
            self.connected = True
            self.store.log(f"Connected to {self.port} ({self.protocol}).")
            for sample in dev.stream_live(stop_flag=self.stopping):
                now = time.time()
                if start is None:
                    start = now
                sample["sample_index"] = self.samples
                sample["elapsed_s"] = round(now - start, 3)
                sample["time_iso"] = datetime.fromtimestamp(now).isoformat(timespec="milliseconds")
                writer.writerow(sample)
                if self.samples % 50 == 0:
                    csv_file.flush()
                self.store.add(sample)
                self.samples += 1
        except Exception as exc:  # surface to the UI, never crash the thread silently
            self.error = str(exc)
            self.store.log(f"Capture error: {exc}")
        finally:
            self.connected = False
            try:
                csv_file.flush()
                csv_file.close()
                raw_file.close()
            except Exception:
                pass
            dev.close()
            self.store.log("Capture stopped.")


def probe_device(port: str, protocol: str = "cms50e", seconds: float = 3.0) -> dict:
    """Briefly read the device to report readiness *before* starting a session.

    Returns a dict with reachable / finger_in booleans and a human message.
    This is what powers the dashboard's "is the SpO2 connected?" pre-check.
    """
    result = {"port": port, "reachable": False, "finger_in": False,
              "frames": 0, "valid": 0, "last_spo2": None, "last_pulse": None,
              "message": ""}
    dev = CMS50(port, protocol=protocol)
    try:
        dev.connect()
    except Exception as exc:
        result["message"] = f"Could not open {port}: {exc}"
        return result
    try:
        deadline = time.monotonic() + seconds
        for s in dev.stream_live(stop_flag=lambda: time.monotonic() >= deadline):
            result["frames"] += 1
            if s.get("valid"):
                result["valid"] += 1
                result["last_spo2"] = s["spo2"]
                result["last_pulse"] = s["pulse_rate"]
    except Exception as exc:
        result["message"] = f"Error reading {port}: {exc}"
        return result
    finally:
        dev.close()

    result["reachable"] = result["frames"] > 0
    result["finger_in"] = result["valid"] > 0
    if not result["reachable"]:
        result["message"] = ("No data from the device. Check it is powered on, a "
                             "finger is inserted, and SpO2 Assistant is closed.")
    elif not result["finger_in"]:
        result["message"] = ("Device connected but not reading — insert a finger "
                             "(or reseat the clip).")
    else:
        result["message"] = (f"Connected — finger detected. SpO2 {result['last_spo2']}%, "
                             f"pulse {result['last_pulse']} bpm.")
    return result


# -- organized session storage --------------------------------------------
SESSIONS_DIRNAME = "sessions"


def _sanitize(name: str, fallback: str) -> str:
    """Filesystem-safe token from a free-text name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("_")
    return cleaned[:64] or fallback


def make_session_dir(base_dir: str, subject: str, session_label: str,
                     when: datetime | None = None) -> tuple[str, str]:
    """Create sessions/<subject>/<label>__<timestamp>/ and return (dir, stamp).

    Sessions are grouped by subject so a person's recordings stay together.
    """
    when = when or datetime.now()
    stamp = when.strftime("%Y%m%d_%H%M%S")
    subj = _sanitize(subject, "subject")
    label = _sanitize(session_label, "session")
    path = os.path.join(base_dir, SESSIONS_DIRNAME, subj, f"{label}__{stamp}")
    os.makedirs(path, exist_ok=True)
    return path, stamp


def write_metadata(session_path: str, metadata: dict) -> str:
    """Write metadata.json into a session folder; return its path."""
    out = os.path.join(session_path, "metadata.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, default=str)
    return out


def list_sessions(base_dir: str) -> list[dict]:
    """Enumerate saved sessions under base_dir/sessions for the load/export UI."""
    root = os.path.join(base_dir, SESSIONS_DIRNAME)
    found = []
    if not os.path.isdir(root):
        return found
    for subject in sorted(os.listdir(root)):
        subj_dir = os.path.join(root, subject)
        if not os.path.isdir(subj_dir):
            continue
        for sess in sorted(os.listdir(subj_dir)):
            sess_dir = os.path.join(subj_dir, sess)
            csv_path = os.path.join(sess_dir, "samples.csv")
            if os.path.isfile(csv_path):
                meta = {}
                meta_path = os.path.join(sess_dir, "metadata.json")
                if os.path.isfile(meta_path):
                    try:
                        with open(meta_path, encoding="utf-8") as fh:
                            meta = json.load(fh)
                    except Exception:
                        meta = {}
                found.append({"subject": subject, "session": sess, "dir": sess_dir,
                              "csv": csv_path, "metadata": meta})
    return found


# ==========================================================================
# Hardware-free self-test of the decoders
# ==========================================================================
def run_selftest() -> None:
    """Verify the decoders against known byte->value vectors. Raises on mismatch."""
    checks = 0

    # CMS50E/W: SpO2 byte 6, pulse byte 5, pleth byte 3, pleth2 byte 4 (low 7 bits).
    s = decode_frame_cms50e([0x01, 0x80, 0x80, 0x80 | 40, 0x80 | 12, 0x80 | 72, 0x80 | 98, 0x80, 0x80])
    assert s["pulse_rate"] == 72 and s["spo2"] == 98 and not s["finger_out"], s
    assert s["pleth"] == 40 and s["pleth2"] == 12 and s["valid"], s
    checks += 1
    # Finger out is the SpO2 sentinel (127), NOT byte 3 (which is the waveform):
    # byte 3 == 0xC0 must stay a valid reading, not a false finger-out flag.
    s = decode_frame_cms50e([0x01, 0x80, 0x80, 0xC0, 0x80, 0x80 | 70, 0x80 | 95, 0xFF, 0xFF])
    assert not s["finger_out"] and s["valid"] and s["pleth"] == 64, s
    s = decode_frame_cms50e([0x01, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80 | 127, 0x80, 0x80])
    assert s["finger_out"] and s["spo2"] == 127 and not s["valid"], s
    checks += 1
    # Regression: a real frame captured from the physical CMS50E (2026-08-27).
    real = list(bytes.fromhex("01e087cb99c4dfffff"))
    s = decode_frame_cms50e(real)
    assert s["spo2"] == 95 and s["pulse_rate"] == 68, s
    assert s["pleth"] == 75 and s["pleth2"] == 25 and s["valid"], s
    checks += 1

    # CMS50E parser resyncs on 0x01 and ignores pre-sync noise.
    p = _ParserCMS50E()
    got = None
    for b in [0xAA, 0xBB, 0x01, 0x80, 0x80, 0x00, 0x80, 0x80 | 60, 0x80 | 97, 0x80, 0x80]:
        r = p.push(b)
        if r:
            got = r
    assert got and got["pulse_rate"] == 60 and got["spo2"] == 97, got
    checks += 1

    # CMS50D+ live: pulse spans byte2 bit6 (high) + byte3 low7; waveform in byte1.
    for x in range(256):
        hi = (x & 0x80) >> 1
        lo = x & 0x7F
        d = decode_live_cms50dplus([0x80, 0, hi, lo, 0])
        assert d["pulse_rate"] == x, (x, d)
    for x in range(128):
        d = decode_live_cms50dplus([0x80, x, 0, 0, 0])
        assert d["pleth"] == x
        d = decode_live_cms50dplus([0x80, 0, 0, 0, x])
        assert d["spo2"] == x
    d = decode_live_cms50dplus([0x80 | 0x10, 0, 0, 0, 0])
    assert d["finger_out"]
    checks += 1

    # CMS50D+ recorded: pulse high bit in byte0 bit0, SpO2 in byte2.
    for x in range(256):
        hi = (x & 0x80) >> 7
        lo = x & 0x7F
        d = decode_recorded_cms50dplus([0xF0 | hi, 0x80 | lo, 0])
        assert d["pulse_rate"] == x, (x, d)
    for x in range(128):
        d = decode_recorded_cms50dplus([0xF0, 0x80, x])
        assert d["spo2"] == x
    checks += 1

    print(f"Self-test passed: {checks} decoder groups OK "
          f"(CMS50E/W + CMS50D+ live & recorded).")


if __name__ == "__main__":
    run_selftest()
