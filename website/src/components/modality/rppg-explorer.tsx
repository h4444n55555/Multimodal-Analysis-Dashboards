"use client";

import { cloneElement, isValidElement, useMemo, useState, type ReactElement } from "react";
import { useAsset } from "@/lib/use-json";
import { dataUrl, type DataIndex, type QualityStatus, type RppgMethod, type RppgSession } from "@/lib/sample-data";
import { ChartFrame, Legend, Tooltip, linePath, linear, niceTicks, extent, useSize } from "@/components/viz/chart";
import { ModalityHeader, StatusBadge, fmt } from "@/components/modality/kit";
import { BigNumber, WidgetShell } from "@/components/modality/widget";
import { RequestAccess } from "@/components/modality/request-access";
import { DraggableWidgetGrid, type WidgetItem } from "@/components/ui/draggable-widget-grid";
import { AboutData, Term } from "@/components/modality/explain";
import { ModalityDetails } from "@/components/modality/details";
import { CAPTIONS } from "@/lib/explanations";

const WINDOW_S = 10;
const STATUS_COLOR: Record<QualityStatus, string> = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
};
const METHOD_LABEL: Record<RppgMethod, string> = { pos: "POS", chrom: "CHROM", green: "Green" };
// Kept to what shows how clean the recording is (Lab 7 review).
const WIDGETS: WidgetItem[] = [
  { id: "pulse", size: "lg", label: "Face colour to pulse" },
  { id: "hr-now", size: "sm", label: "Heart rate" },
  { id: "quality", size: "sm", label: "Signal quality" },
  { id: "overview", size: "wide", label: "Recording overview and signal quality" },
  { id: "hr", size: "wide", label: "Heart rate against the oximeter" },
  { id: "beat", size: "wide", label: "Average pulse shape" },
];

export function RppgExplorer() {
  const index = useAsset<DataIndex>(dataUrl("rppg", "index.json"));
  const first = index.data?.sessions[0]?.id ?? null;
  const session = useAsset<RppgSession>(first ? dataUrl("rppg", `${first}.json`) : null);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-12">
      <ModalityHeader
        current="rppg"
        sourceNote={index.data?.source.note}
        device={session.data ? `${session.data.device.camera} · ${session.data.device.roi}` : undefined}
      />
      {index.error && <p className="text-sm text-destructive">Couldn’t load the rPPG data ({index.error}).</p>}
      {session.data ? <Dashboard session={session.data} /> : <div className="h-[60vh] animate-pulse rounded-3xl bg-muted" />}
    </div>
  );
}

function Dashboard({ session }: { session: RppgSession }) {
  const [windowStart, setWindowStart] = useState(0);
  // one extraction method on the dashboard; POS scores cleanest on this data
  const method: RppgMethod = "pos";
  const v = session.vitals;
  const refHr = useMemo(() => mean(session.track.reference), [session.track.reference]);
  const moveWindow = (center: number) =>
    setWindowStart(Math.max(0, Math.min(session.durationS - WINDOW_S, center - WINDOW_S / 2)));
  const snrLabel = labelOf(v.snr_db);

  const render = (item: WidgetItem) => {
    switch (item.id) {
      case "pulse":
        return (
          <WidgetShell
            title="Face colour → pulse"
            note={`${windowStart.toFixed(0)}–${(windowStart + WINDOW_S).toFixed(0)} s · beats marked`}
          >
            <PulsePair session={session} start={windowStart} method={method} />
          </WidgetShell>
        );
      case "hr-now":
        return (
          <WidgetShell title="Heart rate" note="from the camera alone">
            <BigNumber
              value={fmt(v.hr_bpm, 0)}
              unit="bpm"
              sub={refHr !== undefined ? `oximeter ${fmt(refHr, 0)} bpm · beats ${fmt(v.hr_beats_bpm, 0)}` : `from beats ${fmt(v.hr_beats_bpm, 0)}`}
            />
          </WidgetShell>
        );
      case "overview":
        return (
          <WidgetShell
            title="This recording"
            note="click to move the window · quality every 5 s"
            actions={
              <div className="flex shrink-0 gap-2.5 text-xs">
                <StatusBadge status="good" label="Good" />
                <StatusBadge status="warning" label="Fair" />
                <StatusBadge status="critical" label="Weak" />
              </div>
            }
          >
            <Overview session={session} method={method} start={windowStart} onPick={moveWindow} />
          </WidgetShell>
        );
      case "hr":
        return (
          <WidgetShell title="Heart rate over time" note="10 s window, updated every second">
            <HeartRateTrack session={session} method={method} onPick={moveWindow} />
          </WidgetShell>
        );
      case "quality":
        return (
          <WidgetShell title="Signal quality" note="pulse power vs. the rest of the band">
            <div className="flex h-full flex-col justify-end gap-1">
              <p className="text-2xl">
                <StatusBadge status={snrLabel.status} label={snrLabel.word} />
              </p>
              <p className="text-xs text-muted-foreground">
                <Term name="SNR" /> {fmt(v.snr_db, 1)} dB · below 1 dB nothing is reported
              </p>
            </div>
          </WidgetShell>
        );
      case "beat":
        return session.beatTemplate ? (
          <WidgetShell title="Average pulse" note={`upstroke ${fmt((v.sut_s ?? NaN) * 1000, 0)} ms · cycle ${fmt(session.beatTemplate.cycleS, 2)} s`}>
            <BeatTemplate session={session} />
          </WidgetShell>
        ) : null;
      default:
        return null;
    }
  };

  const withCaption = (item: WidgetItem) => {
    const el = render(item);
    return isValidElement(el) ? cloneElement(el as ReactElement<{ caption?: string }>, { caption: CAPTIONS.rppg[item.id] }) : el;
  };

  return (
    <div className="flex flex-col gap-14">
      <AboutData modality="rppg" />

      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">Drag widgets by their title to rearrange.</p>
        <DraggableWidgetGrid items={WIDGETS} renderItem={withCaption} maxColumns={4} cellSize={280} gap={14} />
      </div>

      <div className="flex flex-col gap-5">
        <ModalityDetails
          modality="rppg"
          title="rPPG"
          highlight={rppgHighlight(session, refHr)}
          source={session.source}
          facts={[
            ["Length", `${fmt(session.durationS, 0)} s`],
            ["Camera", session.device.camera],
            ["Measured from", session.device.roi],
            ["Method", "POS (plane orthogonal to skin)"],
            ["Beats found", `${session.beats.length} (${fmt(v.artifact_pct, 0)}% unreliable)`],
            ["Reference", session.reference ? "Fingertip pulse sensor" : "—"],
            ["Pipeline", "cvpr-lab (study code, untrained model unused)"],
          ]}
        />
        <RequestAccess />
      </div>
    </div>
  );
}

/** "…stayed within 0.2 bpm of a fingertip sensor (71.8 vs 71.8 bpm)" — like-for-like averages. */
function rppgHighlight(session: RppgSession, refHr?: number) {
  const mae = session.scores.pos.maeBpm;
  const camHr = mean(session.track.pos);
  if (refHr === undefined || mae === undefined || camHr === undefined) return undefined;
  return (
    <>
      Without touching the skin, the camera’s heart rate stayed within <strong>{mae.toFixed(1)} bpm</strong> of a
      fingertip sensor on average ({camHr.toFixed(1)} vs {refHr.toFixed(1)} bpm).
    </>
  );
}

/** Green channel on top (what the camera saw), extracted pulse below. */
function PulsePair({ session, start, method }: { session: RppgSession; start: number; method: RppgMethod }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const each = Math.max(90, Math.floor((size.height - 40) / 2));
  return (
    <div ref={ref} className="absolute inset-0 flex flex-col gap-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Green channel · face average</p>
      <GreenStrip session={session} start={start} width={size.width} height={each} />
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Pulse{session.reference ? " · dashed = fingertip oximeter" : ""}
      </p>
      <PulseStrip session={session} start={start} method={method} width={size.width} height={each} />
    </div>
  );
}

function windowIdx(fs: number, n: number, start: number) {
  const i0 = Math.max(0, Math.floor(start * fs));
  const i1 = Math.min(n, Math.ceil((start + WINDOW_S) * fs));
  return { i0, i1, times: Array.from({ length: Math.max(0, i1 - i0) }, (_, k) => (i0 + k) / fs) };
}

function GreenStrip({ session, start, width, height }: { session: RppgSession; start: number; width: number; height: number }) {
  const { fs, g } = session.rgb;
  const margin = { top: 6, right: 6, bottom: 20, left: 44 };
  const { i0, i1, times } = windowIdx(fs, g.length, start);
  const seg = g.slice(i0, i1);
  const x = linear([start, start + WINDOW_S], [margin.left, width - margin.right]);
  const y = linear(extent(seg, 0.1), [height - margin.bottom, margin.top]);
  return (
    <ChartFrame
      width={width}
      height={height}
      margin={margin}
      x={x}
      y={y}
      xTicks={niceTicks(start, start + WINDOW_S, 5)}
      yTicks={niceTicks(y.domain[0], y.domain[1], 2)}
      xFormat={(v) => `${v}s`}
      yFormat={(v) => v.toFixed(1)}
      ariaLabel={`Average green level of the face from ${start.toFixed(0)} to ${(start + WINDOW_S).toFixed(0)} seconds`}
    >
      <path d={linePath(times, seg, x, y)} fill="none" stroke="var(--series-3)" strokeWidth={1.4} strokeLinejoin="round" />
    </ChartFrame>
  );
}

function PulseStrip({
  session,
  start,
  method,
  width,
  height,
}: {
  session: RppgSession;
  start: number;
  method: RppgMethod;
  width: number;
  height: number;
}) {
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const wave = session.waves[method];
  const fs = session.rgb.fs;
  const margin = { top: 6, right: 6, bottom: 20, left: 44 };
  const { i0, i1, times } = windowIdx(fs, wave.length, start);
  const x = linear([start, start + WINDOW_S], [margin.left, width - margin.right]);
  const y = linear([-3, 3], [height - margin.bottom, margin.top]);
  const beats = method === "pos" ? session.beats.filter((b) => b >= i0 && b < i1) : [];
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
        yTicks={[-2, 0, 2]}
        xFormat={(v) => `${v}s`}
        yFormat={(v) => v.toFixed(0)}
        ariaLabel={`${METHOD_LABEL[method]} pulse waveform from ${start.toFixed(0)} to ${(start + WINDOW_S).toFixed(0)} seconds`}
        onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
        clip
      >
        {session.quality
          .filter((q) => q.status !== "good" && q.endS > start && q.startS < start + WINDOW_S)
          .map((q) => (
            <rect
              key={q.startS}
              x={x(Math.max(start, q.startS))}
              y={y.range[1]}
              width={x(Math.min(start + WINDOW_S, q.endS)) - x(Math.max(start, q.startS))}
              height={y.range[0] - y.range[1]}
              fill={STATUS_COLOR[q.status]}
              opacity={0.09}
            />
          ))}
        {session.reference && (
          <path
            d={linePath(times, session.reference.values.slice(i0, i1), x, y)}
            fill="none"
            stroke="var(--viz-text-2)"
            strokeWidth={1.2}
            strokeDasharray="4 3"
          />
        )}
        <path d={linePath(times, wave.slice(i0, i1), x, y)} fill="none" stroke="var(--series-1)" strokeWidth={1.8} strokeLinejoin="round" />
        {beats.map((b) => (
          <circle key={b} cx={x(b / fs)} cy={y(wave[b])} r={4} fill="var(--series-1)" stroke="var(--card)" strokeWidth={2} />
        ))}
        {hover && <line x1={x(hover.t)} x2={x(hover.t)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />}
      </ChartFrame>
      <Tooltip at={hover?.at ?? null} containerWidth={width}>
        {hi !== null && hi < wave.length && (
          <p className="tabular-nums">
            {hover!.t.toFixed(2)} s · pulse {wave[hi].toFixed(2)}
            {session.reference ? ` · oximeter ${session.reference.values[hi]?.toFixed(2)}` : ""}
          </p>
        )}
      </Tooltip>
    </div>
  );
}

/** Whole recording: pulse envelope, phases, the viewing window and quality. */
function Overview({
  session,
  method,
  start,
  onPick,
}: {
  session: RppgSession;
  method: RppgMethod;
  start: number;
  onPick: (t: number) => void;
}) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const wave = session.waves[method];
  const { width } = size;
  const height = Math.max(90, size.height);
  const margin = { top: 14, right: 6, bottom: 40, left: 6 };
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear([-3.5, 3.5], [height - margin.bottom, margin.top]);

  const envelope = useMemo(() => {
    const cols = Math.max(1, Math.floor(x.range[1] - x.range[0]));
    const per = wave.length / cols;
    let d = "";
    for (let c = 0; c < cols; c++) {
      const seg = wave.slice(Math.floor(c * per), Math.floor((c + 1) * per));
      if (!seg.length) continue;
      const px = x.range[0] + c;
      const clampY = (v: number) => y(Math.max(-3.5, Math.min(3.5, v)));
      d += `M${px},${clampY(Math.max(...seg)).toFixed(1)}L${px},${clampY(Math.min(...seg)).toFixed(1)}`;
    }
    return d;
  }, [wave, x, y]);

  const stripY = height - margin.bottom + 6;
  const hovered = hover ? session.quality.find((q) => hover.t >= q.startS && hover.t < q.endS) : null;

  return (
    <div ref={ref} className="absolute inset-0">
      <div data-no-drag className="relative">
        <ChartFrame
          width={width}
          height={height}
          margin={margin}
          x={x}
          y={y}
          bands={session.phases.map((p, i) => ({ from: p.startS, to: p.endS, label: p.name, shaded: i % 2 === 1 }))}
          ariaLabel="Whole recording overview. Click to move the pulse window."
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
          {session.quality.map((q) => (
            <rect
              key={q.startS}
              x={x(q.startS) + 1}
              y={stripY}
              width={Math.max(0, x(q.endS) - x(q.startS) - 2)}
              height={6}
              rx={3}
              fill={STATUS_COLOR[q.status]}
            />
          ))}
          <text x={x(0)} y={stripY + 22} fontSize={12} fill="var(--viz-muted)">
            0 s
          </text>
          <text x={x(session.durationS)} y={stripY + 22} textAnchor="end" fontSize={12} fill="var(--viz-muted)">
            {Math.round(session.durationS)} s
          </text>
        </ChartFrame>
        <Tooltip at={hover?.at ?? null} containerWidth={width}>
          {hovered && (
            <>
              <p className="font-medium tabular-nums">
                {hovered.startS}–{hovered.endS} s
              </p>
              <p className="text-muted-foreground">
                {hovered.label} signal · {hovered.snrDb === null ? "—" : `${hovered.snrDb} dB`}
              </p>
            </>
          )}
        </Tooltip>
      </div>
    </div>
  );
}

function HeartRateTrack({ session, method, onPick }: { session: RppgSession; method: RppgMethod; onPick: (t: number) => void }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { t, reference } = session.track;
  const est = session.track[method];
  const series = [
    { key: "cam", label: `Camera (${METHOD_LABEL[method]})`, color: "var(--series-1)", values: est },
    ...(session.reference ? [{ key: "ref", label: "Fingertip oximeter", color: "var(--viz-text-2)", values: reference }] : []),
  ];
  const { width } = size;
  const height = Math.max(80, size.height - 20);
  const margin = { top: 18, right: 8, bottom: 22, left: 34 };
  const all = series.flatMap((s) => s.values).filter((v): v is number => v !== null);
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear(extent(all, 0.3), [height - margin.bottom, margin.top]);
  const nearest = hover ? t.reduce((b, v, i) => (Math.abs(v - hover.t) < Math.abs(t[b] - hover.t) ? i : b), 0) : null;
  const nums = (vals: (number | null)[]) => vals.map((v) => (v === null ? NaN : v));

  return (
    <div ref={ref} data-no-drag className="absolute inset-0 flex flex-col">
      <Legend items={series.map((s) => ({ key: s.key, label: s.label, color: s.color }))} />
      <div className="relative">
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
          ariaLabel="Heart rate from the camera and from the fingertip oximeter over the recording"
          onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
          onPick={onPick}
        >
          {session.reference && (
            <path d={linePath(t, nums(reference), x, y)} fill="none" stroke="var(--viz-text-2)" strokeWidth={1.5} strokeDasharray="4 3" />
          )}
          <path d={linePath(t, nums(est), x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" />
          {nearest !== null && (
            <line x1={x(t[nearest])} x2={x(t[nearest])} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />
          )}
        </ChartFrame>
        <Tooltip at={hover?.at ?? null} containerWidth={width}>
          {nearest !== null && (
            <>
              <p className="mb-0.5 font-medium tabular-nums">{t[nearest].toFixed(0)} s</p>
              <p className="flex justify-between gap-4 tabular-nums">
                <span className="text-muted-foreground">Camera</span>
                {fmt(est[nearest] ?? undefined, 0)} bpm
              </p>
              {session.reference && (
                <p className="flex justify-between gap-4 tabular-nums">
                  <span className="text-muted-foreground">Oximeter</span>
                  {fmt(reference[nearest] ?? undefined, 0)} bpm
                </p>
              )}
              <p className="flex justify-between gap-4 tabular-nums">
                <span className="text-muted-foreground">Quality</span>
                {fmt(session.track.snrDb[nearest] ?? undefined, 1)} dB
              </p>
            </>
          )}
        </Tooltip>
      </div>
    </div>
  );
}

function BeatTemplate({ session }: { session: RppgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const tpl = session.beatTemplate!;
  const cycleMs = tpl.cycleS * 1000;
  const tMs = tpl.values.map((_, i) => (i / (tpl.values.length - 1)) * cycleMs);
  const { width, height } = size;
  const margin = { top: 6, right: 6, bottom: 22, left: 28 };
  const x = linear([0, cycleMs], [margin.left, width - margin.right]);
  const y = linear([-0.05, 1.08], [height - margin.bottom, margin.top]);
  const area = `${linePath(tMs, tpl.values, x, y)}L${x(cycleMs)},${y(0)}L${x(0)},${y(0)}Z`;
  return (
    <div ref={ref} className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={niceTicks(0, cycleMs, 3)}
        yTicks={[0, 0.5, 1]}
        xFormat={(v) => `${v}ms`}
        yFormat={(v) => v.toFixed(1)}
        ariaLabel="Average pulse shape over one heartbeat"
      >
        <path d={area} fill="var(--series-1)" opacity={0.15} />
        <path d={linePath(tMs, tpl.values, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} />
      </ChartFrame>
    </div>
  );
}

function mean(vals: (number | null)[]) {
  const ok = vals.filter((v): v is number => v !== null && Number.isFinite(v));
  return ok.length ? ok.reduce((a, b) => a + b, 0) / ok.length : undefined;
}

/** The same thresholds as cvprlab.vitals.quality_label. */
function labelOf(snr?: number): { status: QualityStatus; word: string } {
  if (snr === undefined) return { status: "critical", word: "Measuring" };
  if (snr >= 6) return { status: "good", word: "Good" };
  if (snr >= 3) return { status: "warning", word: "Fair" };
  if (snr >= 1) return { status: "critical", word: "Weak" };
  return { status: "critical", word: "Not a pulse" };
}
