# MMAC Study Hub

The website for the **Multimodal Affective Computing (MMAC) study** at IIT
Ropar. The study looks at how brief, involuntary facial and body signals reveal
emotional and cognitive state, recording four signals together:

| Signal | What it measures |
|---|---|
| **Thermal** | Skin temperature across the face, from a heat camera |
| **ECG** | The heart’s electrical activity, beat by beat |
| **EMG** | Small muscle movements, from electrodes on the skin |
| **rPPG** | The pulse, from an ordinary camera, with nothing touching the skin |

The Study Hub introduces the study, shows sample data from each signal in an
interactive dashboard, and handles requests to access the full dataset.

> We built this alongside our main project, **Aura Screen**, while helping our
> professor collect data for the study. See *Related project* below.

---

## Problem statement

Researchers outside the team need to see what the study’s data looks like, and
how clean it is, before asking to use it. The study also needs to control who
receives the data. The first versions fell short:

- Each signal had its own separate recording dashboard. They often failed to
  launch and showed numbers without explaining what they meant.
- The data was offered as open downloads, with no terms of use.
- Visitors struggled to find the data, and to understand it once they did.

---

## Objectives

1. **One dashboard per signal,** focused on how clean the recording is, with
   plain-language explanations of every chart.
2. **Easy to find:** every data page reachable from the home page and the
   navigation.
3. **Controlled access:** a short request form and a data use agreement
   instead of open downloads.
4. **Readable and accessible** in both light and dark themes.
5. **Tested with users,** with every change documented and reversible.

---

## Team

| Name | Entry number |
|---|---|
| Nongmaithem Hans | 2024AIB1011 |
| Himanshu Patel | 2024AIB1007 |

CVPR Lab & ACAI Lab, School of AI & Data Engineering, IIT Ropar.

---

## Technologies used

| Part | Technologies |
|---|---|
| Website | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI, Motion |
| Charts | Custom SVG chart components |
| Data processing | Python, NumPy, SciPy (filtering, beat detection, heart-rate variability, EMG analysis) |
| rPPG pipeline | Python, PyTorch, OpenCV |
| Sensor capture | Python, Streamlit (FLIR C5 thermal camera, Frontier X2 ECG) |

Until the study’s own recordings are released, the dashboards show samples
from open datasets: PhysioNet *drivedb* (ECG), PhysioNet *GRABMyo* (EMG) and a
public-domain thermal video from Wikimedia Commons.

---

## Related project: Aura Screen

Our main project is **Aura Screen**, a contactless health pre-screening app.
Patients scan a QR code at a screening station and get a plain-language
report of their vital signs, read by camera and thermal sensing.

**Repository:** https://github.com/hima1323/health-screening
