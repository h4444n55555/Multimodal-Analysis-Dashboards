"use client";

import { motion } from "motion/react";
import { ArrowUpRight, Code2, Plus, Stethoscope } from "lucide-react";
import { HEALTH_SCREENING } from "@/lib/links";
import { StatusDot } from "@/components/ui/status-dot";

const APPS = [
  {
    name: HEALTH_SCREENING.name,
    kind: "Health Screening",
    icon: Stethoscope,
    description:
      "The patient-facing end of the study: an introduction and consent, a QR-triggered contactless scan at a screening station, and the report and vitals timeline that come out of it.",
    feeds: ["rPPG", "Thermal", "ECG"],
    url: HEALTH_SCREENING.url,
    sourceUrl: HEALTH_SCREENING.sourceUrl,
  },
];

export function Applications() {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {APPS.map((app, i) => (
        <motion.div
          key={app.name}
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: i * 0.12, ease: [0.23, 1, 0.32, 1] }}
          className="flex flex-col rounded-2xl border border-black/15 bg-card p-6 dark:border-white/[0.12]"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-background">
                <app.icon className="h-5 w-5 text-foreground" />
              </span>
              <div>
                <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  {app.kind}
                </p>
                <h3 className="text-lg font-medium tracking-tight text-foreground">
                  {app.name}
                </h3>
              </div>
            </div>
            <StatusDot url={app.url} />
          </div>

          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            {app.description}
          </p>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {app.feeds.map((f) => (
              <span
                key={f}
                className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground"
              >
                {f}
              </span>
            ))}
          </div>

          <div className="mt-auto flex flex-wrap items-center gap-4 pt-6">
            <a
              href={app.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-80"
            >
              Open app
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
            <a
              href={app.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <Code2 className="h-3.5 w-3.5" />
              Source
            </a>
          </div>
        </motion.div>
      ))}

      <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border p-6 text-center">
        <Plus className="h-5 w-5 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">More on the way</p>
        <p className="max-w-xs text-sm text-muted-foreground">
          New tools built on the data will appear here.
        </p>
      </div>
    </div>
  );
}
