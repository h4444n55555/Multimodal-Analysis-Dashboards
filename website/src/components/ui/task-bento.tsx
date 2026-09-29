"use client";

import { useEffect, useState } from "react";
import { motion, useAnimationControls, useReducedMotion } from "motion/react";
import {
  BrainCircuit,
  Brain,
  CornerDownLeft,
  Eye,
  HeartPulse,
  MoveUpRight,
  ScanFace,
  Smile,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Task = {
  title: string;
  blurb: string;
  details: string;
  icon: LucideIcon;
};

// Drawn from the lab's application × modality planning chart, narrowed to
// the 6 applications that best fit the four sensors this hub actually runs
// — rPPG, Thermal, ECG, and EMG — rather than the full lab-wide suite
// (facial video, audio, questionnaires, BP, WiFi, GSR, micro-expressions).
const TASKS: Task[] = [
  {
    title: "Heart Disease Prediction",
    blurb: "Cardiovascular risk assessed from pulse and cardiac signals.",
    icon: HeartPulse,
    details:
      "Estimates cardiovascular risk from camera-based pulse (rPPG) and thermal readings, cross-checked against ECG for waveform accuracy — the strongest match for this hub's four sensors, needing little from the wider lab suite.",
  },
  {
    title: "Engagement Detection",
    blurb: "How attentive and engaged someone is, tracked over a session.",
    icon: Eye,
    details:
      "Tracks attention and engagement using rPPG, thermal, and EMG signals, optionally alongside facial video and micro-expression cues from the wider sensor suite. Built for settings like classrooms or driver monitoring, where sustained attention matters.",
  },
  {
    title: "Mental Health Screening",
    blurb: "Depression, anxiety, and stress indicators from combined signals.",
    icon: Brain,
    details:
      "Screens for depression, anxiety, and stress markers by combining rPPG, thermal, and EMG — the same three signals as most of this hub's applications, here read through an affective-state lens rather than a physical one.",
  },
  {
    title: "Induced Emotion",
    blurb: "Emotional response to a controlled stimulus, measured directly.",
    icon: Smile,
    details:
      "Measures emotional response to a controlled stimulus using rPPG, thermal, and EMG together — built for lab-condition emotion-elicitation studies where the stimulus timing is known in advance.",
  },
  {
    title: "Cognition–Emotion",
    blurb: "How cognitive load and emotional state interact during a task.",
    icon: BrainCircuit,
    details:
      "Studies the interplay between cognitive load and emotional state using rPPG, thermal, and EMG — aimed at understanding how the two systems affect each other mid-task, without needing audio or questionnaire input.",
  },
  {
    title: "Anti-Spoofing",
    blurb: "Liveness checks to catch deepfakes and presentation attacks.",
    icon: ScanFace,
    details:
      "Uses rPPG and thermal signatures — hard to fake convincingly — to catch deepfakes and presentation attacks. The lightest-weight application here, needing only camera-based signals rather than all four sensors.",
  },
];

const SHAKE_INTERVAL_MS = 5000;

function TaskCard({
  task,
  index,
  shakeControls,
  onFlipChange,
}: {
  task: Task;
  index: number;
  shakeControls?: ReturnType<typeof useAnimationControls>;
  onFlipChange?: (flipped: boolean) => void;
}) {
  const [flipped, setFlipped] = useState(false);

  const toggle = () => {
    const next = !flipped;
    setFlipped(next);
    onFlipChange?.(next);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay: index * 0.12, ease: [0.23, 1, 0.32, 1] }}
      className="h-full"
    >
      {/* Separate wrapper so the periodic shake never fights the entrance
          animation or the flip transform. */}
      <motion.div animate={shakeControls} className="h-full">
        <div
          role="button"
          tabIndex={0}
          aria-pressed={flipped}
          aria-label={`${task.title} — click to ${flipped ? "hide" : "show"} details`}
          onClick={toggle}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              toggle();
            }
          }}
          className="group h-full min-h-[320px] cursor-pointer rounded-2xl outline-none [perspective:1200px] focus-visible:ring-2 focus-visible:ring-ring/50 lg:min-h-[360px]"
        >
          <motion.div
            className="relative h-full w-full transform-3d"
            animate={{ rotateY: flipped ? 180 : 0 }}
            transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          >
            {/* Front */}
            <div className="absolute inset-0 flex flex-col rounded-2xl border border-black/15 bg-card p-6 backface-hidden transition-colors group-hover:border-foreground/35 dark:border-white/[0.12]">
              <div className="flex shrink-0 items-start justify-between gap-3">
                <task.icon className="h-5 w-5 text-foreground" />
                <MoveUpRight className="h-4 w-4 text-muted-foreground transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-foreground" />
              </div>
              <div className="mt-5">
                <h3 className="text-lg font-medium tracking-tight text-foreground">
                  {task.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {task.blurb}
                </p>
              </div>
            </div>

            {/* Back */}
            <div
              className="absolute inset-0 flex flex-col rounded-2xl border border-foreground/35 bg-card p-6 backface-hidden"
              style={{ transform: "rotateY(180deg)" }}
            >
              <div className="flex shrink-0 items-start justify-between gap-3">
                <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  {task.title}
                </span>
                <CornerDownLeft className="h-4 w-4 shrink-0 text-muted-foreground" />
              </div>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                {task.details}
              </p>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function TaskBento() {
  const shakeControls = useAnimationControls();
  const shouldReduceMotion = useReducedMotion();
  // The nudge is a one-time hint: once the user has flipped the card, they
  // know the cards are interactive, so it never shakes again.
  const [hintDismissed, setHintDismissed] = useState(false);

  useEffect(() => {
    if (shouldReduceMotion || hintDismissed) return;

    const interval = setInterval(() => {
      shakeControls.start({
        rotate: [0, -1.4, 1.4, -1.4, 1.4, 0],
        x: [0, -4, 4, -4, 4, 0],
        transition: { duration: 0.55, ease: "easeInOut" },
      });
    }, SHAKE_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [shakeControls, shouldReduceMotion, hintDismissed]);

  return (
    <div className={cn("grid gap-5 sm:grid-cols-2 lg:grid-cols-3")}>
      {TASKS.map((task, i) => (
        <TaskCard
          key={task.title}
          task={task}
          index={i}
          shakeControls={i === 0 ? shakeControls : undefined}
          onFlipChange={
            i === 0
              ? (flipped) => {
                  if (!flipped || hintDismissed) return;
                  setHintDismissed(true);
                  // Snap back to rest so the card never freezes mid-shake.
                  shakeControls.stop();
                  shakeControls.set({ rotate: 0, x: 0 });
                }
              : undefined
          }
        />
      ))}
    </div>
  );
}

export default TaskBento;
