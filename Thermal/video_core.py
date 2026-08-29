"""Live UVC video capture + recording for the FLIR C5.

The C5's USB video stream is colorized/8-bit only (confirmed by
inspect_usb_stream.py and a live probe: YUY2, 640x480, no 16-bit/radiometric
pixel format offered) - so this is a plain visual-video recorder, not a
radiometric one. Per-pixel temperature still only comes from stills via
extract_metadata.py.

Mirrors the threaded-capture / thread-safe store pattern used in
SpO2/spo2_core.py (SpO2LiveCapture / SpO2Store) so the two dashboards behave
the same way operationally.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np

FRAME_W, FRAME_H = 640, 480
TARGET_FPS = 30


def list_camera_indices(max_index: int = 6) -> list[dict]:
    """Probe indices 0..max_index-1, returning what each one reports.

    Read-only aside from opening/closing the device to grab one frame - used
    by the dashboard to let the operator pick the right index by sight
    (camera indices can shift across reboots/dock states), rather than
    hardcoding which one is the FLIR.
    """
    found = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue
        ok, frame = cap.read()
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        found.append({
            "index": idx,
            "opened": True,
            "width": w,
            "height": h,
            "frame": frame if ok else None,
        })
    return found


class VideoStore:
    """Thread-safe holder for the latest frame + running session stats."""

    def __init__(self):
        self.lock = threading.Lock()
        self.latest_frame: np.ndarray | None = None
        self.frames = 0
        self.started_at: float | None = None
        self.last_at: float | None = None
        self.recording = False
        self.record_path: str | None = None
        self.error: str | None = None

    def set_frame(self, frame: np.ndarray) -> None:
        with self.lock:
            self.latest_frame = frame
            self.frames += 1
            now = time.monotonic()
            if self.started_at is None:
                self.started_at = now
            self.last_at = now

    def get_frame(self) -> np.ndarray | None:
        with self.lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def stats(self) -> dict:
        with self.lock:
            stale = None if self.last_at is None else time.monotonic() - self.last_at
            return {
                "frames": self.frames,
                "duration_s": (self.last_at - self.started_at) if self.started_at else 0.0,
                "seconds_since_frame": stale,
                "live": stale is not None and stale < 1.0,
                "recording": self.recording,
                "record_path": self.record_path,
                "error": self.error,
            }

    def clear(self) -> None:
        with self.lock:
            self.__init__()


class VideoLiveCapture(threading.Thread):
    """Background reader: pulls frames from the UVC device into a VideoStore,
    and optionally writes them to an .mp4 file via cv2.VideoWriter while
    `recording` is True. Touches no UI.
    """

    def __init__(self, camera_index: int, store: VideoStore):
        super().__init__(daemon=True)
        self.camera_index = camera_index
        self.store = store
        self._stop = threading.Event()
        self._writer: cv2.VideoWriter | None = None
        self._record_lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def start_recording(self, path: str) -> None:
        with self._record_lock:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(path, fourcc, TARGET_FPS, (FRAME_W, FRAME_H))
        with self.store.lock:
            self.store.recording = True
            self.store.record_path = path

    def stop_recording(self) -> None:
        with self._record_lock:
            if self._writer is not None:
                self._writer.release()
                self._writer = None
        with self.store.lock:
            self.store.recording = False

    def run(self) -> None:
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            with self.store.lock:
                self.store.error = f"Could not open camera index {self.camera_index}"
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.01)
                    continue
                self.store.set_frame(frame)
                with self._record_lock:
                    if self._writer is not None:
                        self._writer.write(frame)
        finally:
            cap.release()
            self.stop_recording()


def make_session_dir(base_dir: Path, subject: str, label: str) -> Path:
    safe_subject = "".join(c if c.isalnum() or c in "-_" else "_" for c in (subject or "unknown"))
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "session"))
    ts = time.strftime("%Y%m%d_%H%M%S")
    session_dir = base_dir / safe_subject / f"{safe_label}__{ts}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir
