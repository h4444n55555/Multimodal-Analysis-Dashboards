// The four modalities the site showcases. Each gets a data page once its
// sample (and later, study) data is published under public/data/<key>/.

export type Modality = {
  key: "thermal" | "ecg" | "emg" | "rppg";
  id: string;
  title: string;
  device: string;
  summary: string;
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
    href: "/thermal",
  },
  {
    key: "ecg",
    id: "02",
    title: "ECG",
    device: "Frontier X2 · single lead · 125 Hz",
    summary: "The heart's electrical trace, beat by beat. Heart rate and its variability track the balance between the stress and rest branches of the nervous system.",
    href: "/ecg",
  },
  {
    key: "emg",
    id: "03",
    title: "EMG",
    device: "Surface EMG array",
    summary: "Surface muscle activity from facial and forearm electrodes — the involuntary micro-contractions that accompany expressions too brief to see on camera.",
    href: null,
  },
  {
    key: "rppg",
    id: "04",
    title: "rPPG",
    device: "RGB camera",
    summary: "Contactless pulse recovered from subtle skin-colour changes in ordinary video, checked against the ECG recorded in the same session.",
    href: null,
  },
];
