"use client";

import { createChart, ColorType, IChartApi, LineData, Time } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { InventoryResponse } from "@/lib/api";

const PALETTE = [
  "#22c55e", "#3b82f6", "#a855f7", "#f59e0b",
  "#06b6d4", "#ec4899", "#eab308", "#84cc16",
];

interface Props {
  data: InventoryResponse;
  height?: number;
}

export function InventoryChart({ data, height = 420 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !data || data.lines.length === 0) return;

    const chart: IChartApi = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontFamily: "Inter, system-ui",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      timeScale: { timeVisible: true, borderColor: "#334155" },
      rightPriceScale: {
        borderColor: "#334155",
        visible: true,
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
      leftPriceScale: {
        borderColor: "#334155",
        visible: true,
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
      height,
      width: containerRef.current.clientWidth,
      crosshair: { mode: 1 },
    });

    // Price (right scale)
    const priceSeries = chart.addLineSeries({
      color: "#64748b",
      lineWidth: 1,
      priceScaleId: "right",
      title: "Price",
      lineStyle: 2,
    });
    priceSeries.setData(
      data.price_series.map((p) => ({ time: p.date as Time, value: p.close }))
    );

    // Inventory lines per broker (left scale, in lots)
    data.lines.forEach((line, i) => {
      const series = chart.addLineSeries({
        color: PALETTE[i % PALETTE.length],
        lineWidth: 2,
        priceScaleId: "left",
        title: `${line.broker_code} (${line.cluster_label})`,
      });
      const ld: LineData[] = line.data.map((d) => ({
        time: d.date as Time,
        value: d.inventory_lot,
      }));
      series.setData(ld);
    });

    chart.timeScale().fitContent();

    const onResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [data, height]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-xs">
        {data.lines.map((l, i) => (
          <div
            key={l.broker_code}
            className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-subtle border border-border"
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: PALETTE[i % PALETTE.length] }}
            />
            <span className="font-mono font-semibold">{l.broker_code}</span>
            <span className="text-text-muted">{l.broker_name}</span>
            <span className="text-text-muted">·</span>
            <span
              className={
                l.total_net_lot >= 0 ? "text-accent-green" : "text-accent-red"
              }
            >
              {l.total_net_lot >= 0 ? "+" : ""}
              {(l.total_net_lot / 1000).toFixed(0)}K lot
            </span>
          </div>
        ))}
      </div>
      <div ref={containerRef} className="w-full" />
      <div className="flex justify-between text-[11px] text-text-muted">
        <span>Left: Inventory (lot kumulatif)</span>
        <span>Right: Harga</span>
      </div>
    </div>
  );
}
