"use client";

import ReactECharts from "echarts-for-react";
import type { BalanceResponse } from "@/lib/api";

const BUCKETS = [
  { key: "foreign", label: "Foreign", color: "#3b82f6" },
  { key: "institutional", label: "Institutional", color: "#a855f7" },
  { key: "retail", label: "Retail", color: "#22c55e" },
  { key: "corporate", label: "Corporate", color: "#f59e0b" },
  { key: "other", label: "Other", color: "#64748b" },
];

interface Props {
  balance: BalanceResponse;
  mode?: "buy" | "net";
  height?: number;
}

export function BalancePositionChart({ balance, mode = "buy", height = 360 }: Props) {
  const dates = balance.data.map((d) => d.date);
  const suffix = mode === "buy" ? "_buy_pct" : "_net_pct";

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "#0f172a",
      borderColor: "#334155",
      textStyle: { color: "#f1f5f9", fontSize: 12 },
    },
    legend: {
      textStyle: { color: "#94a3b8", fontSize: 11 },
      bottom: 0,
    },
    grid: { left: "4%", right: "4%", top: "8%", bottom: "12%", containLabel: true },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#64748b", fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      max: mode === "buy" ? 100 : undefined,
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: {
        color: "#64748b",
        fontSize: 10,
        formatter: "{value}%",
      },
    },
    series: BUCKETS.map((b) => ({
      name: b.label,
      type: "bar",
      stack: mode === "buy" ? "total" : undefined,
      data: balance.data.map((d) => d[`${b.key}${suffix}`] || 0),
      itemStyle: { color: b.color },
      barCategoryGap: "10%",
    })),
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: `${height}px`, width: "100%" }}
      opts={{ renderer: "canvas" }}
    />
  );
}
