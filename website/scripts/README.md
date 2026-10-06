# Website data

The modality pages (`/thermal`, `/ecg`, `/emg`, `/rppg`) read static files from
`public/data/<modality>/`. Until the study's own recordings are published,
they show **public sample data**, processed by the scripts here from the
originals kept in `sources/`:

| Page | Source | Licence | Notes |
|---|---|---|---|
| Thermal | [Thermography of a person drinking](https://commons.wikimedia.org/wiki/File:Drinking_a_glass_of_sour_orange_juice.ogv) — Pixelmaniac pictures, Fluke Ti55 | Public domain | False-colour video: temperatures are **illustrative**, reconstructed from the colour palette |
| ECG | [Stress Recognition in Automobile Drivers](https://physionet.org/content/drivedb/1.0.0/) (drivedb), record `drive05` — Healey & Picard, *IEEE T-ITS* 6(2):156–166, 2005 | Open Data Commons Attribution 1.0 | Cite the paper and PhysioNet. 5-minute excerpt (13:00–18:00, rest → city driving) |
| EMG | [GRABMyo](https://physionet.org/content/grabmyo/1.1.0/) (PhysioNet v1.1.0), session 1, participant 1: rest (gesture 17) and hand close (gesture 16), trial 1 — Jiang, Pradhan & He 2024, doi:10.13026/89dm-f662; Pradhan, He & Jiang, *Sci. Data* 9:733, 2022 | CC BY 4.0 | Cite both. 28 forearm/wrist electrodes, 2048 Hz; the two 5 s recordings are shown back to back |
| rPPG | **Synthetic** face colour trace with a known pulse, until a real one is added (see below) | — | Illustrative. Everything downstream is the real cvpr-lab pipeline |

```bash
# from the website folder (ffmpeg needed for the thermal one)
python scripts/thermal/make_showcase.py   # -> public/data/thermal/
python scripts/ecg/make_showcase.py       # -> public/data/ecg/ (uses ../ECG/ecg_analysis.py)
python scripts/emg/make_showcase.py       # -> public/data/emg/ (numpy/scipy; 20-450 Hz band-pass, mains notch, RMS)
python scripts/rppg/make_showcase.py      # -> public/data/rppg/ (uses ../cvpr-lab, numpy/scipy only)
```

Every ECG metric comes from the study's own pipeline, `ECG/ecg_analysis.py`.

## Files

Every modality folder has an `index.json`:

```jsonc
{
  "modality": "thermal",
  "source": { "kind": "public" | "study", "note": "shown on the page" },
  "sessions": [{ "id", "subject": { "id", "ageBand", "sex" }, "label", "durationS" }]
}
```

plus one `<session id>.json` per session. Types are in
`src/lib/sample-data.ts` (`ThermalSession`, `EcgSession`, `RppgSession`) — keep them in sync.
A `source` block on each session credits where the recording came from.

### Thermal

- `frames`: metadata for `<id>.frames.bin` — `count` frames of `width × height`
  bytes, row-major, frame after frame. Each byte maps linearly to
  `tempMinC … tempMaxC`.
- `rois`: `[x, y, w, h]` boxes in frame pixels plus a `valid` flag (e.g. false
  for the eye region when glasses are worn).
- `series.roiMeanC`: each region's mean °C at `series.rateHz`.
- `phases`: named spans of the recording (here: before / drinking / after).

**From study data:** `Thermal/extract_metadata.py` and `extract_seq.py` save one
float32 °C array (`.npy`) per frame plus a JSON record. Stack the frames,
quantise to uint8 over a fixed range, compute the region means from the
full-precision arrays, and copy `session_log` / `roi_validity` into `context` /
`roiValidity`.

### ECG

- `signal`: `raw` and `filtered` mV at `fs` Hz.
- `rPeaks`, `rr`, `hrv`, `psd`, `averageBeat`, `quality`, `qualityWindows`:
  outputs of `ECG/ecg_analysis.py`.
- `companions` (optional): other signals recorded alongside, same excerpt.
- `drive` (optional): the whole original recording at `stepS` resolution, with
  its `segments`.

**From study data:** load a capture with `ECG/ecg_core.py`, then make the same
`ecg_analysis` calls `scripts/ecg/make_showcase.py` makes.

### rPPG

Built with [cvpr-lab](https://github.com/hima1323/cvpr-lab) (cloned at
`../cvpr-lab`): the training-free extractors in `cvprlab/classical.py` (POS,
CHROM, green) turn a per-frame face colour trace into a pulse, and
`cvprlab/vitals.py` derives heart rate, HRV, breathing, pulse shape, per-channel
pulsatility and signal quality from it. The learned model has no trained weights
yet, so it is not used; no torch needed.

- `rgb`: per-frame mean face colour (0–255) at `fs`.
- `waves`: standardised pulse per method, sign-aligned to the reference.
- `reference`: fingertip-oximeter PPG on frame times (optional).
- `beats`, `ibi` (with `valid` — intervals in poor windows or >20% off their
  neighbours are left out of HRV), `track` (10 s sliding HR per method, the
  reference and SNR), `scores`, `vitals` (`vitals.compute_all`, withheld
  measures omitted), `quality`, `spectrum`, `beatTemplate`, `respiration`,
  `channels` (measured over `colourWindowS`, the steadiest stretch).

**Real sample:** put `ubfc_subject1_rgb.csv` (face colour trace) and
`ubfc_subject1_gt.xmp` (oximeter: time ms, HR, SpO2, PPG) in `sources/` and
re-run the script — it prefers them over the synthetic trace.

**From study data:** detect the face with `cvprlab.data.face.detect_face_bbox`,
average each frame's crop to one RGB row (as `webapp/engine.py` does), then run
the same calls on that trace.