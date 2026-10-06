"use client";

import { cloneElement, isValidElement, useMemo, useState, type ReactElement } from "react";
import { useAsset } from "@/lib/use-json";
import { dataUrl, type DataIndex, type EcgSession, type QualityStatus } from "@/lib/sample-data";
import { ChartFrame, Tooltip, linePath, linear, niceTicks, extent, useSize } from "@/components/viz/chart";
import { ModalityHeader, StatusBadge, fmt } from "@/components/modality/kit";
import { BigNumber, WidgetShell } from "@/components/modality/widget";
import { RequestAccess } from "@/components/modality/request-access";
import { DraggableWidgetGrid, type WidgetItem } from "@/components/ui/draggable-widget-grid";
import { AboutData } from "@/components/modality/explain";
import { ModalityDetails } from "@/components/modality/details";
import { CAPTIONS } from "@/lib/explanations";

const WINDOW_S = 10;
const STATUS_COLOR: Record<QualityStatus, string> = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
};

// Kept to what shows how clean the recording is (Lab 7 review).
const WIDGETS: WidgetItem[] = [
  { id: "trace", size: "lg", label: "Raw and cleaned ECG" },
  { id: "hr-now", size: "sm", label: "Mean heart rate" },
  { id: "quality", size: "sm", label: "Signal quality" },
  { id: "overview", size: "wide", label: "Excerpt overview and signal quality" },
  { id: "hr", size: "wide", label: "Heart rate over time" },
  { id: "beat", size: "wide", label: "Average heartbeat" },
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
      case "overview":
        return (
          <WidgetShell
            title="This excerpt"
            note="click to move the window · quality every 5 s"
            actions={
              <div className="flex shrink-0 gap-2.5 text-xs">
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
      case "beat":
        return (
          <WidgetShell title="Average beat" note={`${session.averageBeat.n} beats · ±1 SD`}>
            <AverageBeat session={session} />
          </WidgetShell>
        );
      default:
        return null;
    }
  };

  const withCaption = (item: WidgetItem) => {
    const el = render(item);
    return isValidElement(el) ? cloneElement(el as ReactElement<{ caption?: string }>, { caption: CAPTIONS.ecg[item.id] }) : el;
  };

  return (
    <div className="flex flex-col gap-14">
      <AboutData modality="ecg" />

      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">Drag widgets by their title to rearrange.</p>
        <DraggableWidgetGrid items={WIDGETS} renderItem={withCaption} maxColumns={4} cellSize={280} gap={14} />
      </div>

      <div className="flex flex-col gap-5">
        <ModalityDetails
          modality="ecg"
          title="ECG"
          highlight={ecgHighlight(session)}
          source={session.source}
          facts={[
            ["Record", session.subject.id],
            [
              "Excerpt",
              `${fmtClock(session.source?.windowStartS ?? 0)}–${fmtClock((session.source?.windowStartS ?? 0) + session.durationS)}` +
                (session.drive ? ` of the full ${Math.round(session.drive.durationS / 60)}-minute drive` : ""),
            ],
            ["Lead", session.device.lead],
            ["Sampling", `${session.device.fs} Hz · ${session.device.units}`],
            ["Beats found", `${h.beats ?? "—"} (${fmt(h.artifact_pct, 1)}% left out)`],
            ["Also recorded", "Breathing · skin conductance · shoulder EMG"],
            ["Licence", session.source?.license ?? "—"],
          ]}
        />
        <RequestAccess />
      </div>
    </div>
  );
}

/** "Heart rate went from 66 bpm at rest to 90 bpm in the city…" — from the phase metrics. */
function ecgHighlight(session: EcgSession) {
  const [first, second] = session.phases;
  const a = first && session.hrv.phases[first.name];
  const b = second && session.hrv.phases[second.name];
  if (a?.mean_hr_bpm === undefined || b?.mean_hr_bpm === undefined) return undefined;
  const label = (n: string) => (n.toLowerCase() === "rest" ? "at rest" : `during ${n.toLowerCase()} driving`);
  return (
    <>
      Heart rate went from <strong>{Math.round(a.mean_hr_bpm)} bpm</strong> {label(first.name)} to{" "}
      <strong>{Math.round(b.mean_hr_bpm)} bpm</strong> {label(second.name)}
      {a.rmssd_ms !== undefined && b.rmssd_ms !== undefined && (
        <>
          , and beat-to-beat variation fell from <strong>{Math.round(a.rmssd_ms)}</strong> to{" "}
          <strong>{Math.round(b.rmssd_ms)} ms</strong>
        </>
      )}
      .
    </>
  );
}

const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

/** Raw on top, cleaned with beats below — the same window, stacked. */
function TracePair({ session, start }: { session: EcgSession; start: number }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const each = Math.max(90, Math.floor((size.height - 40) / 2));
  return (
    <div ref={ref} className="absolute inset-0 flex flex-col gap-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Raw</p>
      <EcgStrip session={session} start={start} trace="raw" width={size.width} height={each} />
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Cleaned · beats</p>
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
              <text x={x(e.t) + 4} y={margin.top - 3} fontSize={12} fill="var(--viz-text-2)">
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
          <text x={x(0)} y={stripY + 22} fontSize={12} fill="var(--viz-muted)">
            0 s
          </text>
          <text x={x(session.durationS)} y={stripY + 22} textAnchor="end" fontSize={12} fill="var(--viz-muted)">
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
