// External apps the hub links to. The modality data pages live in
// modalities.ts; the Streamlit capture dashboards are no longer linked from
// the site (they remain in the repo for recording and testing).

/** Where data-access requests are sent (the study lead, as listed in the footer). */
export const DATA_REQUEST_EMAIL = "kushagra.25aiz0001@iitrpr.ac.in";

export const HEALTH_SCREENING = {
  name: "Aura Screen",
  url: process.env.NEXT_PUBLIC_HEALTH_SCREENING_URL ?? "http://localhost:5174",
  sourceUrl: "https://github.com/hima1323/health-screening",
};
