# MMAC study hub — website

Next.js 16 (App Router) site for the multimodal biosensing study: the landing
page plus interactive sample-data pages for thermal, ECG, EMG and rPPG.
Everything is static — no database or server-side secrets.

## Develop

```bash
npm install
npm run dev      # http://localhost:3000
npm run lint
npm run build    # production build, as Vercel runs it
```

Node 20.9+ is required.

## Deploy on Vercel

The site lives in the `website/` folder of the repo, so when importing the
repository set **Root Directory** to `website`. Vercel detects Next.js and
needs no other settings (build `next build`, no environment variables).

Optional environment variable:

| Name | Purpose |
|---|---|
| `NEXT_PUBLIC_HEALTH_SCREENING_URL` | Where the Aura Screen app is hosted (defaults to `http://localhost:5174`) |

## Data

The modality pages read static files from `public/data/`. See
[scripts/README.md](scripts/README.md) for where the sample data comes from and
how to regenerate it (`scripts/sources/` holds the raw originals and is excluded
from Vercel uploads via `.vercelignore`).
