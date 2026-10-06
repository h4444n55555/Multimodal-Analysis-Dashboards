"""
Build the rPPG showcase with the cvpr-lab pipeline (D:\\Multimodal\\cvpr-lab).

rPPG recovers a pulse from tiny skin-colour changes in face video. The input
here is the per-frame mean colour of the face (an R, G, B trace); the
training-free extractors in cvprlab/classical.py (POS, CHROM, green) turn it
into a pulse waveform and cvprlab/vitals.py derives every measure from it, exactly
as the cvpr-lab dashboard does. The learned CVPRLab model has no trained weights
yet, so it is not used.

Source, in order of preference:
  1. scripts/sources/ubfc_subject1_rgb.csv + ubfc_subject1_gt.xmp — a face
     colour trace and its fingertip-oximeter reference from UBFC-rPPG
     (Bobbia et al. 2019), as published in github.com/KrishivSIyer/rPPG.
  2. Otherwise a synthetic trace with a known pulse — marked illustrative.

Run from the website folder:
    python scripts/rppg/make_showcase.py
Writes public/data/rppg/.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                                  # D:\Multimodal
sys.path.insert(0, str(ROOT / "cvpr-lab"))
from cvprlab import classical, vitals  # noqa: E402  (numpy-only; no torch needed)

SOURCES = HERE.parent / "sources"
UBFC_RGB = SOURCES / "ubfc_subject1_rgb.csv"
UBFC_GT = SOURCES / "ubfc_subject1_gt.xmp"
OUT = HERE.parents[1] / "public" / "data" / "rppg"

TRACK_WINDOW_S = 10     # heart rate is re-estimated over a sliding 10 s window…
TRACK_STEP_S = 1        # …every second, like the live dashboard
QUALITY_WINDOW_S = 5
METHODS = ("pos", "chrom", "green")


# ------------------------------------------------------------------ sources
def load_ubfc():
    """(rgb (T,3), fps, reference PPG on frame times or None, meta)."""
    with open(UBFC_RGB, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.reader(f) if r]
    header = [h.strip().lower() for h in rows[0]]
    has_header = any(c.isalpha() for c in "".join(header))
    body = rows[1:] if has_header else rows
    data = np.array([[float(v) for v in r] for r in body], dtype=np.float64)

    def col(*names):
        for n in names:
            if has_header and n in header:
                return header.index(n)
        return None

    ri, gi, bi = col("r", "red", "mean_r"), col("g", "green", "mean_g"), col("b", "blue", "mean_b")
    if None in (ri, gi, bi):                        # no names: last three columns are R, G, B
        ri, gi, bi = data.shape[1] - 3, data.shape[1] - 2, data.shape[1] - 1
    rgb = data[:, [ri, gi, bi]]
    ti = col("t", "time", "timestamp", "time_s", "t_s")
    fps = 30.0
    if ti is not None:
        t = data[:, ti]
        span = t[-1] - t[0]
        if span > 1000:                             # milliseconds
            span /= 1000.0
        if span > 0:
            fps = (len(t) - 1) / span

    ref = None
    if UBFC_GT.exists():
        # UBFC DATASET_1 gtdump.xmp: time (ms), HR, SpO2, PPG — comma separated
        gt = np.array([[float(v) for v in line.split(",")[:4]]
                       for line in UBFC_GT.read_text(encoding="utf-8").splitlines() if line.strip()])
        gt_t = (gt[:, 0] - gt[0, 0]) / 1000.0
        frame_t = np.arange(len(rgb)) / fps
        ref = np.interp(frame_t, gt_t, gt[:, 3])
    meta = {
        "source": {
            "title": "UBFC-rPPG, subject 1 (face colour trace + oximeter)",
            "author": "Bobbia et al., Pattern Recognition Letters 2019 · via KrishivSIyer/rPPG",
            "license": "UBFC-rPPG research licence",
            "url": "https://sites.google.com/view/ybenezeth/ubfcrppg",
        },
        "note": "UBFC-rPPG subject 1. Pulse from cvpr-lab (POS/CHROM/green + vitals.py).",
        "subject": "UBFC-1",
        "label": "Seated, still, facing the camera",
        "phases": [],
        "camera": "Logitech C920 · uncompressed",
    }
    return rgb, fps, ref, meta


def synthetic():
    """A face colour trace with a known pulse, breathing and a burst of head motion.

    Pulse drifts 68→80 bpm with respiratory sinus arrhythmia at 15 breaths/min;
    green carries the most pulsatility, then red, then blue, as haemoglobin
    absorption dictates. 45–55 s adds head motion: large, colour-correlated
    brightness swings that no pulse extractor fully cancels.
    """
    fps, seconds = 30.0, 75.0
    t = np.arange(0, seconds, 1 / fps)
    rng = np.random.default_rng(5)
    rr_hz = 15 / 60
    hr = 72 + 4 * np.sin(2 * np.pi * t / 60 - np.pi / 2) + 2.0 * np.sin(2 * np.pi * rr_hz * t)
    phase = 2 * np.pi * np.cumsum(hr / 60) / fps
    beat = np.sin(phase) + 0.25 * np.sin(2 * phase + 1.1)
    pulse = (1 + 0.15 * np.sin(2 * np.pi * rr_hz * t)) * beat
    pulse /= pulse.std()

    dc = np.array([150.0, 105.0, 85.0])
    ac = np.array([0.20, 0.55, 0.12])                # pixel levels after ROI averaging
    light = 1 + 0.012 * np.sin(2 * np.pi * t / 23) + 0.004 * np.sin(2 * np.pi * rr_hz * t + 0.6)
    # more blood absorbs more light, so every channel darkens on each beat
    rgb = (dc - np.outer(pulse, ac)) * light[:, None]
    motion = (t >= 45) & (t < 55)
    shake = 0.05 * np.sin(2 * np.pi * 1.3 * t) + 0.03 * np.sin(2 * np.pi * 2.1 * t + 1)
    sway = np.where(motion, shake, 0)
    rgb *= 1 + sway[:, None] * np.array([1.0, 0.8, 0.55])
    rgb += np.where(motion, 1.2, 0.06)[:, None] * rng.standard_normal(rgb.shape)

    ref = pulse + 0.03 * rng.standard_normal(t.size)       # fingertip oximeter: clean
    meta = {
        "source": {
            "title": "Synthetic face colour trace (known pulse)",
            "author": "Generated by scripts/rppg/make_showcase.py",
            "license": "simulated, no licence needed",
            "url": "https://github.com/hima1323/cvpr-lab",
            "illustrative": True,
            "note": "Signals are simulated to show what the pipeline produces; no person was recorded.",
        },
        "note": "Synthetic trace with a known pulse. Pulse and vitals from cvpr-lab (POS/CHROM/green + vitals.py).",
        "subject": "Synthetic",
        "label": "Still → head motion → still",
        "phases": [
            {"name": "Still", "startS": 0.0, "endS": 45.0},
            {"name": "Head motion", "startS": 45.0, "endS": 55.0},
            {"name": "Still", "startS": 55.0, "endS": seconds},
        ],
        "camera": "RGB webcam · 30 fps (simulated)",
    }
    return rgb, fps, ref, meta


# ------------------------------------------------------------------ helpers
def r(values, nd=3):
    return [None if v is None or not np.isfinite(v) else round(float(v), nd) for v in values]


def clean(d, nd=3):
    """Round a flat dict of numbers, dropping what the pipeline withheld."""
    out = {}
    for k, v in d.items():
        if isinstance(v, bool) or isinstance(v, str):
            out[k] = v
        elif isinstance(v, (int, float, np.floating, np.integer)) and np.isfinite(v):
            out[k] = round(float(v), nd)
    return out


def std(x):
    x = np.asarray(x, dtype=np.float64)
    s = x.std()
    return (x - x.mean()) / s if s > 1e-9 else x - x.mean()


def status_of(label):
    return {"good": "good", "fair": "warning"}.get(label, "critical")


def main():
    real = UBFC_RGB.exists()
    rgb, fps, ref, meta = load_ubfc() if real else synthetic()
    n = len(rgb)
    dur = n / fps

    waves = {m: classical.extract(rgb, fps, m) for m in METHODS}
    # A colour-derived pulse has no inherent sign. Point each one the same way
    # as the reference (or, without one, inverted green: peaks = most blood) so
    # beats are found on systolic peaks and the traces overlay.
    anchor = std(ref) if ref is not None else waves["green"]
    for m in METHODS:
        if np.corrcoef(waves[m], anchor)[0, 1] < 0:
            waves[m] = -waves[m]
    main_wave = waves["pos"]
    v = vitals.compute_all(main_wave, fps, rgb_trace=rgb)

    beats = vitals.detect_beats(main_wave, fps)
    beats = [] if beats is None else [int(b) for b in beats]
    ibi_t = [round(beats[i + 1] / fps, 3) for i in range(len(beats) - 1)]
    ibi_ms = [round((beats[i + 1] - beats[i]) / fps * 1000, 1) for i in range(len(beats) - 1)]

    # sliding heart rate per method, the reference and the SNR
    win = int(TRACK_WINDOW_S * fps)
    track = {"t": [], "snrDb": [], "reference": [], **{m: [] for m in METHODS}}
    for a in range(0, n - win + 1, int(TRACK_STEP_S * fps)):
        track["t"].append(round((a + win / 2) / fps, 2))
        for m in METHODS:
            track[m].append(vitals.estimate_hr(waves[m][a:a + win], fps))
        track["snrDb"].append(vitals.signal_quality_db(main_wave[a:a + win], fps))
        track["reference"].append(vitals.estimate_hr(ref[a:a + win], fps) if ref is not None else None)
    track = {k: r(vals, 2) for k, vals in track.items()}

    scores = {}
    for m in METHODS:
        est = np.array([np.nan if x is None else x for x in track[m]])
        s = {"snrDb": vitals.signal_quality_db(waves[m], fps), "hrBpm": vitals.estimate_hr(waves[m], fps)}
        if ref is not None:
            gt = np.array([np.nan if x is None else x for x in track["reference"]])
            ok = np.isfinite(est) & np.isfinite(gt)
            s["maeBpm"] = float(np.mean(np.abs(est[ok] - gt[ok]))) if ok.any() else None
            s["pearson"] = float(np.corrcoef(std(waves[m]), std(ref))[0, 1])
        scores[m] = clean(s, 2)

    quality = []
    step = int(QUALITY_WINDOW_S * fps)
    for a in range(0, n - step // 2, step):
        snr = vitals.signal_quality_db(main_wave[a:a + step], fps)
        label, _ = vitals.quality_label(snr)
        quality.append({"startS": round(a / fps, 2), "endS": round(min(a + step, n) / fps, 2),
                        "status": status_of(label), "label": label,
                        "snrDb": None if snr is None else round(snr, 1)})

    # Intervals are left out of HRV, the way the ECG page drops irregular beats,
    # when they end in a window whose quality is not good (one head turn adds
    # false beats) or sit more than 20% from their neighbours' median.
    bad = [(q["startS"], q["endS"]) for q in quality if q["status"] != "good"]
    med = [float(np.median(ibi_ms[max(0, i - 5):i + 6])) for i in range(len(ibi_ms))]
    ibi_valid = [not any(a <= t < b for a, b in bad) and abs(ms - m) <= 0.2 * m
                 for t, ms, m in zip(ibi_t, ibi_ms, med)]
    clean_ibi = np.array([ms for ms, ok in zip(ibi_ms, ibi_valid) if ok and 333 <= ms <= 2000])
    hrv_clean = vitals.hrv_time_domain(clean_ibi) or {}
    v.update(hrv_clean)
    v["artifact_pct"] = 100.0 * (1 - len(clean_ibi) / max(len(ibi_ms), 1))

    # Colour ratios (perfusion, per-channel AC/DC, the SpO2 ratio) over the
    # longest stretch of good signal � motion swamps a channel's "pulse".
    runs, cur = [], []
    for q in quality:
        if q["status"] == "good":
            cur.append(q)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    if runs:
        best = max(runs, key=len)
        a, b = int(best[0]["startS"] * fps), int(best[-1]["endS"] * fps)
        v["channels"] = vitals.channel_ac_dc(rgb[a:b], fps)
        v["perfusion_index_pct"] = vitals.perfusion_index(rgb[a:b], fps)
        spo2 = vitals.estimate_spo2(rgb[a:b], fps)
        if spo2:
            v.update({k: spo2[k] for k in ("ratio_of_ratios", "red_ac_dc_pct", "blue_ac_dc_pct")})
        v["colour_window_s"] = [best[0]["startS"], best[-1]["endS"]]

    bpm, power = vitals.spectrum_bpm(main_wave, fps)
    template, cycle_s = vitals.beat_template(main_wave, fps)
    cues = vitals.respiration_cues(main_wave, fps, np.array(ibi_ms) if len(ibi_ms) > 1 else None)
    channels = v.pop("channels", None) or {}
    colour_window = v.pop("colour_window_s", None)

    record = {
        "id": "S01",
        "subject": {"id": meta["subject"], "ageBand": "—", "sex": "—"},
        "label": meta["label"],
        "durationS": round(dur, 2),
        "device": {"camera": meta["camera"], "fps": round(fps, 2), "roi": "Whole-face mean colour"},
        "source": meta["source"],
        "phases": meta["phases"],
        "rgb": {"fs": round(fps, 3), "r": r(rgb[:, 0]), "g": r(rgb[:, 1]), "b": r(rgb[:, 2])},
        "waves": {m: r(waves[m]) for m in METHODS},
        "reference": {"fs": round(fps, 3), "values": r(std(ref))} if ref is not None else None,
        "beats": beats,
        "ibi": {"t": ibi_t, "ms": ibi_ms, "valid": ibi_valid},
        "track": track,
        "scores": scores,
        "vitals": clean(v, 3),
        "quality": quality,
        "spectrum": {"bpm": r(bpm, 2), "power": r(power, 4)} if bpm is not None else None,
        "beatTemplate": {"values": r(template, 4), "cycleS": round(float(cycle_s), 3)} if template is not None else None,
        "respiration": {k: {"brpm": round(b, 1), "prominence": round(p, 2)} for k, (b, p) in cues.items()},
        "channels": {k: clean(c, 4) for k, c in channels.items()},
        "colourWindowS": colour_window,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    (OUT / "S01.json").write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.json").write_text(
        json.dumps(
            {
                "modality": "rppg",
                "source": {"kind": "public" if real else "synthetic", "note": meta["note"]},
                "sessions": [{k: record[k] for k in ("id", "subject", "label", "durationS")}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    vv = record["vitals"]
    print(f"{'UBFC' if real else 'synthetic'}: {dur:.1f} s at {fps:.1f} fps, {len(beats)} beats")
    print(f"HR {vv.get('hr_bpm')} (beats {vv.get('hr_beats_bpm')}), SNR {vv.get('snr_db')} dB, RR {vv.get('rr_brpm')}, RMSSD {vv.get('rmssd_ms')}")
    print("scores:", scores)
    print("quality:", [q["label"] for q in quality])
    print(f"size {(OUT / 'S01.json').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
