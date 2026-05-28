"use client";

import ReactECharts from "echarts-for-react";
import type { RotationResponse } from "@/lib/api";

const QUADRANT_COLOR: Record<string, string> = {
  leading: "#22c55e",
  weakening: "#f59e0b",
  lagging: "#ef4444",
  improving: "#3b82f6",
};

interface Props {
  rotation: RotationResponse;
  height?: number;
}

export function RRGChart({ rotation, height = 520 }: Props) {
  const minR = Math.min(...rotation.data.map((d) => d.rs_ratio), 95) - 1;
  const maxR = Math.max(...rotation.data.map((d) => d.rs_ratio), 105) + 1;
  const minM = Math.min(...rotation.data.map((d) => d.rs_momentum), 95) - 1;
  const maxM = Math.max(...rotation.data.map((d) => d.rs_momentum), 105) + 1;

  const series: any[] = [];

  // Tail line + scatter for each sector
  rotation.data.forEach((sec) => {
    if (sec.tail.length > 0) {
      series.push({
        name: sec.code + "_tail",
        type: "line",
        data: sec.tail,
        symbol: "circle",
        symbolSize: 4,
        showSymbol: true,
        lineStyle: {
          color: QUADRANT_COLOR[sec.quadrant],
          width: 1.5,
          opacity: 0.6,
        },
        itemStyle: { color: QUADRANT_COLOR[sec.quadrant], opacity: 0.5 },
        z: 2,
      });
    }
    series.push({
      name: sec.code,
      type: "scatter",
      data: [
        {
          value: [sec.rs_ratio, sec.rs_momentum],
          name: sec.code,
        },
      ],
      symbolSize: 28,
      itemStyle: {
        color: QUADRANT_COLOR[sec.quadrant],
        borderColor: "#0f172a",
        borderWidth: 2,
      },
      label: {
        show: true,
        formatter: sec.code,
        position: "right",
        color: "#e2e8f0",
        fontSize: 11,
        fontWeight: 600,
      },
      z: 5,
    });
  });

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "#0f172a",
      borderColor: "#334155",
      textStyle: { color: "#f1f5f9", fontSize: 12 },
      formatter: (p: any) => {
        const sec = rotation.data.find((s) => s.code === p.seriesName);
        if (!sec) return "";
        return `<div style="padding:6px;">
          <div style="font-weight:600">${sec.name}</div>
          <div>RS-Ratio: ${sec.rs_ratio.toFixed(2)}</div>
          <div>RS-Momentum: ${sec.rs_momentum.toFixed(2)}</div>
          <div style="text-transform:uppercase; color:${QUADRANT_COLOR[sec.quadrant]}; margin-top:4px; font-weight:600">${sec.quadrant}</div>
        </div>`;
      },
    },
    grid: { left: "8%", right: "8%", top: "10%", bottom: "10%" },
    xAxis: {
      type: "value",
      name: "RS-Ratio →",
      nameLocation: "middle",
      nameGap: 28,
      nameTextStyle: { color: "#94a3b8", fontSize: 11 },
      min: minR,
      max: maxR,
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: "#64748b", fontSize: 10 },
    },
    yAxis: {
      type: "value",
      name: "RS-Momentum ↑",
      nameLocation: "middle",
      nameGap: 40,
      nameTextStyle: { color: "#94a3b8", fontSize: 11 },
      min: minM,
      max: maxM,
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: "#64748b", fontSize: 10 },
    },
    // Reference lines at 100/100
    markLine: {
      silent: true,
      symbol: "none",
      lineStyle: { color: "#475569", width: 2 },
      data: [{ xAxis: 100 }, { yAxis: 100 }],
    },
    series: series.concat([
      {
        type: "line",
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "#475569", width: 2, type: "solid" },
          label: { show: false },
          data: [{ xAxis: 100 }, { yAxis: 100 }],
        },
        data: [],
      },
    ]),
    graphic: [
      // Quadrant labels
      {
        type: "text",
        right: "12%",
        top: "12%",
        style: {
          text: "LEADING",
          fill: "#22c55e",
          fontSize: 13,
          fontWeight: "bold",
          opacity: 0.4,
        },
      },
      {
        type: "text",
        right: "12%",
        bottom: "14%",
        style: {
          text: "WEAKENING",
          fill: "#f59e0b",
          fontSize: 13,
          fontWeight: "bold",
          opacity: 0.4,
        },
      },
      {
        type: "text",
        left: "12%",
        bottom: "14%",
        style: {
          text: "LAGGING",
          fill: "#ef4444",
          fontSize: 13,
          fontWeight: "bold",
          opacity: 0.4,
        },
      },
      {
        type: "text",
        left: "12%",
        top: "12%",
        style: {
          text: "IMPROVING",
          fill: "#3b82f6",
          fontSize: 13,
          fontWeight: "bold",
          opacity: 0.4,
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: `${height}px`, width: "100%" }}
      opts={{ renderer: "canvas" }}
      theme="dark"
    />
  );
}
