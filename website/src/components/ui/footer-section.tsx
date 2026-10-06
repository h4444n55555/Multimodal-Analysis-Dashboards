"use client";

import Link from "next/link";
import { Mail } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ComponentProps, ReactNode } from "react";
import { MODALITIES } from "@/lib/modalities";
import { DATA_REQUEST_EMAIL } from "@/lib/links";

// Data links come from the modality list, so a new data page appears here too.
const dataLinks = [
  ...MODALITIES.filter((m) => m.href).map((m) => ({ label: `${m.title} data`, href: m.href! })),
  { label: "Data use agreement", href: "/data-agreement" },
];

// The home page sections, in the same order as the nav bar.
const exploreLinks = [
  { label: "Why this research", href: "/#why" },
  { label: "Modalities", href: "/#sensors" },
  { label: "Tasks", href: "/#tasks" },
  { label: "Built with the data", href: "/#apps" },
  { label: "Research pipeline", href: "/#status" },
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

function FooterLinks({ title, links, delay }: { title: string; links: { label: string; href: string }[]; delay: number }) {
  return (
    <AnimatedContainer delay={delay}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="transition-colors duration-300 hover:text-foreground">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </AnimatedContainer>
  );
}

function Footer() {
  return (
    <footer className="relative mx-auto flex w-full max-w-7xl flex-col items-center justify-center rounded-t-4xl border-t bg-[radial-gradient(35%_128px_at_50%_0%,theme(backgroundColor.white/8%),transparent)] px-6 py-6 md:rounded-t-6xl">
      <div className="-translate-x-1/2 -translate-y-1/2 absolute top-0 right-1/2 left-1/2 h-px w-1/3 rounded-full bg-foreground/20 blur" />

      <div className="grid w-full gap-8 py-10 sm:grid-cols-2 lg:grid-cols-4 lg:gap-12">
        <AnimatedContainer className="max-w-xs space-y-3">
          <p className="text-sm font-semibold tracking-tight">
            Multimodal Affective Computing Study
          </p>
          <p className="text-sm text-muted-foreground">
            How brief, involuntary facial and body signals reveal emotional and
            cognitive state.
          </p>
          <p className="text-sm text-muted-foreground">
            CVPR Lab &amp; ACAI Lab, School of AI &amp; Data Engineering, IIT
            Ropar.
          </p>
        </AnimatedContainer>

        <FooterLinks title="Data" links={dataLinks} delay={0.15} />
        <FooterLinks title="Explore" links={exploreLinks} delay={0.2} />

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
          <p className="mt-5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Data requests
          </p>
          <a
            href={`mailto:${DATA_REQUEST_EMAIL}`}
            className="mt-2 block break-all text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground"
          >
            {DATA_REQUEST_EMAIL}
          </a>
        </AnimatedContainer>
      </div>

      <div className="w-full border-t py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} Multimodal Affective Computing (MMAC) Study · CVPR Lab &amp; ACAI Lab, IIT Ropar
      </div>
    </footer>
  );
}

export { Footer };
