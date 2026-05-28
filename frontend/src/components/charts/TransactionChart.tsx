"use client";

import ReactECharts from "echarts-for-react";
import type { TransactionResponse } from "@/lib/api";
import { formatIDR } from "@/lib/utils";

interface Props {
  txn: TransactionResponse;
  height?: number;
}

export function TransactionChart({ txn, height = 480 }: Props) {
  const dates = txn.data.map((d) => d.date);
  const prices = txn.data.map((d) => d.price);
  const cumF = txn.data.map((d) => d.cum_foreign);
  const mfi = txn.data.map((d) => d.mfi);

  // Divergence markers
  const markPoints = txn.divergence_markers.map((m) => ({
    coord: [m.date, m.price],
    name: m.type,
    itemStyle: {
      color: m.type === "BULLISH_DIVERGENCE" ? "#22c55e" : "#ef4444",
    },
    label: {
      show: true,
      formatter: m.type === "BULLISH_DIVERGENCE" ? "↑" : "↓",
      color: "#fff",
      fontSize: 14,
      fontWeight: "bold",
    },
    symbol: "circle",
    symbolSize: 16,
  }));

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "#0f172a",
      borderColor: "#334155",
      textStyle: { color: "#f1f5f9", fontSize: 12 },
    },
    legend: {
      data: ["Price", "Cum. Foreign Net", "MFI"],
      textStyle: { color: "#94a3b8", fontSize: 11 },
      bottom: 0,
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: "5%", right: "8%", top: "5%", height: "55%" },
      { left: "5%", right: "8%", top: "68%", height: "20%" },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        gridIndex: 0,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { show: false },
      },
      {
        type: "category",
        data: dates,
        gridIndex: 1,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#64748b", fontSize: 10, hideOverlap: true },
      },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        position: "left",
        name: "Price",
        nameTextStyle: { color: "#94a3b8", fontSize: 10 },
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b" } },
        axisLabel: { color: "#64748b", fontSize: 10 },
      },
      {
        type: "value",
        gridIndex: 0,
        position: "right",
        name: "Cum Net",
        nameTextStyle: { color: "#94a3b8", fontSize: 10 },
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { show: false },
        axisLabel: {
          color: "#64748b",
          fontSize: 10,
          formatter: (v: number) => formatIDR(v),
        },
      },
      {
        type: "value",
        gridIndex: 1,
        min: 0,
        max: 100,
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b" } },
        axisLabel: { color: "#64748b", fontSize: 10 },
      },
    ],
    series: [
      {
        name: "Price",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: prices,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#e2e8f0", width: 1.8 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(226,232,240,0.15)" },
              { offset: 1, color: "rgba(226,232,240,0.0)" },
            ],
          },
        },
        markPoint: { data: markPoints },
      },
      {
        name: "Cum. Foreign Net",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 1,
        data: cumF,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#a855f7", width: 2 },
      },
      {
        name: "MFI",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 2,
        data: mfi,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#06b6d4", width: 1.5 },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "#475569", type: "dashed" },
          data: [{ yAxis: 80 }, { yAxis: 20 }],
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: `${height}px`, width: "100%" }}
      opts={{ renderer: "canvas" }}
    />
  );
}
