"use client";

import { Button } from "@/components/ui/button";
import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";

function Hero() {
  const [titleNumber, setTitleNumber] = useState(0);
  const titles = useMemo(() => ["Thermal", "ECG", "EMG", "rPPG"], []);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setTitleNumber((titleNumber + 1) % titles.length);
    }, 2000);
    return () => clearTimeout(timeoutId);
  }, [titleNumber, titles]);

  // Titles only ever advance by one, so the one that just handed off the
  // active slot is always the previous index.
  const previousTitleNumber = (titleNumber - 1 + titles.length) % titles.length;

  return (
    <div className="w-full">
      <div className="container mx-auto">
        <div className="flex gap-8 py-20 lg:py-40 items-center justify-center flex-col">
          <div>
            <Button variant="secondary" size="sm" className="gap-4">
              CVPR Lab &amp; ACAI Lab · IIT Ropar
            </Button>
          </div>
          <div className="flex gap-4 flex-col">
            <h1 className="flex flex-col items-center gap-1 md:gap-2 text-5xl md:text-7xl max-w-3xl tracking-tighter text-center font-regular">
              <span className="text-spektr-cyan-50">Multimodal Affective</span>
              <span className="relative flex w-full justify-center overflow-hidden text-center md:pb-4 md:pt-1">
                &nbsp;
                {titles.map((title, index) => (
                  <motion.span
                    key={index}
                    className="absolute font-semibold"
                    initial={{ opacity: 0, y: -100 }}
                    transition={{ type: "spring", stiffness: 50 }}
                    animate={
                      titleNumber === index
                        ? {
                            y: 0,
                            opacity: 1,
                          }
                        : {
                            // The item that just handed off the active slot always
                            // exits upward, so the cycle keeps one direction even
                            // when it wraps from the last title back to the first.
                            y: index === previousTitleNumber ? -150 : 150,
                            opacity: 0,
                          }
                    }
                  >
                    {title}
                  </motion.span>
                ))}
              </span>
              <span className="text-spektr-cyan-50">Computing Study</span>
            </h1>

            <p className="text-lg md:text-xl leading-relaxed tracking-tight text-muted-foreground max-w-2xl text-center">
              We study how brief, involuntary facial and body signals reveal
              emotional and cognitive state, for uses in mental health
              screening, driver monitoring, and human-computer interaction.
              Each session records thermal, ECG, EMG, and rPPG together —
              explore the thermal and ECG data now, with EMG and rPPG to
              follow.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export { Hero };
