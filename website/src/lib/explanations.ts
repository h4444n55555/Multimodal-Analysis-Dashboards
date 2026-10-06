// Plain-language copy for the data pages: what each recording is, what each
// widget shows, and what the jargon means. Kept in one file so it can be
// reviewed and edited without touching the dashboards.

export type ModalityKey = "thermal" | "ecg" | "emg" | "rppg";

/** Short copy for the panel at the top of each dashboard. Fuller recording
 *  specifics live in the details card. */
export type About = {
  /** what this kind of data is, in one or two sentences */
  shows: string;
  /** one line of context: where this sample was recorded, which explains the
   *  phase labels on the charts */
  recorded: string;
  /** what the dashboard below displays */
  dashboard: string;
};

export const ABOUT: Record<ModalityKey, About> = {
  thermal: {
    shows:
      "A thermal camera measures the temperature of every point on the face. Emotion and stress change blood flow, which shows up as small temperature shifts around the nose, eyes and forehead.",
    recorded:
      "This sample was filmed while a person drank a cold glass of juice, hence the Before, Drinking and After labels on the charts.",
    dashboard:
      "The thermal video, the temperature of each face region now and over time, the spread of temperatures across the frame, each region’s range, and quick figures for the frame on screen.",
  },
  ecg: {
    shows:
      "An ECG records the heart’s electrical activity. Each sharp spike is one heartbeat, and the timing between spikes gives the heart rate.",
    recorded:
      "This sample comes from a driver in the Boston area, first parked at rest and then driving through city traffic, hence the Rest and City labels on the charts.",
    dashboard:
      "The raw and cleaned signal, the average heart rate, an overall quality rating, a quality rating for every 5 seconds of the recording, heart rate beat by beat, and the average heartbeat shape.",
  },
  emg: {
    shows:
      "EMG records the tiny electrical signals muscles produce when they contract. Electrodes on the skin pick them up, so even small, involuntary movements show up.",
    recorded:
      "This sample comes from electrodes around a person’s forearm and wrist: first relaxed, then making a fist, hence the Rest and Hand close labels on the charts.",
    dashboard:
      "The raw and cleaned signal from one forearm electrode, how much stronger it gets during the fist, an overall quality rating, muscle activity over time, every electrode’s activity, and the signal’s frequency content.",
  },
  rppg: {
    shows:
      "rPPG measures the pulse with an ordinary camera: every heartbeat changes the skin’s colour very slightly, too little for the eye to see.",
    recorded:
      "This sample is simulated: the head stays still, moves for ten seconds, then is still again, hence the Still and Head motion labels on the charts.",
    dashboard:
      "The face’s colour and the pulse extracted from it, the camera’s heart rate against a fingertip sensor, an overall quality rating, a quality rating for every 5 seconds, and the average pulse shape.",
  },
};

/** Fixed copy for each page's "full details" card. Recording-specific numbers
 *  are computed from the data in each explorer and added alongside. */
export type DetailsCopy = {
  /** what happens in the sample recording */
  recording: string;
  /** how the page turns the raw recording into what is shown */
  processing: string[];
  /** what to keep in mind when reading this sample */
  limits: string[];
};

export const DETAILS: Record<ModalityKey, DetailsCopy> = {
  thermal: {
    recording:
      "A short thermal video of a person drinking a cold glass of juice. The cold drink cools the lips and mouth, which makes it a clear, easy-to-see example of a local temperature change on the face.",
    processing: [
      "Each frame is a grid of temperatures, one per pixel, shown with a colour scale from 22 to 36 °C.",
      "Four face regions (forehead, eyes, nose and mouth) are defined as fixed areas, and the average temperature inside each is tracked over time.",
      "Pixels warmer than 30 °C are counted as face, the rest as room, for the per-frame figures.",
    ],
    limits: [
      "The clip is a public stand-in until the study’s own thermal recordings are released.",
      "The original video stores colours, not temperatures. Temperatures here are rebuilt from the colour palette, so treat exact degrees as approximate; the changes over time are what matter.",
      "The regions stay in fixed positions rather than following facial landmarks, so any head movement shifts what each region covers.",
    ],
  },
  ecg: {
    recording:
      "Five minutes of a driver’s chest ECG from the MIT driver-stress study: the first part parked at rest, the rest driving through a city. Breathing, skin conductance and shoulder muscle activity were recorded at the same time.",
    processing: [
      "Every number comes from the study’s own ECG analysis code, the same code used on study recordings.",
      "The raw signal is filtered to 0.5–40 Hz with a mains-hum notch, and its polarity is checked so beats point upwards.",
      "Each heartbeat (R peak) is located, and the time between beats gives the heart rate. Intervals that are physiologically impossible or far from their neighbours are marked irregular and left out.",
      "Signal quality is rated every 5 seconds: clean, irregular beats, or movement artefact.",
    ],
    limits: [
      "This is a public stand-in until the study’s own ECG recordings are released.",
      "It was recorded with a different device and lead from the study’s chest strap, and resampled to 248 Hz for the web.",
      "Five minutes is short for the slower heart-rate-variability measures, so the excerpt is best read for signal quality and heart rate.",
    ],
  },
  emg: {
    recording:
      "One participant from a public forearm-EMG study: 28 surface electrodes in four rings around the forearm and wrist. Two 5-second recordings, one relaxed and one making a fist, are shown back to back.",
    processing: [
      "Each electrode’s signal is filtered to 20–450 Hz, the standard band for surface EMG, and the mains hum and its harmonics are notched out.",
      "Muscle activity is the signal’s RMS (its typical size) in 100 ms windows; contraction strength is compared with rest in decibels.",
      "Each electrode is checked for a flat signal, for hitting the amplifier’s limit, and for how much of its power is mains hum before filtering.",
      "The frequency content of the contraction is summarised by its median frequency, which drops as a muscle tires.",
    ],
    limits: [
      "This is a public stand-in until the study’s own EMG recordings, which include facial electrodes, are released.",
      "The rest and fist recordings were made separately and are joined only for display, so the step between them is not a real moment in time.",
      "Five seconds per condition is enough to judge signal quality, not to study fatigue or gestures in depth.",
    ],
  },
  rppg: {
    recording:
      "A simulated face colour trace with a known pulse: the head is still, then moves for ten seconds, then is still again.",
    processing: [
      "Each video frame is reduced to one average colour for the face.",
      "The POS method combines the red, green and blue changes so that skin tone and lighting cancel out, leaving the pulse.",
      "Heart rate is the strongest rhythm in the 42–180 bpm range, re-measured over a 10-second window every second.",
      "Signal quality compares the pulse’s strength with everything else in that range. Below the floor, the page reports nothing rather than a guess.",
    ],
    limits: [
      "The sample is simulated, not a recording of a person, so the page can show the method before the study’s own camera recordings are released.",
      "Camera-based pulse is sensitive to movement and lighting; the head-motion stretch shows what that looks like.",
      "Blood pressure and blood oxygen are not shown: a camera can only estimate them after calibration against a real device.",
    ],
  },
};

/** One line under each widget, saying what it shows in everyday words. */
export const CAPTIONS: Record<ModalityKey, Record<string, string>> = {
  thermal: {
    video: "The camera’s view: brighter colours are warmer. Hover to read the temperature at any point.",
    now: "The average temperature inside each box at this moment of the video.",
    hist: "How many pixels sit at each temperature. The left hump is the room, the right one the face.",
    series: "How each face region’s temperature changes through the video. Switch to “Change” to compare them.",
    ranges: "The coolest-to-warmest span of each region over the whole video; the dot is its average.",
    frame: "Quick numbers for the frame on screen: the hottest pixel, the face’s average and how much of the view is face.",
    facts: "The camera and the clip this page is built from.",
  },
  ecg: {
    trace: "The heart’s electrical signal as recorded (top) and after noise is removed (bottom). Each dot is one heartbeat.",
    "hr-now": "Average beats per minute over the whole recording.",
    overview: "The whole recording at a glance. The coloured strip shows how clean the signal is in each 5-second stretch.",
    hr: "Heart rate beat by beat. Hollow dots are irregular beats, left out of the analysis.",
    quality: "Whether the recording is clean enough to trust, and how many beats were left out.",
    beat: "Every heartbeat laid on top of each other and averaged. A narrow band around the line means consistent, clean beats.",
  },
  emg: {
    trace: "One forearm electrode’s signal as recorded (top) and after noise is removed (bottom). The fist turns a quiet line into dense bursts.",
    activation: "How much stronger the muscle signal is while making a fist than at rest.",
    quality: "Whether every electrode is clean: none flat, none overloaded, and little mains hum.",
    envelope: "Muscle activity over time: the signal’s typical size in 100 ms steps, with the 1-second quality strip below.",
    electrodes: "Every electrode around the forearm and wrist, coloured by how much it lights up during the fist. Outlined cells need a check.",
    spectrum: "Which frequencies make up the contraction. A smooth hump with no sharp spikes means clean data.",
  },
  rppg: {
    pulse: "Top: the face’s average green colour, barely changing. Bottom: the pulse extracted from it, with the fingertip sensor dashed.",
    "hr-now": "Heart rate measured by the camera alone, with the fingertip sensor’s value for comparison.",
    overview: "The whole recording at a glance. The strip shows how trustworthy each 5-second stretch is.",
    hr: "The camera’s heart rate (solid) against the fingertip sensor (dashed). Close lines mean an accurate signal.",
    quality: "How strongly the pulse stands out from noise. Below the floor, the page shows nothing rather than a guess.",
    beat: "All pulses averaged into one shape. A clean signal gives a smooth curve that rises quickly and falls slowly.",
  },
};

/** Short definitions shown on hover or keyboard focus. */
export const TERMS: Record<string, string> = {
  RMSSD: "Typical change in time from one heartbeat to the next, in milliseconds. Higher usually means more relaxed.",
  SDNN: "Overall spread of the times between beats, in milliseconds. A broad measure of heart-rate variability.",
  pNN50: "Share of neighbouring beats whose timing differs by more than 50 ms.",
  HRV: "Heart-rate variability: how much the time between heartbeats changes. A healthy, relaxed heart varies more.",
  "LF/HF": "Balance between slow (LF) and breathing-speed (HF) rhythms in heart rate. Often read as stress versus rest.",
  SNR: "Signal-to-noise ratio: how strongly the pulse stands out from everything else, in decibels (dB).",
  POS: "Plane-Orthogonal-to-Skin: a recipe that cancels skin tone and lighting to isolate the pulse.",
  CHROM: "Chrominance method: combines colour differences so that glare on the skin cancels out.",
  Green: "Uses only the green channel, where blood absorbs most light. Simple, but sensitive to glare and movement.",
  "SpO₂": "Blood oxygen saturation: the share of oxygen-carrying blood. A camera can only estimate it after calibration.",
  Perfusion: "How much blood reaches the skin being measured, as the pulsing share of the colour signal.",
  ECG: "Electrocardiogram: the heart’s electrical activity, recorded from electrodes on the chest.",
  rPPG: "Remote photoplethysmography: measuring the pulse from skin-colour changes in ordinary video.",
};
