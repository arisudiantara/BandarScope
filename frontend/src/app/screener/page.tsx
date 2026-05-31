"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Search, Sparkles, Filter, AlertTriangle } from "lucide-react";
import {
  screenerApi,
  sectorApi,
  type ScreenerParams,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { VerdictBadge, RetailNonFlowBadge } from "@/components/ui/VerdictBadge";
import { StarRating } from "@/components/ui/StarRating";
import {
  StageBadge,
  TrendBadge,
  LiquidityBadge,
  ReadinessBadge,
} from "@/components/ui/StageBadge";
import { MarketHealthCard } from "@/components/screener/MarketHealthCard";
import {
  formatIDR,
  formatPrice,
  pctClass,
  scoreBgClass,
  cn,
} from "@/lib/utils";

export default function ScreenerPage() {
  const [filters, setFilters] = useState<ScreenerParams>({
    sort_by: "opportunity_score",
    sort_desc: true,
    limit: 100,
  });
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const presets = useQuery({
    queryKey: ["screener-presets"],
    queryFn: () => screenerApi.presets(),
  });

  const analysisTypes = useQuery({
    queryKey: ["screener-analysis-types"],
    queryFn: () => screenerApi.analysisTypes(),
  });

  const universes = useQuery({
    queryKey: ["screener-universes"],
    queryFn: () => screenerApi.universes(),
  });

  const sectors = useQuery({
    queryKey: ["sectors-list"],
    queryFn: () => sectorApi.activity(5),
  });

  const screener = useQuery({
    queryKey: ["screener", filters],
    queryFn: () => screenerApi.scan(filters),
  });

  const applyPreset = (presetId: string) => {
    const p = presets.data?.find((p) => p.id === presetId);
    if (p) {
      setFilters({ ...p.filters, limit: 100 });
      setActivePreset(presetId);
    }
  };

  const update = (k: keyof ScreenerParams, v: any) => {
    setFilters((prev) => ({ ...prev, [k]: v === "" ? undefined : v }));
    setActivePreset(null);
  };

  const toggleStageFilter = (stage: number) => {
    const current = filters.wyckoff_stages || [];
    const next = current.includes(stage)
      ? current.filter((s) => s !== stage)
      : [...current, stage];
    update("wyckoff_stages", next.length > 0 ? next : undefined);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Search className="h-6 w-6" /> Smart Money Screener V2
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Next-gen screener · Wyckoff stage · Opportunity score · Trade
            readiness
          </p>
        </div>
        <div className="text-xs text-text-secondary">
          As of:{" "}
          <span className="text-text-primary tabular">
            {screener.data?.as_of}
          </span>
        </div>
      </div>

      {/* Market Health */}
      <MarketHealthCard />

      {/* Universe + Analysis Type */}
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Universe */}
          <div>
            <div className="text-xs text-text-muted uppercase tracking-wide mb-2">
              Stock Universe
            </div>
            <div className="flex flex-wrap gap-1.5">
              {universes.data?.map((u) => (
                <button
                  key={u.id}
                  onClick={() => update("universe", u.id === "ALL" ? undefined : u.id)}
                  className={cn(
                    "px-3 py-1 rounded text-xs border",
                    (filters.universe === u.id) ||
                      (!filters.universe && u.id === "ALL")
                      ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30 font-medium"
                      : "bg-bg-subtle text-text-secondary border-border hover:border-border-muted"
                  )}
                >
                  {u.name}
                  {u.count > 0 && (
                    <span className="ml-1 text-text-muted">({u.count})</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Analysis Type */}
          <div>
            <div className="text-xs text-text-muted uppercase tracking-wide mb-2">
              Analysis Type
            </div>
            <select
              value={filters.analysis_type ?? ""}
              onChange={(e) =>
                update("analysis_type", e.target.value || undefined)
              }
              className="w-full bg-bg-subtle border border-border rounded-md px-2 py-1.5 text-sm focus:outline-none focus:border-accent-blue"
            >
              <option value="">— Default (Smart Money) —</option>
              {analysisTypes.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            {filters.analysis_type && (
              <p className="text-[11px] text-text-muted mt-1">
                {
                  analysisTypes.data?.find(
                    (a) => a.id === filters.analysis_type
                  )?.description
                }
              </p>
            )}
          </div>
        </div>
      </Card>

      {/* Presets */}
      <Card>
        <CardHeader
          title="Quick Presets"
          subtitle="Battle-tested screening templates"
          action={<Sparkles className="h-4 w-4 text-accent-yellow" />}
        />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
          {presets.data?.map((p) => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              className={cn(
                "text-left px-2.5 py-2 rounded border text-xs transition",
                activePreset === p.id
                  ? "bg-accent-blue/15 border-accent-blue text-accent-blue"
                  : "bg-bg-subtle border-border hover:border-border-muted"
              )}
            >
              <div className="font-semibold">{p.name}</div>
              <div className="text-text-muted text-[10px] mt-0.5 line-clamp-2">
                {p.description}
              </div>
            </button>
          ))}
        </div>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader title="Advanced Filters" action={<Filter className="h-4 w-4" />} />

        {/* Wyckoff Stage selector — primary filter */}
        <div className="mb-4">
          <div className="text-[10px] uppercase tracking-wide text-text-muted mb-1.5">
            Wyckoff Stage (multi-select)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {[1, 2, 3, 4, 5].map((stage) => {
              const active = (filters.wyckoff_stages || []).includes(stage);
              return (
                <button
                  key={stage}
                  onClick={() => toggleStageFilter(stage)}
                  className={cn(
                    "transition",
                    active ? "ring-2 ring-accent-blue rounded" : "opacity-70 hover:opacity-100"
                  )}
                >
                  <StageBadge stage={stage} />
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <FilterField label="★ Star Rating Min">
            <select
              value={filters.star_rating_min ?? ""}
              onChange={(e) =>
                update("star_rating_min", e.target.value ? Number(e.target.value) : undefined)
              }
              className="filter-input"
            >
              <option value="">All</option>
              <option value="5">★★★★★ (Elite)</option>
              <option value="4">★★★★+</option>
              <option value="3">★★★+</option>
              <option value="2">★★+</option>
            </select>
          </FilterField>

          <FilterField label="Opp Score Min">
            <input
              type="number"
              value={filters.opportunity_score_min ?? ""}
              onChange={(e) => update("opportunity_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>

          <FilterField label="Accum Score Min">
            <input
              type="number"
              value={filters.accumulation_score_min ?? ""}
              onChange={(e) => update("accumulation_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>

          <FilterField label="Foreign Strength Min">
            <input
              type="number"
              value={filters.foreign_strength_min ?? ""}
              onChange={(e) => update("foreign_strength_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>

          <FilterField label="Trend Score Min">
            <input
              type="number"
              value={filters.trend_score_min ?? ""}
              onChange={(e) => update("trend_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>

          <FilterField label="Liquidity Min">
            <input
              type="number"
              value={filters.liquidity_score_min ?? ""}
              onChange={(e) => update("liquidity_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>

          <FilterField label="Trade Readiness">
            <select
              value={filters.trade_readiness_signal ?? ""}
              onChange={(e) => update("trade_readiness_signal", e.target.value || undefined)}
              className="filter-input"
            >
              <option value="">All</option>
              <option value="READY_BUY">Ready to Buy</option>
              <option value="WATCH">Watch</option>
              <option value="WAIT">Wait</option>
              <option value="AVOID">Avoid</option>
            </select>
          </FilterField>

          <FilterField label="Trend Label">
            <select
              value={filters.trend_label ?? ""}
              onChange={(e) => update("trend_label", e.target.value || undefined)}
              className="filter-input"
            >
              <option value="">All</option>
              <option value="STRONG_BULLISH">↑↑ Strong Bullish</option>
              <option value="BULLISH">↑ Bullish</option>
              <option value="NEUTRAL">→ Neutral</option>
              <option value="BEARISH">↓ Bearish</option>
              <option value="STRONG_BEARISH">↓↓ Strong Bearish</option>
            </select>
          </FilterField>

          <FilterField label="Verdict (Kesimpulan)">
            <select
              value={filters.verdict ?? ""}
              onChange={(e) => update("verdict", e.target.value || undefined)}
              className="filter-input"
            >
              <option value="">All</option>
              <option value="GREEN_CHECK">✓ Akumulasi</option>
              <option value="ORANGE_X">✗ Sideways</option>
              <option value="RED_MINUS">− Distribusi</option>
            </select>
          </FilterField>

          <FilterField label="Retail Non-Flow">
            <select
              value={filters.retail_non_flow_label ?? ""}
              onChange={(e) =>
                update("retail_non_flow_label", e.target.value || undefined)
              }
              className="filter-input"
            >
              <option value="">All</option>
              <option value="POSITIVE_NONFLOW">Retail Jual (Positif)</option>
              <option value="NEUTRAL">Netral</option>
              <option value="NEGATIVE_NONFLOW">Retail FOMO (Negatif)</option>
            </select>
          </FilterField>

          <FilterField label="Max FOMO Risk">
            <input
              type="number"
              value={filters.max_fomo_risk ?? ""}
              onChange={(e) => update("max_fomo_risk", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>

          <FilterField label="Sector">
            <select
              value={filters.sector ?? ""}
              onChange={(e) => update("sector", e.target.value || undefined)}
              className="filter-input"
            >
              <option value="">All</option>
              {sectors.data?.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
          </FilterField>

          <FilterField label="Sort by">
            <select
              value={filters.sort_by ?? "opportunity_score"}
              onChange={(e) => update("sort_by", e.target.value)}
              className="filter-input"
            >
              <option value="opportunity_score">Opportunity Score</option>
              <option value="trade_readiness_score">Trade Readiness</option>
              <option value="accumulation_score">Accumulation Score</option>
              <option value="distribution_score">Distribution Score</option>
              <option value="foreign_strength_score">Foreign Strength</option>
              <option value="trend_score">Trend Score</option>
              <option value="liquidity_score">Liquidity Score</option>
              <option value="breakout_quality_score">Breakout Quality</option>
              <option value="retail_non_flow_score">Retail Non-Flow</option>
              <option value="bandar_score">Bandar Score (Legacy)</option>
              <option value="momentum_score">Momentum</option>
              <option value="volume_anomaly">Volume Anomaly</option>
              <option value="foreign_net">Foreign Net IDR</option>
            </select>
          </FilterField>
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

      {/* Results */}
      <Card>
        <CardHeader
          title={`Results (${screener.data?.count ?? 0})`}
          subtitle="Click symbol for full broker flow analysis · sort by clicking header buttons in filters"
        />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border">
                <th className="text-center px-2 py-2 font-medium">★</th>
                <th className="text-center px-2 py-2 font-medium">Verdict</th>
                <th className="text-left px-2 py-2 font-medium">Symbol</th>
                <th className="text-left px-2 py-2 font-medium">Sector</th>
                <th className="text-center px-2 py-2 font-medium">Stage</th>
                <th className="text-right px-2 py-2 font-medium">Price</th>
                <th className="text-right px-2 py-2 font-medium">%</th>
                <th className="text-right px-2 py-2 font-medium">Opp</th>
                <th className="text-right px-2 py-2 font-medium">Accum</th>
                <th className="text-right px-2 py-2 font-medium">Foreign</th>
                <th className="text-center px-2 py-2 font-medium">Trend</th>
                <th className="text-center px-2 py-2 font-medium">Liq</th>
                <th className="text-center px-2 py-2 font-medium">Ready</th>
                <th className="text-left px-2 py-2 font-medium">Retail NF</th>
                <th className="text-right px-2 py-2 font-medium">FOMO</th>
              </tr>
            </thead>
            <tbody>
              {screener.data?.results?.map((r) => (
                <tr
                  key={r.symbol}
                  className="border-b border-border/30 hover:bg-bg-subtle/40"
                >
                  <td className="px-2 py-2 text-center">
                    <StarRating value={r.star_rating} setupLabel={r.setup_label} />
                  </td>
                  <td className="px-2 py-2 text-center">
                    <VerdictBadge
                      verdict={r.verdict}
                      tooltip={r.verdict_explanation}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Link
                      href={`/stock/${r.symbol}`}
                      className="font-mono font-semibold text-accent-blue hover:underline"
                    >
                      {r.symbol}
                    </Link>
                    <div className="flex gap-1 mt-0.5">
                      {r.is_idx30 && <span className="text-[8px] px-1 rounded bg-accent-blue/20 text-accent-blue">IDX30</span>}
                      {r.is_lq45 && !r.is_idx30 && <span className="text-[8px] px-1 rounded bg-accent-cyan/20 text-accent-cyan">LQ45</span>}
                    </div>
                    <div className="text-text-muted text-[10px]">{r.name}</div>
                  </td>
                  <td className="px-2 py-2 text-text-secondary text-[10px]">
                    {r.sector}
                  </td>
                  <td className="px-2 py-2 text-center">
                    <StageBadge stage={r.wyckoff_stage} showLabel={false} />
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {formatPrice(r.close)}
                  </td>
                  <td
                    className={cn(
                      "px-2 py-2 text-right tabular",
                      pctClass(r.pct_change || 0)
                    )}
                  >
                    {(r.pct_change || 0) > 0 && "+"}
                    {(r.pct_change || 0).toFixed(2)}%
                  </td>
                  <td className="px-2 py-2 text-right">
                    <span className={`score-badge ${scoreBgClass(r.opportunity_score)}`}>
                      {r.opportunity_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {r.accumulation_score.toFixed(0)}
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {r.foreign_strength_score.toFixed(0)}
                  </td>
                  <td className="px-2 py-2 text-center">
                    <TrendBadge label={r.trend_label} />
                  </td>
                  <td className="px-2 py-2 text-center">
                    <LiquidityBadge label={r.liquidity_label} />
                  </td>
                  <td className="px-2 py-2 text-center">
                    <ReadinessBadge signal={r.trade_readiness_signal} />
                  </td>
                  <td className="px-2 py-2">
                    <RetailNonFlowBadge
                      score={r.retail_non_flow_score}
                      label={r.retail_non_flow_label}
                    />
                  </td>
                  <td className="px-2 py-2 text-right">
                    <span
                      className={cn(
                        "tabular text-[10px] inline-flex items-center gap-0.5",
                        r.fomo_risk_score > 60
                          ? "text-accent-red"
                          : r.fomo_risk_score > 40
                          ? "text-accent-orange"
                          : "text-text-muted"
                      )}
                      title={r.fomo_warning ?? ""}
                    >
                      {r.fomo_risk_score > 60 && (
                        <AlertTriangle className="h-2.5 w-2.5" />
                      )}
                      {r.fomo_risk_score.toFixed(0)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {screener.data?.results?.length === 0 && (
          <div className="text-center py-8 text-text-muted text-sm">
            No symbols match your filters. Try relaxing the criteria.
          </div>
        )}
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
      <label className="block text-text-muted mb-1">{label}</label>
      {children}
    </div>
  );
}
