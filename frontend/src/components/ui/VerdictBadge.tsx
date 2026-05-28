import { Check, X, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface VerdictBadgeProps {
  verdict: "GREEN_CHECK" | "ORANGE_X" | "RED_MINUS" | string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  tooltip?: string;
  className?: string;
}

const VERDICT_CONFIG = {
  GREEN_CHECK: {
    icon: Check,
    color: "text-accent-green",
    bg: "bg-accent-green/15",
    border: "border-accent-green/30",
    label: "Akumulasi",
    title: "Akumulasi konsisten",
  },
  ORANGE_X: {
    icon: X,
    color: "text-accent-orange",
    bg: "bg-accent-orange/15",
    border: "border-accent-orange/30",
    label: "Sideways",
    title: "Sideways / mixed",
  },
  RED_MINUS: {
    icon: Minus,
    color: "text-accent-red",
    bg: "bg-accent-red/15",
    border: "border-accent-red/30",
    label: "Distribusi",
    title: "Distribusi konsisten",
  },
} as const;

const SIZE_MAP = {
  sm: { wrapper: "h-5 w-5", icon: "h-3 w-3", text: "text-[10px]" },
  md: { wrapper: "h-6 w-6", icon: "h-3.5 w-3.5", text: "text-xs" },
  lg: { wrapper: "h-7 w-7", icon: "h-4 w-4", text: "text-sm" },
};

export function VerdictBadge({
  verdict,
  size = "sm",
  showLabel = false,
  tooltip,
  className,
}: VerdictBadgeProps) {
  const cfg =
    VERDICT_CONFIG[verdict as keyof typeof VERDICT_CONFIG] ??
    VERDICT_CONFIG.ORANGE_X;
  const dims = SIZE_MAP[size];
  const Icon = cfg.icon;

  if (showLabel) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 px-2 py-0.5 rounded border",
          cfg.bg,
          cfg.border,
          cfg.color,
          dims.text,
          "font-medium",
          className
        )}
        title={tooltip || cfg.title}
      >
        <Icon className={dims.icon} />
        {cfg.label}
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded border shrink-0",
        cfg.bg,
        cfg.border,
        cfg.color,
        dims.wrapper,
        className
      )}
      title={tooltip || cfg.title}
    >
      <Icon className={dims.icon} strokeWidth={3} />
    </span>
  );
}


interface RetailNonFlowBadgeProps {
  score: number;
  label?: "POSITIVE_NONFLOW" | "NEUTRAL" | "NEGATIVE_NONFLOW" | string;
  size?: "sm" | "md";
}

export function RetailNonFlowBadge({
  score,
  label,
  size = "sm",
}: RetailNonFlowBadgeProps) {
  const cfg =
    label === "POSITIVE_NONFLOW"
      ? {
          color: "text-accent-green",
          bg: "bg-accent-green/15",
          border: "border-accent-green/30",
          short: "Retail Jual ↓",
        }
      : label === "NEGATIVE_NONFLOW"
      ? {
          color: "text-accent-red",
          bg: "bg-accent-red/15",
          border: "border-accent-red/30",
          short: "Retail FOMO ↑",
        }
      : {
          color: "text-text-secondary",
          bg: "bg-bg-subtle",
          border: "border-border-muted",
          short: "Retail Netral",
        };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border font-medium",
        cfg.bg,
        cfg.border,
        cfg.color,
        size === "sm" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1"
      )}
      title={`Retail Non-Flow Score: ${score.toFixed(0)}/100`}
    >
      <span className="tabular">{score.toFixed(0)}</span>
      <span>·</span>
      <span>{cfg.short}</span>
    </span>
  );
}
