"use client";

import ReactECharts from "echarts-for-react";
import type { ForeignFlowResponse } from "@/lib/api";
import { formatIDR } from "@/lib/utils";

interface Props {
  flow: ForeignFlowResponse;
  height?: number;
}

export function ForeignFlowChart({ flow, height = 380 }: Props) {
  const dates = flow.data.map((d) => d.date);
  const netBars = flow.data.map((d) => d.net);
  const cumLine = flow.data.map((d) => d.cumulative);
  const priceLine = flow.data.map((d) => d.price);

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
      data: ["Foreign Net", "Cum. Foreign Net", "Price"],
      textStyle: { color: "#94a3b8", fontSize: 11 },
      bottom: 0,
    },
    grid: { left: "4%", right: "8%", top: "8%", bottom: "12%", containLabel: true },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#64748b", fontSize: 10, hideOverlap: true },
    },
    yAxis: [
      {
        type: "value",
        name: "Net Flow",
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
    series: [
      {
        name: "Foreign Net",
        type: "bar",
        data: netBars.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? "#22c55e" : "#ef4444", opacity: 0.7 },
        })),
        yAxisIndex: 0,
      },
      {
        name: "Cum. Foreign Net",
        type: "line",
        data: cumLine,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#a855f7", width: 2 },
        yAxisIndex: 0,
      },
      {
        name: "Price",
        type: "line",
        data: priceLine,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#94a3b8", width: 1.5, type: "dashed" },
        yAxisIndex: 1,
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
