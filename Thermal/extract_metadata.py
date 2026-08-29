"""Extract radiometric temperature data and calibration/EXIF metadata from
FLIR radiometric JPEGs (R-JPEG) for use in ML pipelines.

For every input image, writes:
  - <output>/<stem>.json        full metadata record (calibration + EXIF + stats)
  - <output>/<stem>_celsius.npy raw per-pixel temperature array (optional --no-arrays to skip)
  - <output>/<stem>_optical.jpg embedded visible-light photo (only with --save-optical)

And a single manifest across the whole run:
  - <output>/manifest.csv / manifest.json  one row per image, for ML dataset ingestion

Usage
-----
python extract_metadata.py --input images/ --output output/
python extract_metadata.py --input images/DJI_0001_T.jpg --output output/ --save-optical
python extract_metadata.py --input images/ --units kelvin --no-arrays
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Optional

import flyr
import numpy as np
import pandas as pd
from tqdm import tqdm

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
UNIT_ARRAYS = {"celsius", "kelvin", "fahrenheit"}

_NUM_RE = re.compile(r"(\d+)")


def natural_sort_key(name: str) -> tuple:
    """Sort key that orders 'FLIR9' before 'FLIR10' (plain string sort wouldn't).

    Each token is tagged (0, int) or (1, str) so tokens of different types are
    never compared directly against each other (mixing int/str in a tuple
    comparison raises TypeError in Python 3). Returns a tuple (not a list) so
    it stays hashable, since pandas needs that for sort_values.
    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in _NUM_RE.split(name)
        if part
    )


def json_default(value: Any) -> Any:
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dt.datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def find_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(
        (p for p in input_path.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: natural_sort_key(p.name),
    )


def temperature_stats(array: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.nanmin(array)),
        "max": float(np.nanmax(array)),
        "mean": float(np.nanmean(array)),
        "median": float(np.nanmedian(array)),
        "std": float(np.nanstd(array)),
    }


def camera_record(cam) -> dict[str, Any]:
    if cam is None:
        return {}
    return {
        "make": cam.make,
        "model": cam.model,
        "software": cam.software,
        "date_time": cam.date_time,
        "focal_length_mm": cam.focal_length,
        "x_resolution": cam.x_resolution,
        "y_resolution": cam.y_resolution,
        "image_description": cam.image_description,
        "gps_latitude": cam.gps_latitude,
        "gps_longitude": cam.gps_longitude,
        "gps_altitude_m": cam.gps_altitude,
        "gps_image_direction": cam.gps_image_direction,
        "gps_map_datum": cam.gps_map_datum,
    }


def measurement_records(measurements) -> list[dict[str, Any]]:
    return [
        {"tool": m.tool.name, "label": m.label, "params": list(m.params)}
        for m in measurements
    ]


def build_record(
    image_path: Path,
    thermogram,
    units: str,
    session_metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    array = getattr(thermogram, units)
    cam = thermogram.camera_metadata
    pip_info = thermogram.pip_info

    return {
        # Stored as an absolute path so it still resolves correctly no matter
        # what directory the dashboard/CLI happen to be launched from.
        "file": str(image_path.resolve()),
        "identifier": thermogram.identifier,
        "image_height": array.shape[0],
        "image_width": array.shape[1],
        "temperature_unit": units,
        "temperature_stats": temperature_stats(array),
        # Calibration parameters FLIR embeds and uses to convert raw sensor
        # counts to temperature (emissivity, distances, Planck constants, ...).
        # Kept verbatim so temperatures can be recomputed with adjusted
        # parameters via flyr's `adjust_metadata`.
        "radiometric_calibration": thermogram.metadata,
        "camera": camera_record(cam),
        "measurements": measurement_records(thermogram.measurements),
        "has_optical_image": thermogram.optical is not None,
        "has_picture_in_picture": pip_info is not None,
        "picture_in_picture": (
            None
            if pip_info is None
            else {
                "real_to_ir_ratio": pip_info.real_to_ir,
                "offset_x": pip_info.offset_x,
                "offset_y": pip_info.offset_y,
                "crop_box": pip_info.crop_box,
            }
        ),
        # Per-subject / per-session context logged at capture time (ambient
        # conditions, subject prep, etc.) — see the Thermal Data Collection
        # protocol notes. Empty dict when not provided (e.g. plain CLI runs).
        "session_log": session_metadata or {},
        # ROI data-quality flags (glasses/eyes, makeup/facial hair, hair over
        # forehead, ...) — set later from the dashboard's Inspect tab, not at
        # extraction time, so this always starts empty here.
        "roi_validity": {},
    }


def describe_unpack_error(exc: Exception) -> str:
    if isinstance(exc, KeyError):
        return "no radiometric thermal data embedded (this is a plain photo, not a FLIR R-JPEG)"
    return str(exc)


def process_image(
    image_path: Path,
    output_dir: Path,
    units: str,
    save_arrays: bool,
    save_optical: bool,
    save_render: bool,
    on_skip: Optional[Any] = None,
    session_metadata: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    try:
        thermogram = flyr.unpack(str(image_path))
    except Exception as exc:  # not every JPEG is a radiometric FLIR file
        reason = describe_unpack_error(exc)
        if on_skip is not None:
            on_skip(image_path, reason)
        else:
            print(f"skip {image_path}: {reason}")
        return None

    record = build_record(image_path, thermogram, units, session_metadata)
    stem = image_path.stem
    output_dir = output_dir.resolve()

    # Re-extracting an image (e.g. "Scan images/ for unprocessed files" run
    # twice, or a CLI re-run) shouldn't wipe out roi_validity flags a team
    # member already saved from the dashboard for this same file.
    existing_json = output_dir / f"{stem}.json"
    if existing_json.exists():
        try:
            previous = json.loads(existing_json.read_text())
            if previous.get("roi_validity"):
                record["roi_validity"] = previous["roi_validity"]
            if not session_metadata and previous.get("session_log"):
                record["session_log"] = previous["session_log"]
        except (OSError, json.JSONDecodeError):
            pass

    if save_arrays:
        array_path = output_dir / f"{stem}_{units}.npy"
        np.save(array_path, getattr(thermogram, units).astype(np.float32))
        record["temperature_array_path"] = str(array_path)

    if save_optical and thermogram.optical_pil is not None:
        optical_path = output_dir / f"{stem}_optical.jpg"
        thermogram.optical_pil.save(optical_path)
        record["optical_image_path"] = str(optical_path)

    if save_render:
        render_path = output_dir / f"{stem}_thermal.jpg"
        thermogram.render_pil().save(render_path)
        record["render_image_path"] = str(render_path)

    json_path = output_dir / f"{stem}.json"
    record["metadata_json_path"] = str(json_path)
    json_path.write_text(json.dumps(record, indent=2, default=json_default))

    return record


def flatten_for_manifest(record: dict[str, Any]) -> dict[str, Any]:
    calib = record["radiometric_calibration"]
    cam = record["camera"]
    stats = record["temperature_stats"]
    session_log = record.get("session_log") or {}
    roi_validity = record.get("roi_validity") or {}
    invalid_flags = [k for k, v in roi_validity.items() if k != "notes" and v]
    return {
        "file": record["file"],
        "identifier": record["identifier"],
        "width": record["image_width"],
        "height": record["image_height"],
        "temp_unit": record["temperature_unit"],
        "temp_min": stats["min"],
        "temp_max": stats["max"],
        "temp_mean": stats["mean"],
        "temp_median": stats["median"],
        "temp_std": stats["std"],
        "emissivity": calib.get("emissivity"),
        "object_distance_m": calib.get("object_distance"),
        "atmospheric_temperature_k": calib.get("atmospheric_temperature"),
        "reflected_apparent_temperature_k": calib.get("reflected_apparent_temperature"),
        "relative_humidity": calib.get("relative_humidity"),
        "camera_make": cam.get("make"),
        "camera_model": cam.get("model"),
        "date_time": cam.get("date_time"),
        "gps_latitude": cam.get("gps_latitude"),
        "gps_longitude": cam.get("gps_longitude"),
        "gps_altitude_m": cam.get("gps_altitude_m"),
        "num_measurements": len(record["measurements"]),
        # Subject/session logging (see the capture protocol notes) — filled
        # in from the dashboard sidebar at capture time, blank on plain CLI runs.
        "session_id": session_log.get("session_id"),
        "subject_id": session_log.get("subject_id"),
        "skin_type": session_log.get("skin_type"),
        "sweat": session_log.get("sweat"),
        "clothing_level": session_log.get("clothing_level"),
        "recent_activity": session_log.get("recent_activity"),
        "medical_history_notes": session_log.get("medical_history_notes"),
        "ambient_temperature_c": session_log.get("ambient_temperature_c"),
        "airflow": session_log.get("airflow"),
        "sunlight_leakage": session_log.get("sunlight_leakage"),
        "camera_distance_cm": session_log.get("camera_distance_cm"),
        "acclimatization_min": session_log.get("acclimatization_min"),
        "session_time_of_day": session_log.get("time_of_day"),
        "session_notes": session_log.get("notes"),
        # Data-quality flags, e.g. glasses/eyes, makeup/facial hair, hair over
        # forehead — set from the Inspect tab's "Data quality flags" section.
        # Individual booleans (None = never QA'd) alongside the joined summary.
        "eyes_glasses_invalid": roi_validity.get("eyes_glasses_invalid"),
        "makeup_facial_hair_invalid": roi_validity.get("makeup_facial_hair_invalid"),
        "hair_forehead_invalid": roi_validity.get("hair_forehead_invalid"),
        "off_axis_invalid": roi_validity.get("off_axis"),
        "invalid_rois": ", ".join(invalid_flags) if invalid_flags else None,
        "roi_notes": roi_validity.get("notes"),
        "metadata_json_path": record.get("metadata_json_path"),
        "temperature_array_path": record.get("temperature_array_path"),
        "optical_image_path": record.get("optical_image_path"),
        "render_image_path": record.get("render_image_path"),
    }


def sort_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    """Chronological order (capture time) with a natural-filename fallback/tiebreaker."""
    if manifest.empty:
        return manifest
    manifest = manifest.copy()
    manifest["_date_sort"] = pd.to_datetime(manifest["date_time"], errors="coerce")
    manifest["_name_sort"] = manifest["identifier"].map(
        lambda v: natural_sort_key(str(v))
    )
    manifest = manifest.sort_values(
        by=["_date_sort", "_name_sort"], na_position="last", kind="stable"
    )
    return manifest.drop(columns=["_date_sort", "_name_sort"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, help="FLIR image file or directory of images")
    parser.add_argument("--output", default=Path("output"), type=Path, help="Directory to write extracted data")
    parser.add_argument("--units", default="celsius", choices=sorted(UNIT_ARRAYS), help="Temperature unit for arrays/stats")
    parser.add_argument("--no-arrays", dest="save_arrays", action="store_false", help="Skip writing per-pixel .npy temperature arrays")
    parser.add_argument("--save-optical", action="store_true", help="Also extract the embedded visible-light photo")
    parser.add_argument("--save-render", action="store_true", help="Also save a colorized (false-color) JPEG of the thermal data, for visual inspection")
    args = parser.parse_args()

    images = find_images(args.input)
    if not images:
        raise SystemExit(f"No .jpg/.jpeg files found under {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    for image_path in tqdm(images, desc="Extracting"):
        record = process_image(image_path, args.output, args.units, args.save_arrays, args.save_optical, args.save_render)
        if record is not None:
            manifest_rows.append(flatten_for_manifest(record))

    manifest = sort_manifest(pd.DataFrame(manifest_rows))
    manifest.to_csv(args.output / "manifest.csv", index=False)
    manifest.to_json(args.output / "manifest.json", orient="records", indent=2, date_format="iso")

    print(f"Extracted {len(manifest_rows)}/{len(images)} images -> {args.output}")


if __name__ == "__main__":
    main()
