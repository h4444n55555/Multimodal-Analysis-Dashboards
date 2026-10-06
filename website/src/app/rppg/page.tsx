import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteNav } from "@/components/site-nav";
import { RppgExplorer } from "@/components/modality/rppg-explorer";

export const metadata: Metadata = {
  title: "rPPG · Multimodal Affective Computing Study",
  description: "Contactless pulse from face video: heart rate, variability and breathing recovered from skin colour, checked against a fingertip oximeter.",
};

export default function RppgPage() {
  return (
    <div className="flex flex-1 flex-col">
      <SiteNav />
      <main className="flex flex-1 flex-col">
        <Suspense fallback={<div className="mx-auto h-[70vh] w-full max-w-7xl px-6 py-12" />}>
          <RppgExplorer />
        </Suspense>
      </main>
    </div>
  );
}
