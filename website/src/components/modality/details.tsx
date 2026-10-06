"use client";

import type { ReactNode } from "react";
import { Dialog } from "radix-ui";
import { ArrowUpRight, BookOpen, X } from "lucide-react";
import { DETAILS, type ModalityKey } from "@/lib/explanations";
import type { DataSource } from "@/lib/sample-data";

/**
 * "Read the full details" text link and the large reading card it opens.
 * The dashboard stays short; everything specific to the sample recording
 * (what happens in it, where it comes from, how it is processed) lives here.
 */
export function ModalityDetails({
  modality,
  title,
  highlight,
  source,
  facts,
}: {
  modality: ModalityKey;
  /** e.g. "ECG" */
  title: string;
  /** one computed sentence about this recording */
  highlight?: ReactNode;
  source?: DataSource;
  /** recording facts as label/value rows */
  facts: [string, ReactNode][];
}) {
  const copy = DETAILS[modality];
  return (
    <Dialog.Root>
      <Dialog.Trigger
        data-details-link
        className="group inline-flex items-center gap-2 self-start text-base font-medium text-foreground underline decoration-muted-foreground/60 underline-offset-[6px] transition-colors hover:decoration-foreground"
      >
        <BookOpen className="h-4 w-4 shrink-0" aria-hidden="true" />
        Read the full details about this {title} data
        <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-0.5">
          →
        </span>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        {/* wide and two-column so everything fits on one screen without scrolling;
            the scroll area only kicks in on small screens */}
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-1.5rem)] w-[calc(100vw-2rem)] max-w-6xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-3xl border border-border bg-background shadow-2xl data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95">
          <div className="border-b border-border px-8 pb-4 pt-6 pr-16">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">Full details</p>
            <Dialog.Title className="mt-1 text-2xl font-semibold tracking-tight">{title}: the sample recording</Dialog.Title>
            <Dialog.Description className="mt-0.5 text-muted-foreground">
              What this recording is, where it comes from, and how the page processes it.
            </Dialog.Description>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6 [@media(max-height:780px)]:py-4">
            {/* short laptop screens get slightly tighter text so it still fits */}
            <div className="grid gap-x-12 gap-y-6 text-[15px] leading-6 lg:grid-cols-2 [@media(max-height:780px)]:gap-y-4 [@media(max-height:780px)]:text-sm [@media(max-height:780px)]:leading-[1.35rem]">
              <div className="flex flex-col gap-6">
              <Section heading="This recording">
                <p>{copy.recording}</p>
                {highlight && (
                  <p className="mt-3 rounded-xl border border-border bg-muted/50 px-4 py-2.5">{highlight}</p>
                )}
              </Section>

              {source && (
                <Section heading="Where it comes from">
                  <p>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-medium underline underline-offset-4"
                    >
                      {source.title}
                      <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                    </a>
                  </p>
                  <p className="text-muted-foreground">
                    {source.author} · {source.license}
                  </p>
                  {source.note && <p className="mt-2 text-muted-foreground">{source.note}</p>}
                </Section>
              )}

              <Section heading="Recording details">
                <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[auto_1fr]">
                  {facts.map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-muted-foreground">{k}</dt>
                      <dd className="font-medium tabular-nums">{v}</dd>
                    </div>
                  ))}
                </dl>
              </Section>
              </div>

              <div className="flex flex-col gap-6">
              <Section heading="How the page processes it">
                <ul className="flex list-disc flex-col gap-1.5 pl-5">
                  {copy.processing.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </Section>

              <Section heading="Keep in mind">
                <ul className="flex list-disc flex-col gap-1.5 pl-5">
                  {copy.limits.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </Section>
              </div>
            </div>
          </div>

          <Dialog.Close
            className="absolute right-5 top-5 rounded-full p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-1.5 text-lg font-semibold tracking-tight">{heading}</h3>
      {children}
    </section>
  );
}
