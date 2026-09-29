import type { Metadata } from "next";
import { SiteNav } from "@/components/site-nav";
import { AGREEMENT_TITLE, AGREEMENT_VERSION, CLAUSES } from "@/lib/data-agreement";
import { DATA_REQUEST_EMAIL } from "@/lib/links";

export const metadata: Metadata = {
  title: `${AGREEMENT_TITLE} · Multimodal Affective Computing Study`,
  description: "The terms under which MMAC study data is shared with researchers.",
};

/** The full data use agreement, readable and printable on its own. */
export default function DataAgreementPage() {
  return (
    <div className="flex flex-1 flex-col">
      <div className="print:hidden">
        <SiteNav />
      </div>
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-14 print:py-0">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Version {AGREEMENT_VERSION}</p>
        <h1 className="mt-2 text-4xl tracking-tight">{AGREEMENT_TITLE}</h1>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Recordings from the Multimodal Affective Computing (MMAC) study — CVPR Lab &amp; ACAI Lab, IIT Ropar — are
          shared with researchers for non-commercial academic research, case by case. Anyone requesting access must
          accept these terms for themselves and for everyone named in their request. Students apply through their
          supervisor.
        </p>

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
