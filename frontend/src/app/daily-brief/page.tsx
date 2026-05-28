"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Newspaper, Download, RefreshCw, TrendingUp, TrendingDown, AlertTriangle,
} from "lucide-react";
import { dailyBriefApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { formatIDR, formatPrice, pctClass, scoreBgClass } from "@/lib/utils";

const QUADRANT_COLOR: Record<string, string> = {
  leading: "bg-accent-green/10 text-accent-green border-accent-green/30",
  improving: "bg-accent-blue/10 text-accent-blue border-accent-blue/30",
  weakening: "bg-accent-orange/10 text-accent-orange border-accent-orange/30",
  lagging: "bg-accent-red/10 text-accent-red border-accent-red/30",
};

export default function DailyBriefPage() {
  const brief = useQuery({
    queryKey: ["daily-brief"],
    queryFn: () => dailyBriefApi.get(),
    staleTime: 60_000,
  });

  const downloadMarkdown = async () => {
    const md = await dailyBriefApi.markdown();
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bandarscope-brief-${brief.data?.as_of}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (brief.isLoading) {
    return (
      <div className="text-center py-12 text-text-muted">
        Generating daily brief...
      </div>
    );
  }

  const b = brief.data;
  if (!b) return null;

  const m = b.market_summary;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Newspaper className="h-6 w-6" /> Daily Brief
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Smart money intelligence untuk perencanaan trade besok ·{" "}
            <span className="text-text-primary font-medium">{b.as_of}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => brief.refetch()}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-bg-subtle border border-border text-xs hover:bg-bg-subtle/70"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <button
            onClick={downloadMarkdown}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-accent-blue text-white text-xs hover:bg-accent-blue/90"
          >
            <Download className="h-3.5 w-3.5" /> Markdown
          </button>
        </div>
      </div>

      {/* Market Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Advance / Decline"
          value={
            <span className="tabular text-xl">
              <span className="text-accent-green">{m.advance}</span>
              <span className="text-text-muted mx-1">/</span>
              <span className="text-accent-red">{m.decline}</span>
            </span>
          }
          hint={`${(m.advance_ratio * 100).toFixed(0)}% advance ratio`}
        />
        <StatCard
          label="Avg Change"
          value={
            <span className={pctClass(m.avg_change)}>
              {m.avg_change > 0 ? "+" : ""}
              {m.avg_change.toFixed(2)}%
            </span>
          }
        />
        <StatCard
          label="Foreign Net"
          value={
            <span
              className={
                m.foreign_net >= 0 ? "text-accent-green" : "text-accent-red"
              }
            >
              {formatIDR(m.foreign_net)}
            </span>
          }
        />
        <StatCard
          label="Total Value"
          value={formatIDR(m.total_value)}
          hint="Today's traded value"
        />
      </div>

      {/* Top Accumulation */}
      <Card>
        <CardHeader
          title="Top Accumulation Picks"
          subtitle="Saham dengan BandarScore tertinggi"
        />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                <th className="text-left px-4 py-2 font-medium">#</th>
                <th className="text-left px-2 py-2 font-medium">Symbol</th>
                <th className="text-left px-2 py-2 font-medium">Sector</th>
                <th className="text-right px-2 py-2 font-medium">Price</th>
                <th className="text-right px-2 py-2 font-medium">Foreign 20D</th>
                <th className="text-right px-2 py-2 font-medium">Score</th>
                <th className="text-left px-2 py-2 font-medium">Behavior</th>
              </tr>
            </thead>
            <tbody>
              {b.top_accumulation.slice(0, 10).map((s: any, i: number) => (
                <tr
                  key={s.symbol}
                  className="border-b border-border/30 hover:bg-bg-subtle/40"
                >
                  <td className="px-4 py-2 text-text-muted">#{i + 1}</td>
                  <td className="px-2 py-2">
                    <Link
                      href={`/stock/${s.symbol}`}
                      className="font-mono font-semibold text-accent-blue hover:underline"
                    >
                      {s.symbol}
                    </Link>
                    <div className="text-xs text-text-muted">{s.name}</div>
                  </td>
                  <td className="px-2 py-2 text-xs text-text-secondary">
                    {s.sector}
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {formatPrice(s.close)}
                  </td>
                  <td
                    className={`px-2 py-2 text-right tabular ${
                      s.foreign_net >= 0
                        ? "text-accent-green"
                        : "text-accent-red"
                    }`}
                  >
                    {formatIDR(s.foreign_net)}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <span
                      className={`score-badge ${scoreBgClass(s.bandar_score)}`}
                    >
                      {s.bandar_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-text-secondary text-xs">
                    {s.behavior_label}
                  </td>
                </tr>
              ))}
              {b.top_accumulation.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="text-center py-6 text-text-muted text-sm"
                  >
                    Tidak ada saham dengan signal akumulasi kuat hari ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Distribution Warnings */}
      <Card>
        <CardHeader
          title="Distribution Warnings"
          subtitle="Smart money exit candidates"
          action={<AlertTriangle className="h-4 w-4 text-accent-red" />}
        />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                <th className="text-left px-4 py-2 font-medium">#</th>
                <th className="text-left px-2 py-2 font-medium">Symbol</th>
                <th className="text-left px-2 py-2 font-medium">Sector</th>
                <th className="text-right px-2 py-2 font-medium">Price</th>
                <th className="text-right px-2 py-2 font-medium">Score</th>
                <th className="text-left px-2 py-2 font-medium">Behavior</th>
              </tr>
            </thead>
            <tbody>
              {b.distribution_warnings.slice(0, 5).map((s: any, i: number) => (
                <tr
                  key={s.symbol}
                  className="border-b border-border/30 hover:bg-bg-subtle/40"
                >
                  <td className="px-4 py-2 text-text-muted">#{i + 1}</td>
                  <td className="px-2 py-2">
                    <Link
                      href={`/stock/${s.symbol}`}
                      className="font-mono font-semibold text-accent-red hover:underline"
                    >
                      {s.symbol}
                    </Link>
                    <div className="text-xs text-text-muted">{s.name}</div>
                  </td>
                  <td className="px-2 py-2 text-xs text-text-secondary">
                    {s.sector}
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {formatPrice(s.close)}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <span
                      className={`score-badge ${scoreBgClass(s.bandar_score)}`}
                    >
                      {s.bandar_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-text-secondary text-xs">
                    {s.behavior_label}
                  </td>
                </tr>
              ))}
              {b.distribution_warnings.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="text-center py-6 text-text-muted text-sm"
                  >
                    Tidak ada warning distribusi signifikan.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Sector Rotation */}
      <Card>
        <CardHeader
          title="Sector Rotation Snapshot"
          subtitle="Berdasarkan RRG (Relative Rotation Graph)"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {(["leading", "improving", "weakening", "lagging"] as const).map(
            (q) => (
              <div
                key={q}
                className={`rounded-lg border p-3 ${QUADRANT_COLOR[q]}`}
              >
                <div className="text-xs uppercase tracking-wide font-semibold mb-2">
                  {q}
                </div>
                {(b.sector_rotation[q] || []).length === 0 ? (
                  <div className="text-xs text-text-muted italic">
                    No sectors here
                  </div>
                ) : (
                  <div className="space-y-1">
                    {(b.sector_rotation[q] || []).map((s: any) => (
                      <div
                        key={s.code}
                        className="flex justify-between text-xs"
                      >
                        <span className="font-semibold">{s.code}</span>
                        <span className="tabular text-text-muted">
                          RS {s.rs_ratio.toFixed(1)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </div>
      </Card>

      {/* Pattern Alerts */}
      {b.pattern_alerts.length > 0 && (
        <Card>
          <CardHeader
            title="Pattern Alerts"
            subtitle={`${b.pattern_alerts.length} pattern terdeteksi hari ini`}
          />
          <div className="space-y-2">
            {b.pattern_alerts.slice(0, 10).map((p: any, i: number) => (
              <div
                key={`${p.symbol}-${p.pattern}-${i}`}
                className="rounded-lg bg-bg-subtle border border-border p-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <Link
                    href={`/stock/${p.symbol}`}
                    className="font-mono font-semibold text-accent-blue hover:underline"
                  >
                    {p.symbol}
                  </Link>
                  <Badge variant="info" className="text-[10px]">
                    {p.pattern}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-text-muted">{p.sector}</span>
                  <span className="text-text-muted">·</span>
                  <span className={scoreBgClass(p.confidence) + " px-1.5 py-0.5 rounded text-[10px] border"}>
                    Confidence {p.confidence.toFixed(0)}
                  </span>
                </div>
                <p className="text-xs text-text-secondary mt-1">
                  {p.interpretation}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Stocks to Watch */}
      {b.stocks_to_watch.length > 0 && (
        <Card>
          <CardHeader title="Stocks to Watch" subtitle="Action items besok" />
          <div className="space-y-2">
            {b.stocks_to_watch.map((w: any) => (
              <div
                key={w.symbol}
                className="rounded-lg bg-bg-subtle border border-border p-3 flex items-center gap-3"
              >
                <Badge
                  variant={w.side === "LONG" ? "success" : "danger"}
                  className="shrink-0"
                >
                  {w.side}
                </Badge>
                <Link
                  href={`/stock/${w.symbol}`}
                  className="font-mono font-bold text-accent-blue hover:underline shrink-0"
                >
                  {w.symbol}
                </Link>
                <span className="text-xs text-text-secondary">{w.note}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
