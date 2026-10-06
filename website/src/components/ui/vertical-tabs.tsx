"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { MODALITIES as SENSORS } from "@/lib/modalities";

const AUTO_PLAY_DURATION = 5000;

export function VerticalTabs() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [direction, setDirection] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  // once a visitor picks a row, stop rotating it out from under them
  const [stopped, setStopped] = useState(false);

  const handleNext = useCallback(() => {
    setDirection(1);
    setActiveIndex((prev) => (prev + 1) % SENSORS.length);
  }, []);

  const handleTabClick = (index: number) => {
    setStopped(true);
    if (index === activeIndex) return;
    setDirection(index > activeIndex ? 1 : -1);
    setActiveIndex(index);
  };

  useEffect(() => {
    if (isPaused || stopped) return;

    const interval = setInterval(() => {
      handleNext();
    }, AUTO_PLAY_DURATION);

    return () => clearInterval(interval);
  }, [activeIndex, isPaused, stopped, handleNext]);

  const variants = {
    enter: (direction: number) => ({
      y: direction > 0 ? "-100%" : "100%",
      opacity: 0,
    }),
    center: {
      zIndex: 1,
      y: 0,
      opacity: 1,
    },
    exit: (direction: number) => ({
      zIndex: 0,
      y: direction > 0 ? "100%" : "-100%",
      opacity: 0,
    }),
  };

  const activeSensor = SENSORS[activeIndex];

  return (
    <section className="w-full bg-background py-8 md:py-16 lg:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8 lg:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16">
          {/* Left Column: Content */}
          <div className="lg:col-span-5 flex flex-col justify-center lg:order-1 pt-4">
            <div className="space-y-1 mb-12">
              <h2 className="tracking-tighter text-balance text-3xl font-medium md:text-4xl lg:text-5xl text-foreground">
                Modalities
              </h2>
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-[0.3em] block ml-0.5">
                (DATA)
              </span>
            </div>

            <div className="flex flex-col space-y-0">
              {SENSORS.map((sensor, index) => {
                const isActive = activeIndex === index;
                return (
                  <div
                    key={sensor.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleTabClick(index)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleTabClick(index);
                      }
                    }}
                    className={cn(
                      "group relative flex cursor-pointer items-start gap-4 py-6 md:py-8 text-left outline-none transition-all duration-500 border-t border-border/50 first:border-0 focus-visible:ring-2 focus-visible:ring-ring/50",
                      isActive
                        ? "text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <div className="absolute left-[-16px] md:left-[-24px] top-0 bottom-0 w-[2px] bg-muted">
                      {isActive && (
                        <motion.div
                          key={`progress-${index}-${isPaused}-${stopped}`}
                          className="absolute top-0 left-0 w-full bg-foreground origin-top"
                          initial={{ height: stopped ? "100%" : "0%" }}
                          animate={
                            stopped ? { height: "100%" } : isPaused ? { height: "0%" } : { height: "100%" }
                          }
                          transition={{
                            duration: AUTO_PLAY_DURATION / 1000,
                            ease: "linear",
                          }}
                        />
                      )}
                    </div>

                    <span className="text-xs font-medium mt-1 tabular-nums text-muted-foreground">
                      /{sensor.id}
                    </span>

                    <div className="flex flex-col gap-2 flex-1">
                      <span
                        className={cn(
                          "text-2xl md:text-3xl lg:text-4xl font-normal tracking-tight transition-colors duration-500",
                          isActive ? "text-foreground" : ""
                        )}
                      >
                        {sensor.title}
                      </span>

                      {/* every row keeps its link visible, not just the active one */}
                      {sensor.href ? (
                        <Link
                          href={sensor.href}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1.5 pb-2 text-sm font-medium text-foreground underline-offset-4 transition-colors hover:underline"
                        >
                          Explore the {sensor.title} data
                          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </Link>
                      ) : (
                        <span className="inline-block pb-2 text-sm font-medium text-muted-foreground">
                          Data coming soon
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div
            className="lg:col-span-7 flex flex-col justify-center lg:order-2"
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
          >
            <div className="relative min-h-[240px] w-full max-w-md">
              <AnimatePresence initial={false} custom={direction} mode="popLayout">
                <motion.div
                  key={activeIndex}
                  custom={direction}
                  variants={variants}
                  initial="enter"
                  animate="center"
                  exit="exit"
                  transition={{
                    y: { type: "spring", stiffness: 260, damping: 32 },
                    opacity: { duration: 0.4 },
                  }}
                  className="absolute inset-0 flex flex-col justify-center gap-4"
                >
                  <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {activeSensor.device}
                  </span>
                  <p className="text-muted-foreground text-lg md:text-xl leading-relaxed">
                    {activeSensor.summary}
                  </p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default VerticalTabs;
