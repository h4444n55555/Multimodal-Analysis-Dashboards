"""
Contec CMS50E SpO2 research dashboard.

Run with:
    streamlit run dashboard.py

Use it to run a recording session on a subject (check the device is connected
and reading a finger *before* you start, enter who/what the session is, capture
to an organized per-subject folder), then analyse it and export ML-ready data.
A previously saved session (or any samples.csv from stream_capture.py) can be
loaded back for offline analysis.

Live SpO2 / pulse / signal status updates every second in a lightweight strip
that is independent of the heavy analysis, so the app stays responsive while
recording. The live waveform is optional and off by default (the vendor app
shows it anyway); when enabled it only draws a short decimated window.
"""
from __future__ import annotations

import io
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import spo2_analysis as ana
import spo2_core as core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(page_title="SpO2 Research Dashboard", page_icon="O", layout="wide")

# --------------------------------------------------------------------------
# Palette (same family as the ECG dashboard, for a consistent look across the
# sensor suite).
# --------------------------------------------------------------------------
PALETTE = {
    "light": {"surface": "#fcfcfb", "text2": "#52514e", "muted": "#898781",
              "grid": "#e1e0d9", "axis": "#c3c2b7", "s1": "#2a78d6", "s2": "#eb6834",
              "s3": "#1baf7a", "good": "#0ca30c", "warning": "#fab219", "critical": "#d03b3b"},
    "dark": {"surface": "#1a1a19", "text2": "#c3c2b7", "muted": "#898781",
             "grid": "#2c2c2a", "axis": "#383835", "s1": "#3987e5", "s2": "#d95926",
             "s3": "#199e70", "good": "#0ca30c", "warning": "#fab219", "critical": "#d03b3b"},
}


def theme() -> dict:
    try:
        mode = st.context.theme.type or "light"
    except Exception:
        mode = "light"
    return PALETTE.get(mode, PALETTE["light"])


def base_fig(height: int = 320, xtitle: str = "", ytitle: str = "") -> go.Figure:
    c = theme()
    fig = go.Figure()
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=12, color=c["text2"]),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=c["surface"], font_size=12, bordercolor=c["axis"]),
        showlegend=False,
    )
    axis = dict(showgrid=True, gridcolor=c["grid"], gridwidth=1, zeroline=False,
                linecolor=c["axis"], linewidth=1, ticks="outside", tickcolor=c["axis"],
                tickfont=dict(color=c["muted"]))
    fig.update_xaxes(title=dict(text=xtitle, font=dict(color=c["muted"])), **axis)
    fig.update_yaxes(title=dict(text=ytitle, font=dict(color=c["muted"])), **axis)
    return fig


def decimate(x: np.ndarray, y: np.ndarray, target: int = 4000):
    """Envelope-preserving min/max decimation, so pulse peaks survive."""
    n = x.size
    if n <= target:
        return x, y
    bucket = int(np.ceil(n / (target / 2)))
    usable = (n // bucket) * bucket
    xb, yb = x[:usable].reshape(-1, bucket), y[:usable].reshape(-1, bucket)
    imin, imax = yb.argmin(axis=1), yb.argmax(axis=1)
    rows = np.arange(yb.shape[0])
    first = np.where(imin < imax, imin, imax)
    second = np.where(imin < imax, imax, imin)
    xs, ys = np.empty(yb.shape[0] * 2), np.empty(yb.shape[0] * 2)
    xs[0::2], xs[1::2] = xb[rows, first], xb[rows, second]
    ys[0::2], ys[1::2] = yb[rows, first], yb[rows, second]
    if usable < n:
        xs, ys = np.append(xs, x[usable:]), np.append(ys, y[usable:])
    return xs, ys


def stat(col, label: str, value, unit: str = "", help_text=None, fmt: str = "{:.1f}"):
    text = "-" if value is None or (isinstance(value, float) and not np.isfinite(value)) else fmt.format(value)
    col.metric(label, f"{text}{unit}", help=help_text)


def table_view(df: pd.DataFrame, label: str, filename: str, max_rows: int = 3000) -> None:
    with st.expander(f"Table view - {label}"):
        st.caption(f"{len(df):,} rows" + (f" (showing first {max_rows:,})" if len(df) > max_rows else ""))
        st.dataframe(df.head(max_rows), width="stretch", height=260)
        st.download_button(f"Download {filename}", df.to_csv(index=False).encode(),
                           file_name=filename, mime="text/csv", key=f"dl_{filename}")


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "store" not in st.session_state:
    st.session_state.store = core.SpO2Store()
    st.session_state.capture = None
    st.session_state.session_dir = None
    st.session_state.session_meta = {}
    st.session_state.uploaded = None
    st.session_state.probe = None


def capture_running() -> bool:
    cap = st.session_state.capture
    return cap is not None and cap.is_alive()


def start_session(port, protocol, meta) -> None:
    stop_session()
    st.session_state.store.clear()
    session_dir, stamp = core.make_session_dir(BASE_DIR, meta.get("subject_id") or meta.get("subject_name", ""),
                                               meta.get("session_label", ""))
    meta = dict(meta)
    meta.update({"port": port, "protocol": protocol, "started_iso": datetime.now().isoformat(timespec="seconds"),
                 "timestamp": stamp})
    core.write_metadata(session_dir, meta)
    csv_path = os.path.join(session_dir, "samples.csv")
    raw_path = os.path.join(session_dir, "raw.bin")
    cap = core.SpO2LiveCapture(port, protocol, st.session_state.store, csv_path, raw_path)
    cap.start()
    st.session_state.capture = cap
    st.session_state.session_dir = session_dir
    st.session_state.session_meta = meta


def stop_session() -> None:
    cap = st.session_state.capture
    if cap is not None and cap.is_alive():
        cap.stop()
        cap.join(timeout=3.0)
    # Finalize metadata with what was actually captured.
    if st.session_state.session_dir and st.session_state.session_meta:
        s = st.session_state.store.stats()
        meta = dict(st.session_state.session_meta)
        meta.update({"ended_iso": datetime.now().isoformat(timespec="seconds"),
                     "captured_samples": s["frames"], "valid_pct": s["valid_pct"],
                     "duration_s": s["duration_s"]})
        try:
            core.write_metadata(st.session_state.session_dir, meta)
        except Exception:
            pass
    st.session_state.capture = None


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Data source")
    source = st.radio("Source", ["Live capture", "Load saved session"], label_visibility="collapsed")

    if source == "Live capture":
        st.markdown("### Device")
        try:
            detected = core.find_cp210x_ports()
        except Exception:
            detected = []
        default_port = detected[0] if detected else ""
        port = st.text_input("Serial port", value=st.session_state.get("last_port", default_port),
                             placeholder="auto-detect (CP210x)",
                             help="Leave blank to auto-detect the CP210x. Set explicitly if you have more than one.")
        st.session_state.last_port = port
        protocol = st.selectbox("Protocol", ["cms50e", "cms50d+"], index=0,
                                help="cms50e matches SpO2 Assistant. cms50d+ is the older 5-byte format.")
        st.session_state["last_protocol"] = protocol
        if detected:
            st.caption(f"CP210x detected: {', '.join(detected)}")
        else:
            st.caption("No CP210x auto-detected yet.")

        running = capture_running()

        if st.button("Check device", width="stretch", disabled=running,
                     help="Read the device for ~3 s to confirm it is connected and a finger is in, before starting."):
            use_port = port.strip() or (detected[0] if detected else "")
            if not use_port:
                st.session_state.probe = {"reachable": False, "finger_in": False,
                                          "message": "No port. Plug in the CMS50E (CP210x) or type its COM port."}
            else:
                with st.spinner("Checking device..."):
                    try:
                        st.session_state.probe = core.probe_device(use_port, protocol)
                    except Exception as e:  # noqa: BLE001
                        st.session_state.probe = {"reachable": False, "finger_in": False,
                                                  "message": f"Error: {e}"}

        probe = st.session_state.probe
        if probe:
            if probe.get("finger_in"):
                st.success(probe["message"])
            elif probe.get("reachable"):
                st.warning(probe["message"])
            else:
                st.error(probe["message"])

        st.markdown("### Subject & session")
        st.caption("Recorded into metadata.json and used to name the session folder.")
        subject_name = st.text_input("Subject name", key="m_name")
        subject_id = st.text_input("Subject ID", key="m_id", placeholder="e.g. S001")
        session_label = st.text_input("Session label", key="m_label", placeholder="e.g. baseline_rest")
        c1, c2 = st.columns(2)
        age = c1.text_input("Age", key="m_age")
        sex = c2.selectbox("Sex", ["", "F", "M", "Other"], key="m_sex")
        condition = st.text_input("Test condition", key="m_cond", placeholder="e.g. seated, room air")
        notes = st.text_area("Notes", key="m_notes", height=70)
        st.caption("Extra fields (anything relevant to the test):")
        tags = st.data_editor(
            pd.DataFrame(st.session_state.get("m_tags_data", [{"field": "", "value": ""}])),
            num_rows="dynamic", width="stretch", key="m_tags", hide_index=True)
        st.session_state["m_tags_data"] = tags.to_dict("records")

        def collect_meta() -> dict:
            extra = {str(r["field"]).strip(): r["value"] for _, r in tags.iterrows()
                     if str(r.get("field", "")).strip()}
            return {"subject_name": subject_name, "subject_id": subject_id,
                    "session_label": session_label, "age": age, "sex": sex,
                    "condition": condition, "notes": notes, "extra": extra}

        st.markdown("### Recording")
        ready_to_start = bool((subject_name or subject_id) and not running)
        s1, s2 = st.columns(2)
        if s1.button("Start", type="primary", width="stretch", disabled=not ready_to_start,
                     help=None if ready_to_start else "Enter a subject name or ID first."):
            use_port = port.strip() or (detected[0] if detected else "")
            if not use_port:
                st.error("No port to record from. Plug in the device or set the COM port.")
            else:
                start_session(use_port, protocol, collect_meta())
                st.rerun()
        if s2.button("Stop", width="stretch", disabled=not running):
            stop_session()
            st.rerun()

        st.session_state["show_wave"] = st.checkbox(
            "Show live waveform", value=st.session_state.get("show_wave", False),
            help="Optional. Draws a short recent window of the pleth ~1x/s. Off by default to keep the app light.")

        if not running and st.session_state.store.stats()["frames"]:
            st.info("Stopped - captured data is loaded below.")
        if st.button("Refresh view", width="stretch"):
            st.rerun()

    else:  # Load saved session
        st.markdown("### Saved sessions")
        sessions = core.list_sessions(BASE_DIR)
        picked = None
        if sessions:
            labels = [f"{s['subject']} / {s['session']}" for s in sessions]
            idx = st.selectbox("Session", range(len(sessions)), format_func=lambda i: labels[i])
            picked = sessions[idx]
            if st.button("Load selected", width="stretch"):
                try:
                    df = pd.read_csv(picked["csv"])
                    st.session_state.uploaded = {"df": df, "name": labels[idx], "meta": picked["metadata"]}
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not read: {e}")
        else:
            st.caption("No saved sessions yet. Record one in Live capture mode.")

        st.markdown("### Or upload a CSV")
        up = st.file_uploader("samples.csv", type=["csv"],
                              help="A samples.csv written by this dashboard or by stream_capture.py.")
        if up is not None:
            try:
                df = pd.read_csv(io.BytesIO(up.getvalue()))
                st.session_state.uploaded = {"df": df, "name": up.name, "meta": {}}
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read {up.name}: {e}")

    st.divider()
    st.markdown("### Analysis")
    desat_drop = st.slider("Desaturation drop (%)", 2.0, 6.0, 3.0, 1.0,
                           help="A dip this far below the local baseline counts as a desaturation. 3% and 4% are the two ODI conventions.")
    desat_min_s = st.slider("Min event duration (s)", 5.0, 30.0, 10.0, 1.0)


st.title("CMS50E SpO2 research dashboard")


# --------------------------------------------------------------------------
# Live status strip - cheap, ticks every second, independent of analysis
# --------------------------------------------------------------------------
def _live() -> bool:
    return source == "Live capture" and capture_running()


if source == "Live capture":
    @st.fragment(run_every="1s" if _live() else None)
    def live_status():
        s = st.session_state.store.stats()
        cap = st.session_state.capture
        running = cap is not None and cap.is_alive()

        badge, *cols = st.columns([1.5, 1, 1, 1, 1])
        with badge:
            if running and cap.error:
                st.error("Error")
            elif running and s["finger_in"]:
                st.success("Recording")
            elif running:
                st.warning("Finger out / no signal")
            elif s["frames"]:
                st.info("Stopped")
            else:
                st.caption("Not started")
        stat(cols[0], "SpO2", s["last_spo2"], " %", "Latest valid reading.", "{:.0f}")
        stat(cols[1], "Pulse", s["last_pulse"], " bpm", "Latest valid reading.", "{:.0f}")
        stat(cols[2], "Recorded", s["duration_s"] if (running or s["frames"]) else None, " s",
             "Length captured so far.", "{:.0f}")
        stat(cols[3], "Valid", s["valid_pct"] if (running or s["frames"]) else None, " %",
             "Share of samples that were real readings (finger in).", "{:.0f}")

        if running and cap.error:
            st.error(f"Capture error: {cap.error}")
        elif running and not s["finger_in"]:
            st.warning("No live reading - insert a finger. With a finger out this unit stops streaming.")
        if s["frames"] and s["min_spo2"] is not None:
            st.caption(f"Session so far: mean SpO2 {s['mean_spo2']:.0f}%, min {s['min_spo2']}%, "
                       f"pulse {s['mean_pulse']:.0f} bpm  |  {s['frames']:,} samples")

    live_status()

    if st.session_state.get("show_wave") and _live():
        @st.fragment(run_every="1s")
        def live_wave():
            c = theme()
            rows = st.session_state.store.recent(int(12 * ana.NOMINAL_FS))
            if len(rows) < 5:
                st.caption("Waiting for waveform...")
                return
            t = np.array([r["elapsed_s"] for r in rows], dtype=float)
            y = np.array([r.get("pleth", 0) for r in rows], dtype=float)
            fig = base_fig(200, "seconds", "pleth")
            dx, dy = decimate(t, y, 1500)
            fig.add_trace(go.Scattergl(x=dx, y=dy, mode="lines", line=dict(color=c["s1"], width=1.2),
                                       hoverinfo="skip"))
            st.plotly_chart(fig, width="stretch", key="livewave")
        live_wave()

    st.caption("Charts below are a snapshot - use **Refresh view** (or Stop) to pull in the latest data. "
               "They don't auto-update, to keep recording responsive.")
    st.divider()


# --------------------------------------------------------------------------
# Data assembly
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=4)
def analyse_cached(csv_bytes: bytes, desat_drop: float, desat_min_s: float) -> dict:
    df = pd.read_csv(io.BytesIO(csv_bytes))
    series = ana.extract(df)
    return {"df": df, "series": series,
            "res": ana.analyse(series, desat_drop=desat_drop, desat_min_s=desat_min_s)}


def current_frame() -> tuple[pd.DataFrame, str, dict]:
    if source == "Live capture":
        rows = st.session_state.store.snapshot()
        df = pd.DataFrame(rows, columns=core.live_columns(st.session_state.get("last_protocol", "cms50e"))) \
            if rows else pd.DataFrame()
        label = core._sanitize(st.session_state.session_meta.get("subject_id")
                               or st.session_state.session_meta.get("subject_name", "live"), "live")
        return df, label, st.session_state.session_meta
    up = st.session_state.uploaded
    if up:
        return up["df"], core._sanitize(up["name"].rsplit(".", 1)[0], "session"), up.get("meta", {})
    return pd.DataFrame(), "no_data", {}


def render() -> None:
    df, label, meta = current_frame()
    has_data = not df.empty and "spo2" in df.columns

    if not has_data:
        if source == "Live capture":
            st.info("**No data yet.** Fill in the subject, press **Check device** to confirm the SpO2 is "
                    "connected and reading, then **Start**.")
        else:
            st.info("**No session loaded.** Pick a saved session or upload a `samples.csv` in the sidebar.")
        return

    cached = analyse_cached(df.to_csv(index=False).encode(), desat_drop, desat_min_s)
    series, res = cached["series"], cached["res"]
    summary, desat, below, prv, qual = (res["summary"], res["desat"], res["below"],
                                        res["prv"], res["quality"])
    c = theme()

    tabs = st.tabs(["Monitor", "SpO2 & pulse", "Waveform", "Analysis", "Export"])

    # ---- Monitor -------------------------------------------------------
    with tabs[0]:
        who = meta.get("subject_name") or meta.get("subject_id") or "-"
        bits = [b for b in [meta.get("condition"), (f"{meta.get('age')}y" if meta.get("age") else None),
                            meta.get("sex")] if b]
        st.markdown(f"**{who}** " + (" · ".join(bits) if bits else ""))
        if meta.get("notes"):
            st.caption(meta["notes"])
        m = st.columns(4)
        stat(m[0], "Mean SpO2", summary.get("spo2_mean"), " %", None, "{:.1f}")
        stat(m[1], "Min SpO2", summary.get("spo2_min"), " %", "Lowest valid reading.", "{:.0f}")
        stat(m[2], "Mean pulse", summary.get("pulse_mean"), " bpm", None, "{:.0f}")
        stat(m[3], "Duration", summary.get("duration_s"), " s", None, "{:.0f}")
        status, message = ana.quality_verdict(qual)
        {"good": st.success, "warning": st.warning, "critical": st.error}[status](message)
        q = st.columns(3)
        stat(q[0], "Valid time", qual.get("valid_pct"), " %", "Finger-in share of the session.", "{:.0f}")
        stat(q[1], "ODI", desat.get("odi"), " /h",
             f"Desaturations >={desat.get('drop', 3):.0f}% per hour.", "{:.1f}")
        stat(q[2], "Pulse (pleth)", prv.get("pulse_from_pleth_bpm"), " bpm",
             "Independent pulse from the waveform.", "{:.0f}")

    # ---- SpO2 & pulse trends ------------------------------------------
    with tabs[1]:
        sec_t, sec_spo2, sec_pulse = res["sec_t"], res["sec_spo2"], res["sec_pulse"]
        if sec_t.size < 2:
            st.warning("No valid readings to plot - the finger may have been out the whole time.")
        else:
            fig = base_fig(320, "seconds", "SpO2 (%)")
            fig.add_trace(go.Scattergl(x=sec_t - sec_t[0], y=sec_spo2, mode="lines", name="SpO2",
                                       line=dict(color=c["s1"], width=2),
                                       hovertemplate="%{x:.0f}s<br>%{y:.0f}%<extra></extra>"))
            for thr in (90, 88):
                fig.add_hline(y=thr, line=dict(color=c["warning"], width=1, dash="dot"))
            for ev in desat.get("events", []):
                fig.add_vrect(x0=ev["start_s"] - sec_t[0], x1=ev["end_s"] - sec_t[0],
                              fillcolor=c["s2"], opacity=0.12, line_width=0)
            fig.update_yaxes(range=[min(80, np.min(sec_spo2) - 2), 100])
            st.plotly_chart(fig, width="stretch")
            st.caption(f"{desat.get('count', 0)} desaturation event(s) shaded "
                       f"(>={desat.get('drop', 3):.0f}% below a rolling baseline, "
                       f">={desat_min_s:.0f}s).")

            fig = base_fig(260, "seconds", "pulse (bpm)")
            fig.add_trace(go.Scattergl(x=sec_t - sec_t[0], y=sec_pulse, mode="lines", name="pulse",
                                       line=dict(color=c["s3"], width=1.5),
                                       hovertemplate="%{x:.0f}s<br>%{y:.0f} bpm<extra></extra>"))
            st.plotly_chart(fig, width="stretch")

            below_tbl = pd.DataFrame([{"threshold_pct": k, "seconds": v["seconds"], "pct_of_time": v["pct"]}
                                      for k, v in below.items()])
            if not below_tbl.empty:
                st.markdown("#### Time below threshold")
                st.dataframe(below_tbl, width="stretch", hide_index=True)

    # ---- Waveform ------------------------------------------------------
    with tabs[2]:
        if not series.has_waveform:
            st.info("No high-rate waveform in this record (a stored 3 s download has none). "
                    "The live cms50e feed carries the ~58 Hz pleth.")
        else:
            total = float(series.t[-1] - series.t[0])
            ctrl = st.columns([2, 1])
            win = ctrl[0].slider("Window (s)", 3.0, min(60.0, max(4.0, total)), min(10.0, max(4.0, total)), 1.0)
            start = ctrl[1].number_input("Start (s)", 0.0, max(0.0, total - 1), 0.0, 1.0)
            rel = series.t - series.t[0]
            mask = (rel >= start) & (rel <= start + win)
            fig = base_fig(360, "seconds", "pleth (0-127)")
            dx, dy = decimate(rel[mask], series.pleth[mask], 3000)
            fig.add_trace(go.Scattergl(x=dx, y=dy, mode="lines", name="pleth",
                                       line=dict(color=c["s1"], width=1.3),
                                       hovertemplate="%{x:.2f}s<br>%{y:.0f}<extra></extra>"))
            pk = res["peaks"]
            pk_rel = pk / series.fs
            pm = (pk_rel >= start) & (pk_rel <= start + win)
            if pm.any():
                fig.add_trace(go.Scattergl(x=pk_rel[pm], y=series.pleth[pk[pm]], mode="markers",
                                           name="pulse", marker=dict(color=c["s3"], size=8,
                                           symbol="circle-open", line=dict(width=2)), hoverinfo="skip"))
            st.plotly_chart(fig, width="stretch")

            beat = res["beat"]
            if beat:
                st.markdown("#### Average pulse (PPG morphology)")
                fig = base_fig(300, "ms from systolic peak", "pleth")
                upper, lower = beat["mean"] + beat["sd"], beat["mean"] - beat["sd"]
                fig.add_trace(go.Scatter(x=np.concatenate([beat["t_ms"], beat["t_ms"][::-1]]),
                                         y=np.concatenate([upper, lower[::-1]]), fill="toself",
                                         mode="lines", line=dict(width=0), fillcolor=c["s1"],
                                         opacity=0.15, hoverinfo="skip"))
                fig.add_trace(go.Scattergl(x=beat["t_ms"], y=beat["mean"], mode="lines",
                                           line=dict(color=c["s1"], width=2),
                                           hovertemplate="%{x:.0f} ms<br>%{y:.1f}<extra></extra>"))
                st.plotly_chart(fig, width="stretch")
                st.caption(f"Averaged over {beat['n']:,} beats; shaded band is +/-1 SD.")

    # ---- Analysis ------------------------------------------------------
    with tabs[3]:
        st.markdown("#### Oxygenation")
        a = st.columns(4)
        stat(a[0], "Mean SpO2", summary.get("spo2_mean"), " %", None, "{:.1f}")
        stat(a[1], "Median SpO2", summary.get("spo2_median"), " %", None, "{:.0f}")
        stat(a[2], "Min SpO2", summary.get("spo2_min"), " %", None, "{:.0f}")
        stat(a[3], "SpO2 SD", summary.get("spo2_std"), " %", None, "{:.2f}")
        b = st.columns(4)
        stat(b[0], "ODI", desat.get("odi"), " /h", "Desaturation events per hour.", "{:.1f}")
        stat(b[1], "Desat events", desat.get("count"), "", None, "{:.0f}")
        for i, thr in enumerate((90, 88)):
            info = below.get(thr, {})
            stat(b[2 + i], f"Time <{thr}%", info.get("pct"), " %", f"{info.get('seconds', 0):.0f}s.", "{:.1f}")

        st.markdown("#### Pulse & pulse-rate variability (PRV)")
        if prv:
            p = st.columns(4)
            stat(p[0], "Pulse (pleth)", prv.get("pulse_from_pleth_bpm"), " bpm",
                 "From the PPG waveform, independent of the device number.", "{:.0f}")
            stat(p[1], "Mean IBI", prv.get("mean_ibi_ms"), " ms", "Beat-to-beat interval.", "{:.0f}")
            stat(p[2], "SDNN", prv.get("sdnn_ms"), " ms", "Overall pulse-rate variability.", "{:.1f}")
            stat(p[3], "RMSSD", prv.get("rmssd_ms"), " ms", "Short-term variability.", "{:.1f}")
            if res["perfusion"]:
                st.caption(f"Relative perfusion (pleth pulse amplitude): "
                           f"{res['perfusion']['pulse_amplitude_mean']:.1f} "
                           f"(CV {res['perfusion'].get('pulse_amplitude_cv_pct', 0):.0f}%). "
                           "Relative across this session, not a calibrated PI.")
        else:
            st.caption("Needs the high-rate waveform (live cms50e feed) for PRV.")

        if desat.get("events"):
            st.markdown("#### Desaturation events")
            ev_df = pd.DataFrame(desat["events"])
            st.dataframe(ev_df, width="stretch", hide_index=True)

    # ---- Export --------------------------------------------------------
    with tabs[4]:
        st.markdown("#### Export for ML / analysis")
        if source == "Live capture" and st.session_state.session_dir:
            st.caption(f"This session is saved on disk at:  `{st.session_state.session_dir}`")
        st.caption("`samples.csv` is the full per-sample record (SpO2, pulse, pleth, validity, raw frame). "
                   "The feature table gives one row per window - ready to concatenate across subjects for training.")

        feats = ana.windowed_features(series, window_s=30.0)
        feats_df = pd.DataFrame(feats)

        d = st.columns(3)
        d[0].download_button("Samples (CSV)", df.to_csv(index=False).encode(),
                             file_name=f"{label}_samples.csv", mime="text/csv", width="stretch")
        d[1].download_button("Features (CSV)", feats_df.to_csv(index=False).encode(),
                             file_name=f"{label}_features.csv", mime="text/csv", width="stretch",
                             disabled=feats_df.empty)
        metrics = {"subject": {k: meta.get(k) for k in ("subject_name", "subject_id", "session_label",
                                                         "age", "sex", "condition")},
                   "notes": meta.get("notes"), "extra": meta.get("extra", {}),
                   "summary": summary, "quality": qual,
                   "desaturations": {k: v for k, v in desat.items() if k not in ("events", "baseline")},
                   "time_below": {str(k): v for k, v in below.items()},
                   "prv": {k: v for k, v in prv.items() if not isinstance(v, np.ndarray)}}
        d[2].download_button("Metrics (JSON)", json.dumps(metrics, indent=2, default=str).encode(),
                             file_name=f"{label}_metrics.json", mime="application/json", width="stretch")

        if not feats_df.empty:
            st.markdown("#### Feature table preview")
            st.dataframe(feats_df, width="stretch", height=260)

        st.markdown("#### Notes")
        st.caption("ODI and time-below thresholds are computed against a trailing-median baseline and are "
                   "research indicators, not clinical scores. Pulse from the pleth is peak-detected from the "
                   "~58 Hz waveform. This is a research and self-tracking tool, not a diagnostic device.")


# Remember the active protocol so a live snapshot builds the right columns.
render()
