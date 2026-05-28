"use client";

import ReactECharts from "echarts-for-react";
import type { HeatmapItem } from "@/lib/api";
import { useRouter } from "next/navigation";

interface Props {
  items: HeatmapItem[];
  height?: number;
}

export function HeatmapChart({ items, height = 540 }: Props) {
  const router = useRouter();

  // Treemap structure: sectors → symbols
  const sectorMap = new Map<string, HeatmapItem[]>();
  items.forEach((it) => {
    if (!sectorMap.has(it.sector)) sectorMap.set(it.sector, []);
    sectorMap.get(it.sector)!.push(it);
  });

  const treeData = Array.from(sectorMap.entries()).map(([sector, syms]) => ({
    name: sector,
    children: syms.map((s) => ({
      name: s.symbol,
      value: s.value || 1,
      pct: s.pct_change,
      bandar: s.bandar_score,
      itemStyle: { color: pctToColor(s.pct_change) },
      label: {
        formatter: () => `{a|${s.symbol}}\n{b|${s.pct_change >= 0 ? "+" : ""}${s.pct_change.toFixed(1)}%}`,
        rich: {
          a: { color: "#fff", fontWeight: 700, fontSize: 13 },
          b: { color: "#fff", fontSize: 11, opacity: 0.9 },
        },
      },
    })),
  }));

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      backgroundColor: "#0f172a",
      borderColor: "#334155",
      textStyle: { color: "#f1f5f9", fontSize: 12 },
      formatter: (info: any) => {
        const d = info.data;
        if (!d.pct && d.pct !== 0) return d.name;
        return `<div>
          <div style="font-weight:700; font-family:monospace">${d.name}</div>
          <div>Change: <b style="color:${d.pct >= 0 ? "#22c55e" : "#ef4444"}">${d.pct >= 0 ? "+" : ""}${d.pct.toFixed(2)}%</b></div>
          <div>BandarScore: ${d.bandar?.toFixed(0) ?? "-"}</div>
        </div>`;
      },
    },
    series: [
      {
        type: "treemap",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        data: treeData,
        leafDepth: 2,
        levels: [
          {
            itemStyle: {
              borderColor: "#0a0e1a",
              borderWidth: 2,
              gapWidth: 2,
            },
            upperLabel: {
              show: true,
              height: 22,
              color: "#94a3b8",
              fontWeight: 600,
              backgroundColor: "#0f172a",
            },
          },
          {
            itemStyle: { borderColor: "#0a0e1a", borderWidth: 1 },
          },
        ],
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: `${height}px`, width: "100%" }}
      onEvents={{
        click: (params: any) => {
          if (params.data?.name && params.data?.value && !params.data.children) {
            router.push(`/stock/${params.data.name}`);
          }
        },
      }}
    />
  );
}

function pctToColor(pct: number): string {
  if (pct >= 5) return "#15803d";
  if (pct >= 3) return "#16a34a";
  if (pct >= 1) return "#22c55e";
  if (pct > 0) return "#4ade80";
  if (pct === 0) return "#475569";
  if (pct > -1) return "#f87171";
  if (pct > -3) return "#ef4444";
  if (pct > -5) return "#dc2626";
  return "#991b1b";
}
