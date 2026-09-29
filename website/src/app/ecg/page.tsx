import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteNav } from "@/components/site-nav";
import { EcgExplorer } from "@/components/modality/ecg-explorer";

export const metadata: Metadata = {
  title: "ECG · Multimodal Affective Computing Study",
  description: "Single-lead ECG, heart rate and heart-rate variability across a baseline, stimulus and recovery protocol.",
};

export default function EcgPage() {
  return (
    <div className="flex flex-1 flex-col">
      <SiteNav />
      <main className="flex flex-1 flex-col">
        {/* reads ?session= from the URL, so it renders on the client */}
        <Suspense fallback={<div className="mx-auto h-[70vh] w-full max-w-7xl px-6 py-12" />}>
          <EcgExplorer />
        </Suspense>
      </main>
    </div>
  );
}
