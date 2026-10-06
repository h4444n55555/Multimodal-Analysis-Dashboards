"use client";

import type { ReactNode } from "react";
import { Tooltip } from "radix-ui";
import { Lightbulb } from "lucide-react";
import { ABOUT, TERMS, type ModalityKey } from "@/lib/explanations";

/** A jargon word with its plain definition on hover or keyboard focus. */
export function Term({ name, children }: { name: keyof typeof TERMS | string; children?: ReactNode }) {
  const definition = TERMS[name];
  if (!definition) return <>{children ?? name}</>;
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span
            tabIndex={0}
            className="cursor-help underline decoration-dotted decoration-muted-foreground/70 underline-offset-[3px] outline-none focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            {children ?? name}
          </span>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="top"
            sideOffset={6}
            className="z-50 max-w-64 rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs leading-snug text-popover-foreground shadow-md"
          >
            {definition}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

/** A short, general introduction above a data page's widgets. */
export function AboutData({ modality }: { modality: ModalityKey }) {
  const a = ABOUT[modality];
  return (
    <section aria-labelledby="about-data" className="grid gap-5 rounded-3xl border border-border bg-card p-6 md:grid-cols-2 md:gap-10">
      <div className="flex flex-col gap-2">
        <h2 id="about-data" className="flex items-center gap-2 text-sm font-semibold">
          <Lightbulb className="h-4 w-4 shrink-0" style={{ color: "var(--series-4)" }} aria-hidden="true" />
          About this data
        </h2>
        <p className="leading-relaxed">{a.shows}</p>
        <p className="text-sm leading-relaxed text-muted-foreground">{a.recorded}</p>
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">On this dashboard</h3>
        <p className="text-sm leading-relaxed">{a.dashboard}</p>
      </div>
    </section>
  );
}
