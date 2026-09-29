"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useAsset } from "@/lib/use-json";
import { dataUrl, type DataIndex, type EcgSession, type QualityStatus, type SeriesBlock } from "@/lib/sample-data";
import { ChartFrame, Legend, Tooltip, linePath, linear, niceTicks, extent, useSize } from "@/components/viz/chart";
import { ModalityHeader, StatusBadge, fmt } from "@/components/modality/kit";
import { BigNumber, Facts, WidgetShell } from "@/components/modality/widget";
import { RequestAccess } from "@/components/modality/request-access";
import { DraggableWidgetGrid, type WidgetItem } from "@/components/ui/draggable-widget-grid";

const WINDOW_S = 10;
const STATUS_COLOR: Record<QualityStatus, string> = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
};

const WIDGETS: WidgetItem[] = [
  { id: "trace", size: "lg", label: "Raw and cleaned ECG" },
  { id: "hr-now", size: "sm", label: "Mean heart rate" },
  { id: "hrv", size: "sm", label: "Heart-rate variability" },
  { id: "overview", size: "wide", label: "Excerpt overview and signal quality" },
  { id: "drive", size: "wide", label: "The whole drive" },
  { id: "hr", size: "wide", label: "Heart rate over time" },
  { id: "resp", size: "wide", label: "Respiration" },
  { id: "skin", size: "wide", label: "Skin conductance" },
  { id: "quality", size: "sm", label: "Signal quality" },
  { id: "beat", size: "sm", label: "Average heartbeat" },
  { id: "poincare", size: "sm", label: "Beat-to-beat map" },
  { id: "spectrum", size: "wide", label: "Rhythm spectrum" },
  { id: "facts", size: "sm", label: "Recording details" },
  { id: "emg", size: "wide", label: "Shoulder EMG" },
];

export function EcgExplorer() {
  const index = useAsset<DataIndex>(dataUrl("ecg", "index.json"));
  const first = index.data?.sessions[0]?.id ?? null;
  const session = useAsset<EcgSession>(first ? dataUrl("ecg", `${first}.json`) : null);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-12">
      <ModalityHeader
        current="ecg"
        sourceNote={index.data?.source.note}
        source={session.data?.source}
        device={session.data ? `${session.data.device.lead} · ${session.data.device.fs} Hz` : undefined}
      />
      {index.error && <p className="text-sm text-destructive">Couldn’t load the ECG data ({index.error}).</p>}
      {session.data ? <Dashboard session={session.data} /> : <div className="h-[60vh] animate-pulse rounded-3xl bg-muted" />}
    </div>
  );
}

function Dashboard({ session }: { session: EcgSession }) {
  const [windowStart, setWindowStart] = useState(0);
  const h = session.hrv.session;
  const moveWindow = (center: number) =>
    setWindowStart(Math.max(0, Math.min(session.durationS - WINDOW_S, center - WINDOW_S / 2)));

  const render = (item: WidgetItem) => {
    switch (item.id) {
      case "trace":
        return (
          <WidgetShell title="Raw → cleaned" note={`${windowStart.toFixed(0)}–${(windowStart + WINDOW_S).toFixed(0)} s · filtered 0.5–40 Hz, beats located`}>
            <TracePair session={session} start={windowStart} />
          </WidgetShell>
        );
      case "hr-now":
        return (
          <WidgetShell title="Heart rate">
            <BigNumber value={fmt(h.mean_hr_bpm, 0)} unit="bpm" sub={`range ${fmt(h.min_hr_bpm, 0)}–${fmt(h.max_hr_bpm, 0)}`} />
          </WidgetShell>
        );
      case "hrv":
        return (
          <WidgetShell title="Variability" note="time between beats">
            <Facts
              rows={[
                ["RMSSD", `${fmt(h.rmssd_ms, 0)} ms`],
                ["SDNN", `${fmt(h.sdnn_ms, 0)} ms`],
                ["pNN50", `${fmt(h.pnn50_pct, 0)}%`],
              ]}
            />
          </WidgetShell>
        );
      case "overview":
        return (
          <WidgetShell
            title="This excerpt"
            note="click to move the window · quality every 5 s"
            actions={
              <div className="flex shrink-0 gap-2.5 text-[11px]">
                <StatusBadge status="good" label="Clean" />
                <StatusBadge status="warning" label="Irregular" />
                <StatusBadge status="critical" label="Artefact" />
              </div>
            }
          >
            <Overview session={session} start={windowStart} onPick={moveWindow} />
          </WidgetShell>
        );
      case "hr":
        return (
          <WidgetShell title="Heart rate over time" note="one point per beat · hollow = irregular, left out">
            <HeartRateChart session={session} onPick={moveWindow} />
          </WidgetShell>
        );
      case "quality":
        return (
          <WidgetShell title="Signal quality">
            <div className="flex h-full flex-col justify-end gap-1">
              <p className="text-2xl">
                <StatusBadge status={session.quality.status} />
              </p>
              <p className="text-xs text-muted-foreground">
                {h.beats ?? "—"} beats · {fmt(h.artifact_pct, 1)}% left out
              </p>
            </div>
          </WidgetShell>
        );
      case "facts":
        return (
          <WidgetShell title="Recording">
            <Facts
              rows={[
                ["Record", session.subject.id],
                ["Excerpt", `${fmtClock(session.source?.windowStartS ?? 0)}–${fmtClock((session.source?.windowStartS ?? 0) + session.durationS)}`],
                ["ECG", `${session.device.fs} Hz · ${session.device.units}`],
                ["Also has", "Resp · EDA · EMG"],
                ["Licence", session.source?.license ?? "—"],
              ]}
            />
          </WidgetShell>
        );
      case "drive":
        return session.drive ? (
          <WidgetShell title="The whole drive" note={`${Math.round(session.drive.durationS / 60)} min · highlighted: the excerpt on this page`}>
            <DriveOverview drive={session.drive} windowStart={session.source?.windowStartS ?? 0} windowLength={session.durationS} />
          </WidgetShell>
        ) : null;
      case "resp":
        return session.companions ? (
          <WidgetShell title="Respiration" note={breathingNote(session.companions.resp, session.phases)}>
            <SeriesChart
              session={session}
              series={[{ key: "resp", label: "Chest expansion", color: "var(--series-1)", block: session.companions.resp }]}
            />
          </WidgetShell>
        ) : null;
      case "skin":
        return session.companions ? (
          <WidgetShell title="Skin conductance" note="rises with arousal · same excerpt">
            <SeriesChart
              session={session}
              series={[
                { key: "hand", label: "Hand", color: "var(--series-1)", block: session.companions.handGSR },
                { key: "foot", label: "Foot", color: "var(--series-2)", block: session.companions.footGSR },
              ]}
            />
          </WidgetShell>
        ) : null;
      case "emg":
        return session.companions ? (
          <WidgetShell title="Shoulder EMG" note="trapezius muscle activity · same excerpt">
            <SeriesChart
              session={session}
              series={[{ key: "emg", label: "EMG", color: "var(--series-1)", block: session.companions.emg }]}
            />
          </WidgetShell>
        ) : null;
      case "beat":
        return (
          <WidgetShell title="Average beat" note={`${session.averageBeat.n} beats · ±1 SD`}>
            <AverageBeat session={session} />
          </WidgetShell>
        );
      case "poincare":
        return (
          <WidgetShell
            title="Beat-to-beat map"
            note={`SD1 ${fmt(session.hrv.poincare.sd1_ms, 0)} · SD2 ${fmt(session.hrv.poincare.sd2_ms, 0)} ms`}
          >
            <PoincarePlot session={session} />
          </WidgetShell>
        );
      case "spectrum":
        return (
          <WidgetShell
            title="Rhythm spectrum"
            note={`LF/HF ${fmt(session.hrv.frequency.lf_hf_ratio, 2)}${session.hrv.frequency.shortRecord ? " · indicative (< 5 min)" : ""}`}
          >
            <Spectrum session={session} />
          </WidgetShell>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col gap-14">
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">Drag widgets by their title to rearrange.</p>
        <DraggableWidgetGrid items={WIDGETS} renderItem={render} maxColumns={4} cellSize={280} gap={14} />
      </div>

      <RequestAccess />

      <Link href="/thermal" className="self-start text-sm font-medium underline-offset-4 hover:underline">
        See the thermal data →
      </Link>
    </div>
  );
}

/** Raw on top, cleaned with beats below — the same window, stacked. */
function TracePair({ session, start }: { session: EcgSession; start: number }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const each = Math.max(90, Math.floor((size.height - 40) / 2));
  return (
    <div ref={ref} className="absolute inset-0 flex flex-col gap-1">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Raw</p>
      <EcgStrip session={session} start={start} trace="raw" width={size.width} height={each} />
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Cleaned · beats</p>
      <EcgStrip session={session} start={start} trace="filtered" width={size.width} height={each} />
    </div>
  );
}

function EcgStrip({
  session,
  start,
  trace,
  width,
  height,
}: {
  session: EcgSession;
  start: number;
  trace: "filtered" | "raw";
  width: number;
  height: number;
}) {
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { fs } = session.signal;
  const values = session.signal[trace];
  const beatsShown = trace === "filtered";
  const margin = { top: 6, right: 6, bottom: 20, left: 34 };

  // fixed y range per trace, so moving the window never rescales the beats.
  // Sized to the typical beat, not the extremes: one motion spike would
  // otherwise flatten every beat; spikes are clipped at the plot edge.
  const yDomain = useMemo(() => {
    const sorted = [...values].sort((a, b) => a - b);
    const q = (p: number) => sorted[Math.floor((sorted.length - 1) * p)];
    const beats = session.rPeaks.map((p) => values[p]).sort((a, b) => a - b);
    const typicalBeat = beats.length ? beats[Math.floor(beats.length / 2)] : q(0.99);
    const hi = Math.max(q(0.99), typicalBeat * 1.4);
    const lo = Math.min(q(0.01), -Math.abs(hi) * 0.4);
    return extent([lo, hi], 0.1);
  }, [values, session.rPeaks]);

  const i0 = Math.floor(start * fs);
  const i1 = Math.min(values.length, Math.ceil((start + WINDOW_S) * fs));
  const times = Array.from({ length: i1 - i0 }, (_, k) => (i0 + k) / fs);
  const x = linear([start, start + WINDOW_S], [margin.left, width - margin.right]);
  const y = linear(yDomain, [height - margin.bottom, margin.top]);
  const flagged = new Set(session.rr.t.filter((_, k) => !session.rr.valid[k]).map((t) => Math.round(t * fs)));
  const peaks = beatsShown ? session.rPeaks.filter((p) => p >= i0 && p < i1) : [];
  const hi = hover ? Math.round(hover.t * fs) : null;

  return (
    <div data-no-drag className="relative">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={niceTicks(start, start + WINDOW_S, 5)}
        yTicks={niceTicks(yDomain[0], yDomain[1], 3)}
        xFormat={(v) => `${v}s`}
        yFormat={(v) => v.toFixed(1)}
        ariaLabel={`${trace} ECG from ${start.toFixed(1)} to ${(start + WINDOW_S).toFixed(1)} seconds`}
        onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
        clip
      >
        {beatsShown &&
          session.qualityWindows
            .filter((w) => w.status !== "good" && w.endS > start && w.startS < start + WINDOW_S)
            .map((w) => (
              <rect
                key={w.startS}
                x={x(Math.max(start, w.startS))}
                y={y.range[1]}
                width={x(Math.min(start + WINDOW_S, w.endS)) - x(Math.max(start, w.startS))}
                height={y.range[0] - y.range[1]}
                fill={STATUS_COLOR[w.status]}
                opacity={0.09}
              />
            ))}
        <path
          d={linePath(times, values.slice(i0, i1), x, y)}
          fill="none"
          stroke={beatsShown ? "var(--series-1)" : "var(--viz-text-2)"}
          strokeWidth={1.4}
          strokeLinejoin="round"
        />
        {peaks.map((p) => (
          <circle
            key={p}
            cx={x(p / fs)}
            cy={y(values[p])}
            r={4}
            fill={flagged.has(p) ? "var(--card)" : "var(--series-1)"}
            stroke={flagged.has(p) ? "var(--viz-text)" : "var(--card)"}
            strokeWidth={2}
          />
        ))}
        {hover && <line x1={x(hover.t)} x2={x(hover.t)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />}
      </ChartFrame>
      <Tooltip at={hover?.at ?? null} containerWidth={width}>
        {hi !== null && hi < values.length && (
          <p className="tabular-nums">
            {hover!.t.toFixed(2)} s · {values[hi].toFixed(3)} mV
          </p>
        )}
      </Tooltip>
    </div>
  );
}

/** Whole recording: min/max envelope, events, the viewing window and quality. */
function Overview({ session, start, onPick }: { session: EcgSession; start: number; onPick: (t: number) => void }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { filtered } = session.signal;
  const { width } = size;
  const height = Math.max(90, size.height);
  const margin = { top: 14, right: 6, bottom: 40, left: 6 };
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear(extent(filtered, 0.05), [height - margin.bottom, margin.top]);

  // one min/max pair per pixel column keeps 7,500 samples cheap to draw
  const envelope = useMemo(() => {
    const cols = Math.max(1, Math.floor(x.range[1] - x.range[0]));
    const per = filtered.length / cols;
    let d = "";
    for (let c = 0; c < cols; c++) {
      const seg = filtered.slice(Math.floor(c * per), Math.floor((c + 1) * per));
      if (!seg.length) continue;
      const px = x.range[0] + c;
      d += `M${px},${y(Math.max(...seg)).toFixed(1)}L${px},${y(Math.min(...seg)).toFixed(1)}`;
    }
    return d;
  }, [filtered, x, y]);

  const stripY = height - margin.bottom + 6;
  const hovered = hover ? session.qualityWindows.find((w) => hover.t >= w.startS && hover.t < w.endS) : null;

  return (
    <div ref={ref} className="absolute inset-0">
      <div data-no-drag className="relative">
        <ChartFrame
          width={width}
          height={height}
          margin={margin}
          x={x}
          y={y}
          ariaLabel="Whole recording overview. Click to move the ECG window."
          onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
          onPick={onPick}
        >
          <path d={envelope} stroke="var(--viz-muted)" strokeWidth={1} fill="none" />
          <rect
            x={x(start)}
            y={margin.top}
            width={x(start + WINDOW_S) - x(start)}
            height={height - margin.bottom - margin.top}
            fill="var(--series-1)"
            fillOpacity={0.12}
            stroke="var(--series-1)"
            strokeWidth={1.5}
            rx={3}
          />
          {session.events.map((e) => (
            <g key={e.t}>
              <line x1={x(e.t)} x2={x(e.t)} y1={margin.top} y2={height - margin.bottom} stroke="var(--viz-text)" strokeWidth={1} />
              <text x={x(e.t) + 4} y={margin.top - 3} fontSize={10} fill="var(--viz-text-2)">
                {e.kind}
              </text>
            </g>
          ))}
          {session.qualityWindows.map((w) => (
            <rect
              key={w.startS}
              x={x(w.startS) + 1}
              y={stripY}
              width={Math.max(0, x(w.endS) - x(w.startS) - 2)}
              height={6}
              rx={3}
              fill={STATUS_COLOR[w.status]}
            />
          ))}
          <text x={x(0)} y={stripY + 22} fontSize={10.5} fill="var(--viz-muted)">
            0 s
          </text>
          <text x={x(session.durationS)} y={stripY + 22} textAnchor="end" fontSize={10.5} fill="var(--viz-muted)">
            {session.durationS} s
          </text>
        </ChartFrame>
        <Tooltip at={hover?.at ?? null} containerWidth={width}>
          {hovered && (
            <>
              <p className="font-medium tabular-nums">
                {hovered.startS}–{hovered.endS} s
              </p>
              <p className="text-muted-foreground">{hovered.message}</p>
            </>
          )}
        </Tooltip>
      </div>
    </div>
  );
}

function HeartRateChart({ session, onPick }: { session: EcgSession; onPick: (t: number) => void }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { t, ms, valid } = session.rr;
  const bpm = ms.map((v) => 60000 / v);
  const cleanT = t.filter((_, i) => valid[i]);
  const cleanBpm = bpm.filter((_, i) => valid[i]);
  const { width, height } = size;
  const margin = { top: 18, right: 8, bottom: 22, left: 34 };
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear(extent(cleanBpm, 0.25), [height - margin.bottom, margin.top]);
  const clampY = (v: number) => y(Math.min(y.domain[1], Math.max(y.domain[0], v)));
  const nearest = hover ? t.reduce((b, v, i) => (Math.abs(v - hover.t) < Math.abs(t[b] - hover.t) ? i : b), 0) : null;

  return (
    <div ref={ref} data-no-drag className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={niceTicks(0, session.durationS, 6)}
        yTicks={niceTicks(y.domain[0], y.domain[1], 4)}
        xFormat={(v) => `${v}s`}
        yFormat={(v) => v.toFixed(0)}
        yLabel="bpm"
        bands={session.phases.map((p, i) => ({ from: p.startS, to: p.endS, label: p.name, shaded: i % 2 === 1 }))}
        ariaLabel="Heart rate over the recording"
        onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
        onPick={onPick}
      >
        <path d={linePath(cleanT, cleanBpm, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" />
        {t.map((tv, i) =>
          valid[i] ? null : (
            <circle key={tv} cx={x(tv)} cy={clampY(bpm[i])} r={4} fill="var(--card)" stroke="var(--viz-text)" strokeWidth={1.5} />
          ),
        )}
        {nearest !== null && (
          <>
            <line x1={x(t[nearest])} x2={x(t[nearest])} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />
            <circle
              cx={x(t[nearest])}
              cy={clampY(bpm[nearest])}
              r={4.5}
              fill={valid[nearest] ? "var(--series-1)" : "var(--card)"}
              stroke={valid[nearest] ? "var(--card)" : "var(--viz-text)"}
              strokeWidth={2}
            />
          </>
        )}
      </ChartFrame>
      <Tooltip at={hover?.at ?? null} containerWidth={width}>
        {nearest !== null && (
          <>
            <p className="font-medium tabular-nums">
              {bpm[nearest].toFixed(0)} bpm at {t[nearest].toFixed(1)} s
            </p>
            <p className="tabular-nums text-muted-foreground">
              RR {ms[nearest].toFixed(0)} ms{valid[nearest] ? "" : " · irregular, left out"}
            </p>
          </>
        )}
      </Tooltip>
    </div>
  );
}

function AverageBeat({ session }: { session: EcgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const { tMs, mean, sd } = session.averageBeat;
  const { width, height } = size;
  const margin = { top: 6, right: 6, bottom: 22, left: 30 };
  const x = linear([tMs[0], tMs[tMs.length - 1]], [margin.left, width - margin.right]);
  const upper = mean.map((m, i) => m + sd[i]);
  const lower = mean.map((m, i) => m - sd[i]);
  const y = linear(extent([...upper, ...lower], 0.08), [height - margin.bottom, margin.top]);
  const band =
    linePath(tMs, upper, x, y) + linePath([...tMs].reverse(), [...lower].reverse(), x, y).replace(/^M/, "L") + "Z";

  return (
    <div ref={ref} className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={[-200, 0, 200, 400].filter((v) => v >= tMs[0] && v <= tMs[tMs.length - 1])}
        yTicks={niceTicks(y.domain[0], y.domain[1], 3)}
        xFormat={(v) => `${v}ms`}
        yFormat={(v) => v.toFixed(1)}
        ariaLabel="Average heartbeat with ±1 SD band"
      >
        <path d={band} fill="var(--series-1)" opacity={0.15} />
        <path d={linePath(tMs, mean, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} />
      </ChartFrame>
    </div>
  );
}

function PoincarePlot({ session }: { session: EcgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const clean = session.rr.ms.filter((_, i) => session.rr.valid[i]);
  const pts = clean.slice(0, -1).map((v, i) => [v, clean[i + 1]] as const);
  const side = Math.min(size.width, size.height);
  const margin = { top: 6, right: 6, bottom: 22, left: 36 };
  const dom = extent(clean, 0.12);
  const x = linear(dom, [margin.left, side - margin.right]);
  const y = linear(dom, [side - margin.bottom, margin.top]);
  const ticks = niceTicks(dom[0], dom[1], 3);

  return (
    <div ref={ref} className="absolute inset-0 flex justify-center">
      <div style={{ width: side }} data-no-drag className="relative">
        <ChartFrame
          width={side}
          height={side}
          margin={margin}
          x={x}
          y={y}
          xTicks={ticks}
          yTicks={ticks}
          xFormat={(v) => v.toFixed(0)}
          yFormat={(v) => v.toFixed(0)}
          ariaLabel="Each beat interval plotted against the next"
        >
          <line x1={x(dom[0])} y1={y(dom[0])} x2={x(dom[1])} y2={y(dom[1])} stroke="var(--viz-axis)" strokeWidth={1} />
          {pts.map(([a, b], i) => (
            <circle key={i} cx={x(a)} cy={y(b)} r={hover === i ? 5.5 : 4} fill="var(--series-1)" fillOpacity={0.75} stroke="var(--card)" strokeWidth={2} />
          ))}
          {pts.map(([a, b], i) => (
            <circle key={`hit${i}`} cx={x(a)} cy={y(b)} r={12} fill="transparent" onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} />
          ))}
        </ChartFrame>
        {hover !== null && (
          <p className="pointer-events-none absolute right-0 top-0 rounded-md border border-border bg-popover px-2 py-1 text-xs tabular-nums shadow">
            {pts[hover][0].toFixed(0)} → {pts[hover][1].toFixed(0)} ms
          </p>
        )}
      </div>
    </div>
  );
}

function Spectrum({ session }: { session: EcgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  if (!session.psd) return <p className="text-sm text-muted-foreground">Recording too short.</p>;
  // VLF (< 0.04 Hz) needs 5+ minutes of data and mostly reflects slow trends
  // here, which would dwarf the LF/HF bands — so the plot starts at LF.
  const keep = session.psd.freqs.map((f) => f >= 0.04);
  const freqs = session.psd.freqs.filter((_, i) => keep[i]);
  const power = session.psd.power.filter((_, i) => keep[i]);
  const { width, height } = size;
  const margin = { top: 16, right: 8, bottom: 22, left: 44 };
  const x = linear([0.04, 0.5], [margin.left, width - margin.right]);
  const y = linear([0, Math.max(...power) * 1.1], [height - margin.bottom, margin.top]);
  const area = `${linePath(freqs, power, x, y)}L${x(freqs[freqs.length - 1])},${y(0)}L${x(freqs[0])},${y(0)}Z`;

  return (
    <div ref={ref} className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={[0.1, 0.2, 0.3, 0.4, 0.5]}
        yTicks={niceTicks(0, y.domain[1], 3)}
        xFormat={(v) => `${v} Hz`}
        yFormat={(v) => v.toFixed(0)}
        bands={[
          { from: 0.04, to: 0.15, label: "LF", shaded: true },
          { from: 0.15, to: 0.4, label: "HF", shaded: false },
        ]}
        ariaLabel="Power spectrum of the beat-interval series"
      >
        <path d={area} fill="var(--series-1)" opacity={0.18} />
        <path d={linePath(freqs, power, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} />
      </ChartFrame>
    </div>
  );
}

const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

/** Breaths per minute in each phase, from upward crossings of the detrended trace. */
function breathingNote(resp: SeriesBlock, phases: EcgSession["phases"]) {
  const { fs, values } = resp;
  const win = Math.round(fs * 10);
  const detrended = values.map((v, i) => {
    const seg = values.slice(Math.max(0, i - win / 2), i + win / 2);
    return v - seg.reduce((a, b) => a + b, 0) / seg.length;
  });
  const rate = (a: number, b: number) => {
    let n = 0;
    let last = -Infinity;
    for (let i = Math.floor(a * fs) + 1; i < Math.min(detrended.length, b * fs); i++) {
      if (detrended[i - 1] < 0 && detrended[i] >= 0 && i - last > 1.5 * fs) {
        n++;
        last = i;
      }
    }
    return Math.round((n / (b - a)) * 60);
  };
  return phases.map((p) => `${p.name.toLowerCase()} ≈ ${rate(p.startS, p.endS)}/min`).join(" · ");
}

/** One or more companion signals over the excerpt, on a shared axis. */
function SeriesChart({
  session,
  series,
}: {
  session: EcgSession;
  series: { key: string; label: string; color: string; block: SeriesBlock }[];
}) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { width } = size;
  const legend = series.length > 1;
  const height = Math.max(80, size.height - (legend ? 20 : 0));
  const margin = { top: 16, right: 8, bottom: 22, left: 40 };
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear(extent(series.flatMap((s) => s.block.values), 0.08), [height - margin.bottom, margin.top]);
  const at = (b: SeriesBlock, t: number) => b.values[Math.min(b.values.length - 1, Math.max(0, Math.round(t * b.fs)))];

  return (
    <div ref={ref} data-no-drag className="absolute inset-0 flex flex-col">
      {legend && <Legend items={series.map((s) => ({ key: s.key, label: s.label, color: s.color }))} />}
      <div className="relative">
        <ChartFrame
          width={width}
          height={height}
          margin={margin}
          x={x}
          y={y}
          xTicks={niceTicks(0, session.durationS, 5)}
          yTicks={niceTicks(y.domain[0], y.domain[1], 3)}
          xFormat={(v) => `${v}s`}
          yFormat={(v) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1))}
          yLabel={series[0].block.units}
          bands={session.phases.map((p, i) => ({ from: p.startS, to: p.endS, label: p.name, shaded: i % 2 === 1 }))}
          ariaLabel={series.map((s) => s.label).join(" and ") + " over the excerpt"}
          onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
        >
          {series.map((s) => (
            <path
              key={s.key}
              d={linePath(s.block.values.map((_, i) => i / s.block.fs), s.block.values, x, y)}
              fill="none"
              stroke={s.color}
              strokeWidth={1.5}
              strokeLinejoin="round"
            />
          ))}
          {hover && <line x1={x(hover.t)} x2={x(hover.t)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />}
        </ChartFrame>
        <Tooltip at={hover?.at ?? null} containerWidth={width}>
          {hover && (
            <>
              <p className="mb-0.5 font-medium tabular-nums">{hover.t.toFixed(1)} s</p>
              {series.map((s) => (
                <p key={s.key} className="flex items-center justify-between gap-4 tabular-nums">
                  <span className="text-muted-foreground">{s.label}</span>
                  {at(s.block, hover.t).toFixed(2)} {s.block.units}
                </p>
              ))}
            </>
          )}
        </Tooltip>
      </div>
    </div>
  );
}

/** The whole original drive as two small multiples (heart rate, skin conductance). */
function DriveOverview({
  drive,
  windowStart,
  windowLength,
}: {
  drive: NonNullable<EcgSession["drive"]>;
  windowStart: number;
  windowLength: number;
}) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { width } = size;
  const each = Math.max(60, Math.floor((size.height - 4) / 2));
  const minutes = drive.durationS / 60;
  const t = drive.hr.map((_, i) => (i * drive.stepS) / 60);
  const hr = drive.hr.map((v) => (v === null ? NaN : v));
  const panels = [
    { key: "hr", label: "Heart rate", unit: "bpm", values: hr, top: true },
    { key: "eda", label: "Hand EDA", unit: "a.u.", values: drive.handGSR, top: false },
  ];
  const idx = hover ? Math.min(t.length - 1, Math.max(0, Math.round((hover.t * 60) / drive.stepS))) : null;
  const seg = hover ? drive.segments.find((s) => hover.t * 60 >= s.startS && hover.t * 60 < s.endS) : null;

  return (
    <div ref={ref} data-no-drag className="absolute inset-0 flex flex-col gap-1">
      {panels.map((p) => {
        const margin = { top: p.top ? 16 : 4, right: 8, bottom: p.top ? 4 : 20, left: 40 };
        const x = linear([0, minutes], [margin.left, width - margin.right]);
        const y = linear(extent(p.values.filter(Number.isFinite), 0.1), [each - margin.bottom, margin.top]);
        return (
          <div key={p.key} className="relative">
            <ChartFrame
              width={width}
              height={each}
              margin={margin}
              x={x}
              y={y}
              xTicks={p.top ? [] : niceTicks(0, minutes, 6)}
              yTicks={niceTicks(y.domain[0], y.domain[1], 2)}
              xFormat={(v) => `${v}m`}
              yFormat={(v) => v.toFixed(0)}
              yLabel={p.unit}
              bands={drive.segments.map((s, i) => ({
                from: s.startS / 60,
                to: s.endS / 60,
                label: p.top ? s.name : "",
                shaded: i % 2 === 1,
              }))}
              ariaLabel={`${p.label} across the whole drive`}
              onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
            >
              <rect
                x={x(windowStart / 60)}
                y={y.range[1]}
                width={x((windowStart + windowLength) / 60) - x(windowStart / 60)}
                height={y.range[0] - y.range[1]}
                fill="var(--series-1)"
                fillOpacity={0.14}
                stroke="var(--series-1)"
                strokeWidth={1}
              />
              <path d={linePath(t, p.values, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={1.5} strokeLinejoin="round" />
              {hover && <line x1={x(hover.t)} x2={x(hover.t)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />}
            </ChartFrame>
          </div>
        );
      })}
      <Tooltip at={hover?.at ?? null} containerWidth={width}>
        {idx !== null && (
          <>
            <p className="mb-0.5 font-medium tabular-nums">
              {t[idx].toFixed(1)} min{seg ? ` · ${seg.name}` : ""}
            </p>
            <p className="tabular-nums text-muted-foreground">
              {Number.isFinite(hr[idx]) ? `${hr[idx].toFixed(0)} bpm` : "—"} · EDA {drive.handGSR[idx]?.toFixed(2)}
            </p>
          </>
        )}
      </Tooltip>
    </div>
  );
}
