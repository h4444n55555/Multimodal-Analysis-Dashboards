"use client";

import { cloneElement, isValidElement, useCallback, useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { Pause, Play } from "lucide-react";
import { useAsset } from "@/lib/use-json";
import { dataUrl, type DataIndex, type ThermalSession } from "@/lib/sample-data";
import { COLORMAPS, gradientCss, type ColormapKey } from "@/components/viz/colormap";
import { ChartFrame, Legend, Tooltip, linePath, linear, niceTicks, extent, useSize } from "@/components/viz/chart";
import { ModalityHeader, Segmented } from "@/components/modality/kit";
import { Facts, WidgetShell } from "@/components/modality/widget";
import { RequestAccess } from "@/components/modality/request-access";
import { DraggableWidgetGrid, type WidgetItem } from "@/components/ui/draggable-widget-grid";
import { AboutData } from "@/components/modality/explain";
import { ModalityDetails } from "@/components/modality/details";
import { CAPTIONS } from "@/lib/explanations";

// Region identity follows the fixed categorical order (validated slots 1-4)
const ROI_COLOR: Record<string, string> = {
  forehead: "var(--series-1)",
  periorbital: "var(--series-2)",
  nose: "var(--series-3)",
  mouth: "var(--series-4)",
  maxillary: "var(--series-4)",
};

// one fixed window for every frame: wide enough to show the room and a cold
// drink, while the face still spans most of the colour map
const DISPLAY_RANGE: [number, number] = [22, 36];
// pixels warmer than this count as face rather than room
const FACE_C = 30;

const WIDGETS: WidgetItem[] = [
  { id: "video", size: "lg", label: "Thermal video" },
  { id: "now", size: "sm", label: "Region temperatures right now" },
  { id: "hist", size: "sm", label: "Pixel temperature histogram" },
  { id: "series", size: "wide", label: "Region temperatures over time" },
  { id: "ranges", size: "wide", label: "Region temperature ranges" },
  { id: "frame", size: "sm", label: "Current frame statistics" },
  { id: "facts", size: "sm", label: "Recording details" },
];

type Units = "absolute" | "delta";

export function ThermalExplorer() {
  const index = useAsset<DataIndex>(dataUrl("thermal", "index.json"));
  const first = index.data?.sessions[0]?.id ?? null;
  const session = useAsset<ThermalSession>(first ? dataUrl("thermal", `${first}.json`) : null);
  const s = session.data;
  const frames = useAsset<Uint8Array>(s ? dataUrl("thermal", s.frames.file) : null, "bytes");
  const framesReady =
    frames.data && s && frames.data.length === s.frames.count * s.frames.width * s.frames.height ? frames.data : null;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-12">
      <ModalityHeader
        current="thermal"
        sourceNote={index.data?.source.note}
        device={s ? `${s.device.model} · ${s.frames.width} × ${s.frames.height} shown` : undefined}
      />
      {index.error && <p className="text-sm text-destructive">Couldn’t load the thermal data ({index.error}).</p>}
      {s ? <Dashboard session={s} frames={framesReady} /> : <div className="h-[60vh] animate-pulse rounded-3xl bg-muted" />}
    </div>
  );
}

function Dashboard({ session, frames }: { session: ThermalSession; frames: Uint8Array | null }) {
  const { frames: meta, series } = session;
  const duration = session.durationS;
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [cmap, setCmap] = useState<ColormapKey>("inferno");
  const [units, setUnits] = useState<Units>("absolute");
  const clock = useRef(0);

  // playback runs on a ref; React only hears about it 4 times a second
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      clock.current += ((now - last) / 1000) * 2; // 2× real time
      last = now;
      if (clock.current >= duration) clock.current = 0;
      const q = Math.floor(clock.current * 4) / 4;
      setT((prev) => (prev === q ? prev : q));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration]);

  const seek = useCallback(
    (time: number) => {
      clock.current = Math.max(0, Math.min(duration - 0.001, time));
      setT(clock.current);
    },
    [duration],
  );

  const frameIndex = Math.min(meta.count - 1, Math.floor(t * meta.fps));
  const { tempMinC, tempMaxC, width: W, height: H } = meta;
  const frame = useMemo(
    () => (frames ? frames.subarray(frameIndex * W * H, (frameIndex + 1) * W * H) : null),
    [frames, frameIndex, W, H],
  );
  const toC = useCallback((b: number) => tempMinC + (b / 255) * (tempMaxC - tempMinC), [tempMinC, tempMaxC]);

  const sampleAt = (key: string) => {
    const v = series.roiMeanC[key];
    return v[Math.min(v.length - 1, Math.max(0, Math.round(t * series.rateHz)))];
  };
  const start = useMemo(() => {
    const out: Record<string, number> = {};
    for (const roi of session.rois) {
      const seg = series.roiMeanC[roi.key].slice(0, 5 * series.rateHz);
      out[roi.key] = seg.reduce((a, x) => a + x, 0) / seg.length;
    }
    return out;
  }, [session, series]);

  const frameStats = useMemo(() => {
    if (!frame) return null;
    let hot = 0;
    let faceSum = 0;
    let faceN = 0;
    for (let i = 0; i < frame.length; i++) {
      if (frame[i] > hot) hot = frame[i];
      const c = toC(frame[i]);
      if (c > FACE_C) {
        faceSum += c;
        faceN++;
      }
    }
    return { hottest: toC(hot), faceMean: faceSum / Math.max(1, faceN), facePct: (100 * faceN) / frame.length };
  }, [frame, toC]);

  const render = (item: WidgetItem) => {
    switch (item.id) {
      case "video":
        return (
          <WidgetShell
            title="Thermal video"
            note="°C per pixel · hover to read"
            actions={
              <Segmented
                label="Colour map"
                value={cmap}
                onChange={setCmap}
                options={(Object.keys(COLORMAPS) as ColormapKey[]).map((k) => ({ value: k, label: COLORMAPS[k].label }))}
              />
            }
            className="flex flex-col"
          >
            <ThermalCanvas session={session} frame={frame} toC={toC} cmap={cmap} />
            <div className="mt-2 flex items-center gap-3">
              <button
                type="button"
                onClick={() => setPlaying((p) => !p)}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-foreground text-background"
                aria-label={playing ? "Pause" : "Play"}
              >
                {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              </button>
              <input
                type="range"
                min={0}
                max={duration}
                step={0.25}
                value={t}
                onChange={(e) => {
                  setPlaying(false);
                  seek(Number(e.target.value));
                }}
                aria-label="Time"
                className="min-w-0 flex-1 accent-foreground"
              />
              <span className="w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground">{t.toFixed(1)} s</span>
            </div>
          </WidgetShell>
        );

      case "now":
        return (
          <WidgetShell title="Right now" note={`at ${t.toFixed(1)} s`}>
            <ul className="flex h-full flex-col justify-end gap-1.5">
              {session.rois.map((roi) => (
                <li key={roi.key} className="flex items-baseline justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="h-2 w-2 rounded-full" style={{ background: ROI_COLOR[roi.key] }} aria-hidden="true" />
                    {roi.label}
                  </span>
                  <span className="text-lg font-semibold tabular-nums">
                    {roi.valid ? `${sampleAt(roi.key).toFixed(1)}°` : "—"}
                  </span>
                </li>
              ))}
            </ul>
          </WidgetShell>
        );

      case "hist":
        return (
          <WidgetShell title="Pixel temperatures" note="this frame">
            <Histogram frame={frame} toC={toC} />
          </WidgetShell>
        );

      case "series":
        return (
          <WidgetShell
            title="Regions over time"
            note="mean of each box · click to jump"
            actions={
              <Segmented
                label="Units"
                value={units}
                onChange={setUnits}
                options={[
                  { value: "absolute", label: "°C" },
                  { value: "delta", label: "Change" },
                ]}
              />
            }
          >
            <RoiChart
              session={session}
              start={start}
              units={units}
              cursor={t}
              onSeek={(time) => {
                setPlaying(false);
                seek(time);
              }}
            />
          </WidgetShell>
        );

      case "ranges":
        return (
          <WidgetShell title="Region ranges" note="min – max over the recording · dot = mean">
            <RangeSummary session={session} />
          </WidgetShell>
        );

      case "frame":
        return (
          <WidgetShell title="This frame" note={`frame ${frameIndex + 1} of ${meta.count}`}>
            <Facts
              rows={[
                ["Hottest", frameStats ? `${frameStats.hottest.toFixed(1)} °C` : "—"],
                ["Face mean", frameStats ? `${frameStats.faceMean.toFixed(1)} °C` : "—"],
                ["Face area", frameStats ? `${frameStats.facePct.toFixed(0)}%` : "—"],
              ]}
            />
          </WidgetShell>
        );

      case "facts":
        return (
          <WidgetShell title="Recording">
            <Facts
              rows={[
                ["Camera", session.device.model],
                ["Shown at", `${W} × ${H}`],
                ["Frames", `${meta.count} @ ${meta.fps}/s`],
                ["Length", `${session.durationS} s`],
                ...(session.context ? [["Room", `${session.context.ambientC} °C`] as [string, string]] : []),
                ["Licence", session.source?.license ?? "—"],
              ]}
            />
          </WidgetShell>
        );
      default:
        return null;
    }
  };

  const withCaption = (item: WidgetItem) => {
    const el = render(item);
    return isValidElement(el) ? cloneElement(el as ReactElement<{ caption?: string }>, { caption: CAPTIONS.thermal[item.id] }) : el;
  };

  return (
    <div className="flex flex-col gap-14">
      <AboutData modality="thermal" />

      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">Drag widgets by their title to rearrange.</p>
        <DraggableWidgetGrid items={WIDGETS} renderItem={withCaption} maxColumns={4} cellSize={280} gap={14} />
      </div>

      <div className="flex flex-col gap-5">
        <ModalityDetails
          modality="thermal"
          title="Thermal"
          highlight={thermalHighlight(session)}
          source={session.source}
          facts={[
            ["Camera", session.device.model],
            ["Shown at", `${W} × ${H} pixels`],
            ["Frames", `${meta.count} at ${meta.fps} per second`],
            ["Length", `${session.durationS} s`],
            ["Regions tracked", session.rois.map((r) => r.label).join(", ")],
            ...(session.context ? [["Room temperature", `${session.context.ambientC} °C`] as [string, string]] : []),
            ["Licence", session.source?.license ?? "—"],
          ]}
        />
        <RequestAccess />
      </div>
    </div>
  );
}

/** "The mouth cooled by 1.3 °C while drinking…" — the region that changed most. */
function thermalHighlight(session: ThermalSession) {
  const { rateHz, roiMeanC } = session.series;
  const [before, during, after] = ["Before", "Drinking", "After"].map((n) => session.phases.find((p) => p.name === n));
  if (!before || !during) return undefined;
  const mean = (v: number[], p: { startS: number; endS: number }) => {
    const seg = v.slice(Math.floor(p.startS * rateHz), Math.ceil(p.endS * rateHz));
    return seg.reduce((a, x) => a + x, 0) / Math.max(1, seg.length);
  };
  const drops = session.rois
    .filter((r) => r.valid)
    .map((r) => {
      const v = roiMeanC[r.key];
      const b = mean(v, before);
      return { label: r.label, drop: b - mean(v, during), recovered: after ? b - mean(v, after) < 0.3 : false };
    })
    .sort((a, b) => b.drop - a.drop);
  const top = drops[0];
  if (!top || top.drop < 0.2) return undefined;
  return (
    <>
      In this clip, the <strong>{top.label.toLowerCase()}</strong> cooled by <strong>{top.drop.toFixed(1)} °C</strong>{" "}
      while drinking{top.recovered ? ", then warmed back up." : "."}
    </>
  );
}

/** Fits the 4:3 thermogram inside whatever space the widget leaves. */
function ThermalCanvas({
  session,
  frame,
  toC,
  cmap,
}: {
  session: ThermalSession;
  frame: Uint8Array | null;
  toC: (b: number) => number;
  cmap: ColormapKey;
}) {
  const { width: W, height: H } = session.frames;
  const [boxRef, box] = useSize<HTMLDivElement>();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<{ x: number; y: number; px: number; py: number } | null>(null);

  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx || !frame) return;
    const img = ctx.createImageData(W, H);
    const lut = COLORMAPS[cmap].lut;
    const [lo, hi] = DISPLAY_RANGE;
    for (let i = 0; i < frame.length; i++) {
      const k = Math.max(0, Math.min(255, Math.round(((toC(frame[i]) - lo) / (hi - lo)) * 255)));
      img.data[i * 4] = lut[k * 3];
      img.data[i * 4 + 1] = lut[k * 3 + 1];
      img.data[i * 4 + 2] = lut[k * 3 + 2];
      img.data[i * 4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
  }, [frame, cmap, W, H, toC]);

  // largest 4:3 rectangle that fits, leaving room for the colour scale
  const availH = Math.max(40, box.height - 22);
  const scale = Math.min(box.width / W, availH / H);
  const dw = Math.floor(W * scale);
  const dh = Math.floor(H * scale);
  const hoverTemp = hover && frame ? toC(frame[hover.y * W + hover.x]) : null;

  return (
    <div ref={boxRef} className="flex min-h-0 flex-1 flex-col items-center justify-center">
      <div
        data-no-drag
        className="relative overflow-hidden rounded-xl bg-black"
        style={{ width: dw, height: dh }}
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const x = Math.floor(((e.clientX - r.left) / r.width) * W);
          const y = Math.floor(((e.clientY - r.top) / r.height) * H);
          if (x >= 0 && y >= 0 && x < W && y < H) setHover({ x, y, px: e.clientX - r.left, py: e.clientY - r.top });
        }}
        onPointerLeave={() => setHover(null)}
      >
        <canvas ref={canvasRef} width={W} height={H} className="h-full w-full" role="img" aria-label="Thermal frame" />
        {!frame && <div className="absolute inset-0 animate-pulse bg-muted" />}
        {hover && hoverTemp !== null && (
          <div
            className="pointer-events-none absolute rounded-md bg-black/75 px-2 py-1 text-xs tabular-nums text-white"
            style={{ left: hover.px + 12, top: hover.py + 12 }}
          >
            {hoverTemp.toFixed(2)} °C
          </div>
        )}
      </div>
      <div className="mt-2 flex items-center gap-2 text-xs tabular-nums text-muted-foreground" style={{ width: dw }}>
        <span>{DISPLAY_RANGE[0]}°</span>
        <div className="h-1.5 flex-1 rounded-full" style={{ background: gradientCss(cmap) }} aria-hidden="true" />
        <span>{DISPLAY_RANGE[1]}°C</span>
      </div>
    </div>
  );
}

/** Distribution of every pixel's temperature in the current frame. */
function Histogram({ frame, toC }: { frame: Uint8Array | null; toC: (b: number) => number }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const LO = 20;
  const HI = 38;
  const STEP = 0.5;
  const bins = useMemo(() => {
    const n = Math.round((HI - LO) / STEP);
    const counts = new Array(n).fill(0);
    if (frame) {
      for (let i = 0; i < frame.length; i++) {
        const k = Math.floor((toC(frame[i]) - LO) / STEP);
        if (k >= 0 && k < n) counts[k]++;
      }
    }
    const total = frame?.length ?? 1;
    return counts.map((c, i) => ({ from: LO + i * STEP, pct: (100 * c) / total }));
  }, [frame, toC]);

  const { width, height } = size;
  const margin = { top: 6, right: 4, bottom: 20, left: 4 };
  const x = linear([LO, HI], [margin.left, width - margin.right]);
  const y = linear([0, Math.max(1, ...bins.map((b) => b.pct))], [height - margin.bottom, margin.top]);
  const bw = Math.max(1, x(LO + STEP) - x(LO) - 2);

  return (
    <div ref={ref} className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={[20, 25, 30, 35]}
        xFormat={(v) => `${v}°`}
        ariaLabel="Histogram of pixel temperatures in the current frame"
      >
        {bins.map((b, i) =>
          b.pct > 0 ? (
            <rect
              key={b.from}
              x={x(b.from) + 1}
              y={y(b.pct)}
              width={bw}
              height={Math.max(0, y(0) - y(b.pct))}
              rx={Math.min(2, bw / 2)}
              fill={b.from + STEP > FACE_C ? "var(--series-2)" : "var(--viz-muted)"}
              opacity={hover === null || hover === i ? 1 : 0.5}
              onPointerEnter={() => setHover(i)}
              onPointerLeave={() => setHover(null)}
            />
          ) : null,
        )}
      </ChartFrame>
      {hover !== null && (
        <p className="pointer-events-none absolute right-0 top-0 rounded-md border border-border bg-popover px-2 py-1 text-xs tabular-nums shadow">
          {bins[hover].from.toFixed(1)}–{(bins[hover].from + STEP).toFixed(1)}° · {bins[hover].pct.toFixed(1)}% of pixels
        </p>
      )}
      <p className="pointer-events-none absolute left-0 top-0 flex gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm" style={{ background: "var(--viz-muted)" }} /> room
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm" style={{ background: "var(--series-2)" }} /> face
        </span>
      </p>
    </div>
  );
}

function RoiChart({
  session,
  start,
  units,
  cursor,
  onSeek,
}: {
  session: ThermalSession;
  start: Record<string, number>;
  units: Units;
  cursor: number;
  onSeek: (t: number) => void;
}) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { rateHz, roiMeanC } = session.series;
  const valid = session.rois.filter((r) => r.valid);
  const lines = valid.map((roi) => ({
    ...roi,
    values: roiMeanC[roi.key].map((v) => (units === "delta" ? v - start[roi.key] : v)),
  }));
  const times = roiMeanC[valid[0].key].map((_, i) => i / rateHz);

  const { width } = size;
  const height = Math.max(120, size.height - 22);
  const margin = { top: 20, right: 80, bottom: 24, left: 38 };
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear(extent(lines.flatMap((l) => l.values), 0.12), [height - margin.bottom, margin.top]);
  const fmtY = (v: number) => (units === "delta" ? `${v > 0 ? "+" : ""}${v.toFixed(1)}` : v.toFixed(1));

  const ends = lines
    .map((l) => ({ key: l.key, label: l.label, y: y(l.values[l.values.length - 1]) }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 12);
  const hi = hover ? Math.round(hover.t * rateHz) : null;

  return (
    <div ref={ref} className="absolute inset-0 flex flex-col">
      <Legend
        items={session.rois.map((r) => ({
          key: r.key,
          label: r.valid ? r.label : `${r.label} (hidden)`,
          color: ROI_COLOR[r.key],
          muted: !r.valid,
        }))}
      />
      <div data-no-drag className="relative mt-1.5">
        <ChartFrame
          width={width}
          height={height}
          margin={margin}
          x={x}
          y={y}
          xTicks={niceTicks(0, session.durationS, 6)}
          yTicks={niceTicks(y.domain[0], y.domain[1], 4)}
          xFormat={(v) => `${v}s`}
          yFormat={fmtY}
          bands={session.phases.map((p) => ({ from: p.startS, to: p.endS, label: p.name, shaded: p.name === "Drinking" }))}
          ariaLabel="Region temperatures over time"
          onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
          onPick={onSeek}
        >
          {units === "delta" && y.domain[0] < 0 && y.domain[1] > 0 && (
            <line x1={x.range[0]} x2={x.range[1]} y1={y(0)} y2={y(0)} stroke="var(--viz-axis)" strokeWidth={1} />
          )}
          {lines.map((l) => (
            <path key={l.key} d={linePath(times, l.values, x, y)} fill="none" stroke={ROI_COLOR[l.key]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {ends.map((e) => (
            <text key={e.key} x={x.range[1] + 6} y={e.y} dy="0.32em" fontSize={12} fill="var(--viz-text-2)">
              {e.label}
            </text>
          ))}
          <line x1={x(cursor)} x2={x(cursor)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-cursor)" strokeOpacity={0.45} strokeWidth={1} />
          {hover && hi !== null && (
            <>
              <line x1={x(hover.t)} x2={x(hover.t)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />
              {lines.map((l) => (
                <circle key={l.key} cx={x(times[hi])} cy={y(l.values[hi])} r={4} fill={ROI_COLOR[l.key]} stroke="var(--card)" strokeWidth={2} />
              ))}
            </>
          )}
        </ChartFrame>
        <Tooltip at={hover?.at ?? null} containerWidth={width}>
          {hi !== null && (
            <>
              <p className="mb-1 font-medium tabular-nums">{times[hi].toFixed(1)} s</p>
              {lines.map((l) => (
                <p key={l.key} className="flex items-center justify-between gap-4">
                  <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                    <span className="h-2 w-2 rounded-full" style={{ background: ROI_COLOR[l.key] }} />
                    {l.label}
                  </span>
                  <span className="tabular-nums">{roiMeanC[l.key][hi].toFixed(2)} °C</span>
                </p>
              ))}
            </>
          )}
        </Tooltip>
      </div>
    </div>
  );
}

/** Min–max bar per region on one °C axis, mean as a dot, numbers beside. */
function RangeSummary({ session }: { session: ThermalSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const rows = session.rois.map((roi) => {
    const v = session.series.roiMeanC[roi.key];
    return { ...roi, min: Math.min(...v), max: Math.max(...v), mean: v.reduce((a, x) => a + x, 0) / v.length };
  });
  const shown = rows.filter((r) => r.valid);
  const { width, height } = size;
  const narrow = width < 420;
  const margin = { top: 4, right: narrow ? 8 : 120, bottom: 22, left: 78 };
  const x = linear(extent(shown.flatMap((r) => [r.min, r.max]), 0.1), [margin.left, width - margin.right]);
  const band = (height - margin.top - margin.bottom) / rows.length;

  return (
    <div ref={ref} className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={linear([0, 1], [height - margin.bottom, margin.top])}
        xTicks={niceTicks(x.domain[0], x.domain[1], 4)}
        xFormat={(v) => `${v.toFixed(1)}°`}
        ariaLabel="Temperature range of each region"
      >
        {rows.map((r, i) => {
          const cy = margin.top + band * (i + 0.5);
          return (
            <g key={r.key}>
              <text x={margin.left - 10} y={cy} dy="0.32em" textAnchor="end" fontSize={11.5} fill="var(--viz-text)">
                {r.label}
              </text>
              {r.valid ? (
                <>
                  <line x1={x(r.min)} x2={x(r.max)} y1={cy} y2={cy} stroke={ROI_COLOR[r.key]} strokeWidth={8} strokeLinecap="round" opacity={0.35} />
                  <circle cx={x(r.mean)} cy={cy} r={6} fill={ROI_COLOR[r.key]} stroke="var(--card)" strokeWidth={2} />
                  {!narrow && (
                    <text x={width - margin.right + 12} y={cy} dy="0.32em" fontSize={12} fill="var(--viz-text-2)" className="tabular-nums">
                      {r.mean.toFixed(2)}° ({r.min.toFixed(1)}–{r.max.toFixed(1)})
                    </text>
                  )}
                </>
              ) : (
                <text x={margin.left} y={cy} dy="0.32em" fontSize={12} fill="var(--viz-muted)">
                  hidden by glasses
                </text>
              )}
            </g>
          );
        })}
      </ChartFrame>
    </div>
  );
}
