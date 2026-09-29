"use client";

import { cn } from "@/lib/utils";
import { useReachable } from "@/lib/use-reachable";

const LABELS = {
  checking: "Checking…",
  online: "Running",
  offline: "Not running",
} as const;

export function StatusDot({
  url,
  className,
}: {
  url: string;
  className?: string;
}) {
  const state = useReachable(url);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs text-muted-foreground",
        className,
      )}
      title={url}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          state === "online" && "bg-green-500",
          state === "offline" && "bg-muted-foreground/40",
          state === "checking" && "animate-pulse bg-muted-foreground/40",
        )}
      />
      {LABELS[state]}
    </span>
  );
}
