# Frontier X ECG capture & research dashboard

Captures the raw numerical ECG data behind a `liveecg.frontierxapp.com` share
link and turns it into an analysable record.

The protocol was read out of the webapp's own bundle
(`https://liveecg.frontierxapp.com/js/1.js`, `src/views/Livecg.vue`) rather than
guessed: it connects to `wss://liveecgwsapi.<domain>/server<1-5>?Authorization=token`,
sends the same `sendmessage` / `STREAMING` subscribe payload, and applies the
same `× 0.0000038146972` per-count scale.

## Install

```powershell
pip install -r requirements.txt
```

## The dashboard

```powershell
streamlit run dashboard.py
```

Paste your share link in the sidebar and press **Start**, or switch the source to
*Uploaded file* and drop in a `.csv` / `.jsonl` captured earlier.

| Tab | What it gives you |
|---|---|
| **Live monitor** | Live 10 s strip, current HR, packet health (accepted / missed / duplicate), stream events, and signal-quality indicators with a plain-language verdict |
| **Waveform** | Scrollable window over the whole record, raw vs filtered overlay, detected R peaks, optional 0.2 s × 0.5 mV clinical grid |
| **HRV & rhythm** | Time-domain metrics (SDNN, RMSSD, pNN50, CVNN), RR tachogram with artifacts marked, Poincaré plot with SD1/SD2, Welch PSD with LF/HF bands |
| **Beat morphology** | Ensemble-averaged beat ±1 SD with individual beats overlaid |
| **Export** | Samples CSV (raw counts, scaled, filtered, R-peak flags), raw packets JSONL, and a metrics JSON recording every processing setting |

Controls in the sidebar (filters, beat detection, amplitude units) and the
analysis-segment row at the top scope **every** tab, so what you export always
matches what you're looking at.

## The CLI capture

For long unattended recordings, without a browser open:

```powershell
python stream_capture.py https://liveecg.frontierxapp.com/6005748/Hans
python stream_capture.py 6005748 -d 600 -o morning_session
```

Writes `<out>.csv` (one row per sample) and `<out>.jsonl` (one line per unique
packet, lossless). Runs until Ctrl+C, the device stops streaming, or `-d`
elapses; reconnects on a dropped socket.

## What the stream actually delivers

Measured against the live feed, not assumed:

- **125 Hz** — one packet per second carrying 125 samples.
- The server **re-sends each packet about 3×**. Duplicates and out-of-order
  packets are discarded by `packetNo`, the way the webapp discards them.
- `Timestamp` is the **session start** and stays constant for the whole stream;
  `packetNo` counts seconds from it, which is how each sample gets a wall clock.
- Packets also carry `heartrate`, `age`, `gender`, `macID`, and `activity_type`.

## A caveat on amplitude units

The webapp scales raw counts by `0.0000038146972` but **never labels the
resulting unit**, and the constant does not correspond to any obvious ADC
front-end calibration. A peak-to-peak swing of ~1.3 in those units is far too
large for volts at the skin and matches a normal ECG in **millivolts**, so the
dashboard treats 1 stream unit as 1 mV and labels the axis
"mV (uncalibrated)". The sidebar exposes the scale and label if you obtain a
real calibration. The `volts` column keeps its name for compatibility with
`stream_capture.py`; `raw_count` is always the untouched device value.

## Files

| File | Role |
|---|---|
| `dashboard.py` | The Streamlit app |
| `ecg_core.py` | Protocol, link parsing, background capture thread, packet→frame |
| `ecg_analysis.py` | Filtering, R-peak detection, HRV, morphology, quality |
| `stream_capture.py` | Standalone CLI capture |

## Method notes

R peaks come from a Pan-Tompkins pipeline (5–15 Hz band-pass → derivative →
squaring → 150 ms moving-window integration) with detections refined onto the
QRS apex and a refractory period enforced. RR intervals outside 0.30–2.0 s, or
deviating from the local 5-beat median by more than the ectopic tolerance, are
flagged and excluded from HRV but still shown on the tachogram.
Frequency-domain HRV uses a cubic-interpolated 4 Hz tachogram, linear detrend,
and Welch PSD. All filters are zero-phase (`filtfilt`) so R-peak timing is not
shifted.

Validated two ways: on synthetic ECG with known beat times the detector found
216/216 beats and recovered the injected rate and respiratory modulation; on a
real 150 s capture the detected HR range (56.4–91.5 bpm) matched the device's
own reported range (55–90 bpm).

**This is a research and self-tracking tool, not a diagnostic device.**
