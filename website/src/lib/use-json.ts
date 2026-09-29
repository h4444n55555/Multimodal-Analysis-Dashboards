"use client";

import { useEffect, useState } from "react";

type State<T> = { data: T | null; error: string | null; loading: boolean };

/** Fetches a static JSON (or binary) asset, keeping the previous data while a new one loads. */
export function useAsset<T>(url: string | null, kind: "json" | "bytes" = "json"): State<T> {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: Boolean(url) });

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- marks the refetch; previous data stays on screen
    setState((s) => ({ ...s, loading: true, error: null }));
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} loading ${url}`);
        return kind === "json" ? r.json() : r.arrayBuffer().then((b) => new Uint8Array(b));
      })
      .then((data) => !cancelled && setState({ data: data as T, error: null, loading: false }))
      .catch((e: Error) => !cancelled && setState((s) => ({ ...s, error: e.message, loading: false })));
    return () => {
      cancelled = true;
    };
  }, [url, kind]);

  return state;
}
