"""Extract per-frame radiometric temperature data from a FLIR .SEQ recording
(the file FLIR Tools+ produces when recording the C5's live radiometric USB
video stream) for use in ML pipelines.

Uses flirpy (https://github.com/LJMUAstroecology/flirpy), a pure-Python
FFF/SEQ parser - no ExifTool binary required, same approach as flyr uses for
the R-JPEG stills in extract_metadata.py.

IMPORTANT: this script was written from careful reading of flirpy's source
(its FFF binary parsing and its raw2temp Planck-law conversion), but has not
yet been run against a real .SEQ file from this camera - none existed at
the time this was written. The first time you run it, treat the output as
unverified and cross-check a frame or two the same way verify_extraction.py
does for stills (e.g. compare against what FLIR Tools+ itself displays for
the same frame/timestamp).

Output layout matches extract_metadata.py's exactly, so frames extracted
here can live in the same output/ folder and are picked up automatically by
dashboard.py, its Analysis tab, and the batch-export feature - no changes
needed there.

Usage
-----
python extract_seq.py --input session.seq --output output/
python extract_seq.py --input seq_recordings/ --output output/ --save-render
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flirpy.io.seq import Seq
from tqdm import tqdm

from extract_metadata import (
    flatten_for_manifest,
    json_default,
    natural_sort_key,
    sort_manifest,
    temperature_stats,
)


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = value.strip().strip("\x00").strip()
    return value or None


def _celsius_field_to_kelvin(value: Any) -> Optional[float]:
    """flirpy's _get_camera_info stores Atmospheric/Reflected/IRWindow Temperature
    already converted to Celsius. The JPEG/flyr pipeline stores these same fields
    in Kelvin (matching the camera's own embedded convention), so convert back
    here to keep radiometric_calibration's units consistent across both scripts.
    """
    return None if value is None else float(value) + 273.15


def build_seq_record(seq_path: Path, frame_index: int, meta: dict, celsius: np.ndarray) -> dict[str, Any]:
    h, w = celsius.shape
    return {
        "file": str(seq_path.resolve()),
        "identifier": f"{seq_path.stem}_frame{frame_index:06d}",
        "frame_index": frame_index,
        "source_seq": seq_path.name,
        "image_height": h,
        "image_width": w,
        "temperature_unit": "celsius",
        "temperature_stats": temperature_stats(celsius),
        "radiometric_calibration": {
            "emissivity": meta.get("Emissivity"),
            "object_distance": meta.get("Object Distance"),
            "atmospheric_temperature": _celsius_field_to_kelvin(meta.get("Atmospheric Temperature")),
            "reflected_apparent_temperature": _celsius_field_to_kelvin(meta.get("Reflected Apparent Temperature")),
            "ir_window_temperature": _celsius_field_to_kelvin(meta.get("IR Window Temperature")),
            "ir_window_transmission": meta.get("IR Window Transmission"),
            "relative_humidity": meta.get("Relative Humidity"),
            "planck_r1": meta.get("Planck R1"),
            "planck_r2": meta.get("Planck R2"),
            "planck_b": meta.get("Planck B"),
            "planck_f": meta.get("Planck F"),
            "planck_o": meta.get("Planck O"),
            "atmospheric_trans_alpha1": meta.get("Atmospheric Trans Alpha 1"),
            "atmospheric_trans_alpha2": meta.get("Atmospheric Trans Alpha 2"),
            "atmospheric_trans_beta1": meta.get("Atmospheric Trans Beta 1"),
            "atmospheric_trans_beta2": meta.get("Atmospheric Trans Beta 2"),
            "atmospheric_trans_x": meta.get("Atmospheric Trans X"),
            "raw_value_range_min": meta.get("RawValueRangeMin"),
            "raw_value_range_max": meta.get("RawValueRangeMax"),
            "raw_value_median": meta.get("RawValueMedian"),
            "raw_value_range": meta.get("RawValueRange"),
        },
        "camera": {
            "make": "Teledyne FLIR",
            "model": _clean_str(meta.get("CameraModel")),
            "software": _clean_str(meta.get("CameraSoftware")),
            "serial_number": _clean_str(meta.get("CameraSerialNumber")),
            "date_time": meta.get("Datetime (UTC)"),
            "frame_rate_hz": meta.get("FrameRate"),
            "field_of_view_deg": meta.get("FieldOfView"),
        },
        "measurements": [],
        "has_optical_image": False,
        "has_picture_in_picture": False,
    }


def process_seq_file(
    seq_path: Path,
    output_dir: Path,
    save_arrays: bool,
    save_render: bool,
    frame_step: int,
) -> list[dict[str, Any]]:
    output_dir = output_dir.resolve()
    records = []

    try:
        frames = Seq(str(seq_path))
    except Exception as exc:
        print(f"skip {seq_path}: could not parse as a FLIR SEQ file ({exc})")
        return records

    for frame_index, fff in enumerate(tqdm(frames, desc=seq_path.name)):
        if frame_index % frame_step != 0:
            continue
        if not fff.meta:
            print(f"  skip frame {frame_index}: no camera-info record found (not radiometric)")
            continue

        try:
            celsius = fff.get_radiometric_image().astype(np.float32)
        except Exception as exc:
            print(f"  skip frame {frame_index}: temperature conversion failed ({exc})")
            continue

        record = build_seq_record(seq_path, frame_index, fff.meta, celsius)
        stem = f"{seq_path.stem}_frame{frame_index:06d}"

        if save_arrays:
            array_path = output_dir / f"{stem}_celsius.npy"
            np.save(array_path, celsius)
            record["temperature_array_path"] = str(array_path)

        if save_render:
            render_path = output_dir / f"{stem}_thermal.jpg"
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.imshow(celsius, cmap="inferno", interpolation="nearest")
            ax.axis("off")
            fig.savefig(render_path, dpi=100, bbox_inches="tight", pad_inches=0)
            plt.close(fig)
            record["render_image_path"] = str(render_path)

        json_path = output_dir / f"{stem}.json"
        record["metadata_json_path"] = str(json_path)
        json_path.write_text(json.dumps(record, indent=2, default=json_default))

        records.append(record)

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, help="A .seq file, or a directory of .seq files")
    parser.add_argument("--output", default=Path("output"), type=Path, help="Directory to write extracted data (shared with extract_metadata.py)")
    parser.add_argument("--no-arrays", dest="save_arrays", action="store_false", help="Skip writing per-frame .npy temperature arrays")
    parser.add_argument("--save-render", action="store_true", help="Also save a colorized JPEG per frame, for visual inspection")
    parser.add_argument("--frame-step", type=int, default=1, help="Only extract every Nth frame (default 1 = every frame)")
    args = parser.parse_args()

    if args.input.is_file():
        seq_files = [args.input]
    else:
        seq_files = sorted(args.input.glob("*.seq"), key=lambda p: natural_sort_key(p.name))
    if not seq_files:
        raise SystemExit(f"No .seq files found at {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)

    all_records = []
    for seq_path in seq_files:
        all_records.extend(process_seq_file(seq_path, args.output, args.save_arrays, args.save_render, args.frame_step))

    if not all_records:
        raise SystemExit("No radiometric frames were extracted - see skip messages above.")

    manifest_rows = [flatten_for_manifest(r) for r in all_records]
    manifest = sort_manifest(pd.DataFrame(manifest_rows))
    manifest.to_csv(args.output / "manifest.csv", index=False)
    manifest.to_json(args.output / "manifest.json", orient="records", indent=2, date_format="iso")

    print(f"\nExtracted {len(all_records)} frame(s) from {len(seq_files)} .seq file(s) -> {args.output}")
    print("This is the first real run against actual camera output - spot-check a frame's")
    print("temperature_stats against what FLIR Tools+ shows for the same timestamp before trusting it.")


if __name__ == "__main__":
    main()
