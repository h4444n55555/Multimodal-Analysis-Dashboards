// Shapes of the published data files (public/data/<modality>/). The generator
// scripts in website/scripts/ write these; converted study data must match.

export type Subject = { id: string; ageBand: string; sex: string };

export type SessionSummary = {
  id: string;
  subject: Subject;
  label: string;
  durationS: number;
};

export type DataIndex = {
  modality: string;
  source: { kind: "synthetic" | "public" | "study"; note: string };
  sessions: SessionSummary[];
};

export type Phase = { name: string; startS: number; endS: number };

/** Where a published recording comes from — shown on the page for attribution. */
export type DataSource = {
  title: string;
  author: string;
  license: string;
  url: string;
  /** values reconstructed or simulated for display, not measured */
  illustrative?: boolean;
  note?: string;
  /** where the published excerpt starts within the original recording */
  windowStartS?: number;
};

export type SeriesBlock = { fs: number; units: string; values: number[] };

export type ThermalSession = SessionSummary & {
  device: { model: string; sensor: string; emissivity: number };
  source?: DataSource;
  context?: { ambientC: number; humidityPct: number; acclimatisationMin: number; distanceM: number };
  roiValidity: { glasses: boolean; facialHair: boolean; hairOverForehead: boolean };
  phases: Phase[];
  frames: {
    file: string;
    encoding: "uint8";
    count: number;
    width: number;
    height: number;
    fps: number;
    tempMinC: number;
    tempMaxC: number;
  };
  rois: { key: string; label: string; box: [number, number, number, number]; valid: boolean }[];
  series: { rateHz: number; roiMeanC: Record<string, number[]> };
};

export type HrvTime = Partial<{
  beats: number;
  mean_hr_bpm: number;
  min_hr_bpm: number;
  max_hr_bpm: number;
  mean_rr_ms: number;
  sdnn_ms: number;
  rmssd_ms: number;
  pnn50_pct: number;
  artifact_pct: number;
}>;

export type QualityStatus = "good" | "warning" | "critical";

export type EcgSession = SessionSummary & {
  device: { model: string; lead: string; fs: number; units: string };
  source?: DataSource;
  phases: Phase[];
  signal: { fs: number; raw: number[]; filtered: number[] };
  rPeaks: number[];
  rr: { t: number[]; ms: number[]; valid: boolean[] };
  hrv: {
    session: HrvTime;
    phases: Record<string, HrvTime>;
    frequency: Partial<{
      lf_power_ms2: number;
      hf_power_ms2: number;
      lf_hf_ratio: number;
      lf_nu: number;
      hf_nu: number;
      duration_s: number;
    }> & { shortRecord: boolean };
    poincare: { sd1_ms: number; sd2_ms: number; sd1_sd2_ratio: number };
  };
  psd: { freqs: number[]; power: number[] } | null;
  averageBeat: { tMs: number[]; mean: number[]; sd: number[]; n: number };
  quality: Record<string, number> & { status: QualityStatus; message: string };
  qualityWindows: { startS: number; endS: number; status: QualityStatus; message: string }[];
  events: { t: number; kind: string }[];
  /** other signals the dataset recorded alongside the ECG, same window */
  companions?: { resp: SeriesBlock; handGSR: SeriesBlock; footGSR: SeriesBlock; emg: SeriesBlock };
  /** the whole original recording, summarised */
  drive?: {
    stepS: number;
    durationS: number;
    segments: Phase[];
    hr: (number | null)[];
    handGSR: number[];
  };
};

export const dataUrl = (modality: string, file: string) => `/data/${modality}/${file}`;
