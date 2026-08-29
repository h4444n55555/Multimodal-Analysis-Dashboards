# Multimodal Analysis Dashboards

Capture and analysis dashboards for a multimodal biosignal dataset. Each
physical sensor gets its own folder: a capture pipeline that pulls raw
numerical data straight from the device, plus a Streamlit dashboard for
running a recording session and inspecting the results.

| Folder | Sensor | What it captures |
|---|---|---|
| [`ECG/`](ECG/) | Frontier X2 (via WebSocket share link) | Raw ECG waveform, R-peaks, HR, signal quality |
| [`SpO2/`](SpO2/) | Contec CMS50E pulse oximeter (USB serial) | SpO2, pulse rate, plethysmograph waveform |
| [`Thermal/`](Thermal/) | FLIR C5 thermal camera (USB) | Per-pixel radiometric temperature (stills) + colorized video recording |

Each dashboard runs on its own port so they can run side by side during a
session: Thermal `8501`, ECG `8502`, SpO2 `8503`.

See each folder's own README for setup and usage.
