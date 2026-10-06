# Study Hub website: changes implemented

Plan: [website-change-plan.md](website-change-plan.md). Done 6 October 2026.
Items 5 (chart keyboard access) and 6 (theme toggle) were dropped. Aura Screen is
unchanged.

| # | Change | Report issue | Patch |
|---|---|---|---|
| 01 | Explain the sample data | U2 (sev. 3) | `01-explain-the-data.patch` |
| 02 | Make the data easy to find | U4 (sev. 2) | `02-find-the-data.patch` |
| 03 | Shorter access form + agreement summary | U5 (sev. 2) | `03-shorter-access-form.patch` |
| 04 | Readability (faded and tiny text) | Accessibility: text fails | `04-readability.patch` |
| 07 | Say how the two products relate | U7 (sev. 1) | `07-how-the-products-relate.patch` |

Numbers follow the plan, so 05 and 06 are missing on purpose.

**Round 2** (dashboard renovation, from your screenshot review):

| # | Change | Patch |
|---|---|---|
| r2-01 | Remove the "Explore the sample data" cards | `r2-01-remove-sample-cards.patch` |
| r2-02 | General, minimal "About this data" panel | `r2-02-general-about-panel.patch` |
| r2-03 | ECG dashboard: quality views only | `r2-03-ecg-quality-only.patch` |
| r2-04 | rPPG dashboard: quality views only | `r2-04-rppg-quality-only.patch` |
| r2-05 | Remove the "See the … data →" links | `r2-05-remove-bottom-links.patch` |
| r2-06 | Rework "Built with the data" | `r2-06-built-with-the-data.patch` |
| r2-06b | …then drop its grey band and border lines | `r2-06b-no-band.patch` |
| r2-08 | "Full details" link and reading card | `r2-08-details-card.patch` |
| r2-08b | …then made the card wide and two-column so it never scrolls | `r2-08b-details-card-no-scroll.patch` |
| r2-09 | Thermal video: region boxes removed | `r2-09-thermal-no-region-boxes.patch` |
| r2-10 | Fix: nav bar scrolled away on the data-agreement page | `r2-10-agreement-page-nav.patch` |
| r2-11 | About panel: "On this dashboard" + where the sample was recorded | `r2-11-about-panel-context.patch` |
| r2-12 | Research pipeline: no card, general labels, scaled to the page | `r2-12-pipeline-on-page.patch` |
| r2-13 | Footer brought up to date | `r2-13-footer.patch` |
| r2-14 | Pipeline text matched to the section heading and subheading | `r2-14-pipeline-text-size.patch` |
| r2-15 | New EMG dashboard (real GRABMyo sample) | `r2-15-emg-dashboard.patch` |
| r2-15b | EMG source added to `scripts/README.md` | `r2-15b-emg-readme.patch` |

Before/after screenshots for the report are in [screenshots/](screenshots/);
see the end of this file.

## How to revert

Every item is one patch in [website-changes/](website-changes/). From the repo
root (`D:\Multimodal`):

```bash
git apply -R --check docs/evaluation/website-changes/03-shorter-access-form.patch
```

```bash
git apply -R docs/evaluation/website-changes/03-shorter-access-form.patch
```

- The first command only checks; the second reverts.
- **Round 2 rewrote parts of round 1**, so the patches now form a stack. The
  full stack was tested to revert cleanly **newest first**:
  r2-15b → r2-15 → r2-14 → r2-13 → r2-12 → r2-11 → r2-10 → r2-09 → r2-08b →
  r2-06b → r2-08 → r2-06 → r2-05 → r2-04 → r2-03 → r2-02 → r2-01 → 07 → 04 →
  03 → 02 → 01.
- These revert **on their own** from the current state (checked): r2-15b, r2-15,
  r2-14, r2-13, r2-10, r2-09, r2-08b, r2-06b, r2-04 and 03. Others need the
  newer patches that touch the same files reverted first. For example, r2-12
  needs r2-14, and r2-11 needs r2-15. For anything older, run `--check` first; if it fails,
  revert the newer patches that touch the same files. For any other patch, first revert every newer patch that touches
  the same files (see the list above), or run `--check`.
- To bring an item back, run the same command without `-R`.
- Nothing is committed. The changes are ordinary edits in the working tree,
  alongside the earlier, also uncommitted, rPPG page work.
- If you hand-edit a file after this, a patch touching the same lines may stop
  applying. `--check` will say so; revert by hand using the patch as a guide.

**Default chosen** marks decisions I took where the plan left a choice.

---

## 01 · Explain the sample data (U2)

**What a visitor sees**
- **"About this data" panel** at the top of `/thermal`, `/ecg` and `/rppg`. It
  says what was recorded, where the sample comes from and why it stands in for
  study data, three things to look for, and how to read the page.
- **Takeaway sentence, computed from the data** (not typed in, so it stays right
  if the data changes):
  - Thermal: "The **mouth** cooled by **1.3 °C** while drinking, then warmed
    back up."
  - ECG: "Heart rate went from **66 bpm** at rest to **90 bpm** during city
    driving."
  - rPPG: "…the camera’s heart rate stayed within **0.2 bpm** of a fingertip
    sensor on average (71.8 vs 71.8 bpm)."
- **A plain caption under every widget**, 35 in total (thermal 7, ECG 14,
  rPPG 14), shown in full.
- **Jargon definitions** on hover or keyboard focus (dotted underline): RMSSD,
  SDNN, pNN50, LF/HF on ECG; RMSSD, SDNN, SNR, SpO₂ on rPPG.

**Files**
- New: `src/lib/explanations.ts` holds **all wording** (panel text, captions,
  definitions). Edit copy here only.
- New: `src/components/modality/explain.tsx` (`AboutData`, `Term`).
- `src/components/modality/widget.tsx`: `WidgetShell` gets a `caption` prop;
  `Facts` labels accept rich content.
- `src/components/modality/{thermal,ecg,rppg}-explorer.tsx`: the panel, the
  takeaway function and the caption wrapper.

**Default chosen:** all of 1a–1d.

**Checked**
- Copy claims were checked against the ECG data: RMSSD halves (63 → 31 ms);
  skin conductance and shoulder EMG both jump when city driving starts.
- The rPPG takeaway compares second-by-second averages on both sides. Mixing in
  the whole-recording peak made it read "within 0.2 bpm (75 vs 72)", which looked
  contradictory.

**Partial revert:** remove the `<AboutData … />` line from an explorer to drop
the panel there, or empty a modality's entry in `CAPTIONS` to drop its captions.

**Note:** the rPPG copy says the sample is simulated. If the UBFC sample is
added later, update `ABOUT.rppg` in `explanations.ts`.

## 02 · Make the data easy to find (U4)

**What a visitor sees**
- **Hero:** a new "Explore the data ↓" button that scrolls to the data cards.
- **Rotating Modalities list:** every row now shows its "Explore the … data"
  link. Before, only the auto-rotating active row did, so 3 of 4 links were
  always hidden. Rotation stops once the visitor clicks a row.
- **Data cards (new):** below the rotating list, one card per modality with
  what it measures, what the sample contains and an "Explore the data" button,
  or "Coming soon" for EMG.
- **Nav:** "Modalities" is renamed **"Data"** and styled as a pill button with a
  chevron so it reads as clickable. Each dropdown item shows a one-line
  description.
- **Footer:** "Modalities" becomes "All data" (→ the cards), and an **rPPG data**
  link is added; it was missing.

**Files:** `src/components/ui/animated-hero.tsx`, `vertical-tabs.tsx`,
`modality-cards.tsx` (new), `footer-section.tsx`; `src/components/site-nav.tsx`;
`src/app/(home)/page.tsx`; `src/lib/modalities.ts` (new `measures` and `sample`
lines per modality).

**Default chosen:** cards **alongside** the rotating list, not replacing it;
menu renamed to **"Data"**.

**Partial revert:** to keep the name "Modalities", change `label: "Data"` back in
`site-nav.tsx`. To drop the cards, remove `<ModalityCards />` from
`(home)/page.tsx`; the hero button and the footer's "All data" link then point
to `#data`, so change them to `#sensors`.

**Note:** the rPPG card says "75 s of face colour…", which describes the current
synthetic sample.

## 03 · Shorter access form + agreement summary (U5)

**What a visitor sees**
- **Fewer fields:** 19 → 12 for students, 16 → 10 for staff. Removed:
  - department, country, profile page;
  - supervisor's position;
  - access duration (now fixed at 12 months, renewable, stated in the
    agreement);
  - the "everyone who will handle the data" list (replaced by a clause, below);
  - the separate date box (the date now appears in the signature label and the
    email).
- "Approval reference" says "(optional)" unless ethics is approved. The form
  says "Takes about 3 minutes".
- **Agreement step:** an **"In short"** box with 5 plain bullets comes first. The
  12 clauses sit under "Read the full agreement", collapsed, with a link to print
  them. The tick box now reads "I have read the full agreement and accept all
  12 terms."
- **`/data-agreement` page:** the same "In short" box above the clauses.
- **Fix:** the date used the UTC day, so it could be a day early in India late at
  night. It now uses the local date.

**Agreement text: now v1.1** (`src/lib/data-agreement.ts`)
- Clause 3: "colleagues … not named in this request" becomes "anyone else who
  needs the data applies separately".
- Clause 5: access is limited to "people working on the approved project", and
  the requester is responsible for everyone they give access to. This replaces
  the named-people list.
- Clause 9: adds "Access lasts 12 months from approval and can be renewed on
  request."
- New `SUMMARY` (the 5 bullets) and `ACCESS_PERIOD`; `DURATIONS` removed.

**Files:** `src/components/modality/request-access.tsx`,
`src/lib/data-agreement.ts`, `src/app/data-agreement/page.tsx`.

**Default chosen — needs sign-off:** removing department, country, duration and
the team list, and the clause wording above, should be confirmed by the PI /
ethics committee. The agreement was already marked DRAFT for legal review.
Reverting patch 03 restores v1.0 and every removed field.

## 04 · Readability (accessibility check)

**What changed**
- **Grey text darker:** `--muted-foreground` light `oklch(0.556)` → `oklch(0.47)`,
  dark `oklch(0.708)` → `oklch(0.76)`. This is the grey used for notes, captions,
  inactive menu items and card text, site-wide.
- **Chart labels darker:** `--viz-muted` light `#898781` → `#67655f`, dark
  `#898781` → `#a6a49c`.
- **No faded variants:** `text-muted-foreground/50`, `/60` and `/70` → full
  `text-muted-foreground`. This affects inactive rows of the rotating list,
  "soon" items and the drag grips.
- **Minimum text 12 px:** every `text-[9px]`, `[10px]` and `[11px]`, and every
  SVG `fontSize` of 9–11, became 12 px. This covers chart axes, labels, badges and
  small headings.
- **Pipeline diagram:** its own faint greys (`--pv-text-3`, `--pv-text-4`, and
  the header and message lines) were raised. Its smallest SVG labels went 9.5 →
  11 px and 10.5 → 11.5 px; it still fits its boxes.

**Files:** `src/app/globals.css`, `src/components/viz/chart.tsx`, the three
explorers, `kit.tsx`, `widget.tsx`, `site-nav.tsx`, and in `src/components/ui/`:
`applications.tsx`, `pipeline-visualization.tsx`, `task-bento.tsx`,
`vertical-tabs.tsx`.

**Checked:** home and ECG pages in light and dark mode. Labels are readable and
nothing overlaps.

**Partial revert:** the colour changes are the 8 token lines in `globals.css`;
change those back to undo just the colours and keep the larger text.

## 07 · Say how the two products relate (U7)

- **"Built with the data"** intro now says: "This site is for researchers
  exploring the study's data. The tools below are separate apps for other people,
  such as patients, that reuse the same sensing methods: a different audience and
  a different job. Each one opens in a new tab."
- Aura Screen card button: "Open app" → **"Open the patient app"**.

**Files:** `src/app/(home)/page.tsx`, `src/components/ui/applications.tsx`.

---

## Checks run for every item (round 1)

- `tsc --noEmit` and `eslint` pass.
- Each page was viewed in the browser, with no console errors. The only console
  messages are "connection refused" from the Aura Screen card checking whether
  that app is running; it isn't. That check was removed in r2-06.
- Each patch revert was checked individually against the round 1 tree.

---

# Round 2 · Dashboard renovation

Done 6 October 2026, from your screenshot review. Goal: each dashboard shows a
little easy-to-read information about **how clean the data is**; everything
specific to the sample recording moves into a separate reading card.

## r2-01 · Remove the "Explore the sample data" cards

- The four modality cards under the rotating Modalities list are gone
  (`modality-cards.tsx` deleted). The rotating list still has a link on every
  row, from change 02.
- The hero "Explore the data" button and the footer's "All data" link now point
  to the Modalities section (`#sensors`); `#data` no longer exists.
- The unused `sample` line per modality was removed from `src/lib/modalities.ts`.
- The patch also restores `modality-cards.tsx` on revert.

## r2-02 · General, minimal "About this data" panel

- The panel no longer describes the sample. On each page it says, in a sentence
  or two, **what this kind of data is**, then gives three short tips on **what
  clean data looks like**. One line explains how to use the page.
- Removed from the panel: the computed takeaway (e.g. "mouth cooled by 1.3 °C"),
  the "what was recorded" and "where it comes from" text, and the
  sample-specific tips. They now live in the details card (r2-08).
- The "Showing <dataset> — <authors> · <licence>" line under each page title is
  gone too; the credit is now in the details card. The small "Public sample"
  badge stays.
- **Files:** `src/lib/explanations.ts` (`ABOUT` now has `shows` and `lookFor`),
  `src/components/modality/explain.tsx`, and the three explorers.

## r2-03 · ECG: quality views only

- **Kept (6):** Raw → cleaned, Heart rate, Signal quality, This excerpt (with
  the 5-second quality strip), Heart rate over time (irregular beats shown
  hollow), Average beat.
- **Removed (8):** Variability, The whole drive, Respiration, Skin conductance,
  Shoulder EMG, Beat-to-beat map, Rhythm spectrum, Recording (its facts moved to
  the details card).
- **Default chosen:** "Heart rate over time" was a maybe. I kept it because it
  shows which beats were rejected, which is quality information, and it
  completes the grid with no gaps.
- Captions for the kept widgets are reworded to be general (no "five minutes" or
  "city driving").
- **Note:** the charts still mark this recording's own events ("City driving
  starts", the REST/CITY bands), because they are part of the data rather than
  explanatory text. Say if you want those hidden too.

## r2-04 · rPPG: quality views only

- **Kept (6):** Face colour → pulse, Heart rate (camera vs fingertip sensor),
  Signal quality, This recording (quality strip), Heart rate over time (camera vs
  sensor), Average pulse.
- **Removed (8):** Breathing, Three methods compared, Variability, Raw face
  colour, Pulse per colour, Pulse spectrum, Calibrated-only measures, Recording.
- **Default chosen:** with the methods comparison gone, the POS / CHROM / Green
  switch was removed and the page uses **POS only**, the cleanest method on this
  data. The other two waveforms are still in the data file.

## r2-05 · Remove the "See the … data →" links

- Removed from the bottom of all three dashboards. The modality pills at the top
  of each page already link between them.

## r2-06 · Rework "Built with the data"

- **Stands out more:** an "APPLICATIONS" eyebrow, a larger heading, and each app
  as a wide, prominent card with a bigger icon and title.
- **r2-06b (follow-up):** the first version also put the section on a grey
  full-width band with border lines. You found that out of place, so it was
  removed; the card went back to the card colour so it still stands out against
  the page.
- **"More on the way" placeholder removed.**
- **Links go to the app's official home**, not a locally hosted copy. For Aura
  Screen that is the GitHub repo, with the button labelled "View on GitHub". The
  separate "Source" link, the "Not running" status dot and its background check
  are gone, along with the console errors that check caused.
- **Default chosen:** the intro is shortened to "Tools that put the study's
  sensing methods to work for people beyond researchers. Each one links to its
  official home." This replaces the change-07 wording.
- **Not changed:** `start-hub.ps1` still starts Aura Screen locally for
  development. `status-dot.tsx` and `use-reachable.ts` are now unused but kept.
- **Files:** `src/app/(home)/page.tsx`, `src/components/ui/applications.tsx`.

## r2-08 · "Full details" link and reading card

- Each dashboard has a visible text link, **"Read the full details about this
  <modality> data →"**, placed **before** the Request access card, as you asked.
  It is styled as text, not a button.
- It opens a large reading card (up to 768 px wide, about 68 characters per line,
  16 px text, scrolls if long) with five sections:
  1. **This recording:** what happens in the sample, plus a sentence computed
     from the data (e.g. "Heart rate went from 66 bpm at rest to 90 bpm during
     city driving, and beat-to-beat variation fell from 63 to 31 ms.").
  2. **Where it comes from:** dataset title (linked), authors and licence. This
     is now the attribution required by the ECG licence (ODC-By).
  3. **Recording details:** the facts the removed "Recording" widgets used to
     show, plus a few more.
  4. **How the page processes it.**
  5. **Keep in mind:** stand-in data, approximate thermal degrees, simulated
     rPPG, and so on.
- All fixed wording is in `DETAILS` in `src/lib/explanations.ts`.
- **Files:** new `src/components/modality/details.tsx`;
  `src/lib/explanations.ts`; the three explorers.

## r2-08b · Details card fits without scrolling

- You found scrolling the card added cognitive load. It is now much larger (up to
  1152 px wide) with **two columns**: the recording, its source and details on
  the left; processing and caveats on the right. Text is 15 px.
- Measured with the browser on all three pages: **no scrolling at 1295×827 (your
  screen), 1440×900 or 1280×720**. On screens shorter than 780 px the text tightens
  slightly so it still fits; on very small screens the card can still scroll as a
  fallback.
- To fit, two rPPG lines were tightened: the "simulated" note moved into "Keep in
  mind", and the cvpr-lab bullet became the "Pipeline" detail row.

## r2-09 · Thermal: region boxes removed

- The coloured boxes drawn over the thermal video are gone. The video caption now
  says "Hover to read the temperature at any point". The details-card wording
  says "regions" instead of "boxes".
- The region lines in "Regions over time" and the other region widgets are
  unchanged.

## r2-10 · Fix: nav bar on the data-agreement page

- **Bug:** on `/data-agreement` the nav bar scrolled away. It was wrapped in a
  `<div class="print:hidden">`; a sticky element only sticks within its parent,
  and that wrapper was only as tall as the nav itself.
- **Fix:** the wrapper is removed and the nav hides itself when printing
  (`print:hidden` on the `<header>` in `site-nav.tsx`), so printing the agreement
  still leaves the nav out. No other page wrapped the nav.

## r2-11 · About panel: what the dashboard shows + where it was recorded

- "What to look for" is gone. The panel now has:
  - **About this data:** what the data is, plus a short line on **where this
    sample was recorded**. This gives context for the phase labels on the charts:
    - ECG: a driver in the Boston area, parked at rest then in city traffic
      (Rest / City).
    - Thermal: a person drinking a cold glass of juice (Before / Drinking /
      After).
    - rPPG: simulated, still then head motion (Still / Head motion).
  - **On this dashboard:** one sentence listing what the dashboard displays.
- The "Hover a chart…" hint line was dropped; "Drag widgets by their title to
  rearrange" is still above each grid.

## r2-12 · Research pipeline on the page

- **No card:** the bordered, shaded box is gone. The diagram sits directly on
  the page and scales to the section's full width (about 1.6× larger at 1440 px).
  The header, subject counter and status line are plain text above and below
  it, enlarged to match.
- **General labels:** the sensor boxes say just **Thermal, ECG, EMG, rPPG**, with
  no device names (FLIR C5, Frontier X2, sEMG Array, Camera rPPG). The fusion box
  says **"Fusion · All signals combined"** instead of "Fusion model ·
  Cross-Modal Encoder". Status messages no longer mention embeddings or a
  cross-modal encoder.
- **Still distinct from the background:** box borders are 1 px instead of 0.5 px
  and brighter (`--pv-*-border` in `globals.css`); task text is brighter; the
  connecting lines are about 2.5× more opaque.
- **Files:** `src/components/ui/pipeline-visualization.tsx`,
  `src/app/globals.css` (pipeline tokens only).

## r2-13 · Footer brought up to date

- Renamed from "Multimodal Biosensing" to **Multimodal Affective Computing
  Study**, matching the hero, with a one-line description.
- Four columns:
  - **Data:** Thermal / ECG / rPPG data and the data use agreement. These links
    come from the modality list, so EMG appears once it has a page.
  - **Explore:** the home sections, in nav order.
  - **Contact:** the people, plus the **data requests** email.
- Copyright line: "Multimodal Affective Computing (MMAC) Study · CVPR Lab &
  ACAI Lab, IIT Ropar".
- **File:** `src/components/ui/footer-section.tsx`.

## r2-14 · Pipeline text matched to the heading and subheading

- The diagram scales with the page (×1.6), which had made its labels larger than
  the section heading. Its font sizes are now set so they render at the page's
  own sizes:
  - box titles: about 16 px, semibold;
  - task labels: about 15 px;
  - captions: about 14 px;
  - eyebrows: about 12 px.
- All diagram text now uses the site's font instead of `system-ui` and
  monospace.
- The surrounding labels use the subheading style (16 px, muted, sentence case)
  instead of uppercase monospace: "Multimodal pipeline · live", "subjects
  recorded", and the status line. The count is semibold at the heading's size.

## r2-15 · EMG dashboard

- **New page `/emg`**, built like the other three: an About panel; six
  quality-focused widgets; the "Read the full details" card; Request access.
  EMG is now linked everywhere the other modalities are: the nav "Data" menu,
  the modality pills, the rotating Modalities list, and the footer (automatic).
  The hero now says sample data is available for all four.
- **Sample: real, open data.** From [GRABMyo](https://physionet.org/content/grabmyo/1.1.0/)
  on PhysioNet (CC BY 4.0), session 1, participant 1: one 5-second rest
  recording and one 5-second "hand close" (fist) recording, from 28 surface
  electrodes in four rings around the forearm and wrist, sampled at 2048 Hz.
  Only these two trials were downloaded (2 × 640 KB, in
  `scripts/sources/grabmyo/`). The details card credits the dataset and both
  papers.
- **Processing** (`scripts/emg/make_showcase.py`, numpy/scipy):
  - 20–450 Hz band-pass filter;
  - mains notch at 50 Hz and its harmonics (the 50 Hz is detected from the data);
  - RMS envelope in 100 ms windows;
  - fist-vs-rest ratio per electrode;
  - per-electrode checks for flat signal, amplifier overload and mains-hum
    share;
  - 1-second quality windows;
  - the contraction's spectrum, with its median frequency.
- **Widgets:**
  1. Raw → cleaned (electrode F12, the strongest forearm response).
  2. Activation: 5.4× stronger in the fist, 15 → 78 µV.
  3. Signal quality: Good, 28 of 28 electrodes clean, mains hum 6%.
  4. Muscle activity over time, with the quality strip.
  5. All electrodes: a colour map by ring, with outlines for any that need a
     check.
  6. Frequency content: median 90 Hz, no mains spikes.
- **Honesty:** the rest and fist recordings were made separately. Both the panel
  and the details card say they are shown back to back, and that the step
  between them is not a real moment in time.
- The access-form description of the EMG release is updated (it no longer says
  "not yet released").
- **Default chosen:** I used 2 trials from one participant, rest and fist, as
  the "one sample", so the page can show activity against a quiet baseline.

## Checks run (round 2)

- `tsc --noEmit` and `eslint` pass after every change.
- All pages captured in the browser (Edge, dark theme, 1440 px) and reviewed.
- The full patch stack was tested to revert cleanly newest-first in a scratch
  index; the real working tree was not touched.

## Screenshots

In [screenshots/](screenshots/). All are dark theme at 1440 px, made with
`screenshots/capture.py` (`python docs/evaluation/screenshots/capture.py after
<ids>` re-shoots). Before = state before round 2.

| Change | Before | After |
|---|---|---|
| r2-01 Sample cards removed | `01-home-sample-cards-before.png` | `01-home-sample-cards-after.png` |
| r2-02 General about panel | `02-{thermal,ecg,rppg}-top-before.png` | `02-{thermal,ecg,rppg}-top-after.png` |
| r2-03 ECG dashboard | `03-ecg-dashboard-before.png` | `03-ecg-dashboard-after.png` |
| r2-04 rPPG dashboard | `04-rppg-dashboard-before.png` | `04-rppg-dashboard-after.png` |
| r2-05 + r2-08 Page bottom | `05-dashboard-bottom-before.png` | `05-dashboard-bottom-after.png` |
| r2-06 Built with the data | `06-built-with-the-data-before.png` | `06-built-with-the-data-after.png` |
| r2-08 Details card | (did not exist) | `08-{thermal,ecg,rppg}-details-card-after.png` |
| r2-09 Thermal region boxes | `09-thermal-video-before.png` | `09-thermal-video-after.png` |
| r2-10 Agreement page nav (scrolled) | `10-data-agreement-scrolled-before.png` | `10-data-agreement-scrolled-after.png` |
| r2-12 Research pipeline | `11-research-pipeline-before.png` | `11-research-pipeline-after.png` |
| r2-13 Footer | `12-footer-before.png` | `12-footer-after.png` |
| r2-14 Pipeline text | `14-pipeline-text-before.png` (after r2-12, before r2-14) | `14-pipeline-text-after.png` |
| r2-15 EMG: modality pills | `13-modality-pills-before.png` | `13-modality-pills-after.png` |
| r2-15 EMG: Modalities list | `13-emg-modalities-row-before.png` | `13-emg-modalities-row-after.png` |
| r2-15 EMG dashboard | (page did not exist) | `13-emg-dashboard-after.png` |
| r2-15 EMG details card | (did not exist) | `13-emg-details-card-after.png` |

**Every "after" shot (round 1 and round 2) was re-taken from the final site on
6 October**, so each one shows the finished state. For example, the pills show
EMG as live, and the footer has its EMG link.

The `14-pipeline-text-before.png` shot was recreated the same way as the round
1 "before" shots: r2-15b, r2-15 and r2-14 were reverted, the shot taken, and the
patches re-applied. The source, scripts and data were then confirmed identical to
a snapshot.

Follow-up tweaks to my own changes (r2-06b, r2-08b, r2-11) have no separate
"before". Their pairs compare the original site with the final result, which is
what the report needs. The intermediate versions can be recreated the same way
if you want them.

### Round 1 screenshots

Made with `screenshots/capture_r1.py`. "Before" is the site before any Lab 7
change. To recreate it, every patch was reverted newest-first, the shots taken,
and every patch re-applied; the files were then confirmed byte-identical to a
snapshot taken just before. "After" is the current site, so it also reflects
round 2 (e.g. the "Built with the data" card).

| Change | Before | After |
|---|---|---|
| 01 Explanations (whole ECG page) | `r1-01-ecg-page-before.png` | `r1-01-ecg-page-after.png` |
| 02 Hero button | `r1-02-hero-before.png` | `r1-02-hero-after.png` |
| 02 Nav "Data" menu (open) | `r1-02-nav-data-menu-before.png` | `r1-02-nav-data-menu-after.png` |
| 02 Rotating Modalities list | `r1-02-modalities-list-before.png` | `r1-02-modalities-list-after.png` |
| 02 Footer links | `r1-02-footer-before.png` | `r1-02-footer-after.png` |
| 03 Access form, step 1 | `r1-03-access-form-step1-before.png` | `r1-03-access-form-step1-after.png` |
| 03 Access form, agreement step | `r1-03-access-form-agreement-step-before.png` | `r1-03-access-form-agreement-step-after.png` |
| 03 Agreement page | `r1-03-data-agreement-page-before.png` | `r1-03-data-agreement-page-after.png` |
| 04 Pipeline diagram text | `r1-04-pipeline-diagram-before.png` | `r1-04-pipeline-diagram-after.png` |
| 04 Chart labels | `r1-04-chart-labels-before.png` | `r1-04-chart-labels-after.png` |
| 07 Built with the data | `r1-07-built-with-the-data-before.png` | `r1-07-built-with-the-data-after.png` |

The access-form shots use placeholder test values (Jane Doe); the form was
never submitted.

"After" shots will be replaced if you ask for further changes, once you confirm
you're happy with them. "Before" shots stay as they are.
