"""
SpO2 / pulse-oximetry analysis for the CMS50E capture.

Everything works on plain numpy arrays pulled from a captured frame, so it is
equally usable on a live capture, a saved session CSV, or an uploaded file.

What it computes:
  * session summary       - SpO2 and pulse-rate statistics over valid samples
  * desaturations / ODI   - dips below a rolling baseline, oxygen desaturation
                            index (events per hour), and time spent below
                            clinical thresholds (the standard nocturnal-hypoxia
                            readouts)
  * pulse from the pleth  - systolic peaks in the ~58 Hz plethysmograph, giving
                            an independent pulse-rate estimate and pulse-rate
                            variability (PRV: the PPG analogue of ECG HRV)
  * average pulse         - ensemble-averaged PPG beat morphology
  * signal quality        - valid fraction, flatline, pulse-detection stability
  * windowed features     - a per-window feature table for ML training

This is a research and self-tracking tool, not a diagnostic device.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

SPO2_INVALID = 127
NOMINAL_FS = 57.6  # CMS50E live feed, measured

# Thresholds SpO2 studies commonly report time-below for.
DEFAULT_THRESHOLDS = (94, 90, 88, 85)


# --------------------------------------------------------------------------
# Series extraction
# --------------------------------------------------------------------------
@dataclass
class Series:
    t: np.ndarray       # elapsed seconds, per sample
    spo2: np.ndarray    # SpO2 %, per sample (only meaningful where valid)
    pulse: np.ndarray   # device pulse rate, bpm, per sample
    pleth: np.ndarray   # plethysmograph waveform 0..127, per sample
    valid: np.ndarray   # bool mask of real readings (finger in)
    fs: float           # estimated sample rate, Hz

    @property
    def has_waveform(self) -> bool:
        # A real PPG needs a fast feed; stored 3 s downloads do not have one.
        return self.fs >= 10.0 and np.ptp(self.pleth[self.valid]) > 3 if self.valid.any() else False


def estimate_fs(t: np.ndarray) -> float:
    if t.size < 3:
        return NOMINAL_FS
    dt = np.diff(t)
    dt = dt[(dt > 0) & np.isfinite(dt)]
    if dt.size == 0:
        return NOMINAL_FS
    return float(1.0 / np.median(dt))


def extract(df) -> Series:
    """Pull arrays out of a captured DataFrame (tolerant of missing columns)."""
    n = len(df)

    def col(name, default=0.0):
        return df[name].to_numpy(dtype="float64") if name in df.columns else np.full(n, default)

    t = col("elapsed_s", np.nan)
    if not np.isfinite(t).any():
        t = np.arange(n, dtype="float64") / NOMINAL_FS
    spo2 = col("spo2")
    pulse = col("pulse_rate")
    pleth = col("pleth")
    if "valid" in df.columns:
        v = df["valid"]
        valid = (v.astype(str).str.lower() == "true").to_numpy() if v.dtype == object else v.to_numpy(dtype=bool)
    else:
        valid = spo2 != SPO2_INVALID
    return Series(t=t, spo2=spo2, pulse=pulse, pleth=pleth, valid=valid, fs=estimate_fs(t))


# --------------------------------------------------------------------------
# Per-second SpO2 (collapse the ~58 Hz feed to the device's real 1 Hz update)
# --------------------------------------------------------------------------
def per_second(series: Series) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (t_seconds, spo2, pulse) at 1 Hz, valid samples only."""
    m = series.valid
    if not m.any():
        return np.zeros(0), np.zeros(0), np.zeros(0)
    tv, sv, pv = series.t[m], series.spo2[m], series.pulse[m]
    sec = np.floor(tv - tv[0]).astype(int)
    uniq = np.unique(sec)
    st = np.empty(uniq.size)
    ss = np.empty(uniq.size)
    sp = np.empty(uniq.size)
    for i, u in enumerate(uniq):
        sel = sec == u
        st[i] = tv[sel][0]
        ss[i] = np.median(sv[sel])
        sp[i] = np.median(pv[sel])
    return st, ss, sp


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
def session_summary(series: Series) -> dict:
    dur = float(series.t[-1] - series.t[0]) if series.t.size else 0.0
    m = series.valid
    out = {
        "duration_s": dur,
        "n_samples": int(series.t.size),
        "fs_hz": float(series.fs),
        "valid_pct": float(100.0 * m.mean()) if m.size else 0.0,
    }
    if not m.any():
        return out
    sp = series.spo2[m].astype(float)
    pu = series.pulse[m].astype(float)
    out.update({
        "spo2_mean": float(np.mean(sp)),
        "spo2_median": float(np.median(sp)),
        "spo2_min": float(np.min(sp)),
        "spo2_max": float(np.max(sp)),
        "spo2_std": float(np.std(sp)),
        "pulse_mean": float(np.mean(pu)),
        "pulse_min": float(np.min(pu)),
        "pulse_max": float(np.max(pu)),
        "pulse_std": float(np.std(pu)),
    })
    return out


# --------------------------------------------------------------------------
# Desaturations, ODI, time-below-threshold
# --------------------------------------------------------------------------
def time_below(sec_t: np.ndarray, spo2: np.ndarray, thresholds=DEFAULT_THRESHOLDS) -> dict:
    """Seconds and percentage of valid time spent below each SpO2 threshold."""
    if sec_t.size < 2:
        return {}
    dt = float(np.median(np.diff(sec_t))) or 1.0
    total = spo2.size * dt
    out = {}
    for thr in thresholds:
        secs = float(np.sum(spo2 < thr) * dt)
        out[thr] = {"seconds": secs, "pct": (100.0 * secs / total) if total else 0.0}
    return out


def desaturations(sec_t: np.ndarray, spo2: np.ndarray, drop: float = 3.0,
                  min_duration_s: float = 10.0, baseline_window_s: float = 120.0) -> dict:
    """Detect desaturation events against a trailing-median baseline.

    An event is a stretch where SpO2 sits at least `drop` % below the local
    baseline for at least `min_duration_s`. ODI is events per hour. `drop` = 3
    or 4 matches the two ODI conventions used in sleep studies.
    """
    if sec_t.size < 5:
        return {"events": [], "odi": 0.0, "count": 0, "duration_h": 0.0}
    dt = float(np.median(np.diff(sec_t))) or 1.0
    win = max(3, int(round(baseline_window_s / dt)))
    # Causal rolling median baseline (uses data up to each point).
    baseline = np.empty_like(spo2)
    for i in range(spo2.size):
        lo = max(0, i - win + 1)
        baseline[i] = np.median(spo2[lo:i + 1])
    deficit = baseline - spo2
    below = deficit >= drop

    events = []
    i = 0
    min_len = max(1, int(round(min_duration_s / dt)))
    while i < below.size:
        if below[i]:
            j = i
            while j < below.size and below[j]:
                j += 1
            if (j - i) >= min_len:
                seg = spo2[i:j]
                events.append({
                    "start_s": float(sec_t[i]),
                    "end_s": float(sec_t[j - 1]),
                    "duration_s": float((j - i) * dt),
                    "nadir": float(np.min(seg)),
                    "depth": float(np.max(baseline[i:j] - seg)),
                })
            i = j
        else:
            i += 1

    duration_h = (sec_t[-1] - sec_t[0]) / 3600.0
    return {
        "events": events,
        "count": len(events),
        "odi": (len(events) / duration_h) if duration_h > 0 else 0.0,
        "duration_h": float(duration_h),
        "drop": drop,
        "baseline": baseline,
    }


# --------------------------------------------------------------------------
# Plethysmograph: filtering, pulse peaks, PRV, morphology
# --------------------------------------------------------------------------
def _nyq(freq: float, fs: float):
    nyq = fs / 2.0
    if freq <= 0 or freq >= nyq:
        return None
    return freq / nyq


def bandpass(x: np.ndarray, fs: float, low: float, high: float, order: int = 2) -> np.ndarray:
    lo, hi = _nyq(low, fs), _nyq(high, fs)
    if lo is None and hi is None:
        return x
    if lo is None:
        b, a = signal.butter(order, hi, btype="low")
    elif hi is None:
        b, a = signal.butter(order, lo, btype="high")
    else:
        b, a = signal.butter(order, [lo, hi], btype="band")
    return signal.filtfilt(b, a, x)


def preprocess_pleth(series: Series) -> np.ndarray:
    """Band-pass the pleth into the pulse band (0.4-5 Hz ~ 24-300 bpm)."""
    x = np.nan_to_num(series.pleth.astype("float64"))
    if x.size < 30:
        return x - np.mean(x)
    return bandpass(x - np.mean(x), series.fs, 0.4, min(5.0, series.fs / 2 - 0.1))


def detect_pulses(pleth_filt: np.ndarray, fs: float, max_bpm: float = 220) -> np.ndarray:
    """Systolic-peak indices in the band-passed pleth."""
    if pleth_filt.size < int(fs * 2):
        return np.zeros(0, dtype=int)
    min_dist = max(1, int(round(60.0 / max_bpm * fs)))
    prom = np.std(pleth_filt) * 0.3
    peaks, _ = signal.find_peaks(pleth_filt, distance=min_dist, prominence=max(prom, 1e-6))
    return peaks


RR_MIN_S, RR_MAX_S = 0.30, 2.0  # 30-200 bpm plausible pulse interval


def pulse_rate_variability(peaks: np.ndarray, fs: float, valid: np.ndarray | None = None) -> dict:
    """PRV metrics from peak-to-peak intervals (the PPG analogue of HRV)."""
    if peaks.size < 3:
        return {}
    if valid is not None:
        peaks = peaks[valid[peaks]]
        if peaks.size < 3:
            return {}
    t = peaks / fs
    ibi = np.diff(t)
    ok = (ibi >= RR_MIN_S) & (ibi <= RR_MAX_S)
    if ok.sum() < 2:
        return {}
    ibi_ms = ibi[ok] * 1000.0
    diffs = np.diff(ibi_ms)
    hr = 60.0 / ibi[ok]
    return {
        "beats": int(ok.sum() + 1),
        "pulse_from_pleth_bpm": float(np.median(hr)),
        "mean_ibi_ms": float(np.mean(ibi_ms)),
        "sdnn_ms": float(np.std(ibi_ms, ddof=1)) if ibi_ms.size > 1 else 0.0,
        "rmssd_ms": float(np.sqrt(np.mean(diffs ** 2))) if diffs.size else 0.0,
        "pnn50_pct": float(100.0 * np.sum(np.abs(diffs) > 50) / diffs.size) if diffs.size else 0.0,
        "artifact_pct": float(100.0 * (~ok).sum() / ok.size),
        "peak_times": t,
        "ibi_times": t[1:][ok],
        "ibi_ms": ibi_ms,
    }


def average_pulse(pleth_filt: np.ndarray, peaks: np.ndarray, fs: float,
                  before_s: float = 0.25, after_s: float = 0.55) -> dict:
    """Ensemble-average PPG beats aligned on the systolic peak."""
    if peaks.size < 3:
        return {}
    nb, na = int(before_s * fs), int(after_s * fs)
    wins = [pleth_filt[p - nb:p + na] for p in peaks if p - nb >= 0 and p + na <= pleth_filt.size]
    wins = [w for w in wins if w.size == nb + na]
    if len(wins) < 3:
        return {}
    stack = np.vstack(wins)
    return {
        "t_ms": (np.arange(-nb, na) / fs) * 1000.0,
        "mean": stack.mean(axis=0),
        "sd": stack.std(axis=0),
        "n": len(wins),
    }


def perfusion(pleth: np.ndarray, peaks: np.ndarray) -> dict:
    """Relative perfusion: pulsatile amplitude of the pleth (not a calibrated PI).

    The CMS50E already AC-scales the waveform to 0..127, so this is a *relative*
    perfusion indicator across a session, not an absolute perfusion index.
    """
    if peaks.size < 3:
        return {}
    troughs = []
    for a, b in zip(peaks[:-1], peaks[1:]):
        seg = pleth[a:b]
        if seg.size:
            troughs.append(np.min(seg))
    amps = pleth[peaks[:len(troughs)]] - np.asarray(troughs)
    amps = amps[np.isfinite(amps)]
    if amps.size == 0:
        return {}
    return {
        "pulse_amplitude_mean": float(np.mean(amps)),
        "pulse_amplitude_median": float(np.median(amps)),
        "pulse_amplitude_cv_pct": float(100.0 * np.std(amps) / np.mean(amps)) if np.mean(amps) else 0.0,
    }


# --------------------------------------------------------------------------
# Signal quality
# --------------------------------------------------------------------------
def signal_quality(series: Series, prv: dict) -> dict:
    m = series.valid
    q = {
        "valid_pct": float(100.0 * m.mean()) if m.size else 0.0,
        "finger_out_pct": float(100.0 * (~m).mean()) if m.size else 0.0,
    }
    if series.has_waveform and m.any():
        pw = series.pleth[m]
        q["flatline_pct"] = float(100.0 * np.mean(np.abs(np.diff(pw)) < 1e-9)) if pw.size > 1 else 0.0
    # A steady pulse gives a low interval CV; erratic detections mean noise.
    if prv.get("mean_ibi_ms"):
        q["pulse_interval_cv_pct"] = float(prv["sdnn_ms"] / prv["mean_ibi_ms"] * 100.0)
        q["pulse_artifact_pct"] = prv.get("artifact_pct", 0.0)
    return q


def quality_verdict(q: dict) -> tuple[str, str]:
    if not q:
        return "warning", "Not enough data to judge signal quality yet."
    if q.get("valid_pct", 0) < 50:
        return "critical", "Over half the session has no reading — check finger placement."
    if q.get("flatline_pct", 0) > 20:
        return "critical", "Long flat stretches in the waveform — the probe may be loose."
    if q.get("pulse_artifact_pct", 0) > 20 or q.get("valid_pct", 100) < 80:
        return "warning", "Some dropouts or erratic pulse detection — read variability with care."
    return "good", "Signal looks clean."


# --------------------------------------------------------------------------
# Windowed feature table for ML training
# --------------------------------------------------------------------------
def windowed_features(series: Series, window_s: float = 30.0) -> list[dict]:
    """Per-window features suitable as ML rows.

    Each window yields SpO2/pulse statistics, valid fraction, and (when a
    waveform is present) a pleth-derived pulse rate, PRV, and pulse amplitude.
    """
    if series.t.size == 0:
        return []
    t0 = series.t[0]
    rel = series.t - t0
    total = rel[-1]
    pleth_filt = preprocess_pleth(series) if series.has_waveform else None
    rows = []
    n_windows = int(np.floor(total / window_s)) + 1
    for w in range(n_windows):
        lo, hi = w * window_s, (w + 1) * window_s
        mask = (rel >= lo) & (rel < hi)
        if mask.sum() < 2:
            continue
        vmask = mask & series.valid
        row = {
            "window_start_s": float(lo),
            "window_end_s": float(min(hi, total)),
            "n_samples": int(mask.sum()),
            "valid_pct": float(100.0 * vmask.sum() / mask.sum()),
        }
        if vmask.any():
            sp = series.spo2[vmask]
            pu = series.pulse[vmask]
            row.update({
                "spo2_mean": float(np.mean(sp)), "spo2_min": float(np.min(sp)),
                "spo2_std": float(np.std(sp)),
                "pulse_mean": float(np.mean(pu)), "pulse_min": float(np.min(pu)),
                "pulse_max": float(np.max(pu)),
            })
        if pleth_filt is not None and mask.sum() > series.fs:
            seg = pleth_filt[mask]
            peaks = detect_pulses(seg, series.fs)
            prv = pulse_rate_variability(peaks, series.fs)
            if prv:
                row["pulse_from_pleth_bpm"] = prv["pulse_from_pleth_bpm"]
                row["prv_rmssd_ms"] = prv["rmssd_ms"]
                row["prv_sdnn_ms"] = prv["sdnn_ms"]
            perf = perfusion(series.pleth[mask], peaks)
            if perf:
                row["pulse_amplitude_mean"] = perf["pulse_amplitude_mean"]
        rows.append(row)
    return rows


def analyse(series: Series, desat_drop: float = 3.0, desat_min_s: float = 10.0,
            thresholds=DEFAULT_THRESHOLDS) -> dict:
    """One call producing everything the dashboard's Analysis tab needs."""
    sec_t, sec_spo2, sec_pulse = per_second(series)
    summary = session_summary(series)
    desat = desaturations(sec_t, sec_spo2, drop=desat_drop, min_duration_s=desat_min_s)
    below = time_below(sec_t, sec_spo2, thresholds)

    pleth_filt = preprocess_pleth(series) if series.has_waveform else np.zeros(0)
    peaks = detect_pulses(pleth_filt, series.fs) if series.has_waveform else np.zeros(0, dtype=int)
    prv = pulse_rate_variability(peaks, series.fs, series.valid) if peaks.size else {}
    beat = average_pulse(pleth_filt, peaks, series.fs) if peaks.size else {}
    perf = perfusion(series.pleth, peaks) if peaks.size else {}
    qual = signal_quality(series, prv)

    return {
        "sec_t": sec_t, "sec_spo2": sec_spo2, "sec_pulse": sec_pulse,
        "summary": summary, "desat": desat, "below": below,
        "pleth_filt": pleth_filt, "peaks": peaks, "prv": prv,
        "beat": beat, "perfusion": perf, "quality": qual,
    }
