# Study Hub website: change plan (from the Lab 7 report)

Scope: **the website only** (`website/`). Aura Screen issues U1 (report
explainability), U3 (camera error dialog) and U6 (more sign-in options) are out
of scope here.

Edit this file freely: strike items, change wording, answer the questions marked
**Decide**. I will implement exactly what is left.

Order = the report's priority order (severity, then participants affected).

---

## 1. Explain the sample data (U2, severity 3; P1, P3)

*Problem:* the data pages show charts and numbers with no plain-language
explanation; P3 had to ask an AI tool what the data meant.

### 1a. "About this data" panel at the top of each data page
On `/thermal`, `/ecg` and `/rppg`, add a short panel under the title, before the
widgets:
- **What was recorded:** one sentence, e.g. "A chest ECG from a driver, 5 minutes
  covering rest and then city driving."
- **Where it came from:** the public dataset and why it is shown (it stands in
  until the study's own recordings are released).
- **What to look for:** 2–3 bullets, e.g. "Heart rate climbs once city driving
  starts" or "The nose tip cools while drinking a cold drink".
- **How to read the page:** "Each box is one view of the same recording. Hover a
  chart for values; click the overview to move the close-up window."

The text lives in one new file, `src/lib/explanations.ts`, so all copy can be
reviewed in one place.

### 1b. A one-line caption under every chart
`WidgetShell` (`src/components/modality/widget.tsx`) gets a `caption` prop,
shown in readable text under the chart. Each widget states what it shows in
everyday words, e.g. Poincaré plot: "Each dot is one heartbeat interval plotted
against the next. A tighter cloud means a steadier rhythm."
- About 35 captions in total: thermal 7, ECG 14, rPPG 14.
- The existing small grey `note` stays as the technical detail line.

### 1c. A "What this recording shows" takeaway, computed from the data
One plain sentence at the top of each page, built from the JSON rather than
hard-coded:
- ECG: "Heart rate went from **X bpm** at rest to **Y bpm** once city driving
  started."
- Thermal: "The nose cooled by **X °C** while drinking."
- rPPG: "The camera's heart rate stayed within **X bpm** of a fingertip sensor."

This answers T2 ("say in your own words what it shows") directly.

### 1d. Definitions for jargon
A small `Term` component: dotted underline, definition on hover **and**
keyboard focus. It is used for RMSSD, SDNN, pNN50, HRV, LF/HF, SNR, POS, CHROM,
emissivity and similar terms in titles and captions. Definitions go in
`src/lib/explanations.ts`.

**Decide:** keep all of 1a–1d, or only 1a + 1b (the minimum the report promises)?

---

## 2. Make the data easy to find (U4, severity 2; P1, P2, P5)

*Problem:* P5 did not see that "Modalities" was clickable; P2 found the data
section hard to reach.

### 2a. Home page: show every data link at once
In `src/components/ui/vertical-tabs.tsx`, the "Explore the data" link appears
only under the auto-rotating active row, so 3 of 4 links are always hidden.
- Show the link (or "Data coming soon") on **every** row.
- Stop auto-rotation once the user has interacted.

### 2b. Modality cards
Add a row of four cards under the Modalities section (Thermal, ECG, rPPG, EMG).
Each card has:
- the name;
- one line on what it measures;
- what the sample contains;
- an "Explore the data →" button, or "Coming soon".

**Decide:** cards *in addition to* the rotating list, or *replacing* it?

### 2c. Hero call-to-action
Add an "Explore the data" button in the hero (`animated-hero.tsx`) that scrolls
to the modality cards.

### 2d. Nav menu that looks clickable
In `src/components/site-nav.tsx`:
- Rename "Modalities" to **"Data"** (**Decide:** keep "Modalities"?).
- Give the trigger a visible button style: pill background or border, with the
  chevron kept.
- Each item in the dropdown gets its one-line description under the title.

---

## 3. Shorter access form, with an agreement summary (U5, severity 2; P4, P5)

*Problem:* the form is long and the agreement is dense legal text.

### 3a. Fewer fields (`src/components/modality/request-access.tsx`)
Current: 3 steps, 19 fields for a student (16 for staff). Proposal (12 for a
student, 10 for staff):

| Keep | Remove or merge |
|---|---|
| Full name, position, institutional email, institution | Department, country, profile page |
| Supervisor name + email (students only) | Supervisor position |
| Project title, modalities, intended use | Duration (default 12 months, stated in the agreement) |
| Ethics approval (yes / pending / not required) + reference | Team members list: replaced by an agreement clause making the requester responsible for everyone with access |
| Signature (typed name) | Date (filled in automatically) |

- Mark every optional field "(optional)".
- Show "About 3 minutes" on the first step.

**Decide (legal):** confirm that dropping department, country, duration and the
team-members list is acceptable to the PI / ethics committee. The removed items
can return later as "asked on approval".

### 3b. "In short" summary above the agreement
At the agreement step, and on `/data-agreement`, show a five-bullet plain
summary before the full text:
- Research use only, no commercial use.
- No attempt to identify participants.
- Do not share the data onward; colleagues apply separately.
- Cite the study.
- Delete the data when the project ends or on request.

The full 12 clauses move into a collapsed "Read the full agreement" section. A
tick box confirms the user has read it. The summary text goes in
`src/lib/data-agreement.ts`, next to the clauses, so both are reviewed together.

---

## 4. Readability (accessibility check: 2 fails, 2 partial)

- **Faded grey text:** raise `--muted-foreground`, and the `/60` and `/50`
  variants used on inactive menu rows and "Soon" items, to a darker grey in
  `src/app/globals.css`, in both light and dark themes.
- **Chart labels:** darken `--viz-muted` and enlarge axis and label text from
  10–10.5 px to 12 px in `src/components/viz/chart.tsx`.
- **Minimum text size:** replace `text-[9px]`, `text-[10px]` and `text-[11px]`
  site-wide with 12 px (`text-xs`).
- **Check:** look at every page in light and dark mode afterwards. Nothing
  should look faint or need squinting.

---

## 5. Keyboard access for charts (W7, severity 2)

- **5a. Keyboard cursor:** `ChartFrame` (`src/components/viz/chart.tsx`) becomes
  focusable. Left/right arrows move the hover cursor and show the same tooltip;
  Enter does what a click does (e.g. moves the ECG window). This one change
  covers every chart on all three pages.
- **5b. "Show as table":** a toggle on the time-series widgets (heart rate over
  time, region temperatures, rPPG heart-rate track) that shows the numbers as a
  table, one row per second or per beat.

**Decide:** 5a only, or 5a + 5b?

---

## 6. Theme toggle has no name (accessibility: labels)

In `src/components/ui/animated-theme-toggler.tsx`:
- Add an accessible name: "Switch to dark theme" or "Switch to light theme".
- Fix a small bug found while checking: the toggle always starts in "light"
  state, even when the page loads in dark mode. It will read the real theme on
  load.

---

## 7. Say how the two products relate (U7, severity 1; P3)

Website side only:
- One sentence at the start of "Built with the data", e.g. "This site is for
  researchers exploring the study's data. Aura Screen is a separate patient-facing
  app that reuses the same sensing methods: a different audience, a different
  job."
- Change the Aura Screen card's button text to "Open the patient app".

---

## Not in this plan

- Aura Screen changes (U1, U3, U6), per your instruction.
- The rPPG page's data is still synthetic. The UBFC sample download is still
  waiting for your approval. Explanation copy for `/rppg` (item 1) will be
  written so it holds for either source.
- No report changes. I can update the report's improvement plan afterwards if
  you want it to say these items are done.

## How I'll check each item

- Typecheck and lint pass.
- Every page checked in the browser, desktop and mobile width, light and dark.
- Keyboard-only pass: Tab through the nav, cards, widgets and charts; open and
  complete the request form.
- A screenshot of each changed page sent to you.
