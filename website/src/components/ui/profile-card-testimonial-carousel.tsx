"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ChevronLeft,
  ChevronRight,
  Mail,
  GraduationCap,
  User,
  type LucideIcon,
} from "lucide-react";
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";
import { GithubIcon, Linkedin01Icon } from "@hugeicons/core-free-icons";
import { cn } from "@/lib/utils";

type TeamMember = {
  name: string;
  role: string;
  quote: string;
};

const members: TeamMember[] = [
  {
    name: "Nongmaithem Hans",
    role: "Thermal & ECG Engines",
    quote:
      "Owns thermal and ECG capture, calibration, and the control panels for both sensor streams.",
  },
  {
    name: "Himanshu Patel",
    role: "EMG & rPPG Capture",
    quote:
      "Owns EMG and rPPG capture, signal quality, and their control panel on this hub.",
  },
  {
    name: "Kushagra Rathore",
    role: "PhD Student · Project Lead",
    quote:
      "Leads the research project — protocol design, data collection, and the overall study direction.",
  },
  {
    name: "Dr. Puneet Kumar",
    role: "Faculty Advisor",
    quote:
      "Advises on the research protocol and multimodal data collection design.",
  },
  {
    name: "Dr. Santosh Vipparthi",
    role: "Faculty Advisor",
    quote:
      "Advises on the research protocol and multimodal data collection design.",
  },
];

type SocialLink =
  | { label: string; huge: true; icon: IconSvgElement }
  | { label: string; huge: false; icon: LucideIcon };

const socials: SocialLink[] = [
  { icon: GithubIcon, label: "GitHub", huge: true },
  { icon: Linkedin01Icon, label: "LinkedIn", huge: true },
  { icon: Mail, label: "Email", huge: false },
  { icon: GraduationCap, label: "Google Scholar", huge: false },
];

function TestimonialCarousel() {
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(0);

  const go = (dir: 1 | -1) => {
    setDirection(dir);
    setIndex((prev) => (prev + dir + members.length) % members.length);
  };

  const member = members[index];

  return (
    <div className="w-full max-w-md">
      <div className="relative">
        {/* image placeholder */}
        <div className="aspect-[4/5] w-4/5 overflow-hidden rounded-3xl bg-gradient-to-br from-muted to-muted/50">
          <div className="flex h-full w-full items-center justify-center">
            <User className="h-16 w-16 text-muted-foreground" />
          </div>
        </div>

        <div className="absolute -bottom-10 right-0 w-4/5 max-w-xs rounded-2xl bg-card p-6 shadow-xl ring-1 ring-foreground/20 dark:ring-foreground/10">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={member.name}
              custom={direction}
              initial={{ opacity: 0, x: direction >= 0 ? 40 : -40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: direction >= 0 ? -40 : 40 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
            >
              <h3 className="text-xl font-bold text-foreground">{member.name}</h3>
              <p className="mt-1 text-sm text-indigo-500">{member.role}</p>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                {member.quote}
              </p>
              <div className="mt-5 flex gap-3">
                {socials.map((social) => (
                  <a
                    key={social.label}
                    href="#"
                    aria-label={social.label}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-foreground text-background transition-opacity hover:opacity-80"
                  >
                    {social.huge ? (
                      <HugeiconsIcon icon={social.icon} size={16} />
                    ) : (
                      <social.icon className="h-4 w-4" />
                    )}
                  </a>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <div className="mt-16 flex items-center justify-center gap-4">
        <button
          onClick={() => go(-1)}
          aria-label="Previous team member"
          className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2">
          {members.map((m, i) => (
            <button
              key={m.name}
              onClick={() => {
                setDirection(i > index ? 1 : -1);
                setIndex(i);
              }}
              aria-label={`Go to ${m.name}`}
              className={cn(
                "h-1.5 rounded-full transition-all",
                i === index ? "w-6 bg-foreground" : "w-1.5 bg-muted-foreground/40",
              )}
            />
          ))}
        </div>

        <button
          onClick={() => go(1)}
          aria-label="Next team member"
          className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export { TestimonialCarousel };
