# Thermal metadata extraction

Extracts radiometric temperature data and calibration/EXIF metadata from FLIR
radiometric JPEGs (R-JPEG — the format FLIR/DJI thermal cameras save, where a
16-bit thermal image and its calibration constants are embedded inside a
normal-looking `.jpg`), for use as ML pipeline inputs.

Uses [`flyr`](https://pypi.org/project/flyr/), a pure-Python R-JPEG parser —
no ExifTool binary required.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

(A `.venv` with everything installed already exists in this folder.)

## Usage

Drop your FLIR `.jpg`/`.jpeg` files into `images/` (or point `--input`
anywhere), then:

```powershell
.\.venv\Scripts\python.exe extract_metadata.py --input images --output output
```

Options:

- `--units {celsius,kelvin,fahrenheit}` — unit for the saved arrays/stats (default `celsius`)
- `--no-arrays` — skip writing the per-pixel `.npy` temperature array (metadata JSON is always written)
- `--save-optical` — also extract the embedded visible-light photo (useful for RGB+thermal fusion models)
- `--save-render` — also save a colorized JPEG of the thermal data (the camera's false-color palette), for visual inspection

## Dashboard

```powershell
.\.venv\Scripts\streamlit.exe run dashboard.py
```

Opens a browser tab where you can:

- **Collapsible sidebar sections** (capture-side controls, always visible regardless of which main tab you're on) — the checklist, session/subject form, upload controls, and new-batch control are each their own expander, so you can collapse whatever you're not using right now.
- **Main area is split into four tabs** — Browse, Sessions, Export, Inspect — instead of one long scrolling page, with a summary metrics row (image count, dataset min/max, date range, flagged count) always visible above them.
- **Capture protocol checklist + warm-up timer** (sidebar) — the FLIR C5 protocol steps (emissivity, 15–20 min warm-up, head-on positioning, background, ROI checks, distance, MSX/RGB off) as tickable checkboxes, plus a Start/Reset timer that tracks elapsed warm-up time against the 15–20 min target.
- **Session & subject info form** (sidebar, "0.") — logs exactly what the capture protocol notes call for: a **Session ID** (auto-filled with a timestamp — reuse the same one across multiple upload batches to keep them grouped as one session), per-subject fields (skin type, sweat, clothing level, recent activity, medical history notes), and per-session/environment fields (ambient temperature, airflow/drafts, sunlight leakage, camera distance, acclimatization time, time of day, notes). This describes the batch **currently in progress** — "Update current batch details" changes it going forward (images already extracted keep whatever was set at the time). Fields are stored in each image's JSON record under `session_log` and surfaced as extra manifest/CSV columns (`session_id`, `subject_id`, `skin_type`, `ambient_temperature_c`, etc.).
- **Upload multiple FLIR `.jpg` files at once** (drag-and-drop or multi-select) — they're saved into `images/` and extracted immediately, landing in `output/` in the same format the CLI produces. The uploader resets itself after each successful batch so you can keep adding more right away (including re-selecting files with the same names). There's also a button to pick up any files already dropped into `images/` that haven't been extracted yet. Non-radiometric files (no embedded thermal data) are moved into `skipped/` rather than left in `images/`, so they don't get re-scanned and re-skipped on every pass — a dismissable warning lists what was skipped and why, and stays visible until you dismiss it or upload again (it no longer disappears on its own after a few seconds).
- **New batch (archive & clear)** (sidebar, "2.") — once you're done with a subject/session and want a clean slate for the next one, this zips everything currently in `images/`, `output/`, and `skipped/` into `archives/<name>_<timestamp>.zip`, then permanently clears all three folders. The name reflects the session ID(s) actually found in the batch's `output/*.json` records — a single ID if the batch was uniform, several IDs joined with `+` (or `mixed_Nsessions` for more than three), or `unlogged` if none of the images had a session logged — rather than just whatever's currently typed into the sidebar form, so it stays accurate even if you changed the Session ID mid-batch. It's a two-step confirmation (click once to see exactly what will be archived/deleted, click again to actually do it) since it's destructive — the archive ZIP is the only copy kept afterward.
- **Browse tab** — a sortable table of every extracted image, with the sort controls next to it: sort by capture time, filename (natural order, so `FLIR9` sorts before `FLIR10`), or any temperature stat, ascending or descending. A compact view by default (capture time, subject, temperature stats, QA flag) with a "Show all columns" toggle to reveal the full subject/session log and camera/GPS metadata.
- **Sessions tab** — every image is grouped by its Session ID (images without one fall under "(unlogged)"). A summary table shows each session's subject, image count, capture time range, and flagged-image count entirely from `output/*.json` — no separate database, so this works from just the `output/` folder (point the dashboard at any `output/` directory and sessions show up automatically). Pick a session to see its full logged detail (every subject/environment field, "NA" where nothing was entered) side by side with the list of images captured in it — pick any of those by name in "Choose image" in the Inspect tab. Since each image snapshots its subject/session info independently at extraction time, a field can genuinely differ across a session if the sidebar form was edited and re-saved mid-batch; when that happens the field shows `Mixed (N distinct)` instead of silently picking one image's value, with an expander to see the actual per-image breakdown.
- **Inspect tab: one image at a time**, across six sub-tabs:
  - *Per-pixel temperature map* — the raw radiometric array rendered with a scientific colormap and a °C colorbar (not the camera's baked-in palette). Includes a pooling slider: since displaying every raw pixel isn't always readable, you can apply block-mean downsampling — a disclaimer (collapsed by default, click to expand) explains this, and full-resolution vs. pooled stats are shown side by side so pooling never gets mistaken for exact per-pixel data.
  - *Analysis* — colormap/range control, isotherm highlighting, a line profile, an adjustable ROI box with live stats, and a button to trend that ROI's mean temperature across every extracted image in the session.
  - *Session log & QA flags* — shows the subject/session info logged for this specific image, and lets you flag data-quality issues per the protocol notes (glasses/eyes region invalid, makeup/facial hair invalid, hair over forehead invalid, subject off-axis) plus free-text QA notes. Saved back into that image's JSON record and into the manifest as `invalid_rois`/`roi_notes`, so bad ROIs are easy to filter out of an ML pipeline later instead of being silently included.
  - *Camera render* — the camera's own false-color palette image.
  - *Optical photo* — the embedded visible-light photo, if the camera captured one.
  - *Raw metadata* — the full JSON record.
- **Export tab: batch export report** — the export ZIP can include a `subject_environment_report.csv` (on by default): one row per exported image with every subject/environment/QA variable ever logged, in a fixed column order, with anything never entered shown as `NA` rather than a blank cell — so the report is always complete even for a mixed batch of logged and unlogged images.

The dashboard and the CLI share the same `output/` folder and extraction code — anything extracted one way is immediately visible in the other. `--input`/CLI runs without the dashboard simply leave `session_log` empty for those images; QA flags set later from the dashboard survive being re-extracted (e.g. re-running the CLI over the same `images/` folder won't wipe flags already saved for a file).

## Output

For each input image `<stem>.jpg`:

- `output/<stem>.json` — full record: calibration constants, EXIF/GPS, temperature stats, measurement regions
- `output/<stem>_celsius.npy` — per-pixel temperature array, `float32`, shape `[H, W]` (skip with `--no-arrays`)
- `output/<stem>_optical.jpg` — embedded visible photo (only with `--save-optical`)

Across the whole run:

- `output/manifest.csv` / `output/manifest.json` — one row per image with key stats and paths to the files above; this is the file to point a dataloader or `pandas.read_csv` at.
- `skipped/` — non-radiometric files the dashboard moved out of `images/` after failing to extract (see Notes below); untouched by the CLI.
- `archives/` — ZIPs created by the dashboard's "New batch (archive & clear)" control, one per cleared batch, named `<name>_<archived-at>.zip` (where `<name>` is the session ID actually found in the archived `output/*.json` records — joined with `+` if the batch mixed a few, `mixed_Nsessions` for more, or `unlogged` if none) and containing everything that was in `images/`, `output/`, and `skipped/` at that point.

### Per-image JSON fields

- `temperature_stats` — min/max/mean/median/std in the chosen unit
- `radiometric_calibration` — the physical parameters FLIR embeds and uses to
  convert raw sensor counts to temperature: `emissivity`, `object_distance`,
  `atmospheric_temperature`, `reflected_apparent_temperature`,
  `relative_humidity`, `ir_window_temperature`/`transmission`, the Planck
  constants (`planck_r1`, `planck_r2`, `planck_b`, `planck_f`, `planck_o`),
  and atmospheric transmission coefficients. Kept verbatim so temperatures
  can be recomputed with adjusted parameters (e.g. corrected emissivity)
  without re-flying the sensor — see `flyr.FlyrThermogram.adjust_metadata`.
- `camera` — make/model/software, capture `date_time`, focal length, and GPS
  lat/lon/altitude/heading if the camera recorded them (typical for drone
  platforms like DJI).
- `measurements` — any spot/box/line measurement tools the camera operator
  placed in-camera (tool type, label, pixel params).
- `picture_in_picture` — alignment info between the thermal and optical
  sensors, needed to overlay them.
- `session_log` — per-subject/per-session fields logged from the dashboard
  sidebar at capture time (session ID, skin type, sweat, clothing level,
  recent activity, medical history notes, ambient temperature, airflow,
  sunlight leakage, camera distance, acclimatization time, time of day,
  notes). Empty `{}` for images extracted without the dashboard form filled
  in — these show up under the dashboard's "Sessions" section as "(unlogged)".
- `roi_validity` — data-quality flags set later from the dashboard's *Session
  log & QA flags* tab (`eyes_glasses_invalid`, `makeup_facial_hair_invalid`,
  `hair_forehead_invalid`, `off_axis`, `notes`). Empty `{}` until flagged.

## Notes

- Non-radiometric JPEGs (no embedded thermal data) are skipped with a
  message rather than aborting the whole batch. From the dashboard, skipped
  files are moved into `skipped/` (not left in `images/`, where they'd
  otherwise be re-scanned and re-skipped every time); the CLI leaves them
  where they are and just prints a message.
- `flyr` reads calibration + temperature directly; it does not require
  ExifTool. If you need exhaustive raw EXIF/XMP/maker-note dump beyond what's
  captured here, install ExifTool separately and run it on the same files —
  the `camera` block here already covers make/model/date/GPS/focal length,
  which is what most ML metadata needs.
