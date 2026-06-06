"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Activity, Layers, Eye, ArrowUpRight, ArrowDownRight,
} from "lucide-react";
import { sectorApi, screenerApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { formatIDR, formatPrice, pctClass, scoreBgClass, signalClass } from "@/lib/utils";

export default function DashboardPage() {
  const sectors = useQuery({
    queryKey: ["sectors-activity", 5],
    queryFn: () => sectorApi.activity(5),
  });

  const heatmap = useQuery({
    queryKey: ["heatmap"],
    queryFn: () => sectorApi.heatmap(),
  });

  const top = useQuery({
    queryKey: ["screener-top-bandar"],
    queryFn: () =>
      screenerApi.scan({
        bandar_score_min: 70,
        smart_money_signal: "accumulation",
        sort_by: "bandar_score",
        limit: 8,
      }),
  });

  const distribution = useQuery({
    queryKey: ["screener-distribution"],
    queryFn: () =>
      screenerApi.scan({
        smart_money_signal: "distribution",
        sort_by: "bandar_score",
        sort_desc: false,
        limit: 5,
      }),
  });

  // Market summary stats
  const marketStats = (() => {
    if (!heatmap.data) return null;
    const total = heatmap.data.length;
    const advance = heatmap.data.filter((h) => h.pct_change > 0).length;
    const decline = heatmap.data.filter((h) => h.pct_change < 0).length;
    const totalValue = heatmap.data.reduce((s, h) => s + (h.value || 0), 0);
    const avgChange =
      heatmap.data.reduce((s, h) => s + h.pct_change, 0) / total;
    return { total, advance, decline, totalValue, avgChange };
  })();

  const totalForeignNet = sectors.data
    ? sectors.data.reduce((s, x) => s + x.foreign_net, 0)
    : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Market Dashboard</h1>
        <p className="text-sm text-text-secondary mt-1">
          Smart money flow & broker accumulation overview
        </p>
      </div>

      {/* Market Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Advance / Decline"
          value={
            marketStats ? (
              <span className="tabular text-xl">
                <span className="text-accent-green">{marketStats.advance}</span>
                <span className="text-text-muted mx-1">/</span>
                <span className="text-accent-red">{marketStats.decline}</span>
              </span>
            ) : (
              "-"
            )
          }
          icon={<Activity className="h-4 w-4" />}
          hint={`${marketStats?.total ?? 0} stocks`}
        />
        <StatCard
          label="Avg Change"
          value={
            marketStats ? (
              <span className={pctClass(marketStats.avgChange)}>
                {marketStats.avgChange > 0 ? "+" : ""}
                {marketStats.avgChange.toFixed(2)}%
              </span>
            ) : "-"
          }
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <StatCard
          label="Foreign Net (5D)"
          value={
            <span className={totalForeignNet >= 0 ? "text-accent-green" : "text-accent-red"}>
              {formatIDR(totalForeignNet)}
            </span>
          }
          icon={<Eye className="h-4 w-4" />}
        />
        <StatCard
          label="Total Value"
          value={marketStats ? formatIDR(marketStats.totalValue) : "-"}
          icon={<Layers className="h-4 w-4" />}
          hint="Today's traded value"
        />
      </div>

      {/* Top Bandar Picks */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Smart Money Accumulation"
            subtitle="Top stocks with highest BandarScore (institutional buying pressure)"
            action={
              <Link
                href="/screener"
                className="text-xs text-accent-blue hover:underline flex items-center gap-1"
              >
                See all <ArrowUpRight className="h-3 w-3" />
              </Link>
            }
          />
          <div className="overflow-x-auto -mx-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-text-muted border-b border-border">
                  <th className="text-left px-4 py-2 font-medium">Symbol</th>
                  <th className="text-left px-2 py-2 font-medium">Sector</th>
                  <th className="text-right px-2 py-2 font-medium">Price</th>
                  <th className="text-right px-2 py-2 font-medium">Foreign Net 20D</th>
                  <th className="text-right px-2 py-2 font-medium">Score</th>
                  <th className="text-left px-2 py-2 font-medium">Signal</th>
                </tr>
              </thead>
              <tbody>
                {top.data?.results?.map((r) => (
                  <tr
                    key={r.symbol}
                    className="border-b border-border/50 hover:bg-bg-subtle/50"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/stock/${r.symbol}`}
                        className="font-mono font-semibold text-accent-blue hover:underline"
                      >
                        {r.symbol}
                      </Link>
                      <div className="text-xs text-text-muted">{r.name}</div>
                    </td>
                    <td className="px-2 py-2.5 text-xs text-text-secondary">
                      {r.sector}
                    </td>
                    <td className="px-2 py-2.5 text-right tabular">
                      {formatPrice(r.close)}
                    </td>
                    <td
                      className={`px-2 py-2.5 text-right tabular ${
                        r.foreign_net >= 0 ? "text-accent-green" : "text-accent-red"
                      }`}
                    >
                      {formatIDR(r.foreign_net)}
                    </td>
                    <td className="px-2 py-2.5 text-right">
                      <span className={`score-badge ${scoreBgClass(r.bandar_score)}`}>
                        {r.bandar_score.toFixed(0)}
                      </span>
                    </td>
                    <td className="px-2 py-2.5">
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded ${signalClass(
                          r.smart_money_signal
                        )}`}
                      >
                        {r.smart_money_signal}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Distribution warnings */}
        <Card>
          <CardHeader
            title="Distribution Warning"
            subtitle="Smart money exiting"
          />
          <div className="space-y-2">
            {distribution.data?.results?.map((r) => (
              <Link
                key={r.symbol}
                href={`/stock/${r.symbol}`}
                className="flex items-center justify-between p-2 rounded-lg bg-bg-subtle hover:bg-bg-subtle/70"
              >
                <div>
                  <div className="font-mono font-semibold text-sm">
                    {r.symbol}
                  </div>
                  <div className="text-xs text-text-muted">{r.sector}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-accent-red flex items-center gap-1 justify-end">
                    <TrendingDown className="h-3 w-3" />
                    {r.bandar_score.toFixed(0)}
                  </div>
                  <div className="text-[11px] text-text-muted">
                    {formatIDR(r.foreign_net)}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      {/* Sector Activity */}
      <Card>
        <CardHeader
          title="Sector Activity"
          subtitle="Capital flow & momentum ranking"
          action={
            <Link
              href="/sectors"
              className="text-xs text-accent-blue hover:underline flex items-center gap-1"
            >
              Detail <ArrowUpRight className="h-3 w-3" />
            </Link>
          }
        />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {sectors.data?.map((s) => (
            <div
              key={s.code}
              className="rounded-lg bg-bg-subtle border border-border p-3 hover:border-border-muted transition"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: s.color }}
                  />
                  <span className="text-sm font-semibold">{s.code}</span>
                </div>
                <Badge
                  variant={
                    s.flow_label.startsWith("INFLOW") ? "success" : "danger"
                  }
                  className="text-[10px]"
                >
                  #{s.rank}
                </Badge>
              </div>
              <div className="text-xs text-text-muted mb-2">{s.name}</div>
              <div className="flex items-center justify-between text-xs">
                <span
                  className={
                    s.foreign_net >= 0 ? "text-accent-green" : "text-accent-red"
                  }
                >
                  {s.foreign_net >= 0 ? (
                    <ArrowUpRight className="inline h-3 w-3" />
                  ) : (
                    <ArrowDownRight className="inline h-3 w-3" />
                  )}{" "}
                  {formatIDR(s.foreign_net)}
                </span>
                <span className={pctClass(s.momentum_pct)}>
                  {s.momentum_pct >= 0 ? "+" : ""}
                  {s.momentum_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
