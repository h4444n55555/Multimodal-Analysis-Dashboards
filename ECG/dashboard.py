"""
Frontier X live ECG research dashboard.

Run with:
    streamlit run dashboard.py

Paste a live ECG share link to capture in real time, or upload a previously
captured .csv / .jsonl to re-analyse it offline.
"""
from __future__ import annotations

import io
import json
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ecg_analysis as ana
from ecg_core import (
    SAMPLE_RATE_HZ,
    SCALE_VOLTS_PER_COUNT,
    LiveCapture,
    PacketStore,
    elapsed_seconds,
    frame_from_jsonl,
    packets_to_frame,
    parse_stream_link,
)

st.set_page_config(page_title="ECG Research Dashboard", page_icon="~", layout="wide")

# --------------------------------------------------------------------------
# Palette - validated with the dataviz skill's checker in both modes
# (slots blue/orange/aqua, adjacent CVD dE 9.2 light / 9.4 dark).
# --------------------------------------------------------------------------
PALETTE = {
    "light": {
        "surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e",
        "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
        "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a",
        "good": "#0ca30c", "warning": "#fab219", "critical": "#d03b3b",
        "ecg_grid": "rgba(224,90,60,0.30)", "ecg_grid_minor": "rgba(224,90,60,0.13)",
    },
    "dark": {
        "surface": "#1a1a19", "text": "#ffffff", "text2": "#c3c2b7",
        "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835",
        "s1": "#3987e5", "s2": "#d95926", "s3": "#199e70",
        "good": "#0ca30c", "warning": "#fab219", "critical": "#d03b3b",
        "ecg_grid": "rgba(224,90,60,0.34)", "ecg_grid_minor": "rgba(224,90,60,0.15)",
    },
}


def theme() -> dict:
    try:
        mode = st.context.theme.type or "light"
    except Exception:
        mode = "light"
    return PALETTE.get(mode, PALETTE["light"])


def base_fig(height: int = 320, xtitle: str = "", ytitle: str = "") -> go.Figure:
    """A figure with recessive hairline chrome and generous padding."""
    c = theme()
    fig = go.Figure()
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  size=12, color=c["text2"]),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=c["surface"], font_size=12, bordercolor=c["axis"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=c["text2"])),
        showlegend=False,
    )
    axis = dict(showgrid=True, gridcolor=c["grid"], gridwidth=1, griddash="solid",
                zeroline=False, linecolor=c["axis"], linewidth=1,
                ticks="outside", tickcolor=c["axis"], tickfont=dict(color=c["muted"]))
    fig.update_xaxes(title=dict(text=xtitle, font=dict(color=c["muted"])), **axis)
    fig.update_yaxes(title=dict(text=ytitle, font=dict(color=c["muted"])), **axis)
    return fig


def decimate_minmax(x: np.ndarray, y: np.ndarray, target: int = 6000):
    """Envelope-preserving decimation - keeps R peaks that stride sampling loses."""
    n = x.size
    if n <= target:
        return x, y
    bucket = int(np.ceil(n / (target / 2)))
    usable = (n // bucket) * bucket
    xb = x[:usable].reshape(-1, bucket)
    yb = y[:usable].reshape(-1, bucket)
    imin, imax = yb.argmin(axis=1), yb.argmax(axis=1)
    rows = np.arange(yb.shape[0])
    order = np.where(imin < imax, 1, 0)
    first_i = np.where(order == 1, imin, imax)
    second_i = np.where(order == 1, imax, imin)
    xs = np.empty(yb.shape[0] * 2)
    ys = np.empty(yb.shape[0] * 2)
    xs[0::2], xs[1::2] = xb[rows, first_i], xb[rows, second_i]
    ys[0::2], ys[1::2] = yb[rows, first_i], yb[rows, second_i]
    if usable < n:
        xs = np.append(xs, x[usable:])
        ys = np.append(ys, y[usable:])
    return xs, ys


def table_view(df: pd.DataFrame, label: str, filename: str, max_rows: int = 2000) -> None:
    """Every chart gets a table-view twin plus its own download."""
    with st.expander(f"Table view - {label}"):
        st.caption(f"{len(df):,} rows" + (f" (showing first {max_rows:,})" if len(df) > max_rows else ""))
        st.dataframe(df.head(max_rows), width="stretch", height=260)
        st.download_button(
            f"Download {filename}", df.to_csv(index=False).encode(),
            file_name=filename, mime="text/csv", key=f"dl_{filename}",
        )


def stat(col, label: str, value, unit: str = "", help_text: str | None = None, fmt: str = "{:.1f}"):
    text = "-" if value is None or (isinstance(value, float) and not np.isfinite(value)) else fmt.format(value)
    col.metric(label, f"{text}{unit}", help=help_text)


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "store" not in st.session_state:
    st.session_state.store = PacketStore()
    st.session_state.capture = None
    st.session_state.uploaded = None


def start_capture(link: str) -> None:
    userid, domain = parse_stream_link(link)
    stop_capture()
    st.session_state.store.clear()
    cap = LiveCapture(userid, domain, st.session_state.store)
    cap.start()
    st.session_state.capture = cap


def stop_capture() -> None:
    cap = st.session_state.capture
    if cap is not None and cap.is_alive():
        cap.stop()
    st.session_state.capture = None


# --------------------------------------------------------------------------
# Sidebar - one control surface scoping every chart below
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Data source")
    source = st.radio("Source", ["Live stream", "Uploaded file"], label_visibility="collapsed")

    if source == "Live stream":
        link = st.text_input(
            "Live ECG link",
            value=st.session_state.get("last_link", ""),
            placeholder="https://liveecg.frontierxapp.com/6005748/Hans",
            help="The share link from the Frontier X app, or just the numeric user id.",
        )
        st.session_state.last_link = link
        cap = st.session_state.capture
        running = cap is not None and cap.is_alive()

        c1, c2 = st.columns(2)
        if c1.button("Start", type="primary", width="stretch", disabled=running):
            try:
                start_capture(link)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        if c2.button("Stop", width="stretch", disabled=not running):
            stop_capture()
            st.rerun()

        if running:
            st.caption("Recording status is in the status strip at the top of the page.")
        elif st.session_state.store.stats()["packets"]:
            st.info("Stopped - captured data is still loaded.")

        if st.button("Refresh view", width="stretch",
                     help="Pull the latest captured data into the charts below."):
            st.rerun()

        if st.button("Clear captured data", width="stretch"):
            stop_capture()
            st.session_state.store.clear()
            st.rerun()
    else:
        upload = st.file_uploader(
            "Capture file", type=["csv", "jsonl"],
            help="A .csv or .jsonl written by this dashboard or by stream_capture.py.",
        )
        if upload is not None:
            raw_bytes = upload.getvalue()
            try:
                if upload.name.lower().endswith(".jsonl"):
                    df_up, packets_up = frame_from_jsonl(raw_bytes.decode("utf-8", "replace"))
                else:
                    df_up = pd.read_csv(io.BytesIO(raw_bytes))
                    if "volts" not in df_up.columns and "raw_count" in df_up.columns:
                        df_up["volts"] = df_up["raw_count"] * SCALE_VOLTS_PER_COUNT
                    packets_up = []
                st.session_state.uploaded = {"df": df_up, "packets": packets_up, "name": upload.name}
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read {upload.name}: {e}")

    st.divider()
    st.markdown("### Processing")
    fs = st.number_input("Sample rate (Hz)", 10.0, 2000.0, SAMPLE_RATE_HZ, step=1.0,
                         help="125 Hz is what the Frontier X live stream delivers.")
    hp = st.slider("High-pass (Hz)", 0.05, 2.0, 0.5, 0.05,
                   help="Removes baseline wander from breathing and movement.")
    lp = st.slider("Low-pass (Hz)", 15.0, min(60.0, fs / 2 - 1), min(40.0, fs / 2 - 1), 1.0,
                   help="Removes muscle noise above the ECG band.")
    mains = st.selectbox("Powerline notch", ["Off", "50 Hz", "60 Hz"], index=1)
    mains_hz = {"Off": None, "50 Hz": 50.0, "60 Hz": 60.0}[mains]
    if mains_hz and mains_hz >= fs / 2:
        st.caption(f"{mains:.0f} Hz is above Nyquist at {fs:.0f} Hz - notch skipped.")
    auto_invert = st.checkbox("Auto-correct inverted trace", value=True)
    manual_invert = st.checkbox("Force invert", value=False)

    st.divider()
    st.markdown("### Amplitude units")
    st.caption(
        "The webapp scales raw counts by 3.8146972e-6 but never labels the unit. "
        "A peak-to-peak swing of ~1.3 in those units matches a normal ECG in "
        "millivolts, so 1 unit is treated as 1 mV. Change the scale if you have "
        "a real calibration."
    )
    amp_scale = st.number_input("Display scale (per stream unit)", 0.0001, 10000.0, 1.0,
                                format="%.4f")
    unit_label = st.text_input("Unit label", value="mV (uncalibrated)")

    st.divider()
    st.markdown("### Beat detection")
    max_bpm = st.slider("Max plausible HR (bpm)", 120, 260, 220, 5)
    ectopic_tol = st.slider("Ectopic tolerance", 0.05, 0.5, 0.20, 0.01,
                            help="An RR interval deviating from the local median by more "
                                 "than this fraction is flagged as an artifact.")


@st.cache_data(show_spinner=False, max_entries=6)
def analyse(sig_bytes: bytes, fs: float, hp: float, lp: float, mains_hz: float | None,
            auto_invert: bool, manual_invert: bool, max_bpm: float, ectopic_tol: float) -> dict:
    sig = np.frombuffer(sig_bytes, dtype="float64")
    inverted = manual_invert
    if auto_invert and not manual_invert:
        probe = ana.preprocess(sig, fs, hp, lp, mains_hz, invert=False)
        inverted = ana.detect_polarity(probe)
    filt = ana.preprocess(sig, fs, hp, lp, mains_hz, invert=inverted)
    peaks = ana.detect_r_peaks(filt, fs, max_bpm=max_bpm)
    rrs = ana.rr_intervals(peaks, fs, ectopic_tol=ectopic_tol)
    return {
        "filtered": filt,
        "inverted": inverted,
        "peaks": peaks,
        "rr": rrs,
        "time_domain": ana.hrv_time_domain(rrs),
        "poincare": ana.poincare(rrs),
        "frequency": ana.hrv_frequency_domain(rrs),
        "beat": ana.average_beat(filt, peaks, fs),
        "quality": ana.signal_quality(sig, filt, fs, rrs),
    }


st.title("Frontier X ECG research dashboard")


def _live_running() -> bool:
    cap = st.session_state.get("capture")
    return bool(source == "Live stream" and cap is not None and cap.is_alive())


if source == "Live stream":
    # A cheap, always-registered status strip: just packet counts and the
    # device-reported heart rate, no filtering or peak detection - so it can
    # tick every second without the lag a full analysis re-run would cause.
    # Registering it here, before any chance of an early return below, is
    # also what keeps it alive even in the instant right after Start when
    # no packets have arrived yet.
    @st.fragment(run_every="1s" if _live_running() else None)
    def live_status():
        s = st.session_state.store.stats()
        cap = st.session_state.capture
        running = cap is not None and cap.is_alive()

        badge, *cols = st.columns([1.3, 1, 1, 1, 1, 1])
        with badge:
            if running:
                if cap.connected:
                    st.success("Recording")
                else:
                    st.warning("Reconnecting...")
            elif s["packets"]:
                st.info("Stopped")
            else:
                st.caption("Not started")
        who = s["meta"].get("userName")
        stat(cols[0], who or "Heart rate", s["heartrate"], " bpm", "Reported by the device.", "{:.0f}")
        stat(cols[1], "Recorded", (s["samples"] / fs) if s["samples"] else None, " s",
             "Length captured so far.", "{:.0f}")
        stat(cols[2], "Packets", s["packets"] if (running or s["packets"]) else None,
             "", "Unique 1-second packets accepted.", "{:.0f}")
        stat(cols[3], "Missed", s["missed"] if (running or s["packets"]) else None,
             "", "Gaps in packetNo - data the server never delivered.", "{:.0f}")
        stat(cols[4], "Duplicates", s["duplicates"] if (running or s["packets"]) else None,
             "", "Repeat frames discarded (the server sends each packet ~3x).", "{:.0f}")

        if running:
            gap = s["seconds_since_packet"]
            if gap is None:
                st.caption("Connected, waiting for the device to start streaming...")
            elif gap > 8:
                st.warning(f"No data for {gap:.0f}s - the device may have stopped streaming.")

    live_status()
    st.caption(
        "The charts below are a snapshot - use **Refresh view** in the sidebar, or Start/Stop, "
        "to pull in newly captured data. They don't auto-update, to keep the app responsive."
    )
    st.divider()


def render_app():
    store: PacketStore = st.session_state.store
    stats = store.stats()

    if source == "Live stream":
        packets = store.snapshot()
        df = packets_to_frame(packets)
        label = f"live_{stats['meta'].get('userID', 'session')}"
    else:
        up = st.session_state.uploaded
        df = up["df"] if up else pd.DataFrame()
        packets = up["packets"] if up else []
        label = (up["name"].rsplit(".", 1)[0] if up else "no_file")

    has_data = not df.empty and "volts" in df.columns

    if not has_data:
        st.info(
            "**No data loaded.** Paste your live ECG link in the sidebar and press **Start**, "
            "or switch the source to *Uploaded file* and drop in a `.csv` / `.jsonl` "
            "captured earlier."
        )
        st.caption(
            "The live stream delivers 125 samples per second. Capture for at least "
            "two minutes before reading the HRV frequency metrics, and five minutes "
            "for LF power to mean anything."
        )
        return

    # One filter row, scoping every tab below it.
    full_df = df
    full_t = elapsed_seconds(full_df)
    full_duration = float(full_t[-1]) if full_t.size else 0.0

    seg_c = st.columns([1, 1, 3])
    seg_from = seg_c[0].number_input(
        "Analyse from (s)", 0.0, max(0.0, full_duration), 0.0, 5.0,
        help="Crop the record before analysis - useful for picking a stationary segment.",
    )
    seg_len = seg_c[1].number_input(
        "Length (s), 0 = to end", 0.0, max(0.0, full_duration), 0.0, 30.0,
        help="HRV frequency metrics conventionally use a 5-minute (300 s) window.",
    )
    seg_to = full_duration if seg_len <= 0 else min(full_duration, seg_from + seg_len)
    seg_mask = (full_t >= seg_from) & (full_t <= seg_to)
    if seg_mask.sum() < 10:
        seg_mask = np.ones(len(full_df), dtype=bool)
        seg_from, seg_to = 0.0, full_duration
    df = full_df.iloc[seg_mask.nonzero()[0]]
    if seg_to - seg_from < full_duration - 0.5:
        seg_c[2].caption(
            f"Analysing {seg_from:,.0f}-{seg_to:,.0f} s of a {full_duration:,.0f} s record "
            f"({seg_mask.sum():,} samples). Charts below reflect this segment."
        )

    raw_v = df["volts"].to_numpy(dtype="float64")
    t_s = elapsed_seconds(df)
    res = analyse(raw_v.tobytes(), fs, hp, lp, mains_hz, auto_invert, manual_invert, max_bpm, ectopic_tol)
    filt_v, peaks, rrs = res["filtered"], res["peaks"], res["rr"]
    td, freq, pc, beat, qual = (res["time_domain"], res["frequency"], res["poincare"],
                                res["beat"], res["quality"])

    tabs = st.tabs(["Live monitor", "Waveform", "HRV & rhythm", "Beat morphology", "Export"])

    # --------------------------------------------------------------------------
    # Tab 1 - Live monitor
    # --------------------------------------------------------------------------
    with tabs[0]:
        if source == "Live stream":
            meta = stats["meta"]
            who = meta.get("userName") or "-"
            detail = []
            if meta.get("age"):
                detail.append(f"{meta['age']}y")
            if meta.get("gender"):
                detail.append(str(meta["gender"]))
            if meta.get("macID"):
                detail.append(f"device {meta['macID']}")
            st.caption(f"**{who}** " + (" - ".join(detail) if detail else ""))
            st.caption("Live packet counts and heart rate are in the status strip above.")

        if qual:
            status, message = ana.quality_verdict(qual)
            st.markdown("#### Signal quality")
            q = st.columns(4)
            stat(q[0], "Amplitude", qual["amplitude"] * amp_scale, "", "1st-99th percentile span.", "{:.2f}")
            stat(q[1], "HF noise", qual["hf_noise_pct"], " %", "Share of power above 40 Hz.", "{:.0f}")
            stat(q[2], "Flatline", qual["flatline_pct"], " %", "Samples with no change - lead-off.", "{:.1f}")
            stat(q[3], "Artifact beats", qual["artifact_pct"], " %", "RR intervals flagged implausible.", "{:.1f}")
            {"good": st.success, "warning": st.warning, "critical": st.error}[status](message)

    # --------------------------------------------------------------------------
    # Tab 2 - Waveform
    # --------------------------------------------------------------------------
    with tabs[1]:
        c = theme()
        total_s = float(t_s[-1]) if t_s.size else 0.0

        ctrl = st.columns([2, 1, 1, 1])
        win = ctrl[0].slider("Window (s)", 2.0, max(4.0, min(120.0, total_s or 4.0)),
                             min(10.0, max(4.0, total_s)), 1.0)
        start = ctrl[1].number_input("Start (s)", 0.0, max(0.0, total_s - 1), 0.0, 1.0)
        show_raw = ctrl[2].checkbox("Show raw", value=False)
        clinical = ctrl[3].checkbox("ECG grid", value=True,
                                    help="Standard 0.2 s x 0.5 mV major grid.")

        m = (t_s >= start) & (t_s <= start + win)
        seg_t, seg_raw, seg_filt = t_s[m], raw_v[m], filt_v[m]

        fig = base_fig(420, "seconds", unit_label)
        if clinical:
            fig.update_xaxes(dtick=0.2, gridcolor=c["ecg_grid"], minor=dict(
                dtick=0.04, showgrid=True, gridcolor=c["ecg_grid_minor"], griddash="solid"))
            fig.update_yaxes(dtick=0.5, gridcolor=c["ecg_grid"], minor=dict(
                dtick=0.1, showgrid=True, gridcolor=c["ecg_grid_minor"], griddash="solid"))

        if show_raw:
            dx, dy = decimate_minmax(seg_t, (seg_raw - np.mean(seg_raw)) * amp_scale)
            fig.add_trace(go.Scattergl(x=dx, y=dy, mode="lines", name="Raw (centred)",
                                       line=dict(color=c["s2"], width=1),
                                       hovertemplate="%{y:.3f}<extra>Raw</extra>"))
            fig.update_layout(showlegend=True)

        dx, dy = decimate_minmax(seg_t, seg_filt * amp_scale)
        fig.add_trace(go.Scattergl(x=dx, y=dy, mode="lines", name="Filtered",
                                   line=dict(color=c["s1"], width=1.5),
                                   hovertemplate="%{y:.3f}<extra>Filtered</extra>"))

        pk_t = peaks / fs
        pk_m = (pk_t >= start) & (pk_t <= start + win)
        if pk_m.any():
            fig.add_trace(go.Scattergl(
                x=pk_t[pk_m], y=filt_v[peaks[pk_m]] * amp_scale, mode="markers", name="R peak",
                marker=dict(color=c["s3"], size=9, symbol="circle-open", line=dict(width=2)),
                hovertemplate="R at %{x:.3f}s<extra></extra>"))
            fig.update_layout(showlegend=True)

        st.plotly_chart(fig, width="stretch")
        st.caption(
            f"{total_s:,.0f} s recorded at {fs:.0f} Hz - {len(df):,} samples, {peaks.size:,} beats detected"
            + (" - trace auto-inverted" if res["inverted"] else "")
        )

        table_view(df.assign(volts_filtered=filt_v).iloc[m.nonzero()[0]],
                   "waveform window", f"{label}_window.csv")

    # --------------------------------------------------------------------------
    # Tab 3 - HRV & rhythm
    # --------------------------------------------------------------------------
    with tabs[2]:
        c = theme()
        if not td:
            st.warning("Not enough detected beats for HRV yet - capture at least ~30 seconds.")
        else:
            st.markdown("#### Time domain")
            a = st.columns(4)
            stat(a[0], "Mean HR", td["mean_hr_bpm"], " bpm", None, "{:.1f}")
            stat(a[1], "Mean RR", td["mean_rr_ms"], " ms", "Average beat-to-beat interval.", "{:.0f}")
            stat(a[2], "SDNN", td["sdnn_ms"], " ms", "SD of NN intervals - overall variability.", "{:.1f}")
            stat(a[3], "RMSSD", td["rmssd_ms"], " ms", "Beat-to-beat variability; vagal tone.", "{:.1f}")
            b = st.columns(4)
            stat(b[0], "pNN50", td["pnn50_pct"], " %", "Share of successive RR pairs differing >50 ms.", "{:.1f}")
            stat(b[1], "HR range", td["max_hr_bpm"] - td["min_hr_bpm"], " bpm", None, "{:.0f}")
            stat(b[2], "Beats", td["beats"], "", "Beats used after artifact rejection.", "{:.0f}")
            stat(b[3], "Artifacts", td["artifact_pct"], " %", "Flagged and excluded from HRV.", "{:.1f}")

            st.markdown("#### RR tachogram")
            fig = base_fig(300, "seconds", "RR interval (ms)")
            fig.add_trace(go.Scattergl(
                x=rrs.clean_times, y=rrs.clean_rr * 1000.0, mode="lines+markers", name="Accepted",
                line=dict(color=c["s1"], width=1.5), marker=dict(size=5),
                hovertemplate="%{x:.1f}s<br>%{y:.0f} ms<extra></extra>"))
            bad = ~rrs.valid
            if bad.any():
                fig.add_trace(go.Scattergl(
                    x=rrs.times[bad], y=rrs.rr[bad] * 1000.0, mode="markers", name="Artifact",
                    marker=dict(color=c["s2"], size=8, symbol="x", line=dict(width=1)),
                    hovertemplate="%{x:.1f}s<br>%{y:.0f} ms<extra>Artifact</extra>"))
                fig.update_layout(showlegend=True)
            st.plotly_chart(fig, width="stretch")

            left, right = st.columns(2)
            with left:
                st.markdown("#### Poincare plot")
                if pc:
                    fig = base_fig(360, "RR n (ms)", "RR n+1 (ms)")
                    fig.update_layout(hovermode="closest")
                    lo = float(min(pc["x"].min(), pc["y"].min())) - 20
                    hi = float(max(pc["x"].max(), pc["y"].max())) + 20
                    fig.add_trace(go.Scattergl(
                        x=[lo, hi], y=[lo, hi], mode="lines", name="identity",
                        line=dict(color=c["axis"], width=1), hoverinfo="skip", showlegend=False))
                    fig.add_trace(go.Scattergl(
                        x=pc["x"], y=pc["y"], mode="markers", name="RR pair",
                        marker=dict(color=c["s1"], size=7, opacity=0.55,
                                    line=dict(width=2, color=c["surface"])),
                        hovertemplate="%{x:.0f} -> %{y:.0f} ms<extra></extra>"))
                    fig.update_xaxes(range=[lo, hi])
                    fig.update_yaxes(range=[lo, hi], scaleanchor="x", scaleratio=1)
                    fig.add_annotation(x=0.02, y=0.98, xref="paper", yref="paper",
                                       showarrow=False, align="left",
                                       text=f"SD1 {pc['sd1_ms']:.1f} ms<br>SD2 {pc['sd2_ms']:.1f} ms"
                                            f"<br>SD1/SD2 {pc['sd1_sd2_ratio']:.2f}",
                                       font=dict(color=c["text2"], size=12))
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.caption("Needs at least three clean intervals.")

            with right:
                st.markdown("#### RR spectrum")
                if freq.get("too_short") or not freq.get("freqs", np.zeros(0)).size:
                    st.caption(f"Needs ~30 s of beats; have {freq.get('duration_s', 0):.0f} s.")
                else:
                    fig = base_fig(360, "Hz", "PSD (ms^2/Hz)")
                    fig.update_layout(hovermode="x")
                    for name, (blo, bhi), col in (("LF", ana.HRV_BANDS["LF"], c["s1"]),
                                                  ("HF", ana.HRV_BANDS["HF"], c["s2"])):
                        fig.add_vrect(x0=blo, x1=bhi, fillcolor=col, opacity=0.10,
                                      line_width=0, layer="below")
                        fig.add_annotation(x=(blo + bhi) / 2, y=1.0, yref="paper", yanchor="bottom",
                                           text=name, showarrow=False,
                                           font=dict(color=c["text2"], size=12))
                    fmask = freq["freqs"] <= 0.5
                    fig.add_trace(go.Scattergl(
                        x=freq["freqs"][fmask], y=freq["psd"][fmask], mode="lines", name="PSD",
                        line=dict(color=c["s1"], width=2),
                        hovertemplate="%{x:.3f} Hz<br>%{y:.0f}<extra></extra>"))
                    st.plotly_chart(fig, width="stretch")

            if freq.get("freqs", np.zeros(0)).size:
                f = st.columns(4)
                stat(f[0], "LF power", freq["lf_power_ms2"], " ms2", "0.04-0.15 Hz.", "{:.0f}")
                stat(f[1], "HF power", freq["hf_power_ms2"], " ms2", "0.15-0.40 Hz; respiratory.", "{:.0f}")
                stat(f[2], "LF/HF", freq["lf_hf_ratio"], "", "Sympathovagal balance proxy.", "{:.2f}")
                stat(f[3], "Total power", freq["total_power_ms2"], " ms2", "VLF+LF+HF.", "{:.0f}")
                if freq.get("short_record"):
                    st.info(
                        f"Record is {freq['duration_s']:.0f} s. Frequency-domain HRV assumes a "
                        "5-minute stationary segment - LF and especially VLF are unreliable below that."
                    )

            rr_df = pd.DataFrame({
                "time_s": rrs.times, "rr_ms": rrs.rr * 1000.0,
                "instant_hr_bpm": 60.0 / rrs.rr, "accepted": rrs.valid,
            })
            table_view(rr_df, "RR intervals", f"{label}_rr_intervals.csv")

    # --------------------------------------------------------------------------
    # Tab 4 - Beat morphology
    # --------------------------------------------------------------------------
    with tabs[3]:
        c = theme()
        if not beat:
            st.warning("Needs at least three complete beats.")
        else:
            st.markdown("#### Ensemble-averaged beat")
            show_all = st.checkbox("Overlay individual beats", value=True)
            fig = base_fig(420, "ms from R peak", unit_label)
            if show_all:
                step = max(1, beat["beats"].shape[0] // 120)
                for row in beat["beats"][::step]:
                    fig.add_trace(go.Scattergl(
                        x=beat["t_ms"], y=row * amp_scale, mode="lines", showlegend=False,
                        line=dict(color=c["muted"], width=0.6), opacity=0.25, hoverinfo="skip"))
            upper = (beat["mean"] + beat["sd"]) * amp_scale
            lower = (beat["mean"] - beat["sd"]) * amp_scale
            fig.add_trace(go.Scatter(
                x=np.concatenate([beat["t_ms"], beat["t_ms"][::-1]]),
                y=np.concatenate([upper, lower[::-1]]), fill="toself", mode="lines",
                line=dict(width=0), fillcolor=c["s1"], opacity=0.15,
                name="+/-1 SD", hoverinfo="skip"))
            fig.add_trace(go.Scattergl(
                x=beat["t_ms"], y=beat["mean"] * amp_scale, mode="lines", name="Mean beat",
                line=dict(color=c["s1"], width=2),
                hovertemplate="%{x:.0f} ms<br>%{y:.3f}<extra></extra>"))
            fig.add_vline(x=0, line=dict(color=c["axis"], width=1))
            fig.update_layout(showlegend=True)
            st.plotly_chart(fig, width="stretch")
            st.caption(
                f"Averaged over {beat['n']:,} beats. The shaded band is +/-1 SD across beats - "
                "a wide band means variable morphology or residual noise, not a wide QRS."
            )

            beat_df = pd.DataFrame({
                "t_ms": beat["t_ms"],
                "mean_amplitude": beat["mean"] * amp_scale,
                "sd_amplitude": beat["sd"] * amp_scale,
            })
            table_view(beat_df, "average beat", f"{label}_average_beat.csv")

    # --------------------------------------------------------------------------
    # Tab 5 - Export
    # --------------------------------------------------------------------------
    with tabs[4]:
        st.markdown("#### Download the record")
        st.caption(
            f"`raw_count` is exactly what the device sent. `volts` applies the webapp's own "
            f"{SCALE_VOLTS_PER_COUNT:g} per-count factor - the column keeps that name for "
            "compatibility with stream_capture.py, but the absolute unit is undocumented "
            "(see the sidebar). `volts_filtered` reflects the current filter settings."
        )

        export_df = df.copy()
        export_df["volts_filtered"] = filt_v
        export_df["is_r_peak"] = False
        if peaks.size:
            export_df.iloc[peaks, export_df.columns.get_loc("is_r_peak")] = True

        d = st.columns(3)
        d[0].download_button("Samples (CSV)", export_df.to_csv(index=False).encode(),
                             file_name=f"{label}_samples.csv", mime="text/csv", width="stretch")
        if packets:
            jsonl = "\n".join(json.dumps(p, separators=(",", ":")) for p in packets).encode()
            d[1].download_button("Raw packets (JSONL)", jsonl,
                                 file_name=f"{label}_packets.jsonl", mime="application/x-ndjson",
                                 width="stretch")
        else:
            d[1].button("Raw packets (JSONL)", disabled=True, width="stretch",
                        help="Only available for a live capture or an uploaded .jsonl.")

        metrics = {
            "source": label,
            "sample_rate_hz": fs,
            "samples": int(len(df)),
            "duration_s": float(len(df) / fs),
            "segment": {"from_s": float(seg_from), "to_s": float(seg_to),
                        "full_record_s": float(full_duration)},
            "session_start_ms": stats.get("session_timestamp"),
            "subject": stats.get("meta", {}),
            "processing": {
                "highpass_hz": hp, "lowpass_hz": lp, "powerline_notch_hz": mains_hz,
                "inverted": bool(res["inverted"]), "max_bpm": max_bpm,
                "ectopic_tolerance": ectopic_tol,
                "amplitude_scale_per_stream_unit": amp_scale,
                "amplitude_unit_label": unit_label,
            },
            "capture": {k: stats[k] for k in ("packets", "received", "duplicates", "missed")},
            "quality": qual,
            "hrv_time_domain": td,
            "hrv_frequency_domain": {k: v for k, v in freq.items()
                                     if not isinstance(v, np.ndarray)},
            "poincare": {k: v for k, v in pc.items() if not isinstance(v, np.ndarray)},
        }
        d[2].download_button("Metrics (JSON)", json.dumps(metrics, indent=2, default=str).encode(),
                             file_name=f"{label}_metrics.json", mime="application/json",
                             width="stretch")

        st.markdown("#### Session summary")
        st.json(metrics, expanded=False)

        st.markdown("#### Reproducibility note")
        st.caption(
            "R peaks come from a Pan-Tompkins pipeline (5-15 Hz band-pass, derivative, "
            "squaring, 150 ms moving-window integration) with peaks refined onto the QRS "
            "apex. RR intervals outside 0.30-2.0 s, or deviating from the local 5-beat "
            "median by more than the ectopic tolerance, are flagged and excluded from HRV. "
            "Frequency-domain HRV uses a cubic-interpolated 4 Hz tachogram, linear detrend, "
            "and Welch PSD. This is a research and self-tracking tool, not a diagnostic device."
        )

render_app()
