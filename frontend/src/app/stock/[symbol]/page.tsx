"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import {
  TrendingUp, TrendingDown, AlertTriangle, Eye, Users, BarChart3,
  Target, Zap, Layers,
} from "lucide-react";
import {
  symbolsApi, brokerApi, flowApi, verdictApi,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { VerdictBadge, RetailNonFlowBadge } from "@/components/ui/VerdictBadge";
import { PriceChart } from "@/components/charts/PriceChart";
import { InventoryChart } from "@/components/charts/InventoryChart";
import { ForeignFlowChart } from "@/components/charts/ForeignFlowChart";
import { TransactionChart } from "@/components/charts/TransactionChart";
import { MultiEntityChart } from "@/components/charts/MultiEntityChart";
import { BalancePositionChart } from "@/components/charts/BalancePositionChart";
import {
  formatIDR, formatPrice, pctClass, scoreBgClass, signalClass, cn,
} from "@/lib/utils";

export default function StockDetailPage() {
  const params = useParams();
  const symbol = (params.symbol as string).toUpperCase();
  const [periodDays, setPeriodDays] = useState(60);

  const detail = useQuery({
    queryKey: ["symbol", symbol],
    queryFn: () => symbolsApi.get(symbol),
  });
  const candles = useQuery({
    queryKey: ["candles", symbol, periodDays],
    queryFn: () => symbolsApi.candles(symbol, periodDays),
  });
  const inventory = useQuery({
    queryKey: ["inventory", symbol, periodDays],
    queryFn: () => brokerApi.inventory(symbol, periodDays, 6),
  });
  const accumulators = useQuery({
    queryKey: ["accumulators", symbol, periodDays],
    queryFn: () => brokerApi.topAccumulators(symbol, periodDays, 15),
  });
  const foreign = useQuery({
    queryKey: ["foreign", symbol, periodDays],
    queryFn: () => flowApi.foreign(symbol, periodDays),
  });
  const transaction = useQuery({
    queryKey: ["transaction", symbol, 120],
    queryFn: () => flowApi.transaction(symbol, 120),
  });
  const balance = useQuery({
    queryKey: ["balance", symbol, periodDays],
    queryFn: () => flowApi.balance(symbol, periodDays),
  });
  const verdict = useQuery({
    queryKey: ["verdict", symbol],
    queryFn: () => verdictApi.get(symbol),
  });
  const multiEntity = useQuery({
    queryKey: ["multi-entity", symbol, periodDays],
    queryFn: () => flowApi.multiEntity(symbol, periodDays),
  });

  const d = detail.data;
  const score = d?.score;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold font-mono">{symbol}</h1>
            {verdict.data && (
              <VerdictBadge
                verdict={verdict.data.verdict}
                size="lg"
                tooltip={verdict.data.explanation}
              />
            )}
            {d && (
              <Badge variant="info" className="text-xs">
                {d.sector}
              </Badge>
            )}
          </div>
          <p className="text-sm text-text-secondary mt-1">{d?.name}</p>
        </div>

        {d?.latest && (
          <div className="text-right">
            <div className="text-3xl font-bold tabular">
              {formatPrice(d.latest.close)}
            </div>
            <div
              className={cn(
                "text-sm tabular flex items-center justify-end gap-1",
                pctClass(d.latest.pct_change)
              )}
            >
              {d.latest.pct_change > 0 ? (
                <TrendingUp className="h-4 w-4" />
              ) : (
                <TrendingDown className="h-4 w-4" />
              )}
              {d.latest.pct_change > 0 && "+"}
              {d.latest.pct_change.toFixed(2)}%
            </div>
          </div>
        )}
      </div>

      {/* Verdict & Retail Non-Flow Card */}
      {verdict.data && (
        <Card className="bg-gradient-to-br from-bg-card to-bg-subtle border-border">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Verdict block */}
            <div className="flex gap-3 items-start">
              <VerdictBadge
                verdict={verdict.data.verdict}
                size="lg"
                tooltip={verdict.data.explanation}
              />
              <div className="flex-1">
                <div className="text-xs text-text-muted uppercase tracking-wide mb-1">
                  Kesimpulan Trend
                </div>
                <div className="text-sm font-medium mb-1">
                  {verdict.data.verdict === "GREEN_CHECK" && "Akumulasi Konsisten"}
                  {verdict.data.verdict === "ORANGE_X" && "Sideways / Mixed"}
                  {verdict.data.verdict === "RED_MINUS" && "Distribusi Konsisten"}
                  <span className="ml-2 text-xs text-text-muted">
                    ({verdict.data.confidence.toFixed(0)}% confidence)
                  </span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {verdict.data.explanation}
                </p>
                <div className="grid grid-cols-3 gap-2 mt-3 text-[10px]">
                  <div className="rounded bg-bg-subtle border border-border px-2 py-1">
                    <div className="text-text-muted">Slope 5D</div>
                    <div
                      className={cn(
                        "tabular font-semibold",
                        verdict.data.slope_5d > 0
                          ? "text-accent-green"
                          : "text-accent-red"
                      )}
                    >
                      {verdict.data.slope_5d > 0 ? "+" : ""}
                      {verdict.data.slope_5d.toFixed(0)}
                    </div>
                  </div>
                  <div className="rounded bg-bg-subtle border border-border px-2 py-1">
                    <div className="text-text-muted">Slope 15D</div>
                    <div
                      className={cn(
                        "tabular font-semibold",
                        verdict.data.slope_15d > 0
                          ? "text-accent-green"
                          : "text-accent-red"
                      )}
                    >
                      {verdict.data.slope_15d > 0 ? "+" : ""}
                      {verdict.data.slope_15d.toFixed(0)}
                    </div>
                  </div>
                  <div className="rounded bg-bg-subtle border border-border px-2 py-1">
                    <div className="text-text-muted">R² 15D</div>
                    <div className="tabular font-semibold">
                      {verdict.data.r_squared_15d.toFixed(2)}
                    </div>
                  </div>
                </div>
                <div className="text-[10px] text-text-muted mt-2">
                  Konsistensi: {verdict.data.consistency_pct.toFixed(0)}% (
                  {verdict.data.buy_days_15d} dari 15 hari net buy) · Bandar lot
                  growth 15D: {verdict.data.bandar_lot_growth_15d > 0 ? "+" : ""}
                  {verdict.data.bandar_lot_growth_15d.toLocaleString()} lot
                </div>
              </div>
            </div>

            {/* Retail Non-Flow block */}
            <div className="flex gap-3 items-start border-l border-border pl-4">
              <RetailNonFlowBadge
                score={verdict.data.retail_non_flow_score}
                label={verdict.data.retail_non_flow_label}
                size="md"
              />
              <div className="flex-1">
                <div className="text-xs text-text-muted uppercase tracking-wide mb-1">
                  Retail Non-Flow (Kontrarian)
                </div>
                <div className="text-sm font-medium mb-1">
                  Score: {verdict.data.retail_non_flow_score.toFixed(0)}/100
                </div>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {verdict.data.retail_non_flow_explanation}
                </p>
                <div className="text-[10px] text-text-muted mt-2">
                  Retail net 15D:{" "}
                  <span
                    className={
                      verdict.data.retail_net_value_15d >= 0
                        ? "text-accent-red"
                        : "text-accent-green"
                    }
                  >
                    {formatIDR(verdict.data.retail_net_value_15d)}
                  </span>{" "}
                  {verdict.data.retail_net_value_15d >= 0
                    ? "(retail beli — bearish kontrarian)"
                    : "(retail jual — bullish kontrarian)"}
                </div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Period selector */}
      <div className="flex gap-2">
        {[30, 60, 90, 120].map((p) => (
          <button
            key={p}
            onClick={() => setPeriodDays(p)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs",
              periodDays === p
                ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                : "bg-bg-subtle border border-border text-text-secondary"
            )}
          >
            {p}D
          </button>
        ))}
      </div>

      {/* Score panel */}
      {score && (
        <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
          <ScoreTile label="Bandar" value={score.bandar_score} icon={<Zap className="h-3 w-3" />} primary />
          <ScoreTile label="Foreign" value={score.foreign_score} />
          <ScoreTile label="Inventory" value={score.inventory_score} />
          <ScoreTile label="Volume" value={score.volume_score} />
          <ScoreTile label="Momentum" value={score.momentum_score} />
          <ScoreTile label="Consistency" value={score.consistency_score} />
          <Card className="flex flex-col justify-center">
            <div className="text-[10px] uppercase tracking-wide text-text-muted">
              Signal
            </div>
            <div
              className={`mt-1 px-2 py-1 rounded text-xs text-center ${signalClass(score.smart_money_signal)}`}
            >
              {score.smart_money_signal}
            </div>
            <div className="text-[10px] text-text-muted mt-1 truncate">
              {score.behavior_label}
            </div>
          </Card>
        </div>
      )}

      {/* Price chart */}
      <Card>
        <CardHeader
          title="Price & Volume"
          subtitle={`${periodDays} days OHLCV`}
        />
        {candles.data && candles.data.length > 0 && (
          <PriceChart candles={candles.data} height={360} />
        )}
      </Card>

      {/* Inventory chart with stealth detection */}
      <Card>
        <CardHeader
          title="Inventory Chart — Broker Accumulation Lines"
          subtitle="Top 6 brokers by absolute net flow · cumulative net lot vs price"
          action={
            inventory.data?.stealth_accumulation.detected && (
              <Badge variant="success">
                <AlertTriangle className="h-3 w-3 inline mr-1" />
                STEALTH ACCUMULATION
              </Badge>
            )
          }
        />
        {inventory.data && <InventoryChart data={inventory.data} />}
        {inventory.data?.stealth_accumulation && (
          <div className="mt-3 p-3 rounded-lg bg-bg-subtle border border-border-muted text-xs text-text-secondary">
            <strong className="text-text-primary">Stealth Analysis:</strong>{" "}
            {inventory.data.stealth_accumulation.interpretation}
          </div>
        )}
      </Card>

      {/* Top accumulators table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader
            title="Top Accumulators"
            subtitle="Brokers buying the most over the period"
            action={<Users className="h-4 w-4" />}
          />
          <div className="overflow-x-auto -mx-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border">
                  <th className="text-left px-4 py-2 font-medium">Broker</th>
                  <th className="text-right px-2 py-2 font-medium">Net Lot</th>
                  <th className="text-right px-2 py-2 font-medium">Net Value</th>
                  <th className="text-right px-2 py-2 font-medium">Avg Price</th>
                  <th className="text-left px-2 py-2 font-medium">Behavior</th>
                </tr>
              </thead>
              <tbody>
                {accumulators.data?.filter((a) => a.net_value > 0).slice(0, 10).map((a) => (
                  <tr
                    key={a.broker_code}
                    className="border-b border-border/30"
                  >
                    <td className="px-4 py-2">
                      <div className="font-mono font-semibold">
                        {a.broker_code}
                      </div>
                      <div className="text-text-muted text-[10px]">
                        {a.broker_name} · {a.cluster_label}
                        {a.is_foreign && (
                          <span className="ml-1 text-accent-blue">[F]</span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right tabular text-accent-green">
                      +{(a.net_lot / 1000).toFixed(0)}K
                    </td>
                    <td className="px-2 py-2 text-right tabular text-accent-green">
                      {formatIDR(a.net_value)}
                    </td>
                    <td className="px-2 py-2 text-right tabular">
                      {formatPrice(a.avg_buy_price)}
                    </td>
                    <td className="px-2 py-2">
                      <span className="text-[10px] text-text-secondary">
                        {a.behavior_label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Top Distributors"
            subtitle="Brokers selling the most over the period"
            action={<Eye className="h-4 w-4" />}
          />
          <div className="overflow-x-auto -mx-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border">
                  <th className="text-left px-4 py-2 font-medium">Broker</th>
                  <th className="text-right px-2 py-2 font-medium">Net Lot</th>
                  <th className="text-right px-2 py-2 font-medium">Net Value</th>
                  <th className="text-right px-2 py-2 font-medium">Avg Price</th>
                  <th className="text-left px-2 py-2 font-medium">Behavior</th>
                </tr>
              </thead>
              <tbody>
                {accumulators.data?.filter((a) => a.net_value < 0).sort((x, y) => x.net_value - y.net_value).slice(0, 10).map((a) => (
                  <tr key={a.broker_code} className="border-b border-border/30">
                    <td className="px-4 py-2">
                      <div className="font-mono font-semibold">
                        {a.broker_code}
                      </div>
                      <div className="text-text-muted text-[10px]">
                        {a.broker_name} · {a.cluster_label}
                        {a.is_foreign && (
                          <span className="ml-1 text-accent-blue">[F]</span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right tabular text-accent-red">
                      {(a.net_lot / 1000).toFixed(0)}K
                    </td>
                    <td className="px-2 py-2 text-right tabular text-accent-red">
                      {formatIDR(a.net_value)}
                    </td>
                    <td className="px-2 py-2 text-right tabular">
                      {formatPrice(a.avg_buy_price)}
                    </td>
                    <td className="px-2 py-2 text-[10px] text-text-secondary">
                      {a.behavior_label}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Foreign flow */}
      <Card>
        <CardHeader
          title="Foreign Flow"
          subtitle={`Net buy/sell · cumulative · price · ${periodDays}D`}
          action={
            foreign.data?.summary.divergence.type && (
              <Badge
                variant={
                  foreign.data.summary.divergence.type === "BULLISH_DIVERGENCE"
                    ? "success"
                    : "danger"
                }
              >
                {foreign.data.summary.divergence.type}
              </Badge>
            )
          }
        />
        {foreign.data && <ForeignFlowChart flow={foreign.data} />}
        {foreign.data?.summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-xs">
            <Stat
              label="Net Total"
              value={formatIDR(foreign.data.summary.net_total)}
              positive={foreign.data.summary.net_total >= 0}
            />
            <Stat label="Net 5D" value={formatIDR(foreign.data.summary.net_5d)} positive={foreign.data.summary.net_5d >= 0} />
            <Stat label="Net 20D" value={formatIDR(foreign.data.summary.net_20d)} positive={foreign.data.summary.net_20d >= 0} />
            <Stat
              label="Buy Days / Sell Days"
              value={`${foreign.data.summary.buy_days} / ${foreign.data.summary.sell_days}`}
            />
          </div>
        )}
        {foreign.data?.summary.divergence.interpretation && (
          <div className="mt-3 p-3 rounded-lg bg-bg-subtle border border-border-muted text-xs text-text-secondary">
            <strong className="text-text-primary">Divergence:</strong>{" "}
            {foreign.data.summary.divergence.interpretation}
          </div>
        )}
      </Card>

      {/* Multi-Entity Flow Chart */}
      <Card>
        <CardHeader
          title="Multi-Entity Flow Chart"
          subtitle="Foreign / Institutional / Market Maker / Retail / Zombie — siapa akumulasi, siapa distribusi"
          action={<Layers className="h-4 w-4" />}
        />
        {multiEntity.data && multiEntity.data.entities.length > 0 ? (
          <MultiEntityChart data={multiEntity.data} />
        ) : (
          <div className="text-center py-8 text-text-muted text-sm">
            Loading multi-entity data...
          </div>
        )}
      </Card>

      {/* Transaction chart */}
      <Card>
        <CardHeader
          title="Transaction Chart — Multi-Month Flow Analysis"
          subtitle="Price · cumulative foreign net · MFI · divergence markers"
          action={
            transaction.data?.hidden_accumulation.detected && (
              <Badge variant="success">
                <Target className="h-3 w-3 inline mr-1" />
                HIDDEN ACCUMULATION
              </Badge>
            )
          }
        />
        {transaction.data && <TransactionChart txn={transaction.data} />}
        {transaction.data?.hidden_accumulation && (
          <div className="mt-3 p-3 rounded-lg bg-bg-subtle border border-border-muted text-xs text-text-secondary">
            <strong className="text-text-primary">Hidden Accumulation:</strong>{" "}
            {transaction.data.hidden_accumulation.interpretation}
          </div>
        )}
      </Card>

      {/* Balance position */}
      <Card>
        <CardHeader
          title="Balance Position — Entity Type Breakdown"
          subtitle="Daily participation by foreign / institutional / retail / corporate"
          action={<BarChart3 className="h-4 w-4" />}
        />
        {balance.data && <BalancePositionChart balance={balance.data} mode="buy" />}
        {balance.data?.summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-4 text-xs">
            {Object.entries(balance.data.summary).map(([bucket, val]: [string, any]) => (
              <div
                key={bucket}
                className="rounded-lg bg-bg-subtle border border-border p-3"
              >
                <div className="text-text-muted capitalize">{bucket}</div>
                <div className="text-lg font-bold tabular">
                  {val.buy_pct.toFixed(1)}%
                </div>
                <div
                  className={cn(
                    "text-xs tabular",
                    val.net_value >= 0 ? "text-accent-green" : "text-accent-red"
                  )}
                >
                  Net: {formatIDR(val.net_value)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function ScoreTile({
  label,
  value,
  icon,
  primary = false,
}: {
  label: string;
  value: number;
  icon?: React.ReactNode;
  primary?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-3 flex flex-col justify-center",
        primary
          ? "bg-gradient-to-br from-accent-blue/15 to-accent-purple/10 border-accent-blue/30"
          : "bg-bg-card border-border"
      )}
    >
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-text-muted">
        {icon}
        {label}
      </div>
      <div className={cn("text-2xl font-bold tabular mt-1", primary && "text-accent-blue")}>
        {value.toFixed(0)}
      </div>
      <div className="h-1 rounded bg-bg-subtle mt-1.5 overflow-hidden">
        <div
          className={cn(
            "h-full",
            value >= 75 ? "bg-accent-green"
              : value >= 60 ? "bg-accent-cyan"
              : value >= 40 ? "bg-accent-yellow"
              : value >= 25 ? "bg-accent-orange"
              : "bg-accent-red"
          )}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function Stat({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="rounded-lg bg-bg-subtle border border-border p-2.5">
      <div className="text-text-muted text-[10px] uppercase tracking-wide">
        {label}
      </div>
      <div
        className={cn(
          "text-sm font-semibold tabular mt-0.5",
          positive === true && "text-accent-green",
          positive === false && "text-accent-red"
        )}
      >
        {value}
      </div>
    </div>
  );
}
