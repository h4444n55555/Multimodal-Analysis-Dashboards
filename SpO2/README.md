# Contec CMS50E SpO2 capture

Records the numerical data from a **Contec CMS50E** pulse oximeter to disk for
ML/analysis, the same way the `ECG/` folder records the Frontier X stream. The
CMS50E enumerates as a virtual COM port through its **Silicon Labs CP210x**
USB-to-serial bridge (the same driver SpO2 Assistant uses); this tool talks to
that port directly.

Two ways to use it:

- **`stream_capture.py`** — a command-line serial reader that writes clean
  per-sample CSV plus a lossless raw archive (live feed or the device's stored
  session).
- **`dashboard.py`** — a Streamlit dashboard for running a recording **session
  on a subject**: check the device is connected and reading a finger *before*
  you start, capture into an organized per-subject folder, then analyse and
  export ML-ready data. Built to run alongside the other sensor dashboards
  during a session (it uses its own port, `8503`).

The serial protocol was read out of two established reverse-engineered clients
rather than guessed — [tobac/cms50ew](https://github.com/tobac/cms50ew) for the
CMS50E/W framing and command set, and
[atbrask/CMS50Dplus](https://github.com/atbrask/CMS50Dplus) for the older
CMS50D+ layout — and every decoder is checked against their documented
byte→value vectors (`python stream_capture.py selftest`).

## Install

```powershell
pip install -r requirements.txt
```

Only `pyserial` is needed for command-line capture; the dashboard additionally
uses `numpy`, `pandas`, `scipy`, `streamlit`, and `plotly` (all in
`requirements.txt`). Make sure the CP210x driver is installed (you already did
this) and that **SpO2 Assistant is closed** — only one program can hold the COM
port at a time (that includes the dashboard vs. the CLI vs. the vendor app).

## Capture

```powershell
# List serial ports (confirm the CMS50E shows up as a CP210x)
python stream_capture.py ports

# Live feed -> spo2_live_<epoch>.csv / .raw  (Ctrl+C to stop)
python stream_capture.py live
python stream_capture.py live -d 600 -o morning        # stop after 600 s

# Download the session stored on the device
python stream_capture.py download -o last_night --start "2026-08-27 22:30"

# Validate the decoders without a device
python stream_capture.py selftest
```

The port is **auto-detected** by its CP210x USB id (`10C4:EA60`). If you have
more than one CP210x device, pass `--port COM5` explicitly.

## Dashboard

For running a recording session on a subject, use the dashboard instead of the
CLI:

```powershell
streamlit run dashboard.py
```

It opens on **port 8503** (set in `.streamlit/config.toml`) so it can run
alongside the other sensor dashboards (Thermal 8501, ECG 8502) during a
session. Everything is designed to stay responsive while recording: a
background thread does the serial capture, a lightweight status strip refreshes
about once a second, and the heavier charts/analysis are a manual **Refresh
view** snapshot so they never stall the recording.

**Before a session — is the SpO2 connected?** Press **Check device**. It reads
the device for ~3 s and tells you one of three things: not reachable (powered
off / wrong port / SpO2 Assistant still open), connected but no finger, or
connected and reading (with the live SpO₂ and pulse). With a finger out this
unit simply stops streaming, so "no data" *is* the finger-out / disconnect
signal — the live status strip shows **Finger out / no signal** whenever the
stream goes quiet mid-session.

**Organized per-subject storage.** Fill in the subject name / ID, a session
label, and anything relevant to the test (age, sex, condition, free-text notes,
plus any custom key/value fields). Pressing **Start** creates:

```
sessions/<subject>/<label>__<YYYYmmdd_HHMMSS>/
    samples.csv     one decoded row per sample (same columns as the CLI)
    raw.bin         the verbatim serial bytes (lossless archive)
    metadata.json   the subject/session fields, device, and capture summary
```

Sessions are grouped by subject so one person's recordings stay together, and
the folder is written as it records (crash-safe). Saved sessions can be
reloaded later from the sidebar (or drag in any `samples.csv`) for offline
analysis.

**Tabs.** *Monitor* (headline SpO₂/pulse + a signal-quality verdict), *SpO2 &
pulse* (trends with desaturation events shaded and time-below-threshold),
*Waveform* (the ~58 Hz pleth with detected pulses, and an ensemble-averaged
beat), *Analysis* (oxygenation stats, ODI, pulse-rate variability), and
*Export*.

**Extract for ML.** The Export tab downloads the full per-sample `samples.csv`,
a **windowed feature table** (one row per 30 s window — SpO₂/pulse stats, valid
fraction, pleth-derived pulse rate, PRV, pulse amplitude — ready to concatenate
across subjects for training), and a metrics JSON.

**Live waveform is optional and off by default.** The vendor app shows it
anyway; enable **Show live waveform** only if you want a short recent window
drawn ~once a second. It is intentionally opt-in so the dashboard stays light
when several are open at once.

## What gets written

Two files per run, mirroring ECG's `.csv` + `.jsonl` split:

| File | Contents |
|---|---|
| `<out>.csv`  | one decoded row per sample (see columns below) |
| `<out>.raw`  | the exact bytes read from the serial port, verbatim — a lossless archive so nothing is lost if a frame layout ever needs reworking |

**CSV columns (default `cms50e` protocol):**

| Column | Meaning |
|---|---|
| `time_iso` | wall-clock timestamp (live), or start + offset (download, with `--start`) |
| `elapsed_s` | seconds from the first sample |
| `sample_index` | 0-based sample counter |
| `spo2` | blood oxygen saturation, % (127 = no reading) |
| `pulse_rate` | pulse rate, bpm |
| `pleth` | plethysmograph (PPG) waveform sample, 0–127 — the ~58 Hz pulse wave |
| `pleth2` | secondary pulsatile byte, 0–127 (tracks the beat; semantics unconfirmed) |
| `finger_out` | True when the device reports no finger present (SpO₂ = 127) |
| `valid` | True when this is a real reading (finger in, SpO₂ ≠ 127) |
| `status1`, `status2` | raw status/flag bytes, kept for offline analysis |
| `frame_hex` | the full raw device frame as hex, so undecoded bytes are recoverable |

The live feed arrives at **~58 Hz**, so `pleth`/`pleth2` form a real waveform;
`spo2` and `pulse_rate` update roughly once per second and simply repeat across
the intervening waveform samples.

The `cms50d+` protocol carries its own `pleth`, plus `signal_strength`,
`searching`, `probe_error`, and `bar_graph`.

## Protocols

Two protocol generations exist across the CMS50 range; both are supported via
`--protocol`.

- **`cms50e` (default)** — the CMS50E/W protocol, as used by SpO2 Assistant.
  `115200` baud, 8N1, software flow control. The host sends 9-byte
  `0x7d`-prefixed commands; the device replies with 9-byte frames that begin on
  a `0x01` sync byte (payload bytes all carry bit 7, so `0x01` never appears
  mid-frame and is a safe delimiter). Byte layout, confirmed against this unit's
  live feed: `[3]` plethysmograph waveform, `[4]` a secondary pulsatile byte,
  `[5]` pulse rate, `[6]` SpO₂ (all low-7-bit); `[1]`/`[2]` are status/flag
  bytes. Frames arrive at ~58 Hz. The same frame serves the live feed and the
  stored-session download (stored samples are spaced 3 s apart).
- **`cms50d+` (fallback)** — the older CMS50D+ protocol. `19200` baud, 8 data
  bits, **odd** parity. Its 5-byte live frame additionally carries the ~60 Hz
  **plethysmograph waveform**; recorded download uses a `0xf5`/`0xf2` handshake
  with 3-byte samples at 1 Hz.

## Caveats

- **Waveform (`pleth`):** byte 3 of the `cms50e` live frame carries the ~58 Hz
  plethysmograph waveform, decoded here into the `pleth` column (0–127). The
  tobac/cms50ew reference instead reads byte 3 as a finger flag (`== 0xC0`);
  on this unit that byte is the waveform, so that test misfires whenever the
  wave passes through 192. This tool derives finger-out from the SpO₂ sentinel
  (127) instead, which is robust. Byte 4 (`pleth2`) also tracks the pulse but
  its exact meaning is unconfirmed — it is preserved rather than interpreted.
- **Pulse rate width:** on the `cms50e` path pulse rate is taken as 7 bits
  (the reference client's behaviour). Rates >127 bpm would need the high bit,
  which is recoverable from the raw frame if your unit encodes it.
- **Finger-out flags:** `finger_out`/`valid` come from SpO₂ = 127. The exact
  status bit for "finger removed" lives in bytes 1–2 (kept as `status1`/
  `status2`); capture a few seconds with the finger out to pin it down if you
  need finger-state detection independent of the SpO₂ reading.
- Frame layouts vary a little across CMS50 firmware. If decoded values look
  wrong, capture a short `<out>.raw` and the exact bytes can be re-examined.

## Files

| File | Role |
|---|---|
| `spo2_core.py` | port detection, serial protocol, frame decoders, capture loop; plus the dashboard's threaded capture, live store, device probe, and session storage |
| `stream_capture.py` | the CLI (`live` / `download` / `ports` / `selftest`) |
| `spo2_analysis.py` | analysis on plain arrays: summary, desaturations/ODI, time-below-threshold, pulse-from-pleth, PRV, average beat, signal quality, windowed ML features |
| `dashboard.py` | the Streamlit session dashboard (device check, capture, analysis, export) |
| `.streamlit/config.toml` | dashboard port (`8503`) |
| `sessions/` | recorded sessions, grouped by subject (created on first recording) |

## Validation

Decoders are verified against the reference clients' documented byte→value
vectors plus a real captured frame, and the live + download + CSV/raw pipeline
was exercised end-to-end against a simulated serial device
(`python stream_capture.py selftest`).

Validated against the physical CMS50E on **2026-08-27**: COM3 auto-detected via
its CP210x id, a 12 s live capture produced ~58 Hz frames with SpO₂ 95–96 %,
pulse 74 bpm, a clean full-scale `pleth` waveform, and 100 % valid samples —
matching what SpO2 Assistant showed.

**This is a research and self-tracking tool, not a diagnostic device.**
