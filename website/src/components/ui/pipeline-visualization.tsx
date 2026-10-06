"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "motion/react"

const messages = [
  "Session start: Thermal, ECG, EMG, and rPPG sensors synced",
  "Preprocessing: filtering, resampling, and window alignment",
  "Feature extraction: key measures computed for each signal",
  "Fusion: all four signals analysed together",
  "Inference: 6 task heads evaluated in parallel",
  "Heart Disease Prediction → cardiac risk score generated",
  "Engagement Detection → attention level logged",
  "Anti-Spoofing → liveness check passed",
  "Session complete. 6 outputs generated in 342ms.",
  "Idle. Waiting for next recording session...",
]

function AnimatedDot({
  path,
  duration,
  delay,
  size,
  opacity,
}: {
  path: string
  duration: number
  delay: number
  size: number
  opacity: number
}) {
  return (
    <circle r={size} fill="#0052FF" opacity={opacity}>
      <animateMotion
        dur={`${duration}s`}
        repeatCount="indefinite"
        begin={`${delay}s`}
        path={path}
      />
    </circle>
  )
}

function PulsingDot({
  cx,
  cy,
  color,
  duration,
  delay = 0,
}: {
  cx: number
  cy: number
  color: string
  duration: number
  delay?: number
}) {
  return (
    <motion.circle
      cx={cx}
      cy={cy}
      r={2.8}
      fill={color}
      animate={{ opacity: [0.15, 1, 0.15] }}
      transition={{
        duration,
        delay,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  )
}

function useCountUp(target: number, duration = 2400) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    let raf: number
    const start = performance.now()

    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic — decelerates into the target
      setValue(Math.round(eased * target))
      if (t < 1) raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])

  return value
}

function StatusIndicator({
  cx,
  cy,
  color,
  pulsing = false,
  duration = 1.9,
  delay = 0,
}: {
  cx: number
  cy: number
  color: string
  pulsing?: boolean
  duration?: number
  delay?: number
}) {
  if (pulsing) {
    return (
      <motion.circle
        cx={cx}
        cy={cy}
        r={3}
        fill={color}
        animate={{ opacity: [0.3, 1, 0.3] }}
        transition={{
          duration,
          delay,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    )
  }
  return <circle cx={cx} cy={cy} r={3} fill={color} opacity={0.95} />
}

// General labels only: the diagram describes the method, not specific devices.
const sensors = [
  { title: "Thermal", y: 14 },
  { title: "ECG", y: 66 },
  { title: "EMG", y: 118 },
  { title: "rPPG", y: 170 },
]

const tasks = [
  { title: "Heart Disease Prediction", y: 7, color: "#22c55e", pulsing: false },
  { title: "Engagement Detection", y: 43, color: "#f59e0b", pulsing: true, duration: 1.9 },
  { title: "Mental Health Screening", y: 79, color: "#22c55e", pulsing: false },
  { title: "Induced Emotion", y: 115, color: "#f59e0b", pulsing: true, duration: 2.1 },
  { title: "Cognition–Emotion", y: 151, color: "#22c55e", pulsing: false },
  { title: "Anti-Spoofing", y: 187, color: "#f59e0b", pulsing: true, duration: 2.3 },
]

const SENSOR_W = 112
const SENSOR_H = 38
const TASK_W = 156
const TASK_H = 28

const SUBJECTS_RECORDED = 42

export default function MultimodalPipeline() {
  const [messageIndex, setMessageIndex] = useState(0)
  const subjectCount = useCountUp(SUBJECTS_RECORDED)

  useEffect(() => {
    const messageInterval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length)
    }, 2700)

    return () => clearInterval(messageInterval)
  }, [])

  const sensorCenters = sensors.map((s) => s.y + SENSOR_H / 2)
  const taskCenters = tasks.map((t) => t.y + TASK_H / 2)

  const sensorRight = 14 + SENSOR_W
  const preLeft = 216
  const preRight = preLeft + 118
  const fusionLeft = 419
  const fusionRight = fusionLeft + 130
  const taskLeft = 588

  const inputPaths = sensorCenters.map(
    (cy) => `M${sensorRight},${cy} C${sensorRight + 24},${cy} ${preLeft - 18},111 ${preLeft},111`
  )
  const midPath = `M${preRight},111 L${fusionLeft},111`
  const outputPaths = taskCenters.map(
    (cy) => `M${fusionRight},111 C${fusionRight + 16},111 ${taskLeft - 8},${cy} ${taskLeft},${cy}`
  )

  return (
    <div className="pv-card w-full font-sans">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[7px]">
          <motion.span
            className="w-[6px] h-[6px] rounded-full bg-green-500 inline-block"
            animate={{ opacity: [1, 0.2, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
          <span className="text-base text-muted-foreground">Multimodal pipeline · live</span>
        </div>
        <span className="text-base text-muted-foreground">
          4 modalities · 6 tasks
        </span>
      </div>

      {/* Dataset counter */}
      <div className="mt-3 flex items-baseline gap-2.5">
        <span className="text-2xl font-semibold leading-none tracking-tight tabular-nums text-foreground">
          {subjectCount}
        </span>
        <span className="text-base text-muted-foreground">subjects recorded</span>
      </div>

      {/* SVG Pipeline Visualization */}
      <div className="mt-4 overflow-x-auto">
        <svg
          width="100%"
          viewBox="0 0 760 232"
          className="block overflow-visible"
          style={{ minWidth: "700px" }}
        >
        <defs>
          <marker
            id="ma"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto"
          >
            <path
              d="M2 1.5L7.5 5L2 8.5"
              fill="none"
              stroke="rgba(51,117,255,0.7)"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </marker>
        </defs>

        {/* Sensor → preprocessing connections */}
        {inputPaths.map((d, i) => (
          <path
            key={`in-${i}`}
            d={d}
            fill="none"
            stroke="rgba(51,117,255,0.5)"
            strokeWidth="1.5"
            strokeDasharray="3 5"
          />
        ))}

        {/* Preprocessing → fusion */}
        <path
          d={midPath}
          fill="none"
          stroke="rgba(51,117,255,0.55)"
          strokeWidth="1.5"
          strokeDasharray="3 5"
          markerEnd="url(#ma)"
        />

        {/* Fusion → task connections */}
        {outputPaths.map((d, i) => (
          <path
            key={`out-${i}`}
            d={d}
            fill="none"
            stroke="rgba(51,117,255,0.45)"
            strokeWidth="1.5"
            strokeDasharray="3 5"
          />
        ))}

        {/* Animated dots */}
        {inputPaths.map((d, i) => (
          <g key={`in-dots-${i}`}>
            <AnimatedDot path={d} duration={1.1 + i * 0.08} delay={i * 0.2} size={2.3} opacity={0.9} />
            <AnimatedDot path={d} duration={1.1 + i * 0.08} delay={0.5 + i * 0.2} size={1.5} opacity={0.5} />
          </g>
        ))}

        <AnimatedDot path={midPath} duration={0.85} delay={0} size={2.5} opacity={1} />
        <AnimatedDot path={midPath} duration={0.85} delay={0.42} size={1.8} opacity={0.6} />

        {outputPaths.map((d, i) => (
          <g key={`out-dots-${i}`}>
            <AnimatedDot path={d} duration={1.2 + i * 0.1} delay={0.15 + i * 0.18} size={2.2} opacity={0.9} />
            <AnimatedDot path={d} duration={1.2 + i * 0.1} delay={0.7 + i * 0.18} size={1.5} opacity={0.5} />
          </g>
        ))}

        {/* Sensor nodes */}
        {sensors.map((sensor) => (
          <g key={sensor.title}>
            <rect
              x="14"
              y={sensor.y}
              width={SENSOR_W}
              height={SENSOR_H}
              rx="8"
              fill="var(--pv-node-bg)"
              stroke="var(--pv-node-border)"
              strokeWidth="1"
            />
            <text
              x={14 + SENSOR_W / 2}
              y={sensor.y + SENSOR_H / 2}
              dy="0.35em"
              textAnchor="middle"
              fontSize="10"
              fontWeight="600"
              fill="var(--pv-text-1)"
            >
              {sensor.title}
            </text>
          </g>
        ))}

        {/* Preprocessing node */}
        <rect
          x={preLeft}
          y="83"
          width="118"
          height="56"
          rx="8"
          fill="var(--pv-node-bg)"
          stroke="var(--pv-node-border)"
          strokeWidth="1"
        />
        <text
          x={preLeft + 59}
          y="100"
          textAnchor="middle"
          fontSize="7.5"
          fill="var(--pv-text-3)"
          letterSpacing=".07em"
        >
          PREPROCESS
        </text>
        <text
          x={preLeft + 59}
          y="117"
          textAnchor="middle"
          fontSize="10"
          fill="var(--pv-text-1)"
        >
          Sync + Align
        </text>
        <text
          x={preLeft + 59}
          y="151"
          textAnchor="middle"
          fontSize="8.5"
          fill="var(--pv-text-4)"
        >
          windowed, per-session
        </text>

        {/* Fusion model node */}
        <rect
          x={fusionLeft}
          y="65"
          width="130"
          height="92"
          rx="10"
          fill="var(--pv-fusion-bg)"
          stroke="#0052FF"
          strokeWidth="1"
        />
        <rect x={fusionLeft + 12} y="65.5" width="80" height="1" rx="0.5" fill="rgba(51,117,255,0.5)" />
        <text
          x={fusionLeft + 65}
          y="98"
          textAnchor="middle"
          fontSize="7.5"
          fill="rgba(51,117,255,0.9)"
          letterSpacing=".07em"
        >
          FUSION
        </text>
        <text
          x={fusionLeft + 65}
          y="121"
          textAnchor="middle"
          fontSize="10"
          fill="var(--pv-fusion-text)"
          fontWeight="600"
        >
          All signals
        </text>
        <text
          x={fusionLeft + 65}
          y="137"
          textAnchor="middle"
          fontSize="10"
          fill="var(--pv-fusion-text)"
          fontWeight="600"
        >
          combined
        </text>
        <PulsingDot cx={fusionLeft + 53} cy={148} color="#0052FF" duration={1.2} delay={0} />
        <PulsingDot cx={fusionLeft + 65} cy={148} color="#0052FF" duration={1.2} delay={0.4} />
        <PulsingDot cx={fusionLeft + 77} cy={148} color="#0052FF" duration={1.2} delay={0.8} />
        <text
          x={fusionLeft + 65}
          y="173"
          textAnchor="middle"
          fontSize="8.5"
          fill="rgba(0,82,255,0.75)"
        >
          learned from synced sessions
        </text>

        {/* Task output nodes */}
        {tasks.map((task) => (
          <g key={task.title}>
            <rect
              x={taskLeft}
              y={task.y}
              width={TASK_W}
              height={TASK_H}
              rx="7"
              fill="var(--pv-task-bg)"
              stroke="var(--pv-task-border)"
              strokeWidth="1"
            />
            <text
              x={taskLeft + TASK_W / 2 - 4}
              y={task.y + 18.5}
              textAnchor="middle"
              fontSize="9.2"
              fill="var(--pv-text-2)"
            >
              {task.title}
            </text>
            <StatusIndicator
              cx={taskLeft + TASK_W - 12}
              cy={task.y + 14}
              color={task.color}
              pulsing={task.pulsing}
              duration={task.duration}
            />
          </g>
        ))}
        </svg>
      </div>

      {/* Message Display */}
      <div className="mt-4 h-[28px]">
        <div className="flex gap-2 items-start h-full">
          <span className="text-base leading-[1.55] text-muted-foreground shrink-0">
            ›
          </span>
          <div className="relative flex-1 overflow-hidden h-full">
            <AnimatePresence mode="wait">
              <motion.div
                key={messageIndex}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.25 }}
                className="text-base text-muted-foreground leading-[1.55] absolute inset-0"
              >
                {messages[messageIndex]}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
