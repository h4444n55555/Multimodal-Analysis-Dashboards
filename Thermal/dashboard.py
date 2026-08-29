"""Streamlit dashboard for extracting and browsing FLIR radiometric data.

Run with:
    .\\.venv\\Scripts\\streamlit.exe run dashboard.py

Reuses the extraction logic in extract_metadata.py so anything processed
here lands in output/ in exactly the same format the CLI produces, and
vice versa: files already extracted via the CLI show up here too.
"""

from __future__ import annotations

import io
import json
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.patches import Rectangle

from extract_metadata import (
    find_images,
    flatten_for_manifest,
    natural_sort_key,
    process_image,
    sort_manifest,
)
from video_core import (
    VideoLiveCapture,
    VideoStore,
    list_camera_indices,
    make_session_dir,
)

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"
OUTPUT_DIR = BASE_DIR / "output"
ARCHIVE_DIR = BASE_DIR / "archives"
SKIPPED_DIR = BASE_DIR / "skipped"
VIDEO_DIR = BASE_DIR / "videos"
IMAGES_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)
SKIPPED_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)

VIDEO_DISCLAIMER = (
    "**This is ordinary colorized video, not radiometric data.** The FLIR C5's "
    "USB video stream is confirmed 8-bit (YUY2) with no raw/16-bit thermal "
    "format offered — the camera bakes its false-color palette and overlay "
    "into the pixels before they reach USB. Per-pixel temperature is not "
    "recoverable from this recording. For real temperature data, use a still "
    "capture (Browse/Inspect tabs), which embeds full 14-bit radiometric data."
)

PIXEL_DISCLAIMER = (
    "**Per-pixel temperature disclaimer.** These values come from the camera's "
    "embedded calibration (emissivity, reflected/atmospheric temperature, humidity, "
    "object distance) at capture time — they're only as accurate as those settings "
    "were for the actual scene; nothing here corrects for that. When a pooling factor "
    "above 1 is applied below, every cell you see is a **block average** of several "
    "pixels, not a single-pixel reading. For pixel-exact values, use the raw "
    "`*_celsius.npy` array (path shown in the Raw metadata tab), never this render."
)

st.set_page_config(page_title="Thermal Radiometric Dashboard", layout="wide", page_icon="\U0001F321")
st.title("Thermal Radiometric Dashboard")


def block_mean_pool(array: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return array
    h, w = array.shape
    pad_h, pad_w = (-h) % factor, (-w) % factor
    padded = np.pad(array, ((0, pad_h), (0, pad_w)), mode="edge")
    ph, pw = padded.shape
    reshaped = padded.reshape(ph // factor, factor, pw // factor, factor)
    return reshaped.mean(axis=(1, 3))


def safe_path(value) -> Optional[Path]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    path = Path(value)
    return path if path.exists() else None


def process_paths(
    paths: list[Path], session_metadata: Optional[dict] = None
) -> tuple[int, int, list[tuple[str, str]]]:
    ok = 0
    skipped: list[tuple[str, str]] = []

    def on_skip(path: Path, reason: str) -> None:
        skipped.append((path.name, reason))
        # Move out of images/ so it isn't re-scanned (and re-skipped) forever,
        # and isn't silently swept into the next archive as an orphan.
        dest = SKIPPED_DIR / path.name
        if dest.exists():
            dest = SKIPPED_DIR / f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}"
        try:
            path.rename(dest)
        except OSError:
            pass  # leave it in place; the skip reason is still recorded/shown

    for path in paths:
        record = process_image(
            path, OUTPUT_DIR, "celsius", True, True, True,
            on_skip=on_skip, session_metadata=session_metadata,
        )
        if record is not None:
            ok += 1
    return ok, len(paths), skipped


def count_batch_files() -> tuple[int, int, int]:
    """(images/ file count, output/ file count, skipped/ file count) — for the
    new-batch confirmation prompt."""
    images = sum(1 for p in IMAGES_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep")
    outputs = sum(1 for p in OUTPUT_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep")
    skipped = sum(1 for p in SKIPPED_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep")
    return images, outputs, skipped


def collect_output_session_ids(output_files: list[Path]) -> set[str]:
    """Distinct non-empty session_id values actually present in the
    output/*.json files about to be archived — read from each record's own
    session_log, not the sidebar form's current value (which may not match:
    Session ID changed mid-batch, or some images were never logged at all)."""
    ids: set[str] = set()
    for p in output_files:
        if p.suffix != ".json" or p.name == "manifest.json":
            continue
        try:
            record = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        sid = (record.get("session_log") or {}).get("session_id")
        if sid:
            ids.add(sid)
    return ids


def archive_and_clear_batch() -> tuple[Path, int, int, int]:
    """Zip everything currently in images/, output/, and skipped/ into
    archives/, then delete the contents of all three so the next batch
    starts from a clean slate.

    Returns (archive_path, num_images_zipped, num_output_files_zipped, num_skipped_zipped).
    """
    # .gitkeep placeholders are never part of a batch — leave them in place so
    # the folders stay tracked in git instead of being zipped away and deleted.
    image_files = [p for p in IMAGES_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    output_files = [p for p in OUTPUT_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    skipped_files = [p for p in SKIPPED_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep"]

    session_ids = collect_output_session_ids(output_files)
    if not session_ids:
        safe_name = "unlogged"
    elif len(session_ids) == 1:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", next(iter(session_ids))).strip("_") or "batch"
    elif len(session_ids) <= 3:
        safe_name = "+".join(sorted(re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_") for s in session_ids))
    else:
        safe_name = f"mixed_{len(session_ids)}sessions"
    archive_path = ARCHIVE_DIR / f"{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.zip"

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in image_files:
            zf.write(p, f"images/{p.relative_to(IMAGES_DIR)}")
        for p in output_files:
            zf.write(p, f"output/{p.relative_to(OUTPUT_DIR)}")
        for p in skipped_files:
            zf.write(p, f"skipped/{p.relative_to(SKIPPED_DIR)}")

    for p in image_files + output_files + skipped_files:
        p.unlink()

    return archive_path, len(image_files), len(output_files), len(skipped_files)


# (manifest column, human-readable report column) — every field ever logged
# via the sidebar's "Session & subject info" form or the "Session log & QA
# flags" tab, in a fixed order, so the report always has every variable even
# when a particular image/session never filled it in (shown as "NA" then).
REPORT_COLUMNS = [
    ("identifier", "Image"),
    ("date_time", "Capture time"),
    ("session_id", "Session ID"),
    ("subject_id", "Subject ID"),
    ("skin_type", "Skin type"),
    ("sweat", "Sweat"),
    ("clothing_level", "Clothing level"),
    ("recent_activity", "Recent physical activity"),
    ("medical_history_notes", "Medical history notes"),
    ("ambient_temperature_c", "Ambient temperature (C)"),
    ("airflow", "Airflow / drafts"),
    ("sunlight_leakage", "Sunlight leakage"),
    ("camera_distance_cm", "Camera-to-subject distance (cm)"),
    ("acclimatization_min", "Acclimatization time (min)"),
    ("session_time_of_day", "Time of day"),
    ("session_notes", "Other session notes"),
    ("eyes_glasses_invalid", "QA: eyes/glasses ROI invalid"),
    ("makeup_facial_hair_invalid", "QA: makeup/facial hair ROI invalid"),
    ("hair_forehead_invalid", "QA: hair-over-forehead ROI invalid"),
    ("off_axis_invalid", "QA: subject off-axis"),
    ("roi_notes", "QA notes"),
]


def format_report_value(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "NA"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and not value.strip():
        return "NA"
    return str(value)


def session_field_values(session_rows: pd.DataFrame, col: str) -> tuple[str, pd.Series]:
    """(display_value, per_image_series) for one REPORT_COLUMNS field across a
    session's images. display_value is the single formatted value if every
    image that logged this field agrees; otherwise "Mixed (N distinct)" —
    the sidebar form was likely edited and re-saved mid-batch. NA/blank
    values are ignored when checking agreement: an image that predates the
    field being filled in isn't a disagreement, only two differing real
    values are. per_image_series is always returned (formatted, indexed by
    identifier) so the caller can render a per-image breakdown when mixed.
    """
    per_image = session_rows.set_index("identifier")[col].map(format_report_value)
    distinct = per_image[per_image != "NA"].unique()
    if len(distinct) <= 1:
        return (distinct[0] if len(distinct) else "NA"), per_image
    return f"Mixed ({len(distinct)} distinct)", per_image


def build_subject_environment_report(subset: pd.DataFrame) -> bytes:
    """One row per exported image with every subject/environment/QA variable

    logged for it — missing values filled with "NA" rather than left blank,
    so every column is guaranteed present even if nothing was ever entered.
    """
    rows = []
    for row in subset.itertuples(index=False):
        row_dict = row._asdict()
        rows.append({label: format_report_value(row_dict.get(col)) for col, label in REPORT_COLUMNS})
    report_df = pd.DataFrame(rows, columns=[label for _, label in REPORT_COLUMNS])
    return report_df.to_csv(index=False).encode("utf-8")


def build_export_zip(
    subset: pd.DataFrame,
    include_arrays: bool,
    include_json: bool,
    include_optical: bool,
    include_render: bool,
    include_stacked: bool,
    include_report: bool = False,
) -> tuple[bytes, list[str]]:
    """Zip the requested artifacts for `subset`, in its current row order.

    Every file is renamed with a zero-padded sequence prefix (001_, 002_, ...)
    matching that row order, so the export stays correctly ordered even
    though the underlying capture filenames (FLIR0180.jpg, ...) don't sort
    that way in every OS file browser.
    """
    warnings: list[str] = []
    width = max(3, len(str(len(subset))))
    stacked_arrays: dict[str, np.ndarray] = {}
    manifest_rows = []

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(subset.itertuples(index=False), start=1):
            seq = str(i).zfill(width)
            stem = Path(row.identifier).stem
            prefix = f"{seq}_{stem}"

            if include_arrays or include_stacked:
                arr_path = safe_path(row.temperature_array_path)
                if arr_path is None:
                    warnings.append(f"{row.identifier}: no temperature array on disk, skipped")
                else:
                    if include_arrays:
                        zf.write(arr_path, f"arrays/{prefix}_celsius.npy")
                    if include_stacked:
                        stacked_arrays[prefix] = np.load(arr_path)

            if include_json:
                json_path = safe_path(row.metadata_json_path)
                if json_path is None:
                    warnings.append(f"{row.identifier}: no metadata JSON on disk, skipped")
                else:
                    zf.write(json_path, f"json/{prefix}.json")

            if include_optical:
                optical_path = safe_path(row.optical_image_path)
                if optical_path is None:
                    warnings.append(f"{row.identifier}: no optical photo on disk, skipped")
                else:
                    zf.write(optical_path, f"optical/{prefix}_optical.jpg")

            if include_render:
                render_path = safe_path(row.render_image_path)
                if render_path is None:
                    warnings.append(f"{row.identifier}: no camera render on disk, skipped")
                else:
                    zf.write(render_path, f"render/{prefix}_thermal.jpg")

            manifest_rows.append({"sequence": seq, **row._asdict()})

        zf.writestr("selected_manifest.csv", pd.DataFrame(manifest_rows).to_csv(index=False))

        if include_report:
            zf.writestr("subject_environment_report.csv", build_subject_environment_report(subset))

        if include_stacked:
            if not stacked_arrays:
                warnings.append("Stacked .npz skipped: no arrays available for the selection.")
            else:
                shapes = {a.shape for a in stacked_arrays.values()}
                if len(shapes) != 1:
                    warnings.append(
                        f"Stacked .npz skipped: images have differing resolutions {sorted(shapes)} "
                        "— can't stack into one tensor. Use the per-image arrays/ folder instead."
                    )
                else:
                    npz_buf = io.BytesIO()
                    np.savez_compressed(npz_buf, **stacked_arrays)
                    zf.writestr("stacked_temperature_arrays.npz", npz_buf.getvalue())

    return buf.getvalue(), warnings


def output_signature() -> tuple[int, float]:
    jsons = [p for p in OUTPUT_DIR.glob("*.json") if p.name != "manifest.json"]
    if not jsons:
        return (0, 0.0)
    return (len(jsons), max(p.stat().st_mtime for p in jsons))


@st.cache_data(show_spinner=False)
def load_manifest(signature: tuple[int, float]) -> pd.DataFrame:
    """Rebuild the manifest by scanning every *.json in output/ (single source of truth)."""
    rows = []
    for json_path in OUTPUT_DIR.glob("*.json"):
        if json_path.name == "manifest.json":
            continue
        try:
            record = json.loads(json_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(flatten_for_manifest(record))
    return sort_manifest(pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# Sidebar: capture protocol checklist + warm-up timer
# ---------------------------------------------------------------------------
CHECKLIST_KEYS = [
    "chk_emissivity", "chk_warmup", "chk_headon", "chk_background",
    "chk_roi_check", "chk_distance", "chk_msx",
]

with st.sidebar.expander("📋 Capture protocol checklist", expanded=False):
    st.checkbox("Emissivity set to 0.98 (skin)", key="chk_emissivity")
    st.checkbox("Camera warmed up 15–20 min in the room", key="chk_warmup")
    st.checkbox("Subject facing camera head-on (< ~45° off axis)", key="chk_headon")
    st.checkbox("Background temperature neutral, no reflections", key="chk_background")
    st.checkbox("Glasses / heavy makeup / facial hair / hair-over-forehead checked", key="chk_roi_check")
    st.checkbox("Camera distance set close (not far) to subject", key="chk_distance")
    st.checkbox("MSX and RGB overlay disabled", key="chk_msx")

    st.divider()
    st.caption("Warm-up timer (target: 15–20 min)")
    tcol1, tcol2 = st.columns(2)
    if tcol1.button("Start", key="warmup_start"):
        st.session_state["warmup_start_ts"] = time.time()
    if tcol2.button("Reset", key="warmup_reset"):
        st.session_state.pop("warmup_start_ts", None)
    start_ts = st.session_state.get("warmup_start_ts")
    if start_ts:
        elapsed_min = (time.time() - start_ts) / 60
        st.progress(min(elapsed_min / 20, 1.0))
        status = "✅ ready" if elapsed_min >= 15 else "⏳ still warming up"
        st.caption(f"Elapsed: {elapsed_min:.1f} min — {status} (click Start/Reset or any control to refresh)")
    else:
        st.caption("Not started.")

# ---------------------------------------------------------------------------
# Sidebar: session & subject info for the batch currently being processed
# ---------------------------------------------------------------------------
with st.sidebar.expander("0. Session & subject info", expanded=False):
    st.caption(
        "Logged per the capture protocol — attached to every image you process below, "
        "for the batch currently in progress. Editing and saving updates it going forward "
        "(images already extracted keep whatever was set when they were processed). "
        "Leave anything blank if not applicable."
    )
    # The form itself is re-keyed (same trick as the uploader below) whenever
    # "Process new batch" clears things, so every field in it also resets to
    # its coded default instead of keeping whatever was last typed in.
    form_version = st.session_state.get("form_version", 0)
    with st.form(f"session_form_{form_version}", clear_on_submit=False):
        st.markdown("**Session ID**")
        # Seeded into session_state ONCE per batch (keyed so a new batch gets a
        # fresh default) rather than passed as a recomputed `value=` on every
        # rerun — a `value=` that changes every second (wall-clock timestamp)
        # would give the widget a new identity each time and silently discard
        # whatever the operator had typed in the meantime.
        session_id_key = f"session_id_input_{form_version}"
        if session_id_key not in st.session_state:
            st.session_state[session_id_key] = (
                st.session_state.get("session_metadata", {}).get("session_id")
                or f"session_{datetime.now():%Y%m%d_%H%M%S}"
            )
        session_id = st.text_input(
            "Session ID",
            key=session_id_key,
            help="Groups images together under 'Sessions' below. Auto-filled with a timestamp — "
                 "reuse the same ID across multiple upload batches to keep them in one session.",
        )

        st.markdown("**Subject**")
        subject_id = st.text_input("Subject ID", value=st.session_state.get("session_metadata", {}).get("subject_id", ""))
        skin_type = st.selectbox("Skin", ["", "oily", "dry", "combination"], index=0)
        sweat = st.selectbox("Sweat", ["", "none", "light", "heavy"], index=0)
        clothing_level = st.selectbox("Clothing level", ["", "light", "medium", "heavy"], index=0)
        recent_activity = st.selectbox("Recent physical activity", ["", "none", "light", "moderate", "vigorous"], index=0)
        medical_history_notes = st.text_area("Medical history notes (optional)", height=60)

        st.markdown("**Environment**")
        ambient_temperature_c = st.text_input("Ambient temperature (°C)")
        airflow = st.selectbox("Airflow / drafts", ["", "none", "mild", "noticeable"], index=0)
        sunlight_leakage = st.selectbox("Sunlight leakage", ["", "none", "some", "significant"], index=0)
        camera_distance_cm = st.text_input("Camera-to-subject distance (cm)")
        # Same fix as Session ID above: seed once from the timer/clock instead
        # of recomputing `value=` every rerun, which was wiping out edits.
        acclimatization_key = f"acclimatization_input_{form_version}"
        if acclimatization_key not in st.session_state:
            st.session_state[acclimatization_key] = (
                f"{(time.time() - st.session_state['warmup_start_ts']) / 60:.1f}"
                if st.session_state.get("warmup_start_ts") else ""
            )
        acclimatization_min = st.text_input(
            "Acclimatization time (min)",
            key=acclimatization_key,
            help="Pre-filled from the warm-up timer above if it's running — edit freely.",
        )
        time_of_day_key = f"time_of_day_input_{form_version}"
        if time_of_day_key not in st.session_state:
            st.session_state[time_of_day_key] = datetime.now().strftime("%Y-%m-%d %H:%M")
        time_of_day = st.text_input("Time of day", key=time_of_day_key)
        session_notes = st.text_area("Other session notes (optional)", height=60)

        if st.form_submit_button("Update current batch details"):
            st.session_state["session_metadata"] = {
                k: v for k, v in {
                    "session_id": session_id.strip(),
                    "subject_id": subject_id.strip(),
                    "skin_type": skin_type,
                    "sweat": sweat,
                    "clothing_level": clothing_level,
                    "recent_activity": recent_activity,
                    "medical_history_notes": medical_history_notes.strip(),
                    "ambient_temperature_c": ambient_temperature_c.strip(),
                    "airflow": airflow,
                    "sunlight_leakage": sunlight_leakage,
                    "camera_distance_cm": camera_distance_cm.strip(),
                    "acclimatization_min": acclimatization_min.strip(),
                    "time_of_day": time_of_day.strip(),
                    "notes": session_notes.strip(),
                }.items() if v
            }
            st.success("Updated. Applies to every image you process from now on, until you start a new batch.")

    active_meta = st.session_state.get("session_metadata")
    if active_meta:
        summary_bits = [f"{k}={v}" for k, v in active_meta.items() if k in ("session_id", "subject_id", "ambient_temperature_c")]
        st.caption(f"Active for current batch: {', '.join(summary_bits) if summary_bits else 'saved'} · {len(active_meta)} field(s)")
    else:
        st.caption("No session/subject info saved yet — images will be logged without it until you save.")

# ---------------------------------------------------------------------------
# Sidebar: ingest new data
# ---------------------------------------------------------------------------
with st.sidebar.expander("1. Add images", expanded=False):
    # The uploader gets a fresh key (and so a fresh, empty widget) each time a
    # batch is processed below. Without this, the widget keeps holding the
    # same file selection forever — re-picking the exact same file(s) from the
    # OS file dialog doesn't fire a change event, so it can look like the
    # uploader has silently stopped accepting new images.
    # Skip info from the last upload persists in session_state (rather than
    # st.toast) so it survives the st.rerun() below and stays readable until
    # dismissed — a toast right before a rerun gets wiped before it's ever seen.
    pending_skips = st.session_state.get("last_upload_skipped")
    if pending_skips:
        with st.container(border=True):
            st.warning(f"{len(pending_skips)} file(s) skipped on the last upload (moved to `skipped/`):")
            for name, reason in pending_skips:
                st.caption(f"**{name}**: {reason}")
            if st.button("Dismiss", key="dismiss_upload_skips"):
                st.session_state.pop("last_upload_skipped", None)
                st.rerun()

    uploader_key = f"uploader_{st.session_state.get('uploader_version', 0)}"
    uploaded = st.file_uploader(
        "Upload FLIR radiometric JPEGs (multiple allowed)",
        type=["jpg", "jpeg"],
        accept_multiple_files=True,
        key=uploader_key,
    )
    if uploaded and st.button(f"Process {len(uploaded)} uploaded file(s)"):
        with st.spinner("Extracting radiometric data..."):
            saved_paths = []
            for f in uploaded:
                dest = IMAGES_DIR / f.name
                dest.write_bytes(f.getvalue())
                saved_paths.append(dest)
            ok, total, skipped = process_paths(saved_paths, st.session_state.get("session_metadata"))
        # st.toast (not st.success) because st.rerun() below fires immediately
        # after — a regular message would be wiped before it's ever seen;
        # toasts are designed to survive the rerun that follows.
        if ok:
            st.toast(f"Extracted {ok}/{total} file(s)", icon="✅")
        st.session_state["last_upload_skipped"] = skipped
        st.session_state["uploader_version"] = st.session_state.get("uploader_version", 0) + 1
        st.rerun()  # clears the uploader immediately so more images can be added right away

    if st.button("Scan images/ for unprocessed files"):
        pending = [
            p for p in find_images(IMAGES_DIR) if not (OUTPUT_DIR / f"{p.stem}.json").exists()
        ]
        if not pending:
            st.info("Nothing new to extract in images/.")
        else:
            with st.spinner(f"Extracting {len(pending)} file(s) from images/..."):
                ok, total, skipped = process_paths(pending, st.session_state.get("session_metadata"))
            st.success(f"Extracted {ok}/{total} file(s)")
            for name, reason in skipped:
                st.warning(f"Skipped **{name}**: {reason}")

with st.sidebar.expander("2. New batch (archive & clear)", expanded=False):
    n_images, n_outputs, n_skipped = count_batch_files()
    st.caption(
        f"Currently in this batch: {n_images} file(s) in `images/`, {n_outputs} file(s) in "
        f"`output/`, {n_skipped} file(s) in `skipped/`."
    )
    st.caption(
        "When you're done with this subject/session and want a totally clean slate for the "
        "next one: this zips everything currently in `images/`, `output/`, and `skipped/` into "
        "`archives/`, then **permanently deletes** the contents of all three folders. Nothing on "
        "disk is recoverable from the dashboard after that — the ZIP in `archives/` is the only "
        "copy kept. The ZIP is named after the session ID(s) actually found in the batch being "
        "archived (not just whatever's in the sidebar form right now)."
    )
    if not st.session_state.get("confirm_new_batch"):
        if st.button(
            "Process new batch...", key="new_batch_start",
            disabled=(n_images == 0 and n_outputs == 0 and n_skipped == 0),
        ):
            st.session_state["confirm_new_batch"] = True
            st.rerun()
    else:
        st.warning(
            f"This will archive {n_images} image(s) + {n_outputs} output file(s) + {n_skipped} "
            "skipped file(s) to a ZIP in `archives/`, then delete them from `images/`, `output/`, "
            "and `skipped/`. This cannot be undone from here. Are you sure?"
        )
        confirm_col1, confirm_col2 = st.columns(2)
        if confirm_col1.button("Yes, archive and clear", key="new_batch_confirm"):
            with st.spinner("Archiving and clearing..."):
                archive_path, n_img_zipped, n_out_zipped, n_skip_zipped = archive_and_clear_batch()
            st.session_state["confirm_new_batch"] = False
            st.session_state.pop("session_metadata", None)
            st.session_state.pop("warmup_start_ts", None)
            st.session_state.pop("last_upload_skipped", None)
            for chk_key in CHECKLIST_KEYS:
                st.session_state.pop(chk_key, None)
            st.session_state["uploader_version"] = st.session_state.get("uploader_version", 0) + 1
            st.session_state["form_version"] = st.session_state.get("form_version", 0) + 1
            st.toast(
                f"Archived {n_img_zipped} image(s) + {n_out_zipped} output file(s) + "
                f"{n_skip_zipped} skipped file(s) to archives/{archive_path.name}. "
                "Ready for a new batch.",
                icon="✅",
            )
            st.rerun()
        if confirm_col2.button("Cancel", key="new_batch_cancel"):
            st.session_state["confirm_new_batch"] = False
            st.rerun()

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
manifest = load_manifest(output_signature())
no_stills_yet = (
    "No extracted data yet. Upload FLIR .jpg files in the sidebar, or drop them "
    "into `images/` and click **Scan images/ for unprocessed files**."
)

tab_live, tab_browse, tab_sessions, tab_export, tab_inspect = st.tabs(
    ["Live video", "Browse", "Sessions", "Export", "Inspect"]
)

# ---------------------------------------------------------------------------
# Live video tab: record-to-disk only — no in-browser preview. Streamlit's
# rerun-per-frame model can't drive a smooth live image (each frame means
# re-executing the whole script), so this tab just starts/stops a background
# capture+record thread and reports status; watch the feed on the camera's
# own screen while recording. (Not radiometric — see banner.)
# ---------------------------------------------------------------------------
with tab_live:
    st.warning(VIDEO_DISCLAIMER)

    if "video_store" not in st.session_state:
        st.session_state["video_store"] = VideoStore()
    if "video_capture" not in st.session_state:
        st.session_state["video_capture"] = None

    store: VideoStore = st.session_state["video_store"]
    capture: VideoLiveCapture | None = st.session_state["video_capture"]

    cam_col, name_col, label_col = st.columns([1, 1, 1])
    camera_index = cam_col.number_input(
        "Camera index", min_value=0, max_value=10, value=1, step=1,
        help="Usually 1 if index 0 is your laptop's built-in webcam. Use the probe below if unsure.",
    )
    subject_id = name_col.text_input("Subject ID", key="video_subject")
    label = label_col.text_input("Label", value="live", key="video_label")

    with st.expander("Not sure which camera index is the FLIR?"):
        if st.button("Probe camera indices"):
            with st.spinner("Opening each camera index briefly..."):
                st.session_state["camera_probe"] = list_camera_indices()
        for result in st.session_state.get("camera_probe", []):
            cols = st.columns([1, 3])
            cols[0].caption(f"Index {result['index']} ({result['width']}x{result['height']})")
            if result["frame"] is not None:
                cols[1].image(result["frame"], channels="BGR", width=240)

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
    if ctrl1.button("Start streaming", disabled=capture is not None):
        store.clear()
        new_capture = VideoLiveCapture(int(camera_index), store)
        new_capture.start()
        st.session_state["video_capture"] = new_capture
        st.rerun()

    stats = store.stats()
    if ctrl2.button("Start recording", disabled=capture is None or stats["recording"]):
        session_dir = make_session_dir(VIDEO_DIR, subject_id, label)
        capture.start_recording(str(session_dir / f"{label or 'live'}.mp4"))
        st.rerun()
    if ctrl3.button("Stop recording", disabled=capture is None or not stats["recording"]):
        capture.stop_recording()
        st.rerun()
    if ctrl4.button("Stop streaming", disabled=capture is None):
        capture.stop()
        capture.join(timeout=2)
        st.session_state["video_capture"] = None
        st.rerun()

    if stats["error"]:
        st.error(stats["error"])

    status = "Recording" if stats["recording"] else ("Streaming" if capture else "Stopped")
    st.caption(
        f"**{status}** · {stats['frames']} frames · {stats['duration_s']:.0f}s"
        + (f" · saving to `{stats['record_path']}`" if stats["recording"] else "")
        + " — click a button above to refresh this."
    )

# ---------------------------------------------------------------------------
# Browse tab: sortable manifest table
# ---------------------------------------------------------------------------
with tab_browse:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Images", len(manifest))
    m2.metric("Dataset min", f"{manifest['temp_min'].min():.1f} °C")
    m3.metric("Dataset max", f"{manifest['temp_max'].max():.1f} °C")
    dates = pd.to_datetime(manifest["date_time"], errors="coerce")
    m4.metric("Date range", f"{dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}" if dates.notna().any() else "unknown")
    flagged = manifest["invalid_rois"].notna().sum() if "invalid_rois" in manifest else 0
    m5.metric("Flagged (invalid ROI)", int(flagged))
    st.divider()

    sort_options = {
        "Capture time": "date_time",
        "Filename": "identifier",
        "Max temperature": "temp_max",
        "Mean temperature": "temp_mean",
        "Min temperature": "temp_min",
    }
    sort_col1, sort_col2 = st.columns([3, 1])
    sort_choice = sort_col1.selectbox("Sort by", list(sort_options.keys()))
    descending = sort_col2.checkbox("Descending", value=False)

    sort_col = sort_options[sort_choice]
    if sort_col == "identifier":
        manifest = manifest.assign(_key=manifest["identifier"].map(lambda v: natural_sort_key(str(v))))
        manifest = manifest.sort_values("_key", ascending=not descending, kind="stable").drop(columns="_key")
    elif sort_col == "date_time":
        manifest = sort_manifest(manifest)
        if descending:
            manifest = manifest.iloc[::-1]
    else:
        manifest = manifest.sort_values(sort_col, ascending=not descending, na_position="last", kind="stable")
    manifest = manifest.reset_index(drop=True)

    st.subheader("Extracted images")
    show_full_columns = st.checkbox(
        "Show all columns (subject/session log, ROI flags)", value=False,
        help="Off by default to keep the table readable — turn on to audit subject/session logging or QA flags.",
    )
    if show_full_columns:
        display_cols = [c for c in manifest.columns if not c.endswith("_path") and c != "file"]
    else:
        display_cols = [
            "identifier", "date_time", "subject_id",
            "temp_min", "temp_max", "temp_mean", "invalid_rois",
        ]
    st.dataframe(manifest[display_cols], width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Sessions tab — reconstructed entirely from output/*.json (session_id in
# each image's session_log), so this works from just the output folder:
# point the dashboard at any output/ directory and sessions show up
# automatically.
# ---------------------------------------------------------------------------
with tab_sessions:
    st.caption(
        "Images are grouped by the Session ID saved in the sidebar's \"0. Session & subject info\" "
        "form. Images without one (older captures, or plain CLI runs) fall under \"(unlogged)\"."
    )

    session_key = manifest["session_id"].fillna("(unlogged)")
    sessions_summary = (
        manifest.assign(_session=session_key)
        .groupby("_session", dropna=False)
        .agg(
            images=("identifier", "count"),
            subject_id=("subject_id", lambda s: next((v for v in s if pd.notna(v) and v), "NA")),
            first_capture=("date_time", "min"),
            last_capture=("date_time", "max"),
            flagged=("invalid_rois", lambda s: s.notna().sum()),
        )
        .reset_index()
        .rename(columns={"_session": "session_id"})
    )
    sessions_summary = (
        sessions_summary.assign(_sort_ts=pd.to_datetime(sessions_summary["first_capture"], errors="coerce"))
        .sort_values("_sort_ts", na_position="last")
        .drop(columns="_sort_ts")
        .reset_index(drop=True)
    )
    st.dataframe(sessions_summary, width="stretch", hide_index=True)

    chosen_session = st.selectbox("Inspect a session", sessions_summary["session_id"].tolist())
    session_rows = manifest[session_key == chosen_session].reset_index(drop=True)

    detail_col, list_col = st.columns([1, 1])
    with detail_col:
        st.markdown("**Session & subject details**")
        if chosen_session == "(unlogged)":
            st.info("These images have no session/subject info logged — nothing to show per-field.")
        else:
            # Each image snapshots session_log independently at extraction
            # time, so a field can legitimately differ across a session if
            # the sidebar form was edited and re-saved mid-batch — surface
            # that as "Mixed" instead of silently showing one image's value.
            detail = {}
            mixed_breakdown: dict[str, pd.Series] = {}
            for col, label in REPORT_COLUMNS:
                if col in ("identifier", "date_time"):
                    continue
                value, per_image = session_field_values(session_rows, col)
                detail[label] = value
                if value.startswith("Mixed"):
                    mixed_breakdown[label] = per_image
            st.table(pd.Series(detail, name="value").rename_axis("field"))

            if mixed_breakdown:
                with st.expander(
                    f"⚠️ {len(mixed_breakdown)} field(s) differ across this session's images "
                    "— likely the sidebar form was edited and re-saved mid-batch. Per-image values:",
                    expanded=False,
                ):
                    breakdown_df = pd.DataFrame(mixed_breakdown).T
                    breakdown_df.index.name = "field"
                    st.dataframe(breakdown_df, width="stretch")

    with list_col:
        st.markdown("**Images in this session**")
        st.caption("Pick any of these by name in \"Choose image\" in the Inspect tab.")
        st.dataframe(
            session_rows[["identifier", "date_time", "temp_min", "temp_max", "temp_mean", "invalid_rois"]],
            width="stretch", hide_index=True,
        )

# ---------------------------------------------------------------------------
# Export tab: batch export for ML pipelines
# ---------------------------------------------------------------------------
with tab_export:
    st.caption(
        "Pick images and which artifacts to include, then download one ZIP. Files are "
        "renamed with a sequence number (001_, 002_, ...) matching the sort order chosen in the "
        "Browse tab, so the export stays in the right order regardless of the original filenames."
    )

    all_ids = manifest["identifier"].tolist()
    select_all = st.checkbox("Select all", value=True)
    selected_ids = st.multiselect(
        "Images to export", all_ids, default=all_ids if select_all else [],
        key=f"export_select_{select_all}",  # forces the default to re-apply when toggled
    )

    with st.expander("Include in export", expanded=False):
        inc1, inc2, inc3, inc4, inc5, inc6 = st.columns(6)
        include_arrays = inc1.checkbox("Raw temp arrays (.npy)", value=True, help="Per-pixel °C array, one .npy file per image — the ML training input.")
        include_json = inc2.checkbox("Metadata JSON", value=True, help="Calibration constants, EXIF/GPS, stats, subject/session log, ROI flags — one .json per image.")
        include_optical = inc3.checkbox("Optical photos", value=False, help="Embedded visible-light photo, if the camera captured one.")
        include_render = inc4.checkbox("Camera renders", value=False, help="Camera's baked-in false-color palette image.")
        include_stacked = inc5.checkbox("Stacked .npz (1 file)", value=False, help="All selected temperature arrays combined into a single compressed .npz — only works if every selected image has the same resolution.")
        include_report = inc6.checkbox(
            "Subject & environment report (CSV)", value=True,
            help="One row per exported image with every subject/environment/QA variable ever logged "
                 "(session ID, subject prep, ambient conditions, ROI QA flags) — missing values shown as "
                 "'NA' rather than blank, so every column is always present.",
        )

    if selected_ids and st.button(f"Prepare export ({len(selected_ids)} image(s))"):
        ordered_ids = [i for i in all_ids if i in selected_ids]
        subset = manifest.set_index("identifier").loc[ordered_ids].reset_index()
        with st.spinner("Building ZIP..."):
            zip_bytes, warnings = build_export_zip(
                subset, include_arrays, include_json, include_optical, include_render, include_stacked, include_report
            )
        st.session_state["export_zip"] = zip_bytes
        st.session_state["export_zip_name"] = f"thermal_export_{len(subset)}images.zip"
        st.session_state["export_warnings"] = warnings

    if "export_zip" in st.session_state:
        st.download_button(
            f"Download {st.session_state['export_zip_name']}",
            data=st.session_state["export_zip"],
            file_name=st.session_state["export_zip_name"],
            mime="application/zip",
        )
        for w in st.session_state.get("export_warnings", []):
            st.warning(w)

# ---------------------------------------------------------------------------
# Inspect tab: single-image detail viewer
# ---------------------------------------------------------------------------
with tab_inspect:
  if manifest.empty:
    st.info(no_stills_yet)
  else:
    selected = st.selectbox("Choose image", manifest["identifier"].tolist())
    row = manifest.loc[manifest["identifier"] == selected].iloc[0]

    tab_pixel, tab_analysis, tab_qa, tab_render, tab_optical, tab_json = st.tabs(
        ["Per-pixel temperature map", "Analysis", "Session log & QA flags", "Camera render", "Optical photo", "Raw metadata"]
    )

    with tab_pixel:
        with st.expander("⚠️ Per-pixel temperature disclaimer", expanded=False):
            st.markdown(PIXEL_DISCLAIMER)
        array_path = safe_path(row.get("temperature_array_path"))
        if array_path is None:
            st.error("No raw temperature array saved for this image.")
        else:
            array = np.load(array_path)
            h, w = array.shape
            default_factor = max(1, round(max(h, w) / 256))
            factor = st.slider(
                "Pooling factor (block mean — higher = smoother/coarser, for readability only)",
                1, 16, default_factor,
            )
            pooled = block_mean_pool(array, factor)

            fig, ax = plt.subplots(figsize=(6, 4.5))
            # interpolation="nearest": one array cell = one solid color block, no
            # blending on top of the (already disclaimed) pooling above.
            im = ax.imshow(pooled, cmap="inferno", interpolation="nearest")
            cbar = fig.colorbar(im, ax=ax)
            cbar.set_label("Temperature (°C)")
            title = "no pooling (full resolution)" if factor == 1 else f"{factor}×{factor} block-mean pooled"
            ax.set_title(f"{selected} — {title}")
            ax.axis("off")
            st.pyplot(fig)

            col_a, col_b = st.columns(2)
            with col_a:
                st.caption(f"Full-resolution stats ({h}×{w} pixels)")
                st.write(pd.Series({"min °C": array.min(), "max °C": array.max(), "mean °C": array.mean()}))
            with col_b:
                st.caption(f"Displayed/pooled stats ({pooled.shape[0]}×{pooled.shape[1]} cells)")
                st.write(pd.Series({"min °C": pooled.min(), "max °C": pooled.max(), "mean °C": pooled.mean()}))

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            st.download_button(
                "Download this map as PNG", buf.getvalue(),
                file_name=f"{selected}_temperature_map.png", mime="image/png",
            )
            plt.close(fig)

    with tab_analysis:
        with st.expander("⚠️ Per-pixel temperature disclaimer", expanded=False):
            st.markdown(PIXEL_DISCLAIMER)
        analysis_array_path = safe_path(row.get("temperature_array_path"))
        if analysis_array_path is None:
            st.error("No raw temperature array saved for this image.")
        else:
            a_array = np.load(analysis_array_path)
            a_h, a_w = a_array.shape

            st.markdown("**Display**")
            dcol1, dcol2 = st.columns(2)
            cmap_name = dcol1.selectbox(
                "Colormap", ["inferno", "gray", "jet", "viridis", "coolwarm"], key="an_cmap",
                help="Different colormaps make different kinds of features easier to spot — "
                     "e.g. 'coolwarm' emphasizes a hot/cold split, 'gray' avoids color-perception bias.",
            )
            manual_range = dcol2.checkbox("Manually set color range", value=False, key="an_manual_range")
            if manual_range:
                vmin, vmax = st.slider(
                    "Color range (°C)", float(a_array.min()), float(a_array.max()),
                    (float(a_array.min()), float(a_array.max())), key="an_range",
                    help="Clip the color scale to a chosen band — useful for comparing multiple images "
                         "on the same scale, or increasing contrast within a narrow range of interest.",
                )
            else:
                vmin, vmax = float(a_array.min()), float(a_array.max())

            st.markdown("**Isotherm highlight**")
            iso_enabled = st.checkbox(
                "Highlight only a temperature band, gray out everything else", value=False, key="an_iso_enabled"
            )
            if iso_enabled:
                iso_lo, iso_hi = st.slider(
                    "Highlight band (°C)", float(a_array.min()), float(a_array.max()),
                    (float(a_array.min()), float(a_array.max())), key="an_iso_range",
                )

            st.markdown("**Line profile**")
            lp_c1, lp_c2 = st.columns(2)
            lp_axis = lp_c1.radio("Direction", ["Horizontal (row)", "Vertical (column)"], key="an_lp_axis")
            if lp_axis.startswith("Horizontal"):
                lp_index = lp_c2.slider("Row", 0, a_h - 1, a_h // 2, key="an_lp_row")
            else:
                lp_index = lp_c2.slider("Column", 0, a_w - 1, a_w // 2, key="an_lp_col")

            st.markdown("**Region of interest (ROI)**")
            roi_c1, roi_c2, roi_c3, roi_c4 = st.columns(4)
            roi_x1 = roi_c1.number_input("x1", 0, a_w - 1, 0, key="an_roi_x1")
            roi_y1 = roi_c2.number_input("y1", 0, a_h - 1, 0, key="an_roi_y1")
            roi_x2 = roi_c3.number_input("x2", 0, a_w - 1, a_w - 1, key="an_roi_x2")
            roi_y2 = roi_c4.number_input("y2", 0, a_h - 1, a_h - 1, key="an_roi_y2")
            roi_x_lo, roi_x_hi = sorted((roi_x1, roi_x2))
            roi_y_lo, roi_y_hi = sorted((roi_y1, roi_y2))

            # --- Annotated image: colormap/range + isotherm + ROI box + profile line ---
            fig, ax = plt.subplots(figsize=(6.5, 5))
            if iso_enabled:
                ax.imshow(a_array, cmap="gray", interpolation="nearest")
                mask = (a_array >= iso_lo) & (a_array <= iso_hi)
                masked = np.ma.masked_where(~mask, a_array)
                im = ax.imshow(masked, cmap=cmap_name, vmin=vmin, vmax=vmax, interpolation="nearest")
            else:
                im = ax.imshow(a_array, cmap=cmap_name, vmin=vmin, vmax=vmax, interpolation="nearest")
            fig.colorbar(im, ax=ax, label="Temperature (°C)")

            if lp_axis.startswith("Horizontal"):
                ax.axhline(lp_index, color="cyan", linewidth=1)
            else:
                ax.axvline(lp_index, color="cyan", linewidth=1)

            ax.add_patch(Rectangle(
                (roi_x_lo - 0.5, roi_y_lo - 0.5), roi_x_hi - roi_x_lo + 1, roi_y_hi - roi_y_lo + 1,
                fill=False, edgecolor="lime", linewidth=1.5,
            ))
            ax.set_title(f"{selected}  (cyan = profile line, green = ROI box)")
            ax.axis("off")
            st.pyplot(fig)
            plt.close(fig)

            # --- Line profile plot ---
            if lp_axis.startswith("Horizontal"):
                profile = a_array[lp_index, :]
                position = np.arange(a_w)
                pos_label = "Column (x)"
            else:
                profile = a_array[:, lp_index]
                position = np.arange(a_h)
                pos_label = "Row (y)"
            fig_lp, ax_lp = plt.subplots(figsize=(6.5, 2.8))
            ax_lp.plot(position, profile, color="firebrick")
            ax_lp.set_xlabel(pos_label)
            ax_lp.set_ylabel("Temperature (°C)")
            ax_lp.set_title("Line profile (cyan line above)")
            ax_lp.grid(alpha=0.3)
            fig_lp.tight_layout()
            st.pyplot(fig_lp)
            plt.close(fig_lp)

            # --- ROI stats ---
            roi = a_array[roi_y_lo:roi_y_hi + 1, roi_x_lo:roi_x_hi + 1]
            st.caption(f"ROI stats (green box above, {roi.shape[1]}×{roi.shape[0]} px)")
            st.write(pd.Series({
                "min °C": roi.min(), "max °C": roi.max(),
                "mean °C": roi.mean(), "std °C": roi.std(),
            }))

            # --- Track this ROI across the whole session ---
            st.markdown("**Track this ROI across the whole session**")
            st.caption(
                "Computes the same box's mean temperature in every extracted image, in capture-time "
                "order — useful for spotting a trend (e.g. something heating up) across a session."
            )
            if st.button("Compute trend across all images", key="an_trend_btn"):
                trend_rows = []
                skipped = 0
                for _, r in manifest.iterrows():
                    p = safe_path(r.get("temperature_array_path"))
                    if p is None:
                        continue
                    a = np.load(p)
                    if a.shape != a_array.shape:
                        skipped += 1
                        continue
                    sub = a[roi_y_lo:roi_y_hi + 1, roi_x_lo:roi_x_hi + 1]
                    trend_rows.append({"identifier": r["identifier"], "date_time": r["date_time"], "roi_mean": sub.mean()})

                if not trend_rows:
                    st.info("No comparable images found (same resolution required).")
                else:
                    trend_df = pd.DataFrame(trend_rows)
                    trend_df["date_time"] = pd.to_datetime(trend_df["date_time"], errors="coerce")
                    trend_df = trend_df.sort_values("date_time", na_position="last").reset_index(drop=True)

                    fig_tr, ax_tr = plt.subplots(figsize=(8, 3))
                    has_dates = trend_df["date_time"].notna().any()
                    if has_dates:
                        ax_tr.plot(trend_df["date_time"], trend_df["roi_mean"], marker="o", color="darkorange")
                        fig_tr.autofmt_xdate()
                    else:
                        ax_tr.plot(range(len(trend_df)), trend_df["roi_mean"], marker="o", color="darkorange")
                        ax_tr.set_xlabel("Image sequence")
                    ax_tr.set_ylabel("ROI mean (°C)")
                    ax_tr.set_title(f"ROI mean temperature across {len(trend_df)} image(s)")
                    ax_tr.grid(alpha=0.3)
                    fig_tr.tight_layout()
                    st.pyplot(fig_tr)
                    plt.close(fig_tr)
                    if skipped:
                        st.caption(f"{skipped} image(s) skipped (different resolution than {selected}).")

    with tab_qa:
        json_path_qa = safe_path(row.get("metadata_json_path"))
        if json_path_qa is None:
            st.error("No metadata JSON found for this image.")
        else:
            record_qa = json.loads(json_path_qa.read_text())
            session_log = record_qa.get("session_log") or {}
            roi_validity = record_qa.get("roi_validity") or {}

            st.markdown("**Subject / session log captured with this image**")
            if not session_log:
                st.info(
                    "No subject/session info was logged for this image (uploaded before the "
                    "sidebar's \"0. Session & subject info\" form was filled in, or via CLI)."
                )
            else:
                st.table(pd.Series(session_log, name="value").rename_axis("field"))

            st.divider()
            st.markdown("**Data quality flags**")
            st.caption(
                "Per the capture protocol: glasses block LWIR (treat the eye region as invalid), "
                "and heavy makeup, facial hair, or hair over the forehead also invalidate ROIs. "
                "Flag this image so it's easy to filter out (or handle specially) downstream."
            )
            # Keys are namespaced by `selected` so switching images in the picker
            # above shows that image's own saved flags, not whatever was last
            # clicked for a different image.
            eyes_invalid = st.checkbox(
                "Eyes/glasses region invalid", value=bool(roi_validity.get("eyes_glasses_invalid")), key=f"qa_eyes_{selected}"
            )
            makeup_facial_hair_invalid = st.checkbox(
                "Makeup / facial hair invalid", value=bool(roi_validity.get("makeup_facial_hair_invalid")), key=f"qa_makeup_{selected}"
            )
            hair_forehead_invalid = st.checkbox(
                "Hair over forehead invalid", value=bool(roi_validity.get("hair_forehead_invalid")), key=f"qa_hair_{selected}"
            )
            off_axis = st.checkbox(
                "Subject off-axis (> ~45°)", value=bool(roi_validity.get("off_axis")), key=f"qa_off_axis_{selected}"
            )
            qa_notes = st.text_area("QA notes (optional)", value=roi_validity.get("notes", ""), key=f"qa_notes_{selected}")

            if st.button("Save QA flags for this image", key=f"qa_save_{selected}"):
                record_qa["roi_validity"] = {
                    "eyes_glasses_invalid": eyes_invalid,
                    "makeup_facial_hair_invalid": makeup_facial_hair_invalid,
                    "hair_forehead_invalid": hair_forehead_invalid,
                    "off_axis": off_axis,
                    "notes": qa_notes.strip(),
                }
                json_path_qa.write_text(json.dumps(record_qa, indent=2))
                st.success("Saved. Reload/interact with the page to see it reflected in the table above.")

    with tab_render:
        render_path = safe_path(row.get("render_image_path"))
        if render_path is None:
            st.info("No camera-palette render saved for this image.")
        else:
            st.image(str(render_path), caption="Camera-embedded false-color palette render")

    with tab_optical:
        optical_path = safe_path(row.get("optical_image_path"))
        if optical_path is None:
            st.info("No embedded visible-light photo saved for this image.")
        else:
            st.image(str(optical_path), caption="Embedded visible-light photo")

    with tab_json:
        json_path = safe_path(row.get("metadata_json_path"))
        if json_path is None:
            st.info("No metadata JSON found.")
        else:
            st.json(json.loads(json_path.read_text()))
