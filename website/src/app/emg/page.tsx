import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteNav } from "@/components/site-nav";
import { EmgExplorer } from "@/components/modality/emg-explorer";

export const metadata: Metadata = {
  title: "EMG · Multimodal Affective Computing Study",
  description: "Surface EMG from forearm and wrist electrodes: muscle activity at rest and in a fist, with signal quality per electrode.",
};

export default function EmgPage() {
  return (
    <div className="flex flex-1 flex-col">
      <SiteNav />
      <main className="flex flex-1 flex-col">
        <Suspense fallback={<div className="mx-auto h-[70vh] w-full max-w-7xl px-6 py-12" />}>
          <EmgExplorer />
        </Suspense>
      </main>
    </div>
  );
}
