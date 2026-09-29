"use client";

import Link from "next/link";
import { Mail } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ComponentProps, ReactNode } from "react";

const siteLinks = [
  { label: "Modalities", href: "/#sensors" },
  { label: "Thermal data", href: "/thermal" },
  { label: "ECG data", href: "/ecg" },
  { label: "Built with the data", href: "/#apps" },
  { label: "Research Pipeline", href: "/#status" },
  { label: "Team", href: "/#team" },
];

const contacts = [
  { name: "Kushagra Rathore", email: "kushagra.25aiz0001@iitrpr.ac.in" },
  { name: "Dr. Puneet Kumar", email: "puneet.kumar@iitrpr.ac.in" },
  { name: "Dr. Santosh Vipparthi", email: "skvipparthi@iitrpr.ac.in" },
];

type ViewAnimationProps = {
  delay?: number;
  className?: ComponentProps<typeof motion.div>["className"];
  children: ReactNode;
};

function AnimatedContainer({
  className,
  delay = 0.1,
  children,
}: ViewAnimationProps) {
  const shouldReduceMotion = useReducedMotion();

  if (shouldReduceMotion) {
    return children;
  }

  return (
    <motion.div
      className={className}
      initial={{ filter: "blur(4px)", translateY: -8, opacity: 0 }}
      transition={{ delay, duration: 0.8 }}
      viewport={{ once: true }}
      whileInView={{ filter: "blur(0px)", translateY: 0, opacity: 1 }}
    >
      {children}
    </motion.div>
  );
}

function Footer() {
  return (
    <footer className="relative mx-auto flex w-full max-w-7xl flex-col items-center justify-center rounded-t-4xl border-t bg-[radial-gradient(35%_128px_at_50%_0%,theme(backgroundColor.white/8%),transparent)] px-6 py-6 md:rounded-t-6xl">
      <div className="-translate-x-1/2 -translate-y-1/2 absolute top-0 right-1/2 left-1/2 h-px w-1/3 rounded-full bg-foreground/20 blur" />

      <div className="grid w-full gap-8 py-10 sm:grid-cols-3 sm:gap-16">
        <AnimatedContainer className="max-w-xs space-y-4">
          <p className="text-sm font-semibold tracking-tight">
            Multimodal Biosensing
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            CVPR Lab &amp; ACAI Lab, School of AI &amp; Data Engineering, IIT
            Ropar.
          </p>
        </AnimatedContainer>

        <AnimatedContainer delay={0.2}>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Site
          </p>
          <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
            {siteLinks.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="transition-colors duration-300 hover:text-foreground"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </AnimatedContainer>

        <AnimatedContainer delay={0.3}>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Contact
          </p>
          <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
            {contacts.map((c) => (
              <li key={c.email}>
                <a
                  href={`mailto:${c.email}`}
                  className="inline-flex items-center gap-1.5 transition-colors duration-300 hover:text-foreground"
                >
                  <Mail className="h-3.5 w-3.5 shrink-0" />
                  {c.name}
                </a>
              </li>
            ))}
          </ul>
        </AnimatedContainer>
      </div>

      <div className="w-full border-t py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} Multimodal Biosensing Project · IIT Ropar
      </div>
    </footer>
  );
}

export { Footer };
