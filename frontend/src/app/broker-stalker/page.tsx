"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { UserSearch, Users } from "lucide-react";
import {
  brokerStalkerApi,
  type StalkerSymbolResult,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { MultiBrokerPicker } from "@/components/broker-stalker/MultiBrokerPicker";
import { formatIDR, formatPrice, cn } from "@/lib/utils";

const CLUSTER_LABEL: Record<string, string> = {
  market_maker: "Market Maker",
  institutional: "Institusi",
  retail: "Retail",
  corporate: "Corporate",
  zombie: "Zombie",
};

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
  const [selectedCodes, setSelectedCodes] = useState<string[]>(["CC"]);
  const [days, setDays] = useState(20);

  const brokersQuery = useQuery({
    queryKey: ["broker-stalker-brokers"],
    queryFn: () => brokerStalkerApi.brokers(),
  });

  const stalker = useQuery({
    queryKey: ["broker-stalker-multi", selectedCodes, days],
    queryFn: () =>
      brokerStalkerApi.stalkMulti(selectedCodes, days, 100, 100_000_000),
    enabled: selectedCodes.length > 0,
  });

  const accumulating = (stalker.data?.results ?? []).filter(
    (r) => r.net_value > 0
  );
  const distributing = (stalker.data?.results ?? []).filter(
    (r) => r.net_value < 0
  );

  const totalNet = (stalker.data?.results ?? []).reduce(
    (s, r) => s + r.net_value,
    0
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <UserSearch className="h-6 w-6" /> Broker Stalker
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Pilih satu atau beberapa broker → lihat semua saham yang sedang
          mereka akumulasi atau distribusi (combined)
        </p>
      </div>

      {/* Picker + Period */}
      <Card>
        <CardHeader
          title="Pilih Broker"
          subtitle="Tambah broker dengan ngetik di search bar · klik tombol Info untuk lihat daftar lengkap · pilih lebih dari 1 untuk analisa kombinasi"
        />

        <MultiBrokerPicker
          brokers={brokersQuery.data ?? []}
          selected={selectedCodes}
          onSelectedChange={setSelectedCodes}
        />

        <div className="flex items-center gap-2 mt-4">
          <span className="text-xs text-text-muted">Period:</span>
          {[5, 10, 20, 60].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-3 py-1.5 rounded text-xs",
                days === d
                  ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                  : "bg-bg-subtle border border-border text-text-secondary"
              )}
            >
              {d}D
            </button>
          ))}
          <span className="text-xs text-text-muted ml-auto">
            {selectedCodes.length === 0
              ? "Belum ada broker dipilih"
              : selectedCodes.length === 1
              ? "1 broker dipilih"
              : `${selectedCodes.length} broker (combined)`}
          </span>
        </div>
      </Card>

      {selectedCodes.length === 0 && (
        <Card>
          <div className="text-center py-12 text-text-muted text-sm">
            Tambahkan minimal 1 broker untuk mulai analisa.
            <br />
            Coba mulai dari{" "}
            <button
              onClick={() => setSelectedCodes(["CC", "RG"])}
              className="text-accent-blue hover:underline"
            >
              CC + RG (Market Maker)
            </button>
            {" atau "}
            <button
              onClick={() => setSelectedCodes(["YP", "PD", "SS"])}
              className="text-accent-blue hover:underline"
            >
              YP + PD + SS (Retail combined)
            </button>
          </div>
        </Card>
      )}

      {selectedCodes.length > 0 && stalker.isLoading && (
        <Card>
          <div className="text-center py-8 text-text-muted text-sm">
            Stalking {selectedCodes.length} broker...
          </div>
        </Card>
      )}

      {stalker.data && (
        <>
          {/* Selected brokers info card */}
          <Card>
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3 flex-wrap">
                <Users className="h-5 w-5 text-accent-blue" />
                <div>
                  <div className="text-sm font-semibold">
                    {selectedCodes.length} Broker (Combined Analysis)
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {stalker.data.brokers.map((b) => (
                      <Badge
                        key={b.code}
                        variant={
                          b.is_foreign
                            ? "info"
                            : CLUSTER_VARIANT[b.cluster_label] || "default"
                        }
                        className="text-[10px] font-mono"
                      >
                        {b.code} · {b.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
              <div className="text-xs text-text-muted text-right">
                <div>Period: {days} days</div>
                <div>As of: {stalker.data.as_of}</div>
                <div>{stalker.data.total_symbols} saham terdeteksi</div>
              </div>
            </div>
          </Card>

          {/* Quick stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Combined Net"
              value={
                <span
                  className={
                    totalNet >= 0 ? "text-accent-green" : "text-accent-red"
                  }
                >
                  {formatIDR(totalNet)}
                </span>
              }
              hint="Total dari semua broker dipilih"
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
              label="Brokers Aktif"
              value={`${stalker.data.broker_summary.length} / ${selectedCodes.length}`}
              hint="Yang punya transaksi di period"
            />
          </div>

          {/* Per-broker contribution summary */}
          {stalker.data.broker_summary.length > 1 && (
            <Card>
              <CardHeader
                title="Kontribusi Per Broker"
                subtitle="Total flow masing-masing broker selama period"
              />
              <div className="overflow-x-auto -mx-4">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-text-muted border-b border-border">
                      <th className="text-left px-4 py-2 font-medium">Broker</th>
                      <th className="text-left px-2 py-2 font-medium">Cluster</th>
                      <th className="text-right px-2 py-2 font-medium">
                        Buy Value
                      </th>
                      <th className="text-right px-2 py-2 font-medium">
                        Sell Value
                      </th>
                      <th className="text-right px-2 py-2 font-medium">
                        Net Value
                      </th>
                      <th className="text-right px-2 py-2 font-medium">
                        Saham
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {stalker.data.broker_summary.map((b) => (
                      <tr
                        key={b.code}
                        className="border-b border-border/30 hover:bg-bg-subtle/40"
                      >
                        <td className="px-4 py-2">
                          <span className="font-mono font-semibold">
                            {b.code}
                          </span>
                          <div className="text-text-muted text-[10px]">
                            {b.name}
                          </div>
                        </td>
                        <td className="px-2 py-2">
                          <Badge
                            variant={
                              b.is_foreign
                                ? "info"
                                : CLUSTER_VARIANT[b.cluster_label] || "default"
                            }
                            className="text-[10px]"
                          >
                            {b.is_foreign
                              ? "FOREIGN"
                              : CLUSTER_LABEL[b.cluster_label] ||
                                b.cluster_label}
                          </Badge>
                        </td>
                        <td className="px-2 py-2 text-right tabular text-accent-green">
                          {formatIDR(b.buy_value)}
                        </td>
                        <td className="px-2 py-2 text-right tabular text-accent-red">
                          {formatIDR(b.sell_value)}
                        </td>
                        <td
                          className={cn(
                            "px-2 py-2 text-right tabular font-semibold",
                            b.net_value >= 0
                              ? "text-accent-green"
                              : "text-accent-red"
                          )}
                        >
                          {formatIDR(b.net_value)}
                        </td>
                        <td className="px-2 py-2 text-right tabular">
                          {b.symbol_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Accumulating */}
          <Card>
            <CardHeader
              title={`Saham Diakumulasi (${accumulating.length})`}
              subtitle="Combined net buy positif dari semua broker dipilih"
            />
            <ResultsTable
              rows={accumulating}
              mode="accum"
              showContributors={selectedCodes.length > 1}
            />
          </Card>

          {/* Distributing */}
          <Card>
            <CardHeader
              title={`Saham Didistribusi (${distributing.length})`}
              subtitle="Combined net sell — broker jual berat"
            />
            <ResultsTable
              rows={distributing}
              mode="dist"
              showContributors={selectedCodes.length > 1}
            />
          </Card>
        </>
      )}
    </div>
  );
}

function ResultsTable({
  rows,
  mode,
  showContributors,
}: {
  rows: Array<
    StalkerSymbolResult & {
      contributors?: Array<{
        broker_code: string;
        net_value: number;
        net_lot: number;
      }>;
    }
  >;
  mode: "accum" | "dist";
  showContributors?: boolean;
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
            <th className="text-right px-2 py-2 font-medium">Konsist</th>
            <th className="text-left px-2 py-2 font-medium">Behavior</th>
            {showContributors && (
              <th className="text-left px-2 py-2 font-medium">Top Kontributor</th>
            )}
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
              {showContributors && (
                <td className="px-2 py-2">
                  <div className="flex flex-wrap gap-1">
                    {r.contributors?.slice(0, 3).map((c) => (
                      <span
                        key={c.broker_code}
                        className={cn(
                          "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border",
                          c.net_value >= 0
                            ? "bg-accent-green/10 text-accent-green border-accent-green/20"
                            : "bg-accent-red/10 text-accent-red border-accent-red/20"
                        )}
                        title={`${c.broker_code}: ${formatIDR(c.net_value)}`}
                      >
                        {c.broker_code}
                      </span>
                    ))}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
