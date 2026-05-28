"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { TestTube, Play, Sparkles } from "lucide-react";
import ReactECharts from "echarts-for-react";
import { backtestApi, type BacktestStrategy, type BacktestResult } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { formatIDR, cn, pctClass } from "@/lib/utils";

export default function BacktestingPage() {
  const [strategy, setStrategy] = useState<BacktestStrategy>({
    min_composite_score: 65,
    min_foreign_score: 55,
    min_momentum_score: 50,
    min_volume_anomaly: 1.0,
    min_inventory_score: 0,
    hold_days: 20,
    max_positions: 5,
    rebalance_every_days: 5,
    stop_loss_pct: -8,
    take_profit_pct: 15,
    initial_capital: 100_000_000,
    commission_pct: 0.0015,
  });

  const [result, setResult] = useState<BacktestResult | null>(null);

  const presets = useQuery({
    queryKey: ["backtest-presets"],
    queryFn: () => backtestApi.presets(),
  });

  const runMut = useMutation({
    mutationFn: () => backtestApi.run({ strategy }),
    onSuccess: (data) => setResult(data),
  });

  const runPresetMut = useMutation({
    mutationFn: (id: string) => backtestApi.runPreset(id, 365),
    onSuccess: (data) => setResult(data),
  });

  const update = (k: keyof BacktestStrategy, v: any) => {
    setStrategy((prev) => ({ ...prev, [k]: v }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <TestTube className="h-6 w-6" /> Backtesting Engine
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Test strategy di historical data — ukur win rate, Sharpe ratio, max drawdown
        </p>
      </div>

      {/* Presets */}
      <Card>
        <CardHeader
          title="Quick Presets"
          subtitle="Coba preset strategy"
          action={<Sparkles className="h-4 w-4 text-accent-yellow" />}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {presets.data?.map((p) => (
            <button
              key={p.id}
              onClick={() => runPresetMut.mutate(p.id)}
              disabled={runPresetMut.isPending}
              className="text-left p-3 rounded-lg bg-bg-subtle border border-border hover:border-accent-blue text-xs disabled:opacity-50"
            >
              <div className="font-semibold mb-1">{p.name}</div>
              <p className="text-text-muted">{p.description}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Custom Strategy Builder */}
      <Card>
        <CardHeader title="Custom Strategy" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <NumField
            label="Min Composite Score"
            value={strategy.min_composite_score}
            onChange={(v) => update("min_composite_score", v)}
          />
          <NumField
            label="Min Foreign Score"
            value={strategy.min_foreign_score}
            onChange={(v) => update("min_foreign_score", v)}
          />
          <NumField
            label="Min Momentum Score"
            value={strategy.min_momentum_score}
            onChange={(v) => update("min_momentum_score", v)}
          />
          <NumField
            label="Min Volume Anomaly"
            step={0.1}
            value={strategy.min_volume_anomaly}
            onChange={(v) => update("min_volume_anomaly", v)}
          />
          <NumField
            label="Hold Days"
            value={strategy.hold_days}
            onChange={(v) => update("hold_days", v)}
          />
          <NumField
            label="Max Positions"
            value={strategy.max_positions}
            onChange={(v) => update("max_positions", v)}
          />
          <NumField
            label="Rebalance Every (days)"
            value={strategy.rebalance_every_days}
            onChange={(v) => update("rebalance_every_days", v)}
          />
          <NumField
            label="Stop Loss %"
            value={strategy.stop_loss_pct ?? undefined}
            onChange={(v) => update("stop_loss_pct", v)}
          />
          <NumField
            label="Take Profit %"
            value={strategy.take_profit_pct ?? undefined}
            onChange={(v) => update("take_profit_pct", v)}
          />
        </div>
        <button
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
          className="mt-4 flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/90 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {runMut.isPending ? "Running..." : "Run Backtest"}
        </button>
      </Card>

      {/* Results */}
      {(runMut.isPending || runPresetMut.isPending) && (
        <Card>
          <div className="text-center py-8 text-text-muted text-sm">
            Running backtest... ini bisa makan waktu 10-30 detik untuk 1 tahun data.
          </div>
        </Card>
      )}

      {result && <BacktestResultPanel result={result} />}
    </div>
  );
}

function NumField({
  label, value, onChange, step,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  step?: number;
}) {
  return (
    <div>
      <label className="block text-text-muted mb-1">{label}</label>
      <input
        type="number"
        step={step ?? 1}
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? undefined : Number(e.target.value))
        }
        className="w-full bg-bg-subtle border border-border rounded-md px-2 py-1 text-text-primary"
      />
    </div>
  );
}

function BacktestResultPanel({ result }: { result: BacktestResult }) {
  const m = result.metrics;

  // Equity curve chart
  const equityOption = {
    backgroundColor: "transparent",
    grid: { left: "5%", right: "4%", top: "8%", bottom: "10%" },
    tooltip: { trigger: "axis", backgroundColor: "#0f172a", borderColor: "#334155", textStyle: { color: "#f1f5f9" } },
    xAxis: {
      type: "category",
      data: result.equity_curve.map((p) => p.date),
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#64748b", fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: "#64748b", fontSize: 10, formatter: (v: number) => `${(v / 1e6).toFixed(0)}Jt` },
    },
    series: [
      {
        type: "line",
        data: result.equity_curve.map((p) => p.equity),
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#22c55e", width: 2 },
        areaStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(34,197,94,0.3)" },
              { offset: 1, color: "rgba(34,197,94,0)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <>
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Trades"
          value={m.total_trades.toString()}
          hint={`${m.winners}W / ${m.losers}L`}
        />
        <StatCard
          label="Win Rate"
          value={
            <span
              className={
                m.win_rate_pct >= 50 ? "text-accent-green" : "text-accent-red"
              }
            >
              {m.win_rate_pct.toFixed(1)}%
            </span>
          }
        />
        <StatCard
          label="Total Return"
          value={
            <span className={pctClass(m.total_return_pct)}>
              {m.total_return_pct > 0 ? "+" : ""}
              {m.total_return_pct.toFixed(2)}%
            </span>
          }
        />
        <StatCard
          label="Sharpe Ratio"
          value={m.sharpe_ratio.toFixed(2)}
          hint={
            m.sharpe_ratio >= 1.5
              ? "Excellent"
              : m.sharpe_ratio >= 1
              ? "Good"
              : m.sharpe_ratio >= 0
              ? "Mediocre"
              : "Poor"
          }
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Avg Win"
          value={
            <span className="text-accent-green">
              +{m.avg_win_pct.toFixed(2)}%
            </span>
          }
        />
        <StatCard
          label="Avg Loss"
          value={
            <span className="text-accent-red">
              {m.avg_loss_pct.toFixed(2)}%
            </span>
          }
        />
        <StatCard
          label="Max Drawdown"
          value={
            <span className="text-accent-red">
              {m.max_drawdown_pct.toFixed(2)}%
            </span>
          }
        />
        <StatCard
          label="Profit Factor"
          value={m.profit_factor.toFixed(2)}
          hint={m.profit_factor >= 1.5 ? "Profitable" : "Marginal"}
        />
      </div>

      {/* Equity Curve */}
      <Card>
        <CardHeader
          title="Equity Curve"
          subtitle={`${result.period.start} → ${result.period.end}`}
        />
        {result.equity_curve.length > 0 ? (
          <ReactECharts
            option={equityOption}
            style={{ height: "320px", width: "100%" }}
          />
        ) : (
          <div className="text-center py-8 text-text-muted text-sm">
            No equity curve data
          </div>
        )}
      </Card>

      {/* Recent Trades */}
      <Card>
        <CardHeader title="Recent Trades" subtitle="Last 30 trades" />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border">
                <th className="text-left px-4 py-2 font-medium">Symbol</th>
                <th className="text-left px-2 py-2 font-medium">Entry</th>
                <th className="text-right px-2 py-2 font-medium">Entry Price</th>
                <th className="text-left px-2 py-2 font-medium">Exit</th>
                <th className="text-right px-2 py-2 font-medium">Exit Price</th>
                <th className="text-right px-2 py-2 font-medium">Return</th>
                <th className="text-left px-2 py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.slice(-30).reverse().map((t, i) => (
                <tr key={i} className="border-b border-border/30">
                  <td className="px-4 py-2 font-mono font-semibold">
                    {t.symbol}
                  </td>
                  <td className="px-2 py-2 text-text-secondary">
                    {t.entry_date}
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {t.entry_price.toLocaleString()}
                  </td>
                  <td className="px-2 py-2 text-text-secondary">
                    {t.exit_date}
                  </td>
                  <td className="px-2 py-2 text-right tabular">
                    {t.exit_price.toLocaleString()}
                  </td>
                  <td
                    className={cn(
                      "px-2 py-2 text-right tabular font-semibold",
                      t.return_pct >= 0
                        ? "text-accent-green"
                        : "text-accent-red"
                    )}
                  >
                    {t.return_pct > 0 ? "+" : ""}
                    {t.return_pct.toFixed(2)}%
                  </td>
                  <td className="px-2 py-2 text-[10px]">
                    <Badge
                      variant={
                        t.exit_reason === "TAKE_PROFIT"
                          ? "success"
                          : t.exit_reason === "STOP_LOSS"
                          ? "danger"
                          : "default"
                      }
                    >
                      {t.exit_reason}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
