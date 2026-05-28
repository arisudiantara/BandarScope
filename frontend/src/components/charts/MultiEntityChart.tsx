"use client";

import ReactECharts from "echarts-for-react";
import type { MultiEntityResponse } from "@/lib/api";
import { formatIDR, cn } from "@/lib/utils";

const ENTITY_KEYS = [
  "foreign",
  "institutional",
  "market_maker",
  "retail",
  "zombie",
] as const;

const BEHAVIOR_BADGE: Record<string, string> = {
  STRONG_ACCUMULATION:
    "bg-accent-green/20 text-accent-green border-accent-green/40",
  ACCUMULATION:
    "bg-accent-green/10 text-accent-green border-accent-green/30",
  NEUTRAL: "bg-bg-subtle text-text-secondary border-border-muted",
  DISTRIBUTION: "bg-accent-red/10 text-accent-red border-accent-red/30",
  STRONG_DISTRIBUTION:
    "bg-accent-red/20 text-accent-red border-accent-red/40",
  INACTIVE: "bg-bg-subtle text-text-muted border-border-muted",
};

const BEHAVIOR_LABEL: Record<string, string> = {
  STRONG_ACCUMULATION: "AKUMULASI KUAT",
  ACCUMULATION: "AKUMULASI",
  NEUTRAL: "NETRAL",
  DISTRIBUTION: "DISTRIBUSI",
  STRONG_DISTRIBUTION: "DISTRIBUSI KUAT",
  INACTIVE: "TIDAK AKTIF",
};

interface Props {
  data: MultiEntityResponse;
  height?: number;
}

export function MultiEntityChart({ data, height = 480 }: Props) {
  const dates = data.daily_data.map((d) => d.date);

  // Cumulative net per entity (for line chart)
  const cumulativeSeries = data.entities.map((entity) => {
    const lookup: Record<string, number> = {};
    entity.data.forEach((p) => {
      lookup[p.date] = p.cumulative;
    });
    let lastValue = 0;
    const aligned = dates.map((d) => {
      if (lookup[d] !== undefined) lastValue = lookup[d];
      return lastValue;
    });
    return {
      name: entity.label,
      type: "line",
      data: aligned,
      smooth: true,
      symbol: "none",
      lineStyle: { color: entity.color, width: 2 },
      yAxisIndex: 0,
    };
  });

  // Price line (overlay)
  const priceSeries = {
    name: "Price",
    type: "line",
    data: data.daily_data.map((d) => d.price),
    smooth: true,
    symbol: "none",
    lineStyle: { color: "#94a3b8", width: 1, type: "dashed" },
    yAxisIndex: 1,
  };

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "#0f172a",
      borderColor: "#334155",
      textStyle: { color: "#f1f5f9", fontSize: 12 },
      formatter: (params: any[]) => {
        const date = params[0]?.axisValue;
        let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`;
        params.forEach((p) => {
          const v =
            p.seriesName === "Price"
              ? p.value.toLocaleString("id-ID")
              : formatIDR(p.value);
          html += `<div style="color:${p.color}">${p.seriesName}: ${v}</div>`;
        });
        return html;
      },
    },
    legend: {
      data: [...data.entities.map((e) => e.label), "Price"],
      textStyle: { color: "#94a3b8", fontSize: 11 },
      bottom: 0,
    },
    grid: {
      left: "5%",
      right: "8%",
      top: "8%",
      bottom: "12%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#64748b", fontSize: 10, hideOverlap: true },
    },
    yAxis: [
      {
        type: "value",
        name: "Cum Net (IDR)",
        position: "left",
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b" } },
        axisLabel: {
          color: "#64748b",
          fontSize: 10,
          formatter: (v: number) => formatIDR(v),
        },
      },
      {
        type: "value",
        name: "Price",
        position: "right",
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { show: false },
        axisLabel: { color: "#64748b", fontSize: 10 },
      },
    ],
    series: [...cumulativeSeries, priceSeries],
  };

  return (
    <div className="space-y-4">
      {/* Entity summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {data.entities.map((e) => (
          <div
            key={e.entity}
            className="rounded-lg border border-border bg-bg-card p-3"
          >
            <div className="flex items-center gap-2 mb-1">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: e.color }}
              />
              <span className="text-xs font-semibold">{e.label}</span>
            </div>
            <div
              className={cn(
                "text-sm font-bold tabular",
                e.total_net >= 0 ? "text-accent-green" : "text-accent-red"
              )}
            >
              {e.total_net >= 0 ? "+" : ""}
              {formatIDR(e.total_net)}
            </div>
            <div className="text-[10px] text-text-muted mt-0.5">
              {e.buy_days ?? 0}/{e.total_days ?? 0} buy days
            </div>
            <span
              className={cn(
                "inline-block mt-2 px-1.5 py-0.5 rounded text-[10px] font-medium border",
                BEHAVIOR_BADGE[e.behavior]
              )}
            >
              {BEHAVIOR_LABEL[e.behavior]}
            </span>
          </div>
        ))}
      </div>

      {/* Cumulative line chart */}
      <ReactECharts
        option={option}
        style={{ height: `${height}px`, width: "100%" }}
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
}
