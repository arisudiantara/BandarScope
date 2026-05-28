"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Compass } from "lucide-react";
import { sectorApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { RRGChart } from "@/components/charts/RRGChart";
import { cn } from "@/lib/utils";

const QUADRANTS = [
  {
    key: "leading",
    label: "Leading",
    desc: "Strong & accelerating — current outperformers",
    color: "bg-accent-green/10 text-accent-green border-accent-green/30",
  },
  {
    key: "weakening",
    label: "Weakening",
    desc: "Strong but losing momentum — late stage",
    color: "bg-accent-orange/10 text-accent-orange border-accent-orange/30",
  },
  {
    key: "lagging",
    label: "Lagging",
    desc: "Weak & declining — avoid",
    color: "bg-accent-red/10 text-accent-red border-accent-red/30",
  },
  {
    key: "improving",
    label: "Improving",
    desc: "Weak but accelerating — early opportunity",
    color: "bg-accent-blue/10 text-accent-blue border-accent-blue/30",
  },
];

export default function RotationPage() {
  const [period, setPeriod] = useState(30);
  const rotation = useQuery({
    queryKey: ["rotation", period],
    queryFn: () => sectorApi.rotation(period),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Compass className="h-6 w-6" /> Sector Rotation Chart (RRG)
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Relative Rotation Graph — JdK RS-Ratio vs RS-Momentum vs IHSG benchmark
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[14, 30, 60, 90].map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs",
                period === d
                  ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                  : "bg-bg-subtle border border-border text-text-secondary hover:text-text-primary"
              )}
            >
              {d}D
            </button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader
          title="Sector RRG"
          subtitle={`Period: ${period} days · Benchmark: ${rotation.data?.benchmark || "IHSG"}`}
        />
        {rotation.isLoading ? (
          <div className="h-[520px] flex items-center justify-center text-text-muted text-sm">
            Loading rotation data...
          </div>
        ) : rotation.data && rotation.data.data.length > 0 ? (
          <RRGChart rotation={rotation.data} />
        ) : (
          <div className="h-[520px] flex items-center justify-center text-text-muted text-sm">
            No data available
          </div>
        )}
      </Card>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {QUADRANTS.map((q) => {
          const list =
            rotation.data?.data.filter((d) => d.quadrant === q.key) || [];
          return (
            <Card key={q.key} className={cn("border", q.color)}>
              <CardHeader title={q.label} subtitle={q.desc} />
              {list.length === 0 ? (
                <div className="text-text-muted text-xs italic">
                  No sectors here
                </div>
              ) : (
                <div className="space-y-2">
                  {list.map((s) => (
                    <div
                      key={s.code}
                      className="flex items-center justify-between p-2 rounded-lg bg-bg-subtle"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: s.color }}
                        />
                        <span className="font-semibold text-sm">{s.code}</span>
                      </div>
                      <div className="text-right text-xs">
                        <div className="tabular text-text-primary">
                          RS: {s.rs_ratio.toFixed(1)}
                        </div>
                        <div className="tabular text-text-muted">
                          M: {s.rs_momentum.toFixed(1)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader
          title="How to Read the RRG"
          subtitle="Sectors rotate clockwise: Improving → Leading → Weakening → Lagging → Improving"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-text-secondary">
          <div>
            <div className="text-accent-blue font-semibold mb-1">
              Improving (kiri atas)
            </div>
            <p>
              Sektor masih lebih lemah dari benchmark, tapi momentum-nya
              membaik. <strong>Early signal</strong> — fase early-bird,
              accumulation phase. Risk-reward bagus.
            </p>
          </div>
          <div>
            <div className="text-accent-green font-semibold mb-1">
              Leading (kanan atas)
            </div>
            <p>
              Lebih kuat dari benchmark dan momentum masih akselerasi. Sektor
              sedang <strong>outperform</strong>. Hold + ride trend.
            </p>
          </div>
          <div>
            <div className="text-accent-orange font-semibold mb-1">
              Weakening (kanan bawah)
            </div>
            <p>
              Masih lebih kuat dari benchmark tapi momentum melemah. Mulai
              <strong> distribution phase</strong>. Tighten stops atau take
              profit.
            </p>
          </div>
          <div>
            <div className="text-accent-red font-semibold mb-1">
              Lagging (kiri bawah)
            </div>
            <p>
              Lebih lemah dari benchmark dan momentum negatif. <strong>Avoid</strong>
              {" "}atau short candidate. Tunggu rotasi balik ke Improving.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
