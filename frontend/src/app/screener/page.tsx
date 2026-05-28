"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Search, Sparkles, Filter, ArrowUpDown } from "lucide-react";
import { screenerApi, sectorApi, type ScreenerParams } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { VerdictBadge, RetailNonFlowBadge } from "@/components/ui/VerdictBadge";
import {
  formatIDR, formatPrice, pctClass, scoreBgClass, signalClass, cn,
} from "@/lib/utils";

export default function ScreenerPage() {
  const [filters, setFilters] = useState<ScreenerParams>({
    sort_by: "bandar_score",
    sort_desc: true,
    limit: 100,
  });
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const presets = useQuery({
    queryKey: ["screener-presets"],
    queryFn: () => screenerApi.presets(),
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Search className="h-6 w-6" /> Market Summary Screener
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Composite Bandar Score + multi-factor smart money detection
          </p>
        </div>
        <div className="text-xs text-text-secondary">
          As of: <span className="text-text-primary tabular">{screener.data?.as_of}</span>
        </div>
      </div>

      {/* Presets */}
      <Card>
        <CardHeader
          title="Quick Presets"
          subtitle="Battle-tested screening templates"
          action={<Sparkles className="h-4 w-4 text-accent-yellow" />}
        />
        <div className="flex flex-wrap gap-2">
          {presets.data?.map((p) => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              className={cn(
                "text-left px-3 py-2 rounded-lg border text-xs transition",
                activePreset === p.id
                  ? "bg-accent-blue/15 border-accent-blue text-accent-blue"
                  : "bg-bg-subtle border-border hover:border-border-muted"
              )}
            >
              <div className="font-semibold">{p.name}</div>
              <div className="text-text-muted mt-0.5">{p.description}</div>
            </button>
          ))}
        </div>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader title="Filters" action={<Filter className="h-4 w-4" />} />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <FilterField label="BandarScore Min">
            <input
              type="number"
              value={filters.bandar_score_min ?? ""}
              onChange={(e) => update("bandar_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>
          <FilterField label="Inventory Score Min">
            <input
              type="number"
              value={filters.inventory_score_min ?? ""}
              onChange={(e) => update("inventory_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>
          <FilterField label="Momentum Score Min">
            <input
              type="number"
              value={filters.momentum_score_min ?? ""}
              onChange={(e) => update("momentum_score_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="0-100"
              className="filter-input"
            />
          </FilterField>
          <FilterField label="Foreign Net Min (IDR)">
            <input
              type="number"
              value={filters.foreign_net_min ?? ""}
              onChange={(e) => update("foreign_net_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="e.g. 1000000000"
              className="filter-input"
            />
          </FilterField>
          <FilterField label="Volume Anomaly Min">
            <input
              type="number"
              step="0.1"
              value={filters.volume_anomaly_min ?? ""}
              onChange={(e) => update("volume_anomaly_min", e.target.value ? Number(e.target.value) : undefined)}
              placeholder="e.g. 1.5"
              className="filter-input"
            />
          </FilterField>
          <FilterField label="Smart Money Signal">
            <select
              value={filters.smart_money_signal ?? ""}
              onChange={(e) => update("smart_money_signal", e.target.value || undefined)}
              className="filter-input"
            >
              <option value="">All</option>
              <option value="accumulation">Accumulation</option>
              <option value="distribution">Distribution</option>
              <option value="neutral">Neutral</option>
            </select>
          </FilterField>
          <FilterField label="Verdict (Kesimpulan)">
            <select
              value={filters.verdict ?? ""}
              onChange={(e) => update("verdict", e.target.value || undefined)}
              className="filter-input"
            >
              <option value="">All</option>
              <option value="GREEN_CHECK">✓ Akumulasi (Hijau)</option>
              <option value="ORANGE_X">✗ Sideways (Orange)</option>
              <option value="RED_MINUS">− Distribusi (Merah)</option>
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
              value={filters.sort_by ?? "bandar_score"}
              onChange={(e) => update("sort_by", e.target.value)}
              className="filter-input"
            >
              <option value="bandar_score">Bandar Score</option>
              <option value="foreign_score">Foreign Score</option>
              <option value="inventory_score">Inventory Score</option>
              <option value="momentum_score">Momentum</option>
              <option value="volume_anomaly">Volume Anomaly</option>
              <option value="foreign_net">Foreign Net</option>
              <option value="retail_non_flow_score">Retail Non-Flow</option>
              <option value="consistency_pct">Konsistensi 15D</option>
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
          subtitle="Click a symbol for full broker flow analysis"
        />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border">
                <th className="text-center px-2 py-2 font-medium w-8">✓</th>
                <th className="text-left px-2 py-2 font-medium">Symbol</th>
                <th className="text-left px-2 py-2 font-medium">Sector</th>
                <th className="text-right px-2 py-2 font-medium">Price</th>
                <th className="text-right px-2 py-2 font-medium">Vol Anom</th>
                <th className="text-right px-2 py-2 font-medium">Foreign 20D</th>
                <th className="text-right px-2 py-2 font-medium">Bandar</th>
                <th className="text-right px-2 py-2 font-medium">Inventory</th>
                <th className="text-right px-2 py-2 font-medium">Momentum</th>
                <th className="text-left px-2 py-2 font-medium">Retail Non-Flow</th>
                <th className="text-right px-2 py-2 font-medium">Konsist 15D</th>
                <th className="text-left px-2 py-2 font-medium">Behavior</th>
              </tr>
            </thead>
            <tbody>
              {screener.data?.results?.map((r) => (
                <tr
                  key={r.symbol}
                  className="border-b border-border/30 hover:bg-bg-subtle/40"
                >
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
                    <div className="text-text-muted text-[10px]">{r.name}</div>
                  </td>
                  <td className="px-2 py-2 text-text-secondary">{r.sector}</td>
                  <td className="px-2 py-2 text-right tabular">
                    {formatPrice(r.close)}
                  </td>
                  <td
                    className={cn(
                      "px-2 py-2 text-right tabular",
                      r.volume_anomaly > 1.5
                        ? "text-accent-yellow"
                        : "text-text-secondary"
                    )}
                  >
                    {r.volume_anomaly.toFixed(1)}x
                  </td>
                  <td
                    className={cn(
                      "px-2 py-2 text-right tabular",
                      r.foreign_net >= 0
                        ? "text-accent-green"
                        : "text-accent-red"
                    )}
                  >
                    {formatIDR(r.foreign_net)}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <span className={`score-badge ${scoreBgClass(r.bandar_score)}`}>
                      {r.bandar_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {r.inventory_score.toFixed(0)}
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {r.momentum_score.toFixed(0)}
                  </td>
                  <td className="px-2 py-2">
                    <RetailNonFlowBadge
                      score={r.retail_non_flow_score}
                      label={r.retail_non_flow_label}
                    />
                  </td>
                  <td className="px-2 py-2 text-right tabular text-text-secondary">
                    {r.consistency_pct?.toFixed(0) ?? "-"}%
                  </td>
                  <td className="px-2 py-2 text-text-secondary text-[11px]">
                    {r.behavior_label}
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
