"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, useMemo } from "react";
import { UserSearch, Search, ArrowUpDown } from "lucide-react";
import {
  brokerStalkerApi,
  type BrokerInfo,
  type StalkerSymbolResult,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { formatIDR, formatPrice, cn } from "@/lib/utils";

const CLUSTER_VARIANT: Record<
  string,
  "success" | "danger" | "info" | "warning" | "default"
> = {
  market_maker: "warning",
  institutional: "info",
  retail: "success",
  corporate: "default",
  zombie: "danger",
};

const CLUSTER_LABEL: Record<string, string> = {
  market_maker: "Market Maker",
  institutional: "Institusi",
  retail: "Retail",
  corporate: "Corporate",
  zombie: "Zombie",
};

const BEHAVIOR_BADGE: Record<string, string> = {
  STRONG_ACCUMULATION:
    "bg-accent-green/20 text-accent-green border-accent-green/40",
  ACCUMULATION:
    "bg-accent-green/10 text-accent-green border-accent-green/30",
  GRADUAL_ENTRY: "bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30",
  NEUTRAL: "bg-bg-subtle text-text-secondary border-border-muted",
  DISTRIBUTION: "bg-accent-red/10 text-accent-red border-accent-red/30",
  STRONG_DISTRIBUTION:
    "bg-accent-red/20 text-accent-red border-accent-red/40",
};

export default function BrokerStalkerPage() {
  const [selectedBroker, setSelectedBroker] = useState<string>("CC");
  const [days, setDays] = useState(20);
  const [filterText, setFilterText] = useState("");
  const [filterCluster, setFilterCluster] = useState<string>("");
  const [filterForeign, setFilterForeign] = useState<string>("");
  const [sortKey, setSortKey] = useState<keyof StalkerSymbolResult>(
    "net_value"
  );
  const [sortDesc, setSortDesc] = useState(true);

  const brokers = useQuery({
    queryKey: ["broker-stalker-brokers"],
    queryFn: () => brokerStalkerApi.brokers(),
  });

  const stalker = useQuery({
    queryKey: ["broker-stalker-stalk", selectedBroker, days],
    queryFn: () => brokerStalkerApi.stalk(selectedBroker, days, 100),
    enabled: !!selectedBroker,
  });

  // Group brokers by cluster for picker
  const brokersByCluster = useMemo(() => {
    if (!brokers.data) return {};
    const grouped: Record<string, BrokerInfo[]> = {};
    brokers.data.forEach((b) => {
      const key = b.is_foreign ? "foreign" : b.cluster_label || "other";
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(b);
    });
    return grouped;
  }, [brokers.data]);

  // Filter brokers by text
  const visibleBrokers = useMemo(() => {
    if (!brokers.data) return [];
    const t = filterText.toUpperCase();
    if (!t) return brokers.data;
    return brokers.data.filter(
      (b) =>
        b.code.includes(t) ||
        b.name.toUpperCase().includes(t)
    );
  }, [brokers.data, filterText]);

  // Sort/filter results
  const processedResults = useMemo(() => {
    if (!stalker.data) return [];
    let r = [...stalker.data.results];
    if (filterCluster) {
      // No-op for now since results don't include cluster (saham-level)
    }
    r.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const an = typeof av === "number" ? av : 0;
      const bn = typeof bv === "number" ? bv : 0;
      return sortDesc ? bn - an : an - bn;
    });
    return r;
  }, [stalker.data, sortKey, sortDesc, filterCluster]);

  const accumulating = processedResults.filter((r) => r.net_value > 0);
  const distributing = processedResults.filter((r) => r.net_value < 0);

  const totalNet = processedResults.reduce((s, r) => s + r.net_value, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <UserSearch className="h-6 w-6" /> Broker Stalker
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Pilih broker → lihat semua saham yang sedang dia akumulasi atau
          distribusi
        </p>
      </div>

      {/* Broker Picker */}
      <Card>
        <CardHeader
          title="Pilih Broker"
          subtitle="Klik untuk stalk · cari di kotak kalau banyak"
        />
        <div className="flex items-center gap-2 mb-3">
          <Search className="h-4 w-4 text-text-muted" />
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Cari kode atau nama broker..."
            className="flex-1 bg-bg-subtle border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-accent-blue"
          />
          <div className="flex items-center gap-1 ml-2">
            {[5, 10, 20, 60].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  "px-2 py-1 rounded text-xs",
                  days === d
                    ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                    : "bg-bg-subtle border border-border text-text-secondary"
                )}
              >
                {d}D
              </button>
            ))}
          </div>
        </div>

        {Object.entries(brokersByCluster).map(([cluster, list]) => {
          const filtered = list.filter((b) => visibleBrokers.includes(b));
          if (filtered.length === 0) return null;
          return (
            <div key={cluster} className="mb-3">
              <div className="text-xs text-text-muted uppercase tracking-wide mb-1.5">
                {cluster === "foreign"
                  ? "Foreign"
                  : CLUSTER_LABEL[cluster] || cluster}{" "}
                ({filtered.length})
              </div>
              <div className="flex flex-wrap gap-1.5">
                {filtered.map((b) => (
                  <button
                    key={b.code}
                    onClick={() => setSelectedBroker(b.code)}
                    title={b.name}
                    className={cn(
                      "px-2 py-1 rounded text-xs font-mono border transition",
                      selectedBroker === b.code
                        ? "border-accent-blue bg-accent-blue/15 text-accent-blue font-semibold"
                        : "border-border bg-bg-subtle text-text-secondary hover:border-border-muted"
                    )}
                  >
                    {b.code}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </Card>

      {/* Stats */}
      {stalker.data && (
        <>
          <Card>
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <div className="font-mono text-2xl font-bold text-accent-blue">
                  {stalker.data.broker.code}
                </div>
                <div className="text-sm text-text-secondary">
                  {stalker.data.broker.name}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <Badge
                    variant={
                      stalker.data.broker.is_foreign
                        ? "info"
                        : CLUSTER_VARIANT[
                            stalker.data.broker.cluster_label
                          ] || "default"
                    }
                    className="text-[10px]"
                  >
                    {stalker.data.broker.is_foreign
                      ? "FOREIGN"
                      : CLUSTER_LABEL[stalker.data.broker.cluster_label] ||
                        stalker.data.broker.cluster_label}
                  </Badge>
                  <span className="text-xs text-text-muted">
                    {stalker.data.broker.type}
                  </span>
                </div>
              </div>
              <div className="text-xs text-text-muted text-right">
                <div>Period: {days} days</div>
                <div>As of: {stalker.data.as_of}</div>
                <div>{stalker.data.total_symbols} saham terdeteksi</div>
              </div>
            </div>
          </Card>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Net Total"
              value={
                <span
                  className={
                    totalNet >= 0 ? "text-accent-green" : "text-accent-red"
                  }
                >
                  {formatIDR(totalNet)}
                </span>
              }
            />
            <StatCard
              label="Saham Diakumulasi"
              value={
                <span className="text-accent-green">
                  {accumulating.length}
                </span>
              }
            />
            <StatCard
              label="Saham Didistribusi"
              value={
                <span className="text-accent-red">{distributing.length}</span>
              }
            />
            <StatCard
              label="Cluster"
              value={
                stalker.data.broker.is_foreign
                  ? "Foreign"
                  : CLUSTER_LABEL[stalker.data.broker.cluster_label] || "—"
              }
            />
          </div>

          {/* Accumulating */}
          <Card>
            <CardHeader
              title={`Saham Diakumulasi (${accumulating.length})`}
              subtitle="Net buy positif — broker beli berat"
            />
            <ResultsTable rows={accumulating} mode="accum" />
          </Card>

          {/* Distributing */}
          <Card>
            <CardHeader
              title={`Saham Didistribusi (${distributing.length})`}
              subtitle="Net sell — broker jual berat"
            />
            <ResultsTable rows={distributing} mode="dist" />
          </Card>
        </>
      )}

      {!stalker.data && stalker.isLoading && (
        <Card>
          <div className="text-center py-8 text-text-muted text-sm">
            Stalking broker...
          </div>
        </Card>
      )}
    </div>
  );
}

function ResultsTable({
  rows,
  mode,
}: {
  rows: StalkerSymbolResult[];
  mode: "accum" | "dist";
}) {
  if (rows.length === 0) {
    return (
      <div className="text-center py-6 text-text-muted text-sm">
        Tidak ada saham di kategori ini.
      </div>
    );
  }

  const sorted =
    mode === "accum"
      ? [...rows].sort((a, b) => b.net_value - a.net_value)
      : [...rows].sort((a, b) => a.net_value - b.net_value);

  return (
    <div className="overflow-x-auto -mx-4">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-text-muted border-b border-border">
            <th className="text-left px-4 py-2 font-medium">Symbol</th>
            <th className="text-left px-2 py-2 font-medium">Sector</th>
            <th className="text-right px-2 py-2 font-medium">Close</th>
            <th className="text-right px-2 py-2 font-medium">Net Lot</th>
            <th className="text-right px-2 py-2 font-medium">Net Value</th>
            <th className="text-right px-2 py-2 font-medium">Avg Buy Price</th>
            <th className="text-right px-2 py-2 font-medium">Active Days</th>
            <th className="text-right px-2 py-2 font-medium">Konsist</th>
            <th className="text-left px-2 py-2 font-medium">Behavior</th>
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 30).map((r) => (
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
                <div className="text-text-muted text-[10px]">{r.name}</div>
              </td>
              <td className="px-2 py-2 text-text-secondary">
                {r.sector || "-"}
              </td>
              <td className="px-2 py-2 text-right tabular">
                {formatPrice(r.close)}
              </td>
              <td
                className={cn(
                  "px-2 py-2 text-right tabular",
                  r.net_lot >= 0 ? "text-accent-green" : "text-accent-red"
                )}
              >
                {r.net_lot >= 0 ? "+" : ""}
                {(r.net_lot / 1000).toFixed(0)}K
              </td>
              <td
                className={cn(
                  "px-2 py-2 text-right tabular font-semibold",
                  r.net_value >= 0 ? "text-accent-green" : "text-accent-red"
                )}
              >
                {formatIDR(r.net_value)}
              </td>
              <td className="px-2 py-2 text-right tabular">
                {r.avg_buy_price ? formatPrice(r.avg_buy_price) : "-"}
              </td>
              <td className="px-2 py-2 text-right tabular text-text-secondary">
                {r.buy_days}/{r.active_days}
              </td>
              <td className="px-2 py-2 text-right tabular">
                {r.consistency_pct.toFixed(0)}%
              </td>
              <td className="px-2 py-2">
                <span
                  className={cn(
                    "inline-block px-1.5 py-0.5 rounded text-[10px] font-medium border",
                    BEHAVIOR_BADGE[r.behavior_label] || BEHAVIOR_BADGE.NEUTRAL
                  )}
                >
                  {r.behavior_label}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
