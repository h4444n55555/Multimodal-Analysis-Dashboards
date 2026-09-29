"""
Build the thermal showcase from a public thermal video.

Source: "Thermography of a person drinking" (Drinking a glass of sour orange
juice.ogv) by Pixelmaniac pictures, Fluke Ti55 — public domain, Wikimedia
Commons. The file is a false-colour video, not radiometric data, so the
temperatures here are ILLUSTRATIVE: each pixel's colour is mapped back along
the camera palette (blue = cold ... orange = warm) onto a nominal °C range.
It stands in until the study's own FLIR C5 recordings are published.

Run from the website folder:
    python scripts/thermal/make_showcase.py
Needs ffmpeg on PATH. Reads scripts/sources/drinking_juice.ogv and writes
public/data/thermal/{index.json, S01.json, S01.frames.bin}.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "sources" / "drinking_juice.ogv"
OUT = HERE.parents[1] / "public" / "data" / "thermal"

W, H = 204, 144          # the camera's active area, keeping its aspect
FPS = 8
# the video is pillar-boxed: the camera image is the middle 383/480 of the width
CROP = "crop=iw*383/480:ih:iw*53/480:0"

# nominal range the palette is mapped onto (illustrative, not measured)
T_LO, T_HI = 20.0, 37.0
# frames are stored as uint8 over this range
Q_LO, Q_HI = 20.0, 37.0

# regions in frame pixels [x, y, w, h], placed on the subject's face
ROIS = [
    {"key": "forehead", "label": "Forehead", "box": [100, 30, 30, 12]},
    {"key": "periorbital", "label": "Eyes", "box": [100, 54, 40, 8]},
    {"key": "nose", "label": "Nose", "box": [110, 64, 12, 10]},
    {"key": "mouth", "label": "Mouth", "box": [104, 78, 24, 10]},
]
# from the glass entering the lower face (see README)
PHASES = [("Before", 0.0, 2.75), ("Drinking", 2.75, 7.0), ("After", 7.0, None)]


def read_frames() -> np.ndarray:
    vf = f"{CROP},scale={W}:{H}:flags=area,fps={FPS}"
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(SRC), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(out, np.uint8).reshape(-1, H, W, 3)


def palette_to_celsius(rgb: np.ndarray) -> np.ndarray:
    """Hue runs blue (240°) → cyan → yellow → orange (≈20°) from cold to warm."""
    c = rgb.astype(np.float32) / 255
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mx, mn = c.max(-1), c.min(-1)
    d = np.where(mx - mn == 0, 1e-6, mx - mn)
    hue = np.where(
        mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)
    ) * 60
    warmth = np.clip((240 - hue) / 225, 0, 1)
    return T_LO + warmth * (T_HI - T_LO)


def main():
    frames = palette_to_celsius(read_frames())
    n = frames.shape[0]
    duration = round(n / FPS, 2)
    q = np.clip(np.round((frames - Q_LO) / (Q_HI - Q_LO) * 255), 0, 255).astype(np.uint8)

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    (OUT / "S01.frames.bin").write_bytes(q.tobytes())

    series = {}
    for roi in ROIS:
        x, y, w, h = roi["box"]
        series[roi["key"]] = [round(float(v), 3) for v in frames[:, y : y + h, x : x + w].mean(axis=(1, 2))]

    record = {
        "id": "S01",
        "subject": {"id": "S01", "ageBand": "—", "sex": "—"},
        "label": "Drinking a cold drink",
        "durationS": duration,
        "device": {"model": "Fluke Ti55", "sensor": "320 × 240 microbolometer", "emissivity": 0.98},
        "source": {
            "title": "Thermography of a person drinking",
            "author": "Pixelmaniac pictures",
            "license": "Public domain",
            "url": "https://commons.wikimedia.org/wiki/File:Drinking_a_glass_of_sour_orange_juice.ogv",
            "illustrative": True,
            "note": "False-colour video; temperatures are reconstructed from the colour palette for illustration.",
        },
        "roiValidity": {"glasses": False, "facialHair": False, "hairOverForehead": True},
        "phases": [
            {"name": p, "startS": a, "endS": b if b is not None else duration} for p, a, b in PHASES
        ],
        "frames": {
            "file": "S01.frames.bin",
            "encoding": "uint8",
            "count": n,
            "width": W,
            "height": H,
            "fps": FPS,
            "tempMinC": Q_LO,
            "tempMaxC": Q_HI,
        },
        "rois": [{**r, "valid": True} for r in ROIS],
        "series": {"rateHz": FPS, "roiMeanC": series},
    }
    (OUT / "S01.json").write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.json").write_text(
        json.dumps(
            {
                "modality": "thermal",
                "source": {
                    "kind": "public",
                    "note": "Public-domain thermal video (Wikimedia Commons); temperatures are illustrative.",
                },
                "sessions": [{k: record[k] for k in ("id", "subject", "label", "durationS")}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"{n} frames {W}x{H} @ {FPS} fps = {q.nbytes / 1e6:.2f} MB, {duration} s")
    for k, v in series.items():
        v = np.array(v)
        before, drink = v[: int(2.5 * FPS)].mean(), v[int(3.5 * FPS) : int(6.5 * FPS)].mean()
        print(f"  {k:12} before {before:.1f}  drinking {drink:.1f}  range {v.min():.1f}-{v.max():.1f}")


if __name__ == "__main__":
    main()
