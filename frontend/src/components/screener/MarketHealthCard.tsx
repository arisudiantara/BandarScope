"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { screenerApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const REGIME_CONFIG = {
  RISK_ON: {
    label: "RISK ON",
    color: "text-accent-green",
    bg: "from-accent-green/20 to-accent-green/5 border-accent-green/30",
    icon: TrendingUp,
  },
  NEUTRAL: {
    label: "NEUTRAL",
    color: "text-accent-cyan",
    bg: "from-accent-cyan/15 to-accent-cyan/5 border-accent-cyan/30",
    icon: Activity,
  },
  RISK_OFF: {
    label: "RISK OFF",
    color: "text-accent-red",
    bg: "from-accent-red/20 to-accent-red/5 border-accent-red/30",
    icon: TrendingDown,
  },
};

export function MarketHealthCard() {
  const health = useQuery({
    queryKey: ["market-health"],
    queryFn: () => screenerApi.marketHealth(),
    staleTime: 60_000,
  });

  if (health.isLoading) {
    return (
      <div className="rounded-xl bg-bg-card border border-border p-4 text-text-muted text-sm">
        Loading market health...
      </div>
    );
  }
  if (!health.data) return null;
  const h = health.data;
  const regime = REGIME_CONFIG[h.regime] || REGIME_CONFIG.NEUTRAL;
  const Icon = regime.icon;

  return (
    <div
      className={cn(
        "rounded-xl border p-4 bg-gradient-to-br",
        regime.bg
      )}
    >
      <div className="flex items-center gap-3 mb-3">
        <Icon className={cn("h-6 w-6", regime.color)} />
        <div>
          <div className="text-[10px] uppercase tracking-wider text-text-muted">
            Market Health Index
          </div>
          <div className={cn("text-2xl font-bold tabular", regime.color)}>
            {h.health_score.toFixed(0)} <span className="text-xs">{regime.label}</span>
          </div>
        </div>
        <div className="flex-1" />
        <div className="text-right">
          <div className="text-[10px] text-text-muted">Advance / Decline</div>
          <div className="text-sm tabular">
            <span className="text-accent-green">{h.advance}</span>
            <span className="text-text-muted mx-0.5">/</span>
            <span className="text-accent-red">{h.decline}</span>
            <span className="text-text-muted ml-1.5">({h.advance_ratio_pct.toFixed(0)}%)</span>
          </div>
        </div>
      </div>

      <p className="text-xs text-text-secondary mb-3">{h.regime_label}</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <Stat label="Avg Opp Score" value={h.avg_opportunity_score.toFixed(0)} />
        <Stat label="Avg Trend" value={h.avg_trend_score.toFixed(0)} />
        <Stat label="Avg Foreign" value={h.avg_foreign_strength.toFixed(0)} />
        <Stat
          label="Avg FOMO Risk"
          value={h.avg_fomo_risk.toFixed(0)}
          warning={h.avg_fomo_risk > 50}
        />
      </div>

      {/* Stage distribution mini bar */}
      <div className="mt-3 pt-3 border-t border-border/50">
        <div className="text-[10px] text-text-muted mb-1.5 flex items-center justify-between">
          <span>Stage Distribution</span>
          <span>{h.total_stocks} stocks</span>
        </div>
        <div className="flex h-2 rounded overflow-hidden">
          {[1, 2, 3, 4, 5].map((stage) => {
            const count = h.stage_distribution[stage] ?? 0;
            const pct = (count / Math.max(h.total_stocks, 1)) * 100;
            const color = {
              1: "#06b6d4",
              2: "#22c55e",
              3: "#3b82f6",
              4: "#f59e0b",
              5: "#ef4444",
            }[stage];
            return (
              <div
                key={stage}
                style={{ width: `${pct}%`, background: color }}
                title={`Stage ${stage}: ${count} (${pct.toFixed(0)}%)`}
              />
            );
          })}
        </div>
        <div className="flex justify-between text-[9px] text-text-muted mt-1 tabular">
          <span>S1 Accum: {h.stage_distribution[1] ?? 0}</span>
          <span>S2 Brkt: {h.stage_distribution[2] ?? 0}</span>
          <span>S3 Trend: {h.stage_distribution[3] ?? 0}</span>
          <span>S4 Late: {h.stage_distribution[4] ?? 0}</span>
          <span>S5 Dist: {h.stage_distribution[5] ?? 0}</span>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  warning,
}: {
  label: string;
  value: string;
  warning?: boolean;
}) {
  return (
    <div className="rounded bg-bg-card/50 border border-border p-2">
      <div className="text-text-muted text-[10px]">{label}</div>
      <div
        className={cn(
          "text-sm font-bold tabular flex items-center gap-1",
          warning && "text-accent-orange"
        )}
      >
        {warning && <AlertTriangle className="h-3 w-3" />}
        {value}
      </div>
    </div>
  );
}
