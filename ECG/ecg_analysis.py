"""
ECG signal processing and HRV analysis for the Frontier X live stream.

Everything here works on a plain 1-D numpy array of volts sampled at a fixed
rate, so it is equally usable on a live capture, a saved CSV, or a JSONL
archive. All filters are zero-phase (filtfilt) so R-peak timing is not shifted.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import interpolate, signal

# Standard HRV frequency bands (Task Force of the ESC / NASPE, 1996).
HRV_BANDS = {
    "VLF": (0.0033, 0.04),
    "LF": (0.04, 0.15),
    "HF": (0.15, 0.40),
}

# Physiologically plausible RR interval range, in seconds (30-200 bpm).
RR_MIN_S, RR_MAX_S = 0.30, 2.0


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------

def _nyquist_guard(freq: float, fs: float) -> float | None:
    """Clamp a corner frequency below Nyquist, or return None if unusable."""
    nyq = fs / 2.0
    if freq <= 0 or freq >= nyq:
        return None
    return freq / nyq


def bandpass(sig: np.ndarray, fs: float, low: float, high: float, order: int = 2) -> np.ndarray:
    """Zero-phase Butterworth band-pass. Falls back to whichever end is valid."""
    lo = _nyquist_guard(low, fs)
    hi = _nyquist_guard(high, fs)
    if lo is None and hi is None:
        return sig
    if lo is None:
        b, a = signal.butter(order, hi, btype="low")
    elif hi is None:
        b, a = signal.butter(order, lo, btype="high")
    else:
        b, a = signal.butter(order, [lo, hi], btype="band")
    return signal.filtfilt(b, a, sig)


def notch(sig: np.ndarray, fs: float, freq: float, q: float = 30.0) -> np.ndarray:
    """Zero-phase powerline notch. No-op if the frequency is at/above Nyquist."""
    w0 = _nyquist_guard(freq, fs)
    if w0 is None:
        return sig
    b, a = signal.iirnotch(w0, q)
    return signal.filtfilt(b, a, sig)


def preprocess(
    sig: np.ndarray,
    fs: float,
    highpass: float = 0.5,
    lowpass: float = 40.0,
    powerline: float | None = 50.0,
    invert: bool = False,
) -> np.ndarray:
    """Baseline-wander removal + anti-noise low-pass + optional mains notch."""
    out = np.asarray(sig, dtype="float64")
    if out.size < 30:
        return out
    out = out - np.nanmean(out)
    out = np.nan_to_num(out)
    out = bandpass(out, fs, highpass, lowpass)
    if powerline:
        out = notch(out, fs, powerline)
    return -out if invert else out


def detect_polarity(sig: np.ndarray) -> bool:
    """True when the dominant deflection points down, i.e. the trace is inverted."""
    if sig.size < 10:
        return False
    hi = np.percentile(sig, 99.5) - np.median(sig)
    lo = np.median(sig) - np.percentile(sig, 0.5)
    return bool(lo > hi * 1.35)


# --------------------------------------------------------------------------
# R-peak detection (Pan-Tompkins style)
# --------------------------------------------------------------------------

def detect_r_peaks(sig: np.ndarray, fs: float, min_bpm: float = 30, max_bpm: float = 220) -> np.ndarray:
    """Return R-peak sample indices using a Pan-Tompkins style pipeline."""
    if sig.size < int(fs * 2):
        return np.zeros(0, dtype=int)

    # QRS-band emphasis, derivative, squaring, moving-window integration.
    qrs = bandpass(np.asarray(sig, dtype="float64"), fs, 5.0, min(15.0, fs / 2 - 1))
    deriv = np.gradient(qrs)
    squared = deriv ** 2
    win = max(3, int(round(0.150 * fs)))
    integrated = np.convolve(squared, np.ones(win) / win, mode="same")

    min_dist = max(1, int(round(60.0 / max_bpm * fs)))
    # Adaptive threshold: a fraction of the strong-peak level, robust to outliers.
    strong = np.percentile(integrated, 98)
    if not np.isfinite(strong) or strong <= 0:
        return np.zeros(0, dtype=int)
    peaks, _ = signal.find_peaks(integrated, distance=min_dist, height=0.25 * strong)
    if peaks.size == 0:
        return np.zeros(0, dtype=int)

    # Snap each detection onto the true R apex in the band-passed trace.
    search = max(1, int(round(0.05 * fs)))
    refined = []
    for p in peaks:
        a, b = max(0, p - search), min(sig.size, p + search + 1)
        refined.append(a + int(np.argmax(qrs[a:b])))
    refined = np.unique(np.asarray(refined, dtype=int))

    # Enforce the refractory period after refinement.
    keep = [refined[0]]
    for p in refined[1:]:
        if p - keep[-1] >= min_dist:
            keep.append(p)
        elif qrs[p] > qrs[keep[-1]]:
            keep[-1] = p
    return np.asarray(keep, dtype=int)


# --------------------------------------------------------------------------
# RR intervals
# --------------------------------------------------------------------------

@dataclass
class RRSeries:
    times: np.ndarray      # time of each interval's ending beat, seconds
    rr: np.ndarray         # interval length, seconds
    valid: np.ndarray      # boolean mask of physiologically plausible intervals

    @property
    def clean_rr(self) -> np.ndarray:
        return self.rr[self.valid]

    @property
    def clean_times(self) -> np.ndarray:
        return self.times[self.valid]

    @property
    def artifact_pct(self) -> float:
        return float(100.0 * (~self.valid).sum() / self.valid.size) if self.valid.size else 0.0


def rr_intervals(peaks: np.ndarray, fs: float, ectopic_tol: float = 0.20) -> RRSeries:
    """RR intervals with implausible and ectopic beats flagged (not deleted)."""
    if peaks.size < 3:
        return RRSeries(np.zeros(0), np.zeros(0), np.zeros(0, dtype=bool))

    t = peaks / fs
    rr = np.diff(t)
    times = t[1:]

    valid = (rr >= RR_MIN_S) & (rr <= RR_MAX_S)
    # Flag intervals that jump away from the local rhythm (ectopics, missed beats).
    if rr.size >= 5:
        med = signal.medfilt(rr, kernel_size=5)
        with np.errstate(divide="ignore", invalid="ignore"):
            dev = np.abs(rr - med) / np.where(med > 0, med, np.nan)
        valid &= np.nan_to_num(dev, nan=1.0) <= ectopic_tol
    return RRSeries(times, rr, valid)


# --------------------------------------------------------------------------
# HRV metrics
# --------------------------------------------------------------------------

def hrv_time_domain(rrs: RRSeries) -> dict:
    rr = rrs.clean_rr
    if rr.size < 2:
        return {}
    rr_ms = rr * 1000.0
    diffs = np.diff(rr_ms)
    hr = 60.0 / rr
    return {
        "beats": int(rr.size + 1),
        "mean_hr_bpm": float(np.mean(hr)),
        "min_hr_bpm": float(np.min(hr)),
        "max_hr_bpm": float(np.max(hr)),
        "mean_rr_ms": float(np.mean(rr_ms)),
        "sdnn_ms": float(np.std(rr_ms, ddof=1)) if rr.size > 1 else 0.0,
        "rmssd_ms": float(np.sqrt(np.mean(diffs ** 2))) if diffs.size else 0.0,
        "sdsd_ms": float(np.std(diffs, ddof=1)) if diffs.size > 1 else 0.0,
        "pnn50_pct": float(100.0 * np.sum(np.abs(diffs) > 50) / diffs.size) if diffs.size else 0.0,
        "pnn20_pct": float(100.0 * np.sum(np.abs(diffs) > 20) / diffs.size) if diffs.size else 0.0,
        "cvnn_pct": float(100.0 * np.std(rr_ms, ddof=1) / np.mean(rr_ms)) if rr.size > 1 else 0.0,
        "artifact_pct": rrs.artifact_pct,
    }


def poincare(rrs: RRSeries) -> dict:
    """SD1/SD2 from the Poincare plot of successive RR intervals."""
    rr = rrs.clean_rr * 1000.0
    if rr.size < 3:
        return {}
    x, y = rr[:-1], rr[1:]
    diffs = y - x
    sd1 = float(np.std(diffs, ddof=1) / np.sqrt(2))
    sd2_sq = 2 * np.var(rr, ddof=1) - 0.5 * np.var(diffs, ddof=1)
    sd2 = float(np.sqrt(sd2_sq)) if sd2_sq > 0 else 0.0
    return {
        "sd1_ms": sd1,
        "sd2_ms": sd2,
        "sd1_sd2_ratio": float(sd1 / sd2) if sd2 > 0 else 0.0,
        "ellipse_area_ms2": float(np.pi * sd1 * sd2),
        "x": x,
        "y": y,
    }


def hrv_frequency_domain(rrs: RRSeries, resample_hz: float = 4.0) -> dict:
    """Welch PSD of the evenly resampled RR tachogram, integrated over bands."""
    t, rr = rrs.clean_times, rrs.clean_rr
    if rr.size < 12:
        return {}
    duration = t[-1] - t[0]
    if duration < 30:
        return {"too_short": True, "duration_s": float(duration)}

    grid = np.arange(t[0], t[-1], 1.0 / resample_hz)
    kind = "cubic" if rr.size > 3 else "linear"
    tachogram = interpolate.interp1d(t, rr * 1000.0, kind=kind)(grid)
    tachogram = signal.detrend(tachogram, type="linear")

    # ~4 windows across the record, capped so short records still yield a PSD.
    nperseg = int(min(len(tachogram), max(64, resample_hz * 60)))
    freqs, psd = signal.welch(tachogram, fs=resample_hz, nperseg=nperseg,
                              noverlap=nperseg // 2, detrend=False)

    out = {"freqs": freqs, "psd": psd, "duration_s": float(duration)}
    total = 0.0
    for name, (lo, hi) in HRV_BANDS.items():
        mask = (freqs >= lo) & (freqs < hi)
        power = float(np.trapezoid(psd[mask], freqs[mask])) if mask.sum() > 1 else 0.0
        out[f"{name.lower()}_power_ms2"] = power
        total += power
    out["total_power_ms2"] = total

    lf, hf = out["lf_power_ms2"], out["hf_power_ms2"]
    out["lf_hf_ratio"] = float(lf / hf) if hf > 0 else 0.0
    if lf + hf > 0:
        out["lf_nu"] = float(100.0 * lf / (lf + hf))
        out["hf_nu"] = float(100.0 * hf / (lf + hf))
    # Frequency HRV wants >=5 min; below that LF (and VLF especially) is unreliable.
    out["short_record"] = bool(duration < 300)
    return out


# --------------------------------------------------------------------------
# Beat morphology
# --------------------------------------------------------------------------

def average_beat(sig: np.ndarray, peaks: np.ndarray, fs: float,
                 before_s: float = 0.25, after_s: float = 0.45) -> dict:
    """Ensemble-average the beats, aligned on the R peak."""
    if peaks.size < 3:
        return {}
    n_before, n_after = int(before_s * fs), int(after_s * fs)
    windows = [
        sig[p - n_before: p + n_after]
        for p in peaks
        if p - n_before >= 0 and p + n_after <= sig.size
    ]
    windows = [w for w in windows if w.size == n_before + n_after]
    if len(windows) < 3:
        return {}
    stack = np.vstack(windows)
    return {
        "t_ms": (np.arange(-n_before, n_after) / fs) * 1000.0,
        "mean": stack.mean(axis=0),
        "sd": stack.std(axis=0),
        "beats": stack,
        "n": len(windows),
    }


# --------------------------------------------------------------------------
# Signal quality
# --------------------------------------------------------------------------

def signal_quality(raw: np.ndarray, filtered: np.ndarray, fs: float, rrs: RRSeries) -> dict:
    """Cheap, interpretable quality indicators for a research record."""
    if raw.size < int(fs):
        return {}
    # Power above 40 Hz is mostly muscle/EMG noise rather than cardiac signal.
    freqs, psd = signal.welch(filtered, fs=fs, nperseg=int(min(filtered.size, fs * 4)))
    total = float(np.trapezoid(psd, freqs))
    hi_mask = freqs >= 40
    hi = float(np.trapezoid(psd[hi_mask], freqs[hi_mask])) if hi_mask.sum() > 1 else 0.0

    # Flatline = a run of near-identical consecutive raw counts.
    flat = float(100.0 * np.mean(np.abs(np.diff(raw)) < 1e-9)) if raw.size > 1 else 0.0
    return {
        "duration_s": float(raw.size / fs),
        "hf_noise_pct": float(100.0 * hi / total) if total > 0 else 0.0,
        "flatline_pct": flat,
        # In the stream's own scaled units; the caller applies a display scale.
        "amplitude": float(np.percentile(filtered, 99) - np.percentile(filtered, 1)),
        "artifact_pct": rrs.artifact_pct,
        "rr_count": int(rrs.rr.size),
    }


def quality_verdict(q: dict) -> tuple[str, str]:
    """Map quality numbers onto a (status, message) pair for the UI."""
    if not q:
        return "warning", "Not enough data to judge signal quality yet."
    if q["flatline_pct"] > 20:
        return "critical", "Long flat stretches - the sensor may not be in contact."
    if q["artifact_pct"] > 20:
        return "critical", "Over a fifth of beats look implausible - treat HRV as unreliable."
    if q["hf_noise_pct"] > 40 or q["artifact_pct"] > 5:
        return "warning", "Noticeable high-frequency noise or ectopic beats present."
    return "good", "Signal looks clean enough for HRV analysis."
