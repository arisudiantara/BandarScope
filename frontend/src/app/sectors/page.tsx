"use client";

import { useQuery } from "@tanstack/react-query";
import { Layers, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { sectorApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatIDR, pctClass, scoreBgClass } from "@/lib/utils";

export default function SectorsPage() {
  const sectors = useQuery({
    queryKey: ["sectors-activity-detail", 5],
    queryFn: () => sectorApi.activity(5),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Layers className="h-6 w-6" /> Sector Activity
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Capital inflow/outflow ranking & relative momentum across IDX sectors
        </p>
      </div>

      <Card>
        <CardHeader
          title="Sector Ranking"
          subtitle="Sorted by foreign net flow over the period"
        />
        <div className="overflow-x-auto -mx-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                <th className="text-left px-4 py-2 font-medium">#</th>
                <th className="text-left px-2 py-2 font-medium">Sector</th>
                <th className="text-right px-2 py-2 font-medium">Stocks</th>
                <th className="text-right px-2 py-2 font-medium">Total Value</th>
                <th className="text-right px-2 py-2 font-medium">Foreign Net</th>
                <th className="text-right px-2 py-2 font-medium">Foreign Net 5D</th>
                <th className="text-right px-2 py-2 font-medium">Momentum</th>
                <th className="text-right px-2 py-2 font-medium">Avg BandarScore</th>
                <th className="text-left px-2 py-2 font-medium">Flow Signal</th>
              </tr>
            </thead>
            <tbody>
              {sectors.data?.map((s) => (
                <tr
                  key={s.code}
                  className="border-b border-border/40 hover:bg-bg-subtle/40"
                >
                  <td className="px-4 py-3">
                    <span className="text-text-muted tabular">#{s.rank}</span>
                  </td>
                  <td className="px-2 py-3">
                    <div className="flex items-center gap-2">
                      <span
                        className="h-3 w-3 rounded"
                        style={{ background: s.color }}
                      />
                      <div>
                        <div className="font-semibold">{s.name}</div>
                        <div className="text-xs text-text-muted">{s.name_id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-3 text-right tabular text-text-secondary">
                    {s.symbol_count}
                  </td>
                  <td className="px-2 py-3 text-right tabular">
                    {formatIDR(s.total_value)}
                  </td>
                  <td
                    className={`px-2 py-3 text-right tabular font-semibold ${
                      s.foreign_net >= 0 ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {s.foreign_net >= 0 ? (
                      <ArrowUpRight className="inline h-3 w-3 mr-0.5" />
                    ) : (
                      <ArrowDownRight className="inline h-3 w-3 mr-0.5" />
                    )}
                    {formatIDR(s.foreign_net)}
                  </td>
                  <td
                    className={`px-2 py-3 text-right tabular ${
                      s.foreign_net_5d >= 0 ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {formatIDR(s.foreign_net_5d)}
                  </td>
                  <td className={`px-2 py-3 text-right tabular ${pctClass(s.momentum_pct)}`}>
                    {s.momentum_pct >= 0 ? "+" : ""}
                    {s.momentum_pct.toFixed(2)}%
                  </td>
                  <td className="px-2 py-3 text-right">
                    <span className={`score-badge ${scoreBgClass(s.avg_bandar_score)}`}>
                      {s.avg_bandar_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="px-2 py-3">
                    <Badge
                      variant={
                        s.flow_label === "INFLOW_RISING"
                          ? "success"
                          : s.flow_label === "INFLOW_BUILDING"
                          ? "info"
                          : s.flow_label === "OUTFLOW_DEFYING"
                          ? "warning"
                          : "danger"
                      }
                    >
                      {s.flow_label.replace("_", " ")}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader
            title="Capital Inflow (Hot Sectors)"
            subtitle="Foreign money flowing in"
          />
          <div className="space-y-2">
            {sectors.data
              ?.filter((s) => s.foreign_net > 0)
              .slice(0, 5)
              .map((s) => (
                <div
                  key={s.code}
                  className="flex items-center justify-between p-2 rounded-lg bg-accent-green/5 border border-accent-green/20"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded"
                      style={{ background: s.color }}
                    />
                    <span className="font-semibold text-sm">{s.name}</span>
                  </div>
                  <span className="text-accent-green tabular text-sm font-mono">
                    +{formatIDR(s.foreign_net)}
                  </span>
                </div>
              ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Capital Outflow (Cooling Sectors)"
            subtitle="Foreign money exiting"
          />
          <div className="space-y-2">
            {sectors.data
              ?.filter((s) => s.foreign_net < 0)
              .slice(0, 5)
              .map((s) => (
                <div
                  key={s.code}
                  className="flex items-center justify-between p-2 rounded-lg bg-accent-red/5 border border-accent-red/20"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded"
                      style={{ background: s.color }}
                    />
                    <span className="font-semibold text-sm">{s.name}</span>
                  </div>
                  <span className="text-accent-red tabular text-sm font-mono">
                    {formatIDR(s.foreign_net)}
                  </span>
                </div>
              ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
