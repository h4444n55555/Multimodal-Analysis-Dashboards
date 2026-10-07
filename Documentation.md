# Aura Screen: Initial Project Documentation

**Contactless health pre-screening**
Nongmaithem Hans (2024AIB1011) · Himanshu Patel (2024AIB1007)
CVPR Lab & ACAI Lab, School of AI & Data Engineering, IIT Ropar

---

## 1. Introduction

Aura Screen is a health pre-screening app. A patient signs up, sets up their
health record, and scans a QR code at a screening station. The station then
reads their vital signs **without contact**, using a camera (rPPG) and a
thermal sensor. The patient gets a plain-language report, and readings outside
the normal range are flagged for a nurse check.

It runs on a patient’s phone or on a kiosk at the screening station.

## 2. Problem statement

Pre-screening before a consultation (heart rate, temperature, breathing) is
usually done by hand. This:

- takes staff time and creates queues,
- needs physical contact with every patient, and
- leaves patients with numbers they don’t understand: what a value means,
  whether it is normal, and what happens next.

## 3. Objectives

1. Measure heart rate, body temperature and respiration **without contact**.
2. Keep the patient journey short and simple: sign up → record → scan → report.
3. Explain every result in plain language, with its normal range.
4. Hand off safely to staff: nurse-check alerts and sharing with a doctor.
5. Design for phone and kiosk first.
6. Evaluate with real users and improve from what they find.

## 4. Scope

**In scope**
- Patient accounts, health record and consent
- QR-based connection to a screening station
- Contactless scan and session report
- Nurse-check flag and a vitals timeline across sessions

**Out of scope (for now)**
- Medical diagnosis: Aura Screen screens, it does not diagnose
- Clinical certification and integration with hospital systems
- Blood pressure and SpO₂ (a camera can only estimate them after calibration)

## 5. Users

| User | Needs |
|---|---|
| **Patient** | A quick, private scan and a result they can understand |
| **Nurse / clinic staff** | To see who needs attention, without measuring everyone by hand |
| **Doctor** | The screening results, shared by the patient |

## 6. Requirements

**Functional**
- Sign up and sign in with email and password, or Google.
- Onboarding: health details, consent, optional upload of past reports.
- Scan a station’s QR code; fall back to manual start if the camera is blocked.
- Contactless scan of heart rate, temperature and respiration.
- Report: each reading with its status, normal range and explanation.
- Flag out-of-range readings for a nurse check.
- Show a timeline of past sessions.

**Non-functional**
- **Usable:** a first-time user completes a scan without help.
- **Responsive:** fits phone and kiosk screens without unnecessary scrolling.
- **Accessible:** readable text and contrast, touch targets of at least 44 px.
- **Private:** hashed passwords, token-based sessions, users see only their own
  records.
- **Honest:** results are shown as screening, not diagnosis.

## 7. Design and architecture

    Patient phone / kiosk ──► React app ──► Express API ──► MongoDB
                                  ▲
    Screening station ──QR──┘     │
    (camera + thermal) ── vitals ─┘   rPPG + thermal processing (Python)

| Part | Technology |
|---|---|
| Front end | React, Vite, CSS Modules (container queries for phone and kiosk) |
| Back end | Node.js, Express |
| Database | MongoDB (Mongoose) |
| Authentication | JWT, bcrypt, Google sign-in |
| QR scanning | jsQR in the browser |
| Sensing | rPPG (pulse from camera) and thermal imaging, in Python |

**Main user flow:** Welcome → Sign up → Health record and consent → Scan
station QR → Contactless scan → Session report → Timeline


---

## Side project: MMAC Study Hub

While building Aura Screen, we also help our professor collect data for the
**Multimodal Affective Computing (MMAC) study**, which records thermal, ECG, EMG
and rPPG signals together. We built the study’s website, the **Study Hub**. It
shows sample data from each signal in an interactive dashboard and handles data
access requests.

Technologies: Next.js, React, TypeScript, Tailwind CSS; Python (NumPy, SciPy)
for data processing.

**Repositories**
- Aura Screen: https://github.com/hima1323/health-screening
- MMAC Study Hub: this repository
