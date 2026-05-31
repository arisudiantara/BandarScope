import { cn } from "@/lib/utils";

const TIER_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; range: string }
> = {
  INSTITUTIONAL_ACCUMULATION: {
    label: "Institutional Accum",
    color: "text-accent-yellow",
    bg: "bg-accent-yellow/15 border-accent-yellow/40",
    range: "90-100",
  },
  STRONG_OPPORTUNITY: {
    label: "Strong Opportunity",
    color: "text-accent-green",
    bg: "bg-accent-green/15 border-accent-green/40",
    range: "80-89",
  },
  WATCHLIST: {
    label: "Watchlist",
    color: "text-accent-cyan",
    bg: "bg-accent-cyan/15 border-accent-cyan/30",
    range: "70-79",
  },
  NEUTRAL: {
    label: "Neutral",
    color: "text-text-secondary",
    bg: "bg-bg-subtle border-border-muted",
    range: "60-69",
  },
  AVOID: {
    label: "Avoid",
    color: "text-accent-red",
    bg: "bg-accent-red/15 border-accent-red/30",
    range: "<60",
  },
};

interface Props {
  score: number;
  tier: string;
  size?: "sm" | "md";
  showScore?: boolean;
}

export function ProbabilityBadge({ score, tier, size = "sm", showScore = true }: Props) {
  const cfg = TIER_CONFIG[tier] || TIER_CONFIG.NEUTRAL;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded font-medium border tabular",
        cfg.color,
        cfg.bg,
        size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs"
      )}
      title={`${cfg.label} (range ${cfg.range})`}
    >
      {showScore && <span className="font-bold">{score.toFixed(0)}</span>}
      <span>{cfg.label}</span>
    </span>
  );
}
