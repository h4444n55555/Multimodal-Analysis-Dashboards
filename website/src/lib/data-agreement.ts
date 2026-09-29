// The MMAC Data Use Agreement and the request-form options, in one place so
// the form, the emailed request and the /data-agreement page stay in sync.
//
// DRAFT — modelled on established dataset agreements (VIPL-HR-V2, PhysioNet
// Credentialed Health Data License 1.5.0, DEAP, MAHNOB-HCI). Have IIT Ropar's
// ethics committee / legal office review it before real data is shared.

export const AGREEMENT_VERSION = "1.0";
export const AGREEMENT_TITLE = "MMAC Study Data Use Agreement";

export type Clause = { title: string; text: string };

export const CLAUSES: Clause[] = [
  {
    title: "Research use only",
    text: "The data will be used solely for lawful, non-commercial academic research and teaching. It will not be used in any product, service or commercial activity, or to make decisions about any individual.",
  },
  {
    title: "No re-identification",
    text: "I will not attempt to identify any participant, including by linking the data with other information. If I come across anything that could identify a participant, I will stop using it and report it to the study team promptly.",
  },
  {
    title: "No redistribution",
    text: "I will not share, publish, sell or pass on the data or any copy of it — including to colleagues in my own institution who are not named in this request. I will not upload it to public repositories, shared cloud folders, or online tools and AI services that keep or learn from uploaded data.",
  },
  {
    title: "Faces and images",
    text: "Thermal and video recordings show participants' faces. Frames or clips may appear only in scientific papers and technical reports, only where needed to illustrate a method, and only from participants marked as consenting to publication. They will never appear in news media, advertising, social media or commercial material.",
  },
  {
    title: "Secure storage",
    text: "I will keep the data on secure, access-controlled systems, limit access to the people named in this request, and protect it with appropriate technical measures such as encryption.",
  },
  {
    title: "Ethics and law",
    text: "My use will follow my institution's ethics requirements and applicable data-protection law, including India's Digital Personal Data Protection Act, 2023 and, where they apply to me, the GDPR or HIPAA.",
  },
  {
    title: "Derived data and models",
    text: "Results may be published in aggregate. I will not release derived data, features or trained models from which a participant's identity or face could be recovered.",
  },
  {
    title: "Citation",
    text: "All publications and reports using the data will acknowledge the MMAC study and cite its reference publication, and I will let the study team know about them.",
  },
  {
    title: "Retention and deletion",
    text: "I will delete all copies of the data when the approved access period ends, when my project ends, or when the study team asks — whichever comes first — and confirm the deletion in writing.",
  },
  {
    title: "No warranty",
    text: "The data is provided as is, without any warranty. The study team and IIT Ropar are not liable for any consequence of its use.",
  },
  {
    title: "Breach and termination",
    text: "If these terms are broken, access will be withdrawn immediately and all copies must be deleted. Access can also be withdrawn at any time by the study team. My obligations under this agreement continue after access ends.",
  },
  {
    title: "Changes to these terms",
    text: "The study team may update this agreement and will notify me first. I may decline the new terms, in which case my access ends and I must delete the data.",
  },
];

export const POSITIONS = [
  "Faculty / Professor",
  "Postdoctoral researcher",
  "Research staff / engineer",
  "PhD student",
  "Master's student",
  "Undergraduate student",
  "Other",
] as const;

/** Students must name a supervisor, who is copied on the request and co-signs. */
export const STUDENT_POSITIONS = new Set<string>(["PhD student", "Master's student", "Undergraduate student"]);

export const ETHICS_OPTIONS = [
  "Approved by my institution's ethics board",
  "Submitted, awaiting approval",
  "Not required at my institution for this use",
] as const;

export const DURATIONS = ["6 months", "12 months", "24 months"] as const;

/** What each modality's release contains, shown in the form. */
export const MODALITY_CONTENTS: Record<string, string> = {
  thermal: "Facial thermal video (°C per pixel), face-region time series, recording conditions",
  ecg: "Raw and filtered single-lead ECG, detected beats and intervals, HRV and signal quality",
  emg: "Surface EMG recordings — not yet released",
  rppg: "Face video for remote pulse, with reference ECG — not yet released",
};

/** Personal webmail — institutional addresses are asked for instead. */
export const PERSONAL_EMAIL = /@(gmail|googlemail|yahoo|ymail|outlook|hotmail|live|icloud|me|aol|proton|protonmail|163|126|qq|rediffmail|zoho)\./i;
