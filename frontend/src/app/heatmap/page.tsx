"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { sectorApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { HeatmapChart } from "@/components/charts/HeatmapChart";

export default function HeatmapPage() {
  const heatmap = useQuery({
    queryKey: ["heatmap"],
    queryFn: () => sectorApi.heatmap(),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="h-6 w-6" /> Market Heatmap
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Color = pct change · Size = traded value · Click stock for detail
        </p>
      </div>

      <Card>
        <CardHeader
          title="IDX Heatmap"
          subtitle={`${heatmap.data?.length ?? 0} stocks · grouped by sector`}
        />
        {heatmap.isLoading ? (
          <div className="h-[540px] flex items-center justify-center text-text-muted text-sm">
            Loading heatmap...
          </div>
        ) : heatmap.data ? (
          <HeatmapChart items={heatmap.data} />
        ) : null}
      </Card>

      <Card>
        <CardHeader title="Color legend" />
        <div className="flex flex-wrap gap-2 text-xs">
          {[
            { c: "#15803d", l: "+5%" },
            { c: "#16a34a", l: "+3%" },
            { c: "#22c55e", l: "+1%" },
            { c: "#4ade80", l: "+0%" },
            { c: "#475569", l: "0%" },
            { c: "#f87171", l: "-0%" },
            { c: "#ef4444", l: "-1%" },
            { c: "#dc2626", l: "-3%" },
            { c: "#991b1b", l: "-5%" },
          ].map(({ c, l }) => (
            <div key={l} className="flex items-center gap-1.5">
              <span
                className="inline-block h-4 w-6 rounded"
                style={{ background: c }}
              />
              <span className="text-text-secondary tabular">{l}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
