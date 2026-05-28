"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Calendar } from "lucide-react";
import { yearlyHeatmapApi, symbolsApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn, formatIDR } from "@/lib/utils";

function scoreToColor(s: number): string {
  if (s >= 60) return "#15803d";
  if (s >= 25) return "#22c55e";
  if (s >= 10) return "#4ade80";
  if (s > -10) return "#475569";
  if (s > -25) return "#f87171";
  if (s > -60) return "#ef4444";
  return "#991b1b";
}

export default function YearlyHeatmapPage() {
  const [tab, setTab] = useState<"universe" | "symbol">("universe");
  const [selectedSymbol, setSelectedSymbol] = useState<string>("BBCA");
  const [months, setMonths] = useState(12);

  const universe = useQuery({
    queryKey: ["yearly-universe", months],
    queryFn: () => yearlyHeatmapApi.universe(months, 30),
    enabled: tab === "universe",
  });

  const symbolView = useQuery({
    queryKey: ["yearly-symbol", selectedSymbol, months],
    queryFn: () => yearlyHeatmapApi.perSymbol(selectedSymbol, months),
    enabled: tab === "symbol",
  });

  const symbols = useQuery({
    queryKey: ["symbols-all"],
    queryFn: () => symbolsApi.list(),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Calendar className="h-6 w-6" /> Yearly Smart Money Heatmap
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Pola seasonal akumulasi/distribusi bandar — cari bulan apa biasanya
            saham favorit kamu di-akumulasi
          </p>
        </div>
        <div className="flex gap-2">
          {[6, 12, 18, 24].map((m) => (
            <button
              key={m}
              onClick={() => setMonths(m)}
              className={cn(
                "px-3 py-1.5 rounded text-xs",
                months === m
                  ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                  : "bg-bg-subtle border border-border text-text-secondary"
              )}
            >
              {m}M
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab("universe")}
          className={cn(
            "px-4 py-2 rounded-lg text-sm border",
            tab === "universe"
              ? "border-accent-blue bg-accent-blue/10 text-accent-blue font-medium"
              : "border-border bg-bg-card text-text-secondary"
          )}
        >
          Universe (Top 30)
        </button>
        <button
          onClick={() => setTab("symbol")}
          className={cn(
            "px-4 py-2 rounded-lg text-sm border",
            tab === "symbol"
              ? "border-accent-blue bg-accent-blue/10 text-accent-blue font-medium"
              : "border-border bg-bg-card text-text-secondary"
          )}
        >
          Per-Symbol
        </button>
      </div>

      {/* Universe Tab */}
      {tab === "universe" && (
        <Card>
          <CardHeader
            title="Universe Cross-Section"
            subtitle={`Top 30 saham · matrix ${months} bulan · color = behavior score`}
          />
          {universe.isLoading && (
            <div className="text-center py-8 text-text-muted text-sm">
              Loading...
            </div>
          )}
          {universe.data && (
            <div className="overflow-x-auto">
              <table className="text-xs">
                <thead>
                  <tr>
                    <th className="text-left px-2 py-2 sticky left-0 bg-bg-card border-b border-border">
                      Symbol
                    </th>
                    <th className="text-right px-2 py-2 border-b border-border">
                      Avg
                    </th>
                    {universe.data.months.map((m) => (
                      <th
                        key={m}
                        className="text-center px-1 py-2 text-text-muted font-medium border-b border-border min-w-[55px]"
                      >
                        {m.slice(2)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {universe.data.matrix.map((row) => (
                    <tr
                      key={row.symbol}
                      className="hover:bg-bg-subtle/50 border-b border-border/30"
                    >
                      <td className="sticky left-0 bg-bg-card px-2 py-1.5">
                        <Link
                          href={`/stock/${row.symbol}`}
                          className="font-mono font-semibold text-accent-blue hover:underline"
                        >
                          {row.symbol}
                        </Link>
                        <div className="text-[10px] text-text-muted">
                          {row.sector}
                        </div>
                      </td>
                      <td
                        className="px-2 py-1.5 text-right tabular text-[10px] font-medium"
                        style={{
                          color: scoreToColor(row.avg_score),
                        }}
                      >
                        {row.avg_score > 0 ? "+" : ""}
                        {row.avg_score.toFixed(0)}
                      </td>
                      {row.cells.map((c) => (
                        <td
                          key={c.month}
                          className="text-center px-1 py-1.5 tabular text-[10px] font-bold"
                          style={{
                            background: scoreToColor(c.score),
                            color: "#fff",
                          }}
                          title={`${c.month}: ${c.label} (${c.score.toFixed(0)})`}
                        >
                          {c.score > 0 ? "+" : ""}
                          {c.score.toFixed(0)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Color legend */}
              <div className="flex items-center gap-2 mt-4 text-[10px]">
                <span className="text-text-muted">Distribution</span>
                {[-80, -50, -25, 0, 25, 50, 80].map((s) => (
                  <span
                    key={s}
                    className="inline-block h-4 w-8 rounded-sm tabular text-center font-bold text-white"
                    style={{ background: scoreToColor(s) }}
                  >
                    {s}
                  </span>
                ))}
                <span className="text-text-muted">Accumulation</span>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Per-Symbol Tab */}
      {tab === "symbol" && (
        <>
          <Card>
            <CardHeader title="Pilih Symbol" />
            <div className="flex flex-wrap gap-2">
              {symbols.data?.slice(0, 30).map((s) => (
                <button
                  key={s.code}
                  onClick={() => setSelectedSymbol(s.code)}
                  className={cn(
                    "px-2 py-1 rounded font-mono text-xs",
                    selectedSymbol === s.code
                      ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                      : "bg-bg-subtle border border-border text-text-secondary"
                  )}
                >
                  {s.code}
                </button>
              ))}
            </div>
          </Card>

          {symbolView.data && (
            <>
              {/* Summary stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <Card className="p-3">
                  <div className="text-text-muted">Avg Behavior</div>
                  <div
                    className="text-xl font-bold tabular"
                    style={{
                      color: scoreToColor(
                        symbolView.data.summary.avg_behavior_score
                      ),
                    }}
                  >
                    {symbolView.data.summary.avg_behavior_score > 0 && "+"}
                    {symbolView.data.summary.avg_behavior_score.toFixed(0)}
                  </div>
                </Card>
                <Card className="p-3">
                  <div className="text-text-muted">Akumulasi / Distribusi</div>
                  <div className="text-xl font-bold tabular">
                    <span className="text-accent-green">
                      {symbolView.data.summary.accumulation_months}
                    </span>
                    <span className="text-text-muted mx-1">/</span>
                    <span className="text-accent-red">
                      {symbolView.data.summary.distribution_months}
                    </span>
                  </div>
                  <div className="text-[10px] text-text-muted mt-1">bulan</div>
                </Card>
                <Card className="p-3">
                  <div className="text-text-muted">Current Streak</div>
                  <div
                    className={cn(
                      "text-xl font-bold tabular",
                      symbolView.data.summary.current_streak.type === "ACCUMULATION"
                        ? "text-accent-green"
                        : symbolView.data.summary.current_streak.type === "DISTRIBUTION"
                        ? "text-accent-red"
                        : "text-text-secondary"
                    )}
                  >
                    {symbolView.data.summary.current_streak.length}M
                  </div>
                  <div className="text-[10px] text-text-muted mt-1">
                    {symbolView.data.summary.current_streak.type}
                  </div>
                </Card>
                <Card className="p-3">
                  <div className="text-text-muted">Cum Foreign Net</div>
                  <div
                    className={cn(
                      "text-base font-bold tabular",
                      symbolView.data.summary.cumulative_foreign_net >= 0
                        ? "text-accent-green"
                        : "text-accent-red"
                    )}
                  >
                    {formatIDR(symbolView.data.summary.cumulative_foreign_net)}
                  </div>
                </Card>
              </div>

              {/* Monthly table */}
              <Card>
                <CardHeader
                  title={`${selectedSymbol} — Monthly Breakdown`}
                  subtitle="Behavior score, foreign net, bandar lot per bulan"
                />
                <div className="overflow-x-auto -mx-4">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-text-muted border-b border-border">
                        <th className="text-left px-4 py-2 font-medium">Month</th>
                        <th className="text-right px-2 py-2 font-medium">Open</th>
                        <th className="text-right px-2 py-2 font-medium">Close</th>
                        <th className="text-right px-2 py-2 font-medium">Return</th>
                        <th className="text-right px-2 py-2 font-medium">Foreign Net</th>
                        <th className="text-right px-2 py-2 font-medium">Bandar Lot</th>
                        <th className="text-right px-2 py-2 font-medium">Score</th>
                        <th className="text-left px-2 py-2 font-medium">Label</th>
                      </tr>
                    </thead>
                    <tbody>
                      {symbolView.data.months.map((m) => (
                        <tr
                          key={m.month}
                          className="border-b border-border/30 hover:bg-bg-subtle/40"
                        >
                          <td className="px-4 py-2 font-medium">{m.month}</td>
                          <td className="px-2 py-2 text-right tabular">
                            {m.open.toLocaleString()}
                          </td>
                          <td className="px-2 py-2 text-right tabular">
                            {m.close.toLocaleString()}
                          </td>
                          <td
                            className={cn(
                              "px-2 py-2 text-right tabular font-semibold",
                              m.price_return_pct >= 0
                                ? "text-accent-green"
                                : "text-accent-red"
                            )}
                          >
                            {m.price_return_pct > 0 && "+"}
                            {m.price_return_pct.toFixed(2)}%
                          </td>
                          <td
                            className={cn(
                              "px-2 py-2 text-right tabular",
                              m.foreign_net >= 0
                                ? "text-accent-green"
                                : "text-accent-red"
                            )}
                          >
                            {formatIDR(m.foreign_net)}
                          </td>
                          <td
                            className={cn(
                              "px-2 py-2 text-right tabular",
                              m.bandar_net_lot >= 0
                                ? "text-accent-green"
                                : "text-accent-red"
                            )}
                          >
                            {m.bandar_net_lot > 0 && "+"}
                            {(m.bandar_net_lot / 1000).toFixed(0)}K
                          </td>
                          <td className="px-2 py-2 text-right">
                            <span
                              className="inline-block px-2 py-0.5 rounded text-white text-[10px] font-bold tabular"
                              style={{
                                background: scoreToColor(m.behavior_score),
                              }}
                            >
                              {m.behavior_score > 0 && "+"}
                              {m.behavior_score.toFixed(0)}
                            </span>
                          </td>
                          <td className="px-2 py-2 text-[10px] text-text-secondary">
                            {m.behavior_label.replace("_", " ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
