import { cn } from "@/lib/utils";

const STAGE_CONFIG: Record<
  number,
  { label: string; color: string; description: string }
> = {
  1: {
    label: "Stage 1",
    color: "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
    description: "Accumulation",
  },
  2: {
    label: "Stage 2",
    color: "bg-accent-green/15 text-accent-green border-accent-green/30",
    description: "Early Breakout",
  },
  3: {
    label: "Stage 3",
    color: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
    description: "Trend Expansion",
  },
  4: {
    label: "Stage 4",
    color: "bg-accent-orange/15 text-accent-orange border-accent-orange/30",
    description: "Late Trend",
  },
  5: {
    label: "Stage 5",
    color: "bg-accent-red/15 text-accent-red border-accent-red/30",
    description: "Distribution",
  },
};

interface Props {
  stage: number;
  showLabel?: boolean;
  className?: string;
}

export function StageBadge({ stage, showLabel = true, className }: Props) {
  const cfg = STAGE_CONFIG[stage] || STAGE_CONFIG[1];
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border",
        cfg.color,
        className
      )}
      title={`${cfg.label} - ${cfg.description}`}
    >
      <span className="font-mono mr-1">S{stage}</span>
      {showLabel && cfg.description}
    </span>
  );
}

const TREND_CONFIG: Record<string, { color: string; arrow: string }> = {
  STRONG_BULLISH: { color: "bg-accent-green/20 text-accent-green border-accent-green/40", arrow: "↑↑" },
  BULLISH: { color: "bg-accent-green/10 text-accent-green border-accent-green/30", arrow: "↑" },
  NEUTRAL: { color: "bg-bg-subtle text-text-secondary border-border-muted", arrow: "→" },
  BEARISH: { color: "bg-accent-red/10 text-accent-red border-accent-red/30", arrow: "↓" },
  STRONG_BEARISH: { color: "bg-accent-red/20 text-accent-red border-accent-red/40", arrow: "↓↓" },
};

export function TrendBadge({ label }: { label: string }) {
  const cfg = TREND_CONFIG[label] || TREND_CONFIG.NEUTRAL;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border",
        cfg.color
      )}
    >
      <span>{cfg.arrow}</span>
      <span>{label.replace("_", " ")}</span>
    </span>
  );
}

const LIQUIDITY_CONFIG: Record<string, string> = {
  EXCELLENT: "bg-accent-green/15 text-accent-green border-accent-green/30",
  GOOD: "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
  MODERATE: "bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30",
  POOR: "bg-accent-orange/15 text-accent-orange border-accent-orange/30",
  ILLIQUID: "bg-accent-red/15 text-accent-red border-accent-red/30",
};

export function LiquidityBadge({ label }: { label: string }) {
  const color = LIQUIDITY_CONFIG[label] || LIQUIDITY_CONFIG.MODERATE;
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border",
        color
      )}
    >
      {label}
    </span>
  );
}

const READINESS_CONFIG: Record<string, string> = {
  READY_BUY: "bg-accent-green/20 text-accent-green border-accent-green/40",
  WATCH: "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
  WAIT: "bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30",
  AVOID: "bg-accent-red/20 text-accent-red border-accent-red/40",
};

export function ReadinessBadge({ signal }: { signal: string }) {
  const color = READINESS_CONFIG[signal] || READINESS_CONFIG.WAIT;
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border",
        color
      )}
    >
      {signal.replace("_", " ")}
    </span>
  );
}
