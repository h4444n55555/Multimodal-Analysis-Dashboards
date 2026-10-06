"use client";

import { cloneElement, isValidElement, useMemo, useState, type ReactElement } from "react";
import { useAsset } from "@/lib/use-json";
import { dataUrl, type DataIndex, type EmgChannel, type EmgSession, type QualityStatus } from "@/lib/sample-data";
import { ChartFrame, Tooltip, linePath, linear, niceTicks, useSize } from "@/components/viz/chart";
import { COLORMAPS } from "@/components/viz/colormap";
import { ModalityHeader, StatusBadge, fmt } from "@/components/modality/kit";
import { BigNumber, WidgetShell } from "@/components/modality/widget";
import { RequestAccess } from "@/components/modality/request-access";
import { DraggableWidgetGrid, type WidgetItem } from "@/components/ui/draggable-widget-grid";
import { AboutData } from "@/components/modality/explain";
import { ModalityDetails } from "@/components/modality/details";
import { CAPTIONS } from "@/lib/explanations";

const STATUS_COLOR: Record<QualityStatus, string> = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
};

// Same quality-first layout as the other dashboards.
const WIDGETS: WidgetItem[] = [
  { id: "trace", size: "lg", label: "Raw and cleaned EMG" },
  { id: "activation", size: "sm", label: "Activation" },
  { id: "quality", size: "sm", label: "Signal quality" },
  { id: "envelope", size: "wide", label: "Muscle activity over time" },
  { id: "electrodes", size: "wide", label: "All electrodes" },
  { id: "spectrum", size: "wide", label: "Frequency content" },
];

export function EmgExplorer() {
  const index = useAsset<DataIndex>(dataUrl("emg", "index.json"));
  const first = index.data?.sessions[0]?.id ?? null;
  const session = useAsset<EmgSession>(first ? dataUrl("emg", `${first}.json`) : null);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-12">
      <ModalityHeader
        current="emg"
        sourceNote={index.data?.source.note}
        device={session.data ? `${session.data.channels.length} surface electrodes · ${session.data.device.fs} Hz` : undefined}
      />
      {index.error && <p className="text-sm text-destructive">Couldn’t load the EMG data ({index.error}).</p>}
      {session.data ? <Dashboard session={session.data} /> : <div className="h-[60vh] animate-pulse rounded-3xl bg-muted" />}
    </div>
  );
}

function Dashboard({ session }: { session: EmgSession }) {
  const q = session.quality;
  const main = session.channels.find((c) => c.name === session.mainChannel);
  const factor = 10 ** (q.snrDb / 20);

  const render = (item: WidgetItem) => {
    switch (item.id) {
      case "trace":
        return (
          <WidgetShell title="Raw → cleaned" note={`electrode ${session.mainChannel} · filtered 20–450 Hz, ${session.lineHz} Hz hum removed`}>
            <TracePair session={session} />
          </WidgetShell>
        );
      case "activation":
        return (
          <WidgetShell title="Activation" note={`electrode ${session.mainChannel}`}>
            <BigNumber
              value={`${fmt(factor, 1)}×`}
              unit="stronger"
              sub={main ? `${fmt(main.restRms, 0)} µV at rest → ${fmt(main.activeRms, 0)} µV in a fist` : undefined}
            />
          </WidgetShell>
        );
      case "quality":
        return (
          <WidgetShell title="Signal quality">
            <div className="flex h-full flex-col justify-end gap-1">
              <p className="text-2xl">
                <StatusBadge status={q.status} />
              </p>
              <p className="text-xs text-muted-foreground">
                {q.goodChannels} of {q.totalChannels} electrodes clean · mains hum {fmt(q.lineSharePct, 0)}% before filtering
              </p>
            </div>
          </WidgetShell>
        );
      case "envelope":
        return (
          <WidgetShell
            title="Muscle activity over time"
            note="RMS in 100 ms steps · quality every second"
            actions={
              <div className="flex shrink-0 gap-2.5 text-xs">
                <StatusBadge status="good" label="Clean" />
                <StatusBadge status="warning" label="Hum" />
                <StatusBadge status="critical" label="Overload" />
              </div>
            }
          >
            <Envelope session={session} />
          </WidgetShell>
        );
      case "electrodes":
        return (
          <WidgetShell title="All electrodes" note="fist vs rest, per electrode">
            <ElectrodeMap session={session} />
          </WidgetShell>
        );
      case "spectrum":
        return (
          <WidgetShell title="Frequency content" note={`during the fist · median ${fmt(session.psd.medianHz, 0)} Hz`}>
            <Spectrum session={session} />
          </WidgetShell>
        );
      default:
        return null;
    }
  };

  const withCaption = (item: WidgetItem) => {
    const el = render(item);
    return isValidElement(el) ? cloneElement(el as ReactElement<{ caption?: string }>, { caption: CAPTIONS.emg[item.id] }) : el;
  };

  return (
    <div className="flex flex-col gap-14">
      <AboutData modality="emg" />

      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">Drag widgets by their title to rearrange.</p>
        <DraggableWidgetGrid items={WIDGETS} renderItem={withCaption} maxColumns={4} cellSize={280} gap={14} />
      </div>

      <div className="flex flex-col gap-5">
        <ModalityDetails
          modality="emg"
          title="EMG"
          highlight={
            main ? (
              <>
                Making a fist raised the signal on electrode {session.mainChannel} from{" "}
                <strong>{fmt(main.restRms, 0)} µV</strong> to <strong>{fmt(main.activeRms, 0)} µV</strong>, about{" "}
                <strong>{fmt(factor, 1)}×</strong>, and all {q.totalChannels} electrodes passed the quality checks.
              </>
            ) : undefined
          }
          source={session.source}
          facts={[
            ["Participant", session.subject.id],
            ["Electrodes", `${session.channels.length} · ${session.device.placement.toLowerCase()}`],
            ["Sampling", `${session.device.fs} Hz`],
            ["Recordings", "5 s rest + 5 s hand close"],
            ["Shown electrode", `${session.mainChannel} (strongest forearm response)`],
            ["Mains frequency", `${session.lineHz} Hz`],
            ["Licence", session.source?.license ?? "—"],
          ]}
        />
        <RequestAccess />
      </div>
    </div>
  );
}

const bands = (session: EmgSession) =>
  session.phases.map((p, i) => ({ from: p.startS, to: p.endS, label: p.name, shaded: i % 2 === 1 }));

/** Raw on top, cleaned below, over the whole 10 s. */
function TracePair({ session }: { session: EmgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const each = Math.max(90, Math.floor((size.height - 40) / 2));
  return (
    <div ref={ref} className="absolute inset-0 flex flex-col gap-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Raw</p>
      <Strip session={session} trace="raw" width={size.width} height={each} />
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Cleaned</p>
      <Strip session={session} trace="clean" width={size.width} height={each} />
    </div>
  );
}

function Strip({ session, trace, width, height }: { session: EmgSession; trace: "raw" | "clean"; width: number; height: number }) {
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { fs } = session.signal;
  const values = session.signal[trace];
  const margin = { top: 16, right: 6, bottom: 20, left: 40 };
  // symmetric range around zero, sized to the contraction so the rest looks as quiet as it is
  const lim = useMemo(() => {
    const a = values.map(Math.abs).sort((p, q) => p - q);
    return a[Math.floor((a.length - 1) * 0.995)] * 1.1;
  }, [values]);
  // the centre of the raw trace is its DC offset; plot it around its median
  const offset = useMemo(() => {
    if (trace === "clean") return 0;
    const s = [...values].sort((p, q) => p - q);
    return s[Math.floor(s.length / 2)];
  }, [values, trace]);
  const rawLim = useMemo(() => {
    if (trace === "clean") return lim;
    const a = values.map((v) => Math.abs(v - offset)).sort((p, q) => p - q);
    return a[Math.floor((a.length - 1) * 0.995)] * 1.1;
  }, [values, offset, trace, lim]);
  const span = trace === "clean" ? lim : rawLim;
  const times = useMemo(() => values.map((_, i) => i / fs), [values, fs]);
  const centred = useMemo(() => values.map((v) => v - offset), [values, offset]);
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear([-span, span], [height - margin.bottom, margin.top]);
  const hi = hover ? Math.min(values.length - 1, Math.max(0, Math.round(hover.t * fs))) : null;

  return (
    <div data-no-drag className="relative">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={niceTicks(0, session.durationS, 5)}
        yTicks={niceTicks(-span, span, 2)}
        xFormat={(v) => `${v}s`}
        yFormat={(v) => v.toFixed(0)}
        yLabel="µV"
        bands={bands(session)}
        ariaLabel={`${trace === "raw" ? "Raw" : "Cleaned"} EMG from electrode ${session.mainChannel}`}
        onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
        clip
      >
        <path
          d={linePath(times, centred, x, y)}
          fill="none"
          stroke={trace === "clean" ? "var(--series-1)" : "var(--viz-text-2)"}
          strokeWidth={0.8}
          strokeLinejoin="round"
        />
        {hover && <line x1={x(hover.t)} x2={x(hover.t)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />}
      </ChartFrame>
      <Tooltip at={hover?.at ?? null} containerWidth={width}>
        {hi !== null && (
          <p className="tabular-nums">
            {hover!.t.toFixed(2)} s · {centred[hi].toFixed(1)} µV
          </p>
        )}
      </Tooltip>
    </div>
  );
}

/** RMS envelope with the 1-second quality strip underneath. */
function Envelope({ session }: { session: EmgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ t: number; at: { x: number; y: number } } | null>(null);
  const { t, uv } = session.envelope;
  const { width } = size;
  const height = Math.max(100, size.height);
  const margin = { top: 18, right: 8, bottom: 40, left: 40 };
  const x = linear([0, session.durationS], [margin.left, width - margin.right]);
  const y = linear([0, Math.max(...uv) * 1.1], [height - margin.bottom, margin.top]);
  const area = `${linePath(t, uv, x, y)}L${x(t[t.length - 1])},${y(0)}L${x(t[0])},${y(0)}Z`;
  const stripY = height - margin.bottom + 18;
  const nearest = hover ? t.reduce((b, v, i) => (Math.abs(v - hover.t) < Math.abs(t[b] - hover.t) ? i : b), 0) : null;
  const win = hover ? session.qualityWindows.find((w) => hover.t >= w.startS && hover.t < w.endS) : null;

  return (
    <div ref={ref} data-no-drag className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={niceTicks(0, session.durationS, 5)}
        yTicks={niceTicks(0, y.domain[1], 3)}
        xFormat={(v) => `${v}s`}
        yFormat={(v) => v.toFixed(0)}
        yLabel="µV"
        bands={bands(session)}
        ariaLabel="Muscle activity (RMS) over the recording"
        onHover={(v, px) => setHover(v === null || !px ? null : { t: v, at: px })}
      >
        <path d={area} fill="var(--series-1)" opacity={0.18} />
        <path d={linePath(t, uv, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" />
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
        {nearest !== null && (
          <line x1={x(t[nearest])} x2={x(t[nearest])} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-muted)" strokeWidth={1} />
        )}
      </ChartFrame>
      <Tooltip at={hover?.at ?? null} containerWidth={width}>
        {nearest !== null && (
          <>
            <p className="font-medium tabular-nums">
              {t[nearest].toFixed(2)} s · {uv[nearest].toFixed(1)} µV
            </p>
            {win && <p className="text-muted-foreground">{win.message}</p>}
          </>
        )}
      </Tooltip>
    </div>
  );
}

/** Four rings of electrodes as rows, coloured by fist-vs-rest strength. */
function ElectrodeMap({ session }: { session: EmgSession }) {
  const [hover, setHover] = useState<EmgChannel | null>(null);
  const rings = [1, 2, 3, 4].map((r) => session.channels.filter((c) => c.ring === r).sort((a, b) => a.pos - b.pos));
  const ringLabel = ["Forearm ring 1", "Forearm ring 2", "Wrist ring 1", "Wrist ring 2"];
  const dbs = session.channels.map((c) => c.ratioDb);
  const lo = Math.min(0, ...dbs);
  const hi = Math.max(...dbs);
  const lut = COLORMAPS.inferno.lut;
  const rgbOf = (db: number) => {
    const k = Math.round(Math.max(0, Math.min(1, (db - lo) / (hi - lo || 1))) * 200) + 40; // skip the near-black end
    return [lut[k * 3], lut[k * 3 + 1], lut[k * 3 + 2]];
  };
  const colour = (db: number) => `rgb(${rgbOf(db).join(", ")})`;
  // dark cells get white labels, light cells black, so every name stays readable
  const ink = (db: number) => {
    const [r, g, b] = rgbOf(db);
    return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? "rgba(0,0,0,0.85)" : "rgba(255,255,255,0.95)";
  };

  return (
    <div data-no-drag className="flex h-full flex-col justify-center gap-2">
      {rings.map((row, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="w-28 shrink-0 text-xs text-muted-foreground">{ringLabel[i]}</span>
          <div className="grid flex-1 gap-1.5" style={{ gridTemplateColumns: "repeat(8, minmax(0, 1fr))" }}>
            {row.map((c) => (
              <button
                key={c.name}
                type="button"
                onPointerEnter={() => setHover(c)}
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover(c)}
                onBlur={() => setHover(null)}
                aria-label={`${c.name}: ${c.ratioDb} dB stronger in a fist, ${c.status}`}
                className="flex h-8 items-center justify-center rounded-md text-xs font-medium"
                style={{
                  background: colour(c.ratioDb),
                  color: ink(c.ratioDb),
                  outline: c.status === "good" ? "none" : `2px solid ${STATUS_COLOR[c.status]}`,
                  outlineOffset: 1,
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="w-28 shrink-0" />
        {hover ? (
          <span className="tabular-nums">
            <strong className="text-foreground">{hover.name}</strong> · rest {hover.restRms} µV → fist {hover.activeRms} µV ({hover.ratioDb > 0 ? "+" : ""}
            {hover.ratioDb} dB) · hum {hover.lineSharePct}%
          </span>
        ) : (
          <span className="flex items-center gap-2">
            {fmt(lo, 0)} dB
            <span
              className="h-2 w-32 rounded-full"
              style={{ background: `linear-gradient(to right, ${colour(lo)}, ${colour((lo + hi) / 2)}, ${colour(hi)})` }}
              aria-hidden="true"
            />
            {fmt(hi, 0)} dB stronger in a fist
          </span>
        )}
      </div>
    </div>
  );
}

function Spectrum({ session }: { session: EmgSession }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const { freqs, power, medianHz } = session.psd;
  const { width, height } = size;
  const margin = { top: 16, right: 8, bottom: 22, left: 36 };
  const x = linear([0, freqs[freqs.length - 1]], [margin.left, width - margin.right]);
  const y = linear([0, 1.1], [height - margin.bottom, margin.top]);
  const area = `${linePath(freqs, power, x, y)}L${x(freqs[freqs.length - 1])},${y(0)}L${x(freqs[0])},${y(0)}Z`;
  return (
    <div ref={ref} className="absolute inset-0">
      <ChartFrame
        width={width}
        height={height}
        margin={margin}
        x={x}
        y={y}
        xTicks={[0, 100, 200, 300, 400, 500].filter((v) => v <= freqs[freqs.length - 1])}
        yTicks={[0, 0.5, 1]}
        xFormat={(v) => `${v}`}
        yFormat={(v) => v.toFixed(1)}
        xLabel="Hz"
        bands={[{ from: 20, to: 450, label: "EMG band", shaded: true }]}
        ariaLabel="Frequency content of the contraction"
      >
        <path d={area} fill="var(--series-1)" opacity={0.18} />
        <path d={linePath(freqs, power, x, y)} fill="none" stroke="var(--series-1)" strokeWidth={2} />
        <line x1={x(medianHz)} x2={x(medianHz)} y1={y.range[1]} y2={y.range[0]} stroke="var(--viz-text-2)" strokeWidth={1.2} strokeDasharray="4 3" />
        <text x={x(medianHz) + 4} y={margin.top + 10} fontSize={12} fill="var(--viz-text-2)">
          median {medianHz.toFixed(0)} Hz
        </text>
      </ChartFrame>
    </div>
  );
}
