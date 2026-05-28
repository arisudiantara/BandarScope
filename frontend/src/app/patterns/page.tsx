"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { BookOpen, Search } from "lucide-react";
import { patternsApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn, scoreBgClass } from "@/lib/utils";

const CATEGORY_VARIANT: Record<string, "success" | "danger" | "info" | "warning" | "default"> = {
  ACCUMULATION: "success",
  DISTRIBUTION: "danger",
  REVERSAL: "warning",
  TREND: "info",
  TRANSITION: "default",
  DIVERGENCE: "info",
};

export default function PatternsPage() {
  const [activePattern, setActivePattern] = useState<string | null>(null);
  const [minConfidence, setMinConfidence] = useState(60);

  const catalog = useQuery({
    queryKey: ["patterns-catalog"],
    queryFn: () => patternsApi.catalog(),
  });

  const scan = useQuery({
    queryKey: ["patterns-scan", activePattern, minConfidence],
    queryFn: () =>
      activePattern
        ? patternsApi.scan(activePattern, minConfidence, 50)
        : null,
    enabled: !!activePattern,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen className="h-6 w-6" /> Pattern Library
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          8 pattern bandarmology classic — klik untuk scan saham yang match
        </p>
      </div>

      {/* Catalog Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {catalog.data?.map((p) => (
          <button
            key={p.code}
            onClick={() => setActivePattern(p.code)}
            className={cn(
              "text-left rounded-xl border p-4 transition",
              activePattern === p.code
                ? "border-accent-blue bg-accent-blue/5"
                : "bg-bg-card border-border hover:border-border-muted"
            )}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="font-semibold">{p.name}</div>
                <div className="text-xs text-text-muted">{p.name_id}</div>
              </div>
              <Badge variant={CATEGORY_VARIANT[p.category] || "default"} className="text-[10px]">
                {p.category}
              </Badge>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed mb-2">
              {p.description}
            </p>
            <div className="text-[11px] text-text-muted">
              <strong>Win rate:</strong> {p.win_rate_label}
            </div>
            <div className="text-[11px] text-text-muted mt-1">
              <strong>Playbook:</strong> {p.playbook}
            </div>
          </button>
        ))}
      </div>

      {/* Scan Results */}
      {activePattern && (
        <Card>
          <CardHeader
            title={`Scan: ${activePattern}`}
            subtitle="Saham yang sedang menunjukkan pattern ini"
            action={
              <div className="flex items-center gap-2 text-xs">
                <label className="text-text-muted">Min confidence:</label>
                <input
                  type="number"
                  value={minConfidence}
                  onChange={(e) => setMinConfidence(Number(e.target.value))}
                  className="w-16 bg-bg-subtle border border-border rounded px-2 py-1 text-center"
                />
              </div>
            }
          />

          {scan.isLoading && (
            <div className="text-center py-8 text-text-muted text-sm">
              Scanning universe...
            </div>
          )}

          {scan.data && (
            <>
              <div className="text-xs text-text-secondary mb-3">
                {scan.data.total_hits} saham ditemukan
              </div>
              {scan.data.results.length === 0 ? (
                <div className="text-center py-6 text-text-muted text-sm">
                  Tidak ada saham yang match dengan confidence ≥ {minConfidence}.
                </div>
              ) : (
                <div className="overflow-x-auto -mx-4">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-text-muted border-b border-border">
                        <th className="text-left px-4 py-2 font-medium">Symbol</th>
                        <th className="text-left px-2 py-2 font-medium">Sector</th>
                        <th className="text-right px-2 py-2 font-medium">Confidence</th>
                        <th className="text-left px-2 py-2 font-medium">Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scan.data.results.map((r) => (
                        <tr
                          key={r.symbol}
                          className="border-b border-border/30 hover:bg-bg-subtle/40"
                        >
                          <td className="px-4 py-2">
                            <Link
                              href={`/stock/${r.symbol}`}
                              className="font-mono font-semibold text-accent-blue hover:underline"
                            >
                              {r.symbol}
                            </Link>
                            <div className="text-xs text-text-muted">{r.name}</div>
                          </td>
                          <td className="px-2 py-2 text-xs text-text-secondary">
                            {r.sector}
                          </td>
                          <td className="px-2 py-2 text-right">
                            <span className={`score-badge ${scoreBgClass(r.confidence)}`}>
                              {r.confidence.toFixed(0)}
                            </span>
                          </td>
                          <td className="px-2 py-2 text-[10px] text-text-secondary font-mono">
                            {Object.entries(r.evidence).slice(0, 3).map(([k, v]) => (
                              <div key={k}>
                                <span className="text-text-muted">{k}:</span>{" "}
                                {typeof v === "number" ? v.toFixed(2) : String(v)}
                              </div>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
