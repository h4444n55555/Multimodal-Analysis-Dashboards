"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertTriangle, ArrowUpRight, CheckCircle2, FlaskConical, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { MODALITIES, type Modality } from "@/lib/modalities";
import type { DataSource, QualityStatus } from "@/lib/sample-data";

/** Title, device, data-source badge, and the switcher between modality pages. */
export function ModalityHeader({
  current,
  sourceNote,
  source,
  device,
  children,
}: {
  current: Modality["key"];
  sourceNote?: string;
  /** the published recording's origin, credited under the title */
  source?: DataSource;
  /** the device the shown recording came from (defaults to the study's) */
  device?: string;
  /** controls that sit on the title row (the recording picker) */
  children?: ReactNode;
}) {
  const m = MODALITIES.find((x) => x.key === current)!;
  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Modalities" className="flex flex-wrap gap-1.5">
        {MODALITIES.map((x) =>
          x.href ? (
            <Link
              key={x.key}
              href={x.href}
              aria-current={x.key === current ? "page" : undefined}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-sm transition-colors",
                x.key === current
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {x.title}
            </Link>
          ) : (
            <span
              key={x.key}
              className="cursor-default rounded-full border border-dashed border-border px-3.5 py-1.5 text-sm text-muted-foreground/60"
            >
              {x.title} · soon
            </span>
          ),
        )}
      </nav>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl tracking-tight md:text-5xl">{m.title}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {device ?? m.device}
            {sourceNote && (
              <span
                title={sourceNote}
                className="inline-flex items-center gap-1 rounded-full border border-dashed border-border px-2 py-0.5 text-xs"
              >
                <FlaskConical className="h-3 w-3" aria-hidden="true" />
                Public sample
              </span>
            )}
          </p>
          {source && (
            <p className="mt-1.5 max-w-3xl text-xs text-muted-foreground">
              Showing{" "}
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 underline underline-offset-4 hover:text-foreground"
              >
                {source.title}
                <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
              </a>{" "}
              — {source.author} · {source.license}. {source.illustrative && source.note}
              {" "}Our own recordings replace it once published.
            </p>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}

const STATUS = {
  good: { icon: CheckCircle2, label: "Good", color: "var(--status-good)" },
  warning: { icon: AlertTriangle, label: "Check", color: "var(--status-warning)" },
  critical: { icon: XCircle, label: "Poor", color: "var(--status-critical)" },
} as const;

/** Status is never colour alone: icon + word + colour. */
export function StatusBadge({ status, label }: { status: QualityStatus; label?: string }) {
  const s = STATUS[status];
  return (
    <span className="viz inline-flex items-center gap-1.5 font-medium">
      <s.icon className="h-4 w-4" style={{ color: s.color }} aria-hidden="true" />
      {label ?? s.label}
    </span>
  );
}

/** Segmented control for small view options. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full border border-border p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-full px-3 py-1 transition-colors",
            o.value === value ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const fmt = (v: number | undefined, digits = 1) =>
  v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(digits);
