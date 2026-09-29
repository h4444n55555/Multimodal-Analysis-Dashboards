"use client";

import { useEffect, useState } from "react";

export type Reachability = "checking" | "online" | "offline";

const POLL_MS = 10_000;

/**
 * Pings a locally run app so its launch link can say whether it is running.
 * `no-cors` gives an opaque response we can't read, but the fetch only
 * rejects when nothing is listening — which is exactly the signal we want.
 */
export function useReachable(url: string | null): Reachability {
  const [state, setState] = useState<Reachability>("checking");

  useEffect(() => {
    if (!url) return;
    let cancelled = false;

    const check = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      try {
        await fetch(url, {
          mode: "no-cors",
          cache: "no-store",
          signal: controller.signal,
        });
        if (!cancelled) setState("online");
      } catch {
        if (!cancelled) setState("offline");
      } finally {
        clearTimeout(timeout);
      }
    };

    check();
    const interval = setInterval(check, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [url]);

  return state;
}
