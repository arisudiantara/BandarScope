"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import {
  TrendingUp, Download, AlertTriangle, Sparkles, Filter, Eye,
} from "lucide-react";
import {
  marketSummaryProApi,
  type MSProScanParams,
  type AnalysisMethod,
  type NormalizationMethod,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { VerdictBadge } from "@/components/ui/VerdictBadge";
import { StarRating } from "@/components/ui/StarRating";
import { StageBadge } from "@/components/ui/StageBadge";
import {
  FlowCells, FlowHeader, MAFlag,
} from "@/components/market-summary-pro/MoneyFlowCells";
import { ProbabilityBadge } from "@/components/market-summary-pro/ProbabilityBadge";
import {
  formatIDR, formatPrice, pctClass, cn,
} from "@/lib/utils";

export default function MarketSummaryProPage() {
  const [params, setParams] = useState<MSProScanParams>({
    universe: "ALL",
    analysis_method: "smart_money",
    period: "daily",
    normalization: "normalized",
    apply_noise_filter: true,
    sort_by: "probability_score",
    sort_desc: true,
    limit: 200,
  });

  const config = useQuery({
    queryKey: ["msp-config"],
    queryFn: () => marketSummaryProApi.config(),
  });

  const scan = useQuery({
    queryKey: ["msp-scan", params],
    queryFn: () => marketSummaryProApi.scan(params),
  });

  const update = (k: keyof MSProScanParams, v: any) => {
    setParams((prev) => ({ ...prev, [k]: v === "" ? undefined : v }));
  };

  const handleExportCSV = async () => {
    const csv = await marketSummaryProApi.exportCsv(params);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `market-summary-pro-${scan.data?.as_of || "today"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const rows = scan.data?.rows ?? [];
  const summary = scan.data?.summary;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="h-6 w-6" /> Market Summary Pro
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Institutional money flow grid · 8 analysis methods · noise reduction
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-secondary">
            As of:{" "}
            <span className="text-text-primary tabular">{scan.data?.as_of}</span>
          </span>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-accent-blue text-white text-xs hover:bg-accent-blue/90"
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
        </div>
      </div>

      {/* Top filters: Method / Period / Normalization */}
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <FilterField label="Analysis Method">
            <select
              value={params.analysis_method ?? "smart_money"}
              onChange={(e) =>
                update("analysis_method", e.target.value as AnalysisMethod)
              }
              className="filter-input"
            >
              {config.data?.analysis_methods.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            {config.data?.analysis_methods.find(
              (m) => m.id === params.analysis_method
            )?.description && (
              <p className="text-[11px] text-text-muted mt-1">
                {
                  config.data.analysis_methods.find(
                    (m) => m.id === params.analysis_method
                  )?.description
                }
              </p>
            )}
          </FilterField>

          <FilterField label="Period">
            <select
              value={params.period ?? "daily"}
              onChange={(e) => update("period", e.target.value)}
              className="filter-input"
            >
              {config.data?.periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </FilterField>

          <FilterField label="Normalization">
            <select
              value={params.normalization ?? "normalized"}
              onChange={(e) =>
                update("normalization", e.target.value as NormalizationMethod)
              }
              className="filter-input"
            >
              {config.data?.normalization_methods.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
          </FilterField>
        </div>

        {/* Universe tabs */}
        <div>
          <div className="text-[10px] uppercase text-text-muted mb-1.5">
            Stock Universe
          </div>
          <div className="flex flex-wrap gap-1.5">
            {config.data?.universes.map((u) => (
              <button
                key={u.id}
                onClick={() => update("universe", u.id)}
                className={cn(
                  "px-2 py-1 rounded text-[11px] border",
                  (params.universe ?? "ALL") === u.id
                    ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30 font-medium"
                    : "bg-bg-subtle text-text-secondary border-border hover:border-border-muted"
                )}
              >
                {u.name}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Advanced filters */}
      <Card>
        <CardHeader title="Advanced Filters" action={<Filter className="h-4 w-4" />} />
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 text-xs">
          <NumberField
            label="Accum >"
            value={params.min_accumulation}
            onChange={(v) => update("min_accumulation", v)}
          />
          <NumberField
            label="Foreign >"
            value={params.min_foreign_flow}
            onChange={(v) => update("min_foreign_flow", v)}
          />
          <NumberField
            label="Vol Spike >"
            step={0.1}
            value={params.min_volume_spike}
            onChange={(v) => update("min_volume_spike", v)}
          />
          <NumberField
            label="Momentum >"
            value={params.min_momentum}
            onChange={(v) => update("min_momentum", v)}
          />
          <NumberField
            label="Liquidity >"
            value={params.min_liquidity}
            onChange={(v) => update("min_liquidity", v)}
          />
          <NumberField
            label="Trend >"
            value={params.min_trend}
            onChange={(v) => update("min_trend", v)}
          />
          <NumberField
            label="Probability >"
            value={params.min_probability}
            onChange={(v) => update("min_probability", v)}
          />
        </div>

        <div className="mt-3 flex items-center gap-3 flex-wrap text-xs">
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={params.apply_noise_filter ?? true}
              onChange={(e) => update("apply_noise_filter", e.target.checked)}
            />
            <span>Filter Noise (gorengan, pump, FOMO trap)</span>
          </label>

          {/* MA quick toggles */}
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-text-muted">Above:</span>
            {[5, 20, 50, 200].map((ma) => {
              const key = `require_above_ma${ma}` as keyof MSProScanParams;
              const active = (params as any)[key] === true;
              return (
                <button
                  key={ma}
                  onClick={() => update(key, active ? undefined : true)}
                  className={cn(
                    "px-2 py-0.5 rounded border text-[10px]",
                    active
                      ? "bg-accent-green/15 text-accent-green border-accent-green/30"
                      : "bg-bg-subtle border-border text-text-secondary"
                  )}
                >
                  MA{ma}
                </button>
              );
            })}
          </div>
        </div>

        <style jsx>{`
          :global(.filter-input) {
            width: 100%;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 8px;
            color: #f1f5f9;
            font-size: 12px;
          }
          :global(.filter-input:focus) {
            outline: none;
            border-color: #3b82f6;
          }
        `}</style>
      </Card>

      {/* Summary */}
      {summary && (
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
            <div className="rounded bg-bg-subtle border border-border p-2.5">
              <div className="text-text-muted">Total in Universe</div>
              <div className="text-lg font-bold tabular">
                {summary.total_in_universe}
              </div>
            </div>
            <div className="rounded bg-accent-green/5 border border-accent-green/30 p-2.5">
              <div className="text-accent-green">Accepted</div>
              <div className="text-lg font-bold tabular text-accent-green">
                {summary.accepted}
              </div>
            </div>
            <div className="rounded bg-accent-red/5 border border-accent-red/30 p-2.5">
              <div className="text-accent-red">Rejected (Noise)</div>
              <div className="text-lg font-bold tabular text-accent-red">
                {summary.rejected_as_noise}
              </div>
            </div>
            {(["INSTITUTIONAL_ACCUMULATION", "STRONG_OPPORTUNITY"] as const).map(
              (tier) => (
                <div
                  key={tier}
                  className="rounded bg-accent-yellow/5 border border-accent-yellow/30 p-2.5"
                >
                  <div className="text-accent-yellow text-[10px]">
                    {tier.replace("_", " ")}
                  </div>
                  <div className="text-lg font-bold tabular text-accent-yellow">
                    {summary.tier_distribution[tier] ?? 0}
                  </div>
                </div>
              )
            )}
          </div>
        </Card>
      )}

      {/* Main grid table */}
      <Card>
        <CardHeader
          title={`Results (${rows.length})`}
          subtitle="Cells dn-5..dn-0 = daily normalized flow · Hover untuk detail · Click symbol untuk drill-down"
        />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-card z-10">
              <tr className="text-text-muted border-b border-border">
                <th className="px-2 py-2 text-center font-medium">★</th>
                <th className="px-2 py-2 text-center font-medium">V</th>
                <th className="px-2 py-2 text-left font-medium">Symbol</th>
                <th className="px-2 py-2 text-right font-medium">Price</th>
                <th className="px-2 py-2 text-right font-medium">%</th>
                <th className="px-2 py-2 text-right font-medium">Vol</th>
                <th className="px-2 py-2 text-right font-medium">Value</th>
                <th className="px-2 py-2 text-center font-medium">Stage</th>
                <FlowHeader prefix="d" />
                <FlowHeader prefix="w" />
                {/* MA section */}
                <th className="px-1 py-2 text-center font-medium">MA5</th>
                <th className="px-1 py-2 text-center font-medium">MA10</th>
                <th className="px-1 py-2 text-center font-medium">MA20</th>
                <th className="px-1 py-2 text-center font-medium">MA50</th>
                <th className="px-1 py-2 text-center font-medium">MA100</th>
                <th className="px-1 py-2 text-center font-medium">MA200</th>
                {/* Probability */}
                <th className="px-2 py-2 text-left font-medium">Probability</th>
                <th className="px-2 py-2 text-left font-medium">Signals</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.symbol}
                  className="border-b border-border/30 hover:bg-bg-subtle/40"
                >
                  <td className="px-2 py-1.5 text-center">
                    <StarRating value={r.star_rating} />
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    <VerdictBadge verdict={r.verdict} />
                  </td>
                  <td className="px-2 py-1.5">
                    <Link
                      href={`/stock/${r.symbol}`}
                      className="font-mono font-semibold text-accent-blue hover:underline"
                    >
                      {r.symbol}
                    </Link>
                    <div className="flex gap-1 mt-0.5 items-center">
                      {r.is_idx30 && (
                        <span className="text-[8px] px-1 rounded bg-accent-blue/20 text-accent-blue">
                          IDX30
                        </span>
                      )}
                      {r.is_lq45 && !r.is_idx30 && (
                        <span className="text-[8px] px-1 rounded bg-accent-cyan/20 text-accent-cyan">
                          LQ45
                        </span>
                      )}
                      <span className="text-text-muted text-[9px] truncate max-w-[100px]">
                        {r.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-2 py-1.5 text-right tabular">
                    {formatPrice(r.price)}
                  </td>
                  <td
                    className={cn(
                      "px-2 py-1.5 text-right tabular",
                      pctClass(r.pct_change)
                    )}
                  >
                    {r.pct_change > 0 && "+"}
                    {r.pct_change.toFixed(2)}%
                  </td>
                  <td className="px-2 py-1.5 text-right tabular text-text-secondary">
                    {(r.volume / 1_000_000).toFixed(1)}M
                  </td>
                  <td className="px-2 py-1.5 text-right tabular text-text-secondary">
                    {formatIDR(r.value)}
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    <StageBadge stage={r.wyckoff_stage} showLabel={false} />
                  </td>
                  {/* Daily flow grid */}
                  <FlowCells values={r.daily_flow} prefix="d" />
                  {/* Weekly flow grid */}
                  <FlowCells values={r.weekly_flow} prefix="w" />
                  {/* MA flags */}
                  <MAFlag above={r.above_ma5} distance={r.dist_ma5} />
                  <MAFlag above={r.above_ma10} distance={r.dist_ma10} />
                  <MAFlag above={r.above_ma20} distance={r.dist_ma20} />
                  <MAFlag above={r.above_ma50} distance={r.dist_ma50} />
                  <MAFlag above={r.above_ma100} distance={r.dist_ma100} />
                  <MAFlag above={r.above_ma200} distance={r.dist_ma200} />
                  {/* Probability */}
                  <td className="px-2 py-1.5">
                    <ProbabilityBadge
                      score={r.probability_score}
                      tier={r.probability_tier}
                    />
                  </td>
                  {/* Signals */}
                  <td className="px-2 py-1.5">
                    <div className="flex flex-wrap gap-0.5 max-w-[180px]">
                      {r.signals.slice(0, 3).map((s) => (
                        <span
                          key={s.code}
                          title={s.explanation}
                          className={cn(
                            "px-1 py-0.5 rounded text-[9px] font-medium",
                            s.color === "green" && "bg-accent-green/15 text-accent-green",
                            s.color === "blue" && "bg-accent-blue/15 text-accent-blue",
                            s.color === "cyan" && "bg-accent-cyan/15 text-accent-cyan",
                            s.color === "orange" && "bg-accent-orange/15 text-accent-orange",
                            s.color === "red" && "bg-accent-red/15 text-accent-red"
                          )}
                        >
                          {s.label}
                        </span>
                      ))}
                      {r.signals.length === 0 && (
                        <span className="text-text-muted text-[9px]">—</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {scan.isLoading && (
            <div className="text-center py-8 text-text-muted text-sm">
              Loading...
            </div>
          )}
          {!scan.isLoading && rows.length === 0 && (
            <div className="text-center py-8 text-text-muted text-sm">
              Tidak ada saham yang match filters. Coba relax thresholds atau
              uncheck noise filter.
            </div>
          )}
        </div>
      </Card>

      {/* Cell Color Legend */}
      <Card>
        <CardHeader
          title="Money Flow Cell Legend"
          subtitle={`Period: ${params.period} · Normalization: ${params.normalization}`}
        />
        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          <span className="text-text-muted">Distribution</span>
          {[-80, -50, -25, 0, 25, 50, 80].map((v) => {
            const colors =
              v >= 60 ? { bg: "rgba(21, 128, 61, 0.85)", c: "#fff" } :
              v >= 40 ? { bg: "rgba(34, 197, 94, 0.75)", c: "#fff" } :
              v >= 20 ? { bg: "rgba(74, 222, 128, 0.55)", c: "#fff" } :
              v >= 5  ? { bg: "rgba(74, 222, 128, 0.30)", c: "#bbf7d0" } :
              v > -5  ? { bg: "rgba(71, 85, 105, 0.30)", c: "#94a3b8" } :
              v > -20 ? { bg: "rgba(248, 113, 113, 0.30)", c: "#fecaca" } :
              v > -40 ? { bg: "rgba(248, 113, 113, 0.55)", c: "#fff" } :
              v > -60 ? { bg: "rgba(239, 68, 68, 0.75)", c: "#fff" } :
                        { bg: "rgba(153, 27, 27, 0.85)", c: "#fff" };
            return (
              <span
                key={v}
                className="inline-block h-5 w-10 rounded text-center font-bold tabular leading-5"
                style={{ background: colors.bg, color: colors.c }}
              >
                {v > 0 ? "+" : ""}
                {v}
              </span>
            );
          })}
          <span className="text-text-muted">Accumulation</span>
        </div>
      </Card>
    </div>
  );
}

function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[10px] uppercase text-text-muted mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

function NumberField({
  label, value, onChange, step = 1,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  step?: number;
}) {
  return (
    <div>
      <label className="block text-[10px] text-text-muted mb-0.5">{label}</label>
      <input
        type="number"
        step={step}
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? undefined : Number(e.target.value))
        }
        className="w-full bg-bg-subtle border border-border rounded px-2 py-1 text-text-primary text-xs focus:outline-none focus:border-accent-blue"
      />
    </div>
  );
}
