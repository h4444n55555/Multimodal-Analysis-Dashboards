import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteNav } from "@/components/site-nav";
import { ThermalExplorer } from "@/components/modality/thermal-explorer";

export const metadata: Metadata = {
  title: "Thermal · Multimodal Affective Computing Study",
  description: "Facial thermograms and region temperatures across a baseline, stimulus and recovery protocol.",
};

export default function ThermalPage() {
  return (
    <div className="flex flex-1 flex-col">
      <SiteNav />
      <main className="flex flex-1 flex-col">
        {/* reads ?session= from the URL, so it renders on the client */}
        <Suspense fallback={<div className="mx-auto h-[70vh] w-full max-w-7xl px-6 py-12" />}>
          <ThermalExplorer />
        </Suspense>
      </main>
    </div>
  );
}
