import { Users } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Hero } from "@/components/ui/animated-hero";
import { TestimonialCarousel } from "@/components/ui/profile-card-testimonial-carousel";
import { VerticalTabs } from "@/components/ui/vertical-tabs";
import MultimodalPipeline from "@/components/ui/pipeline-visualization";
import { TaskBento } from "@/components/ui/task-bento";
import { Applications } from "@/components/ui/applications";import Text3DFlip from "@/registry/magicui/text-3d-flip";
import { Highlighter } from "@/registry/magicui/highlighter";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <SiteNav />

      <main className="flex flex-1 flex-col">
        {/* Hero */}
        <section id="hero" className="mx-auto w-full max-w-7xl scroll-mt-24 px-6">
          <Hero />
        </section>

        {/* Why this research */}
        <section id="why" className="scroll-mt-24 border-t border-border/60">
          <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-6 py-24 text-center">
            <Text3DFlip
              as="h2"
              className="justify-center bg-background font-heading text-3xl text-foreground sm:text-4xl md:text-5xl"
              textClassName="bg-background text-foreground"
              flipTextClassName="bg-background text-foreground"
              rotateDirection="top"
              staggerDuration={0.03}
              staggerFrom="first"
              transition={{ type: "spring", damping: 25, stiffness: 160 }}
            >
              Why this research
            </Text3DFlip>
            <p className="mt-6 max-w-2xl leading-relaxed text-muted-foreground">
              Most systems read emotion from a single signal and break the
              moment lighting changes, a subject moves, or a face turns
              away. We fuse{" "}
              <Highlighter
                action="underline"
                color="#0052FF"
                isView
                delay={3000}
              >
                <span className="text-foreground">
                  four independent sensor streams
                </span>
              </Highlighter>{" "}
              — thermal, ECG, EMG, and rPPG — captured together in the same
              recording session rather than stitched together afterward, so
              the model keeps working when any one of them drops out or
              degrades. That matters because the settings we actually care
              about — mental health screening, driver monitoring,
              human-computer interaction — happen outside a controlled
              studio, where lighting shifts, people move, and no single
              sensor can be trusted on its own. The goal isn&apos;t a
              benchmark number; it&apos;s{" "}
              <Highlighter
                action="highlight"
                color="#dbe7ff"
                isView
                delay={3000}
              >
                <span className="text-black">
                  screening that&apos;s reliable enough to actually use
                </span>
              </Highlighter>{" "}
              in the room it was built for, not just a lab demo.
            </p>
            <p className="mt-4 max-w-2xl leading-relaxed text-muted-foreground">
              This site is the front door to the study: each modality below
              opens its data — recordings you can play back, inspect, and
              download — and the tools further down show what we have built
              with it.
            </p>
          </div>
        </section>

        {/* Modalities → data dashboards */}
        <section id="sensors" className="scroll-mt-24">
          <VerticalTabs />
        </section>

        {/* Downstream tasks */}
        <section id="tasks" className="scroll-mt-24">
          <div className="mx-auto w-full max-w-7xl px-6 py-24">
            <h2 className="text-2xl font-semibold tracking-tight">
              Downstream Tasks
            </h2>
            <p className="mt-1 max-w-xl text-muted-foreground">
              What the fused sensor streams are used to predict. Click any
              card to read more.
            </p>
            <div className="mt-10">
              <TaskBento />
            </div>
          </div>
        </section>

        {/* What we have built with the data */}
        <section id="apps" className="scroll-mt-24">
          <div className="mx-auto w-full max-w-7xl px-6 py-24">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Applications
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Built with the data
            </h2>
            <p className="mt-3 max-w-2xl text-lg text-muted-foreground">
              Tools that put the study&apos;s sensing methods to work for people
              beyond researchers. Each one links to its official home.
            </p>
            <div className="mt-10">
              <Applications />
            </div>
          </div>
        </section>

        {/* Pipeline overview */}
        <section id="status" className="scroll-mt-24">
          <div className="mx-auto w-full max-w-7xl px-6 py-24">
            <h2 className="text-2xl font-semibold tracking-tight">
              Research Pipeline
            </h2>
            <p className="mt-1 max-w-xl text-muted-foreground">
              How the four sensor streams are synchronized, fused, and turned
              into downstream predictions.
            </p>
            <div className="mt-10">
              <MultimodalPipeline />
            </div>
          </div>
        </section>

        {/* Team */}
        <section id="team" className="mx-auto flex w-full max-w-7xl scroll-mt-24 flex-col items-center px-6 py-24">
          <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Users className="h-5 w-5" />
            Team
          </h2>
          <p className="mt-1 max-w-xl text-center text-muted-foreground">
            The people building and running this project — from sensor
            engineering to the research direction behind it.
          </p>
          <div className="mt-8 flex w-full justify-center">
            <TestimonialCarousel />
          </div>
        </section>
      </main>
    </div>
  );
}
