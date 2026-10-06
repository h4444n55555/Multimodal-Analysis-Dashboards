// The four modalities the site showcases. Each gets a data page once its
// sample (and later, study) data is published under public/data/<key>/.

export type Modality = {
  key: "thermal" | "ecg" | "emg" | "rppg";
  id: string;
  title: string;
  device: string;
  summary: string;
  /** one short line: what the signal measures, in everyday words */
  measures: string;
  /** null until the modality has a data page */
  href: string | null;
};

export const MODALITIES: Modality[] = [
  {
    key: "thermal",
    id: "01",
    title: "Thermal",
    device: "FLIR C5 · 160 × 120",
    summary: "Per-pixel facial temperature. Stress and arousal show up as heat moving across the face — the nose tip cools, the inner eye corners warm, and every breath warms the skin under the nostrils.",
    measures: "Skin temperature across the face, from a heat camera.",
    href: "/thermal",
  },
  {
    key: "ecg",
    id: "02",
    title: "ECG",
    device: "Frontier X2 · single lead · 125 Hz",
    summary: "The heart's electrical trace, beat by beat. Heart rate and its variability track the balance between the stress and rest branches of the nervous system.",
    measures: "The heart’s electrical signal, beat by beat, from a chest sensor.",
    href: "/ecg",
  },
  {
    key: "emg",
    id: "03",
    title: "EMG",
    device: "Surface EMG array",
    summary: "Surface muscle activity from facial and forearm electrodes — the involuntary micro-contractions that accompany expressions too brief to see on camera.",
    measures: "Tiny muscle movements in the face and forearm, from skin electrodes.",
    href: "/emg",
  },
  {
    key: "rppg",
    id: "04",
    title: "rPPG",
    device: "RGB camera",
    summary: "Contactless pulse recovered from subtle skin-colour changes in ordinary video, checked against the ECG recorded in the same session.",
    measures: "Your pulse from an ordinary camera, with nothing touching the skin.",
    href: "/rppg",
  },
];
