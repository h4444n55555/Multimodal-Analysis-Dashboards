"use client";

import type { ReactNode } from "react";
import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Content frame for a dashboard widget: a title row (which doubles as the drag
 * handle — the grip says so) and a body that fills the rest of the cell.
 */
export function WidgetShell({
  title,
  note,
  caption,
  actions,
  children,
  className,
}: {
  title: string;
  note?: ReactNode;
  /** one plain-language line under the chart: what this widget shows */
  caption?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="viz flex h-full min-h-0 flex-col p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="flex items-center gap-1 truncate text-sm font-semibold">
            <GripVertical className="-ml-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            {title}
          </h3>
          {note && <p className="truncate text-xs text-muted-foreground">{note}</p>}
        </div>
        {actions}
      </div>
      <div className={cn("relative min-h-0 flex-1", className)}>{children}</div>
      {caption && (
        <p className="mt-2 shrink-0 border-t border-border/60 pt-2 text-xs leading-snug text-foreground/80">
          {caption}
        </p>
      )}
    </div>
  );
}

/** A single headline number filling a small widget. */
export function BigNumber({ value, unit, sub }: { value: ReactNode; unit?: string; sub?: ReactNode }) {
  return (
    <div className="flex h-full flex-col justify-end">
      <p className="text-4xl font-semibold tracking-tight lg:text-5xl">
        {value}
        {unit && <span className="ml-1 text-lg font-normal text-muted-foreground">{unit}</span>}
      </p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

/** Key/value facts about a recording. */
export function Facts({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid h-full content-end gap-y-1.5 text-sm">
      {rows.map(([k, v], i) => (
        <div key={i} className="flex items-baseline justify-between gap-3 border-b border-border/60 pb-1.5 last:border-0">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="text-right font-medium tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
