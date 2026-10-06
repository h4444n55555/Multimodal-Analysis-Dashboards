"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/*
 * Small SVG chart kit shared by the modality pages. Deliberately minimal:
 * linear scales, nice ticks, a frame that draws recessive hairline grid/axes,
 * and a hover layer. Marks are drawn by the caller in the frame's coordinates.
 */

export type Scale = ((v: number) => number) & {
  invert: (px: number) => number;
  domain: [number, number];
  range: [number, number];
};

export function linear(domain: [number, number], range: [number, number]): Scale {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  const f = ((v: number) => r0 + (v - d0) * k) as Scale;
  f.invert = (px: number) => (k === 0 ? d0 : d0 + (px - r0) / k);
  f.domain = domain;
  f.range = range;
  return f;
}

/** Round ticks (1, 2, 5 × 10^n steps) spanning [min, max]. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  const raw = (max - min) / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) {
    out.push(Number(v.toFixed(10)));
  }
  return out;
}

/** Pads a data extent so marks never sit on the plot edge. */
export function extent(values: number[], pad = 0.08): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (!Number.isFinite(lo)) return [0, 1];
  const span = hi - lo || Math.abs(hi) || 1;
  return [lo - span * pad, hi + span * pad];
}

/** Tracks an element's content width, so charts fill their card. */
export function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setWidth(Math.max(240, Math.floor(entry.contentRect.width)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Tracks an element's content box, so a chart can fill a fixed-size widget. */
export function useSize<T extends HTMLElement>(fallback = { width: 320, height: 200 }) {
  const ref = useRef<T>(null);
  const [size, setSize] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize((was) =>
        Math.abs(was.width - width) < 1 && Math.abs(was.height - height) < 1
          ? was
          : { width: Math.max(160, Math.floor(width)), height: Math.max(80, Math.floor(height)) },
      );
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

export type Margin = { top: number; right: number; bottom: number; left: number };

type FrameProps = {
  width: number;
  height: number;
  /** the caller's plot margins — already baked into the scales' ranges */
  margin: Margin;
  x: Scale;
  y: Scale;
  xTicks?: number[];
  yTicks?: number[];
  xFormat?: (v: number) => string;
  yFormat?: (v: number) => string;
  yLabel?: string;
  xLabel?: string;
  /** shaded protocol blocks, labelled along the top */
  bands?: { from: number; to: number; label: string; shaded?: boolean }[];
  children?: ReactNode;
  onHover?: (xValue: number | null, px: { x: number; y: number } | null) => void;
  onPick?: (xValue: number) => void;
  ariaLabel: string;
  /** clip the marks to the plot area (for signals with out-of-range spikes) */
  clip?: boolean;
};

/** Axes, gridlines, protocol bands and the pointer layer around a plot. */
export function ChartFrame({
  width,
  height,
  x,
  y,
  xTicks = [],
  yTicks = [],
  xFormat = String,
  yFormat = String,
  yLabel,
  xLabel,
  bands = [],
  children,
  onHover,
  onPick,
  ariaLabel,
  clip = false,
}: FrameProps) {
  const [x0, x1] = x.range;
  const [y1, y0] = y.range; // range is [bottom, top]
  const clipId = useId();

  const toValue = (e: React.PointerEvent<SVGRectElement>) => {
    const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * width;
    const py = ((e.clientY - box.top) / box.height) * height;
    return { value: x.invert(Math.min(x1, Math.max(x0, px))), px, py };
  };

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
      className="block overflow-visible select-none"
    >
      {bands.map((b) => (
        <g key={`${b.label}@${b.from}`}>
          {b.shaded && (
            <rect x={x(b.from)} y={y0} width={Math.max(0, x(b.to) - x(b.from))} height={y1 - y0} fill="var(--viz-band)" />
          )}
          <text
            x={(x(b.from) + x(b.to)) / 2}
            y={y0 - 6}
            textAnchor="middle"
            fontSize={12}
            fill="var(--viz-muted)"
            letterSpacing="0.06em"
          >
            {b.label.toUpperCase()}
          </text>
        </g>
      ))}

      {yTicks.map((t) => (
        <g key={`y${t}`}>
          <line x1={x0} x2={x1} y1={y(t)} y2={y(t)} stroke="var(--viz-grid)" strokeWidth={1} />
          <text x={x0 - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={12} fill="var(--viz-muted)" className="tabular-nums">
            {yFormat(t)}
          </text>
        </g>
      ))}
      <line x1={x0} x2={x1} y1={y1} y2={y1} stroke="var(--viz-axis)" strokeWidth={1} />
      {xTicks.map((t) => (
        <text key={`x${t}`} x={x(t)} y={y1 + 16} textAnchor="middle" fontSize={12} fill="var(--viz-muted)" className="tabular-nums">
          {xFormat(t)}
        </text>
      ))}
      {yLabel && (
        <text x={x0 - 8} y={y0 - 6} textAnchor="end" fontSize={12} fill="var(--viz-muted)">
          {yLabel}
        </text>
      )}
      {xLabel && (
        <text x={x1} y={y1 + 30} textAnchor="end" fontSize={12} fill="var(--viz-muted)">
          {xLabel}
        </text>
      )}

      {clip ? (
        <>
          <clipPath id={clipId}>
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} />
          </clipPath>
          <g clipPath={`url(#${clipId})`}>{children}</g>
        </>
      ) : (
        children
      )}

      {(onHover || onPick) && (
        <rect
          x={x0}
          y={y0}
          width={x1 - x0}
          height={y1 - y0}
          fill="transparent"
          style={{ cursor: onPick ? "pointer" : "crosshair" }}
          onPointerMove={(e) => {
            const v = toValue(e);
            onHover?.(v.value, { x: v.px, y: v.py });
          }}
          onPointerLeave={() => onHover?.(null, null)}
          onPointerDown={(e) => onPick?.(toValue(e).value)}
        />
      )}
    </svg>
  );
}

/** A polyline path for evenly or unevenly spaced samples. */
export function linePath(xs: ArrayLike<number>, ys: ArrayLike<number>, x: Scale, y: Scale): string {
  let d = "";
  for (let i = 0; i < ys.length; i++) {
    const v = ys[i];
    if (!Number.isFinite(v)) continue;
    d += `${d ? "L" : "M"}${x(xs[i]).toFixed(1)},${y(v).toFixed(1)}`;
  }
  return d;
}

/** Floating tooltip positioned inside a relative container. */
export function Tooltip({
  at,
  containerWidth,
  children,
}: {
  at: { x: number; y: number } | null;
  containerWidth: number;
  children: ReactNode;
}) {
  if (!at) return null;
  const flip = at.x > containerWidth * 0.62;
  return (
    <div
      className="pointer-events-none absolute z-10 min-w-36 rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg"
      style={{
        left: at.x,
        top: Math.max(0, at.y - 12),
        transform: `translate(${flip ? "calc(-100% - 12px)" : "12px"}, -100%)`,
      }}
    >
      {children}
    </div>
  );
}

/** Legend row: a short line swatch beside text-coloured labels. */
export function Legend({ items }: { items: { key: string; label: string; color: string; muted?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((it) => (
        <li key={it.key} className={it.muted ? "opacity-50" : undefined}>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-3.5 rounded-full" style={{ background: it.color }} />
            {it.label}
          </span>
        </li>
      ))}
    </ul>
  );
}
