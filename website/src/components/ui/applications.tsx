"use client";

import { motion } from "motion/react";
import { ArrowUpRight, Stethoscope } from "lucide-react";
import { HEALTH_SCREENING } from "@/lib/links";

// Each application links to its own official home rather than a copy hosted
// alongside this site.
const APPS = [
  {
    name: HEALTH_SCREENING.name,
    kind: "Health Screening",
    icon: Stethoscope,
    description:
      "The patient-facing end of the study: an introduction and consent, a QR-triggered contactless scan at a screening station, and the report and vitals timeline that come out of it.",
    feeds: ["rPPG", "Thermal", "ECG"],
    href: HEALTH_SCREENING.sourceUrl,
    linkLabel: "View on GitHub",
  },
];

export function Applications() {
  return (
    <div className="grid gap-6">
      {APPS.map((app, i) => (
        <motion.article
          key={app.name}
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: i * 0.12, ease: [0.23, 1, 0.32, 1] }}
          className="grid gap-8 rounded-3xl border border-border bg-card p-8 shadow-xl shadow-black/5 md:grid-cols-[1fr_auto] md:items-center md:p-10 dark:shadow-black/40"
        >
          <div>
            <div className="flex items-center gap-4">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-foreground text-background">
                <app.icon className="h-7 w-7" aria-hidden="true" />
              </span>
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">{app.kind}</p>
                <h3 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">{app.name}</h3>
              </div>
            </div>

            <p className="mt-5 max-w-2xl leading-relaxed text-muted-foreground">{app.description}</p>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Uses</span>
              {app.feeds.map((f) => (
                <span key={f} className="rounded-full border border-border bg-background px-2.5 py-0.5 text-xs font-medium">
                  {f}
                </span>
              ))}
            </div>
          </div>

          <a
            href={app.href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 self-start rounded-full bg-foreground px-6 py-3 text-sm font-medium text-background transition-opacity hover:opacity-85 md:self-center"
          >
            {app.linkLabel}
            <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
          </a>
        </motion.article>
      ))}
    </div>
  );
}
