"""
Build the EMG showcase from a public forearm surface-EMG recording.

Source: GRABMyo (Gesture Recognition and Biometrics ElectroMyogram), PhysioNet
v1.1.0 — Jiang N., Pradhan A., He J. (2024), doi:10.13026/89dm-f662; Pradhan,
He & Jiang, Scientific Data 9:733 (2022). CC BY 4.0. It stands in until the
study's own EMG recordings are published.

One participant (session 1, participant 1): a 5-second rest recording and a
5-second "hand close" (fist) recording, 28 surface electrodes on the forearm
and wrist at 2048 Hz. They are shown back to back as Rest → Hand close.

Run from the website folder:
    python scripts/emg/make_showcase.py
Reads scripts/sources/grabmyo/*.{hea,dat}; writes public/data/emg/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import signal as sps

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "sources" / "grabmyo"
OUT = HERE.parents[1] / "public" / "data" / "emg"

REST = "session1_participant1_gesture17_trial1"
ACTIVE = "session1_participant1_gesture16_trial1"   # gesture 16 = Hand Close
BAND = (20.0, 450.0)          # standard surface-EMG band
ENV_WIN_S, ENV_STEP_S = 0.1, 0.025
QUALITY_WIN_S = 1.0
DISPLAY_FS = 1024             # traces are halved in rate for the web


def read_wfdb(name):
    """WFDB format-16 record → (fs, names, data in mV with shape (n, ch))."""
    lines = [l for l in (SRC / f"{name}.hea").read_text().splitlines() if l and not l.startswith("#")]
    _, nch, fs, n = lines[0].split()[:4]
    nch, fs, n = int(nch), float(fs), int(n)
    gains, bases, names = [], [], []
    for l in lines[1 : 1 + nch]:
        parts = l.split()
        g = parts[2]                                   # e.g. 96551.5(12891)/mV
        gains.append(float(g.split("(")[0]))
        bases.append(float(g.split("(")[1].split(")")[0]) if "(" in g else 0.0)
        names.append(parts[-1])
    raw = np.fromfile(SRC / f"{name}.dat", dtype="<i2")[: n * nch].reshape(n, nch).astype(np.float64)
    return fs, names, (raw - np.array(bases)) / np.array(gains)


def bandpass(x, fs):
    sos = sps.butter(4, BAND, btype="band", fs=fs, output="sos")
    return sps.sosfiltfilt(sos, x, axis=0)


def notch(x, fs, f0):
    out = x
    for h in (f0, 2 * f0, 3 * f0, 4 * f0, 5 * f0, 6 * f0, 7 * f0):
        if h >= BAND[1]:
            break
        b, a = sps.iirnotch(h, 30.0, fs)
        out = sps.filtfilt(b, a, out, axis=0)
    return out


def line_share(x, fs, f0):
    """Share of 20–450 Hz power within ±1 Hz of the mains frequency and its harmonics."""
    f, p = sps.welch(x, fs=fs, nperseg=min(2048, len(x)))
    band = (f >= BAND[0]) & (f <= BAND[1])
    near = np.zeros_like(band)
    for h in np.arange(f0, BAND[1], f0):
        near |= np.abs(f - h) <= 1.0
    tot = p[band].sum()
    return float(p[band & near].sum() / tot) if tot > 0 else 0.0


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


def r(values, nd=4):
    return [round(float(v), nd) for v in values]


def main():
    fs, names, rest = read_wfdb(REST)
    fs2, names2, act = read_wfdb(ACTIVE)
    assert fs == fs2 and names == names2
    keep = [i for i, nm in enumerate(names) if not nm.startswith("U")]   # U1–U4 unused
    names = [names[i] for i in keep]
    rest, act = rest[:, keep], act[:, keep]
    both = np.vstack([rest, act])
    dur = both.shape[0] / fs
    split_s = rest.shape[0] / fs

    # mains frequency: whichever of 50/60 Hz carries more raw power
    f, p = sps.welch(both[:, 0], fs=fs, nperseg=4096)
    line_hz = 60.0 if p[np.argmin(np.abs(f - 60))] > p[np.argmin(np.abs(f - 50))] else 50.0

    clean = notch(bandpass(both, fs), fs, line_hz)
    n_rest = rest.shape[0]
    rest_rms = np.array([rms(clean[:n_rest, c]) for c in range(clean.shape[1])])
    act_rms = np.array([rms(clean[n_rest:, c]) for c in range(clean.shape[1])])
    ratio_db = 20 * np.log10(np.maximum(act_rms, 1e-12) / np.maximum(rest_rms, 1e-12))

    channels = []
    for c, nm in enumerate(names):
        raw_line = line_share(both[:, c] - both[:, c].mean(), fs, line_hz)
        flat = rest_rms[c] < 1e-5 and act_rms[c] < 1e-5
        clipped = float(np.mean(np.abs(both[:, c]) >= 0.98 * np.abs(both[:, c]).max())) > 0.001
        status = "critical" if flat or clipped else ("warning" if raw_line > 0.25 else "good")
        ring = 1 if nm.startswith("F") and int(nm[1:]) <= 8 else 2 if nm.startswith("F") else 3 if int(nm[1:]) <= 6 else 4
        pos = (int(nm[1:]) - 1) % (8 if nm.startswith("F") else 6)
        channels.append({
            "name": nm, "ring": ring, "pos": pos,
            "restRms": round(float(rest_rms[c] * 1000), 2),       # µV
            "activeRms": round(float(act_rms[c] * 1000), 2),
            "ratioDb": round(float(ratio_db[c]), 1),
            "lineSharePct": round(raw_line * 100, 1),
            "status": status,
        })

    forearm = [i for i, nm in enumerate(names) if nm.startswith("F")]
    main = max(forearm, key=lambda i: ratio_db[i])
    x_raw, x_clean = both[:, main], clean[:, main]

    # RMS envelope
    w, s = int(ENV_WIN_S * fs), int(ENV_STEP_S * fs)
    env_t, env_v = [], []
    for a in range(0, len(x_clean) - w + 1, s):
        env_t.append((a + w / 2) / fs)
        env_v.append(rms(x_clean[a : a + w]) * 1000)            # µV

    # quality, every second
    windows = []
    for a in np.arange(0, dur, QUALITY_WIN_S):
        i0, i1 = int(a * fs), int(min(dur, a + QUALITY_WIN_S) * fs)
        share = line_share(x_raw[i0:i1] - x_raw[i0:i1].mean(), fs, line_hz)
        clip = float(np.mean(np.abs(x_raw[i0:i1]) >= 0.98 * np.abs(x_raw).max())) > 0.001
        if clip:
            st, msg = "critical", "Signal hits the amplifier limit."
        elif share > 0.25:
            st, msg = "warning", f"Mains hum is {share * 100:.0f}% of the signal before filtering."
        else:
            st, msg = "good", f"Clean · mains hum {share * 100:.0f}% before filtering."
        windows.append({"startS": round(float(a), 2), "endS": round(float(min(dur, a + QUALITY_WIN_S)), 2), "status": st, "message": msg})

    # spectrum of the contraction, cleaned
    f, pw = sps.welch(x_clean[n_rest:], fs=fs, nperseg=1024)
    keep_f = f <= 500
    f, pw = f[keep_f], pw[keep_f]
    band = (f >= BAND[0]) & (f <= BAND[1])
    cum = np.cumsum(pw[band])
    median_hz = float(f[band][np.searchsorted(cum, cum[-1] / 2)])
    mean_hz = float(np.sum(f[band] * pw[band]) / np.sum(pw[band]))

    snr_db = float(ratio_db[main])
    good = sum(ch["status"] == "good" for ch in channels)
    overall = "good" if good == len(channels) and snr_db > 10 else "warning" if good >= len(channels) - 2 else "critical"
    message = (f"{good} of {len(channels)} electrodes clean; the fist is {snr_db:.0f} dB above rest on {names[main]}.")

    q = int(fs // DISPLAY_FS)
    record = {
        "id": "S01",
        "subject": {"id": "GRABMyo · participant 1", "ageBand": "24–35", "sex": "—"},
        "label": "Rest → hand close",
        "durationS": round(dur, 2),
        "device": {"model": "Biosignal amplifier, 28 surface electrodes", "fs": fs, "units": "mV",
                   "placement": "Two rings of 8 on the forearm, two rings of 6 at the wrist"},
        "source": {
            "title": "GRABMyo: forearm and wrist EMG (PhysioNet), session 1, participant 1",
            "author": "Jiang, Pradhan & He 2024 · Pradhan, He & Jiang, Sci. Data 2022",
            "license": "CC BY 4.0",
            "url": "https://physionet.org/content/grabmyo/1.1.0/",
            "note": "Two separate 5-second recordings, rest and hand close, shown back to back.",
        },
        "phases": [
            {"name": "Rest", "startS": 0.0, "endS": round(split_s, 2)},
            {"name": "Hand close", "startS": round(split_s, 2), "endS": round(dur, 2)},
        ],
        "lineHz": line_hz,
        "mainChannel": names[main],
        "signal": {
            "fs": fs / q,
            "raw": r(x_raw[::q] * 1000, 2),          # µV, every other sample
            "clean": r(x_clean[::q] * 1000, 2),
            "units": "µV",
        },
        "envelope": {"t": r(env_t, 3), "uv": r(env_v, 2)},
        "channels": channels,
        "quality": {"status": overall, "message": message, "snrDb": round(snr_db, 1),
                    "goodChannels": good, "totalChannels": len(channels),
                    "lineSharePct": round(np.median([c["lineSharePct"] for c in channels]), 1)},
        "qualityWindows": windows,
        "psd": {"freqs": r(f, 2), "power": r(pw / pw.max(), 4), "medianHz": round(median_hz, 1), "meanHz": round(mean_hz, 1)},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    (OUT / "S01.json").write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.json").write_text(
        json.dumps(
            {
                "modality": "emg",
                "source": {"kind": "public", "note": "PhysioNet GRABMyo (CC BY 4.0), session 1, participant 1: rest and hand close."},
                "sessions": [{k: record[k] for k in ("id", "subject", "label", "durationS")}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"{dur:.1f} s at {fs:.0f} Hz, {len(channels)} channels, mains {line_hz:.0f} Hz")
    print(f"main {names[main]}: rest {rest_rms[main]*1000:.1f} µV, fist {act_rms[main]*1000:.1f} µV, {snr_db:.1f} dB")
    print("channel status:", {s: sum(c["status"] == s for c in channels) for s in ("good", "warning", "critical")})
    print("line share % (median):", record["quality"]["lineSharePct"], "max:", max(c["lineSharePct"] for c in channels))
    print("ratio dB range:", round(float(ratio_db.min()), 1), "to", round(float(ratio_db.max()), 1))
    print(f"median freq {median_hz:.1f} Hz, mean {mean_hz:.1f} Hz; windows:", [w["status"] for w in windows])
    print(f"size {(OUT / 'S01.json').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
