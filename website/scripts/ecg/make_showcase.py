"""
Build the ECG showcase from a public driver-stress recording.

Source: PhysioNet "Stress Recognition in Automobile Drivers" (drivedb), record
drive05 — Healey JA, Picard RW (2005), IEEE Trans. Intelligent Transportation
Systems 6(2):156-166; Open Data Commons Attribution License v1.0. It stands in
until the study's own Frontier X2 recordings are published.

The 84-minute drive alternates rest, city and highway driving. The showcase
takes a 5-minute ECG window spanning rest → city driving, runs it through the
study's own pipeline (ECG/ecg_analysis.py), and keeps the record's other
signals (respiration, skin conductance, EMG, heart rate) for context.

Run from the website folder:
    python scripts/ecg/make_showcase.py
Reads scripts/sources/drive05.{hea,dat}; writes public/data/ecg/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import signal as sps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                                  # D:\Multimodal
sys.path.insert(0, str(ROOT / "ECG"))
import ecg_analysis as ea  # noqa: E402  (the study's own pipeline)

SRC = HERE.parent / "sources" / "drive05"
OUT = HERE.parents[1] / "public" / "data" / "ecg"

FRAME_HZ = 15.5
# samples per frame, in header order: ECG 32, EMG 1, foot GSR 2, hand GSR 2, HR 1, marker 1, RESP 2
LAYOUT = [("ECG", 32), ("EMG", 1), ("footGSR", 2), ("handGSR", 2), ("HR", 1), ("marker", 1), ("RESP", 2)]
GAIN = {"ECG": 1000.0, "EMG": 1000.0, "footGSR": 1000.0, "handGSR": 1000.0, "HR": 1.0, "marker": 100.0, "RESP": 100.0}

WINDOW = (13 * 60, 18 * 60)       # s — spans the end of rest and the start of city driving
DECIMATE = 2                      # 496 Hz -> 248 Hz
QUALITY_WINDOW_S = 5
OVERVIEW_STEP_S = 5


def read_record():
    raw = np.fromfile(SRC.with_suffix(".dat"), dtype="<i2")
    width = sum(k for _, k in LAYOUT)
    frames = raw[: raw.size // width * width].reshape(-1, width)
    out, col = {}, 0
    for name, k in LAYOUT:
        out[name] = {"fs": FRAME_HZ * k, "v": frames[:, col : col + k].reshape(-1).astype(np.float64) / GAIN[name]}
        col += k
    return out, frames.shape[0] / FRAME_HZ


def segments(marker, total_s):
    """The marker channel pulses at each change of driving condition."""
    v = marker["v"]
    hi = np.flatnonzero(v > np.median(v) + 20)
    starts = []
    for i in hi:
        t = i / marker["fs"]
        if not starts or t - starts[-1] > 20:
            starts.append(t)
    names = ["Rest", "City", "Highway", "City", "Highway", "City", "Rest"]
    bounds = [0.0] + starts[: len(names) - 1] + [total_s]
    return [
        {"name": n, "startS": round(a, 1), "endS": round(b, 1)}
        for n, a, b in zip(names, bounds[:-1], bounds[1:])
    ]


def window(sig, a, b):
    fs = sig["fs"]
    return sig["v"][int(a * fs) : int(b * fs)]


def r(values, nd=4):
    return [round(float(v), nd) for v in values]


def time_metrics(rrs):
    m = ea.hrv_time_domain(rrs)
    keep = ("beats", "mean_hr_bpm", "min_hr_bpm", "max_hr_bpm", "mean_rr_ms", "sdnn_ms", "rmssd_ms", "pnn50_pct", "artifact_pct")
    return {k: round(float(m[k]), 2) for k in keep if k in m}


def main():
    sig, total_s = read_record()
    segs = segments(sig["marker"], total_s)
    a, b = WINDOW
    dur = b - a

    # --- ECG through the study pipeline -----------------------------------
    fs = sig["ECG"]["fs"] / DECIMATE
    raw = sps.decimate(window(sig["ECG"], a, b), DECIMATE, zero_phase=True)
    # polarity is judged on a filtered probe (as ECG/dashboard.py does) — the
    # raw trace's baseline wander and spikes would mislead it
    probe = ea.preprocess(raw, fs, powerline=60.0, invert=False)       # recorded in the US
    invert = ea.detect_polarity(probe)
    filtered = ea.preprocess(raw, fs, powerline=60.0, invert=invert)
    peaks = ea.detect_r_peaks(filtered, fs)
    rrs = ea.rr_intervals(peaks, fs)

    # phases inside the window, from the drive's own segments
    phases = []
    for s in segs:
        lo, hi = max(s["startS"], a), min(s["endS"], b)
        if hi - lo > 1:
            phases.append({"name": s["name"], "startS": round(lo - a, 1), "endS": round(hi - a, 1)})
    phase_metrics = {}
    for p in phases:
        sel = (rrs.times >= p["startS"]) & (rrs.times < p["endS"])
        phase_metrics[p["name"]] = time_metrics(ea.RRSeries(rrs.times[sel], rrs.rr[sel], rrs.valid[sel]))

    freq = ea.hrv_frequency_domain(rrs)
    pc = ea.poincare(rrs)
    avg = ea.average_beat(filtered, peaks, fs)
    quality = ea.signal_quality(raw, filtered, fs, rrs)
    status, message = ea.quality_verdict(quality)

    windows = []
    step = int(QUALITY_WINDOW_S * fs)
    typical = float(np.median([np.std(raw[i : i + step]) for i in range(0, raw.size, step)]))
    for i in range(0, raw.size, step):
        lo, hi = i / fs, (i + step) / fs
        sel = (rrs.times >= lo) & (rrs.times < hi)
        q = ea.signal_quality(raw[i : i + step], filtered[i : i + step], fs, ea.RRSeries(rrs.times[sel], rrs.rr[sel], rrs.valid[sel]))
        st, msg = ea.quality_verdict(q)
        if float(np.std(raw[i : i + step])) > 1.8 * typical:
            st, msg = "critical", "Motion artefact — large non-cardiac swings."
        elif q.get("artifact_pct", 0) > 0 and q.get("flatline_pct", 0) <= 20:
            st, msg = "warning", "Irregular beat — its intervals are excluded from HRV."
        windows.append({"startS": lo, "endS": min(hi, dur), "status": st, "message": msg})

    psd_mask = freq["freqs"] <= 0.5 if "freqs" in freq else None

    # --- companion signals in the same window -----------------------------
    def companion(name, units, nd=3):
        return {"fs": sig[name]["fs"], "units": units, "values": r(window(sig[name], a, b), nd)}

    # --- whole-drive overview ---------------------------------------------
    def per_step(name, reducer):
        v, fs_ = sig[name]["v"], sig[name]["fs"]
        n = int(OVERVIEW_STEP_S * fs_)
        return [reducer(v[i : i + n]) for i in range(0, v.size - n + 1, n)]

    def hr_median(chunk):
        ok = chunk[(chunk > 30) & (chunk < 200)]
        return round(float(np.median(ok)), 1) if ok.size else None

    change = next((s["startS"] - a for s in segs if a < s["startS"] < b), None)

    record = {
        "id": "S01",
        "subject": {"id": "drive05", "ageBand": "—", "sex": "—"},
        "label": "Rest → city driving",
        "durationS": dur,
        "device": {"model": "Driver-stress rig (MIT Media Lab)", "lead": "Chest ECG, modified lead II", "fs": fs, "units": "mV"},
        "source": {
            "title": "Stress Recognition in Automobile Drivers (drivedb), record drive05",
            "author": "Healey & Picard, IEEE T-ITS 2005 · PhysioNet",
            "license": "ODC Attribution 1.0",
            "url": "https://physionet.org/content/drivedb/1.0.0/",
            "windowStartS": a,
        },
        "phases": phases,
        "signal": {"fs": fs, "raw": r(raw), "filtered": r(filtered)},
        "rPeaks": [int(p) for p in peaks],
        "rr": {"t": r(rrs.times, 3), "ms": r(rrs.rr * 1000, 1), "valid": [bool(v) for v in rrs.valid]},
        "hrv": {
            "session": time_metrics(rrs),
            "phases": phase_metrics,
            "frequency": {
                k: round(float(freq[k]), 3)
                for k in ("lf_power_ms2", "hf_power_ms2", "lf_hf_ratio", "lf_nu", "hf_nu", "duration_s")
                if k in freq
            }
            | {"shortRecord": bool(freq.get("short_record", True))},
            "poincare": {k: round(float(pc[k]), 2) for k in ("sd1_ms", "sd2_ms", "sd1_sd2_ratio")},
        },
        "psd": {"freqs": r(freq["freqs"][psd_mask], 4), "power": r(freq["psd"][psd_mask], 3)} if psd_mask is not None else None,
        "averageBeat": {"tMs": r(avg["t_ms"], 1), "mean": r(avg["mean"]), "sd": r(avg["sd"]), "n": avg["n"]},
        "quality": {k: round(float(v), 2) for k, v in quality.items()} | {"status": status, "message": message},
        "qualityWindows": windows,
        "events": [{"t": round(change, 1), "kind": "City driving starts"}] if change is not None else [],
        "companions": {
            "resp": companion("RESP", "a.u.", 2),
            "handGSR": companion("handGSR", "a.u."),
            "footGSR": companion("footGSR", "a.u."),
            "emg": companion("EMG", "a.u."),
        },
        "drive": {
            "stepS": OVERVIEW_STEP_S,
            "durationS": round(total_s, 1),
            "segments": segs,
            "hr": per_step("HR", hr_median),
            "handGSR": per_step("handGSR", lambda c: round(float(np.mean(c)), 3)),
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    (OUT / "S01.json").write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.json").write_text(
        json.dumps(
            {
                "modality": "ecg",
                "source": {"kind": "public", "note": "PhysioNet drivedb record drive05 (ODC-By). Metrics from ECG/ecg_analysis.py."},
                "sessions": [{k: record[k] for k in ("id", "subject", "label", "durationS")}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    hv = record["hrv"]["session"]
    print(f"window {a}-{b}s, fs {fs} Hz, {len(peaks)} beats, HR {hv.get('mean_hr_bpm')}, RMSSD {hv.get('rmssd_ms')}, quality {status}")
    print("phases:", {k: v.get("mean_hr_bpm") for k, v in phase_metrics.items()}, "event at", change)
    print("ECG range mV:", round(float(np.percentile(filtered, 1)), 2), round(float(np.percentile(filtered, 99)), 2))
    print("segments:", [(s["name"], round(s["startS"] / 60, 1)) for s in segs])
    print(f"size {(OUT / 'S01.json').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
