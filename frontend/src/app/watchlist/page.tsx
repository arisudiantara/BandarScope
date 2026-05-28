"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Star, Plus, Trash2, X } from "lucide-react";
import {
  watchlistApi, symbolsApi, type Watchlist, screenerApi,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { VerdictBadge, RetailNonFlowBadge } from "@/components/ui/VerdictBadge";
import {
  formatPrice, pctClass, scoreBgClass, signalClass, formatIDR, cn,
} from "@/lib/utils";

export default function WatchlistPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  const watchlists = useQuery({
    queryKey: ["watchlists"],
    queryFn: () => watchlistApi.list(),
  });

  const active = watchlists.data?.find((w) => w.id === activeId)
    ?? watchlists.data?.[0];

  // Get screener scores for the symbols in the active watchlist
  const screener = useQuery({
    queryKey: ["screener-watch", active?.id],
    queryFn: async () => {
      if (!active) return null;
      const all = await screenerApi.scan({ limit: 500 });
      return {
        ...all,
        results: all.results.filter((r) => active.symbols.includes(r.symbol)),
      };
    },
    enabled: !!active,
  });

  const createMut = useMutation({
    mutationFn: (name: string) =>
      watchlistApi.create({ name, symbols: [], color: "#3b82f6" }),
    onSuccess: (w) => {
      qc.invalidateQueries({ queryKey: ["watchlists"] });
      setActiveId(w.id);
      setNewName("");
      setShowCreate(false);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => watchlistApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlists"] });
      setActiveId(null);
    },
  });

  const removeSymbol = useMutation({
    mutationFn: async ({ id, symbol }: { id: string; symbol: string }) => {
      const w = watchlists.data?.find((x) => x.id === id);
      if (!w) return;
      return watchlistApi.update(id, {
        symbols: w.symbols.filter((s) => s !== symbol),
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Star className="h-6 w-6" /> Watchlist
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Track your selected stocks with live BandarScore
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg bg-accent-blue text-white hover:bg-accent-blue/90"
        >
          <Plus className="h-4 w-4" /> New Watchlist
        </button>
      </div>

      {showCreate && (
        <Card>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Watchlist name"
              className="flex-1 bg-bg-subtle border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-blue"
            />
            <button
              onClick={() => newName && createMut.mutate(newName)}
              className="px-3 py-2 text-sm rounded-lg bg-accent-green text-white"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-3 py-2 text-sm rounded-lg bg-bg-subtle border border-border"
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {watchlists.data?.map((w) => (
          <button
            key={w.id}
            onClick={() => setActiveId(w.id)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm border flex items-center gap-2",
              (active?.id === w.id)
                ? "border-accent-blue bg-accent-blue/10 text-accent-blue"
                : "border-border bg-bg-card text-text-secondary"
            )}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: w.color }}
            />
            {w.name}
            <span className="text-text-muted text-xs">
              ({w.symbols.length})
            </span>
          </button>
        ))}
      </div>

      {active && (
        <Card>
          <CardHeader
            title={active.name}
            subtitle={active.description || `${active.symbols.length} symbols`}
            action={
              <button
                onClick={() =>
                  confirm(`Delete watchlist "${active.name}"?`) &&
                  deleteMut.mutate(active.id)
                }
                className="text-text-muted hover:text-accent-red p-1.5"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            }
          />

          {active.symbols.length === 0 ? (
            <div className="text-center py-8 text-text-muted text-sm">
              No symbols yet. Add stocks via the Screener or search bar.
            </div>
          ) : (
            <div className="overflow-x-auto -mx-4">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted border-b border-border">
                    <th className="text-center px-2 py-2 font-medium w-8">✓</th>
                    <th className="text-left px-2 py-2 font-medium">Symbol</th>
                    <th className="text-left px-2 py-2 font-medium">Sector</th>
                    <th className="text-right px-2 py-2 font-medium">Price</th>
                    <th className="text-right px-2 py-2 font-medium">Foreign 20D</th>
                    <th className="text-right px-2 py-2 font-medium">BandarScore</th>
                    <th className="text-left px-2 py-2 font-medium">Retail Non-Flow</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {screener.data?.results?.map((r) => (
                    <tr
                      key={r.symbol}
                      className="border-b border-border/30 hover:bg-bg-subtle/40"
                    >
                      <td className="px-2 py-2.5 text-center">
                        <VerdictBadge
                          verdict={r.verdict}
                          tooltip={r.verdict_explanation}
                        />
                      </td>
                      <td className="px-2 py-2.5">
                        <Link
                          href={`/stock/${r.symbol}`}
                          className="font-mono font-semibold text-accent-blue hover:underline"
                        >
                          {r.symbol}
                        </Link>
                        <div className="text-text-muted text-[10px]">
                          {r.name}
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-text-secondary">
                        {r.sector}
                      </td>
                      <td className="px-2 py-2.5 text-right tabular">
                        {formatPrice(r.close)}
                      </td>
                      <td
                        className={cn(
                          "px-2 py-2.5 text-right tabular",
                          r.foreign_net >= 0 ? "text-accent-green" : "text-accent-red"
                        )}
                      >
                        {formatIDR(r.foreign_net)}
                      </td>
                      <td className="px-2 py-2.5 text-right">
                        <span className={`score-badge ${scoreBgClass(r.bandar_score)}`}>
                          {r.bandar_score.toFixed(0)}
                        </span>
                      </td>
                      <td className="px-2 py-2.5">
                        <RetailNonFlowBadge
                          score={r.retail_non_flow_score}
                          label={r.retail_non_flow_label}
                        />
                      </td>
                      <td className="px-2 py-2.5 text-right">
                        <button
                          onClick={() =>
                            removeSymbol.mutate({
                              id: active.id,
                              symbol: r.symbol,
                            })
                          }
                          className="text-text-muted hover:text-accent-red p-1"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
