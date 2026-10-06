import type { Metadata } from "next";
import { SiteNav } from "@/components/site-nav";
import { AGREEMENT_TITLE, AGREEMENT_VERSION, CLAUSES, SUMMARY } from "@/lib/data-agreement";
import { DATA_REQUEST_EMAIL } from "@/lib/links";

export const metadata: Metadata = {
  title: `${AGREEMENT_TITLE} · Multimodal Affective Computing Study`,
  description: "The terms under which MMAC study data is shared with researchers.",
};

/** The full data use agreement, readable and printable on its own. */
export default function DataAgreementPage() {
  return (
    <div className="flex flex-1 flex-col">
      {/* not wrapped: a wrapper would confine the sticky nav and it would scroll away */}
      <SiteNav />
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-14 print:py-0">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Version {AGREEMENT_VERSION}</p>
        <h1 className="mt-2 text-4xl tracking-tight">{AGREEMENT_TITLE}</h1>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Recordings from the Multimodal Affective Computing (MMAC) study — CVPR Lab &amp; ACAI Lab, IIT Ropar — are
          shared with researchers for non-commercial academic research, case by case. Anyone requesting access must
          accept these terms and is responsible for everyone they give access to. Students apply through their
          supervisor.
        </p>

        <section aria-labelledby="in-short" className="mt-8 rounded-2xl border border-border bg-muted/40 p-6 print:border-0 print:p-0">
          <h2 id="in-short" className="font-semibold">
            In short
          </h2>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 leading-relaxed">
            {SUMMARY.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-muted-foreground">This summary is for convenience; the full terms below apply.</p>
        </section>

        <ol className="mt-10 flex flex-col gap-6">
          {CLAUSES.map((c, i) => (
            <li key={c.title} className="flex gap-4">
              <span className="w-6 shrink-0 text-right font-semibold tabular-nums text-muted-foreground">{i + 1}.</span>
              <div>
                <h2 className="font-semibold">{c.title}</h2>
                <p className="mt-1 leading-relaxed text-muted-foreground">{c.text}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          Questions about these terms:{" "}
          <a href={`mailto:${DATA_REQUEST_EMAIL}`} className="underline underline-offset-4 hover:text-foreground">
            {DATA_REQUEST_EMAIL}
          </a>
          . To request access, use the “Request access” button on any data page.
        </p>
      </main>
    </div>
  );
}
