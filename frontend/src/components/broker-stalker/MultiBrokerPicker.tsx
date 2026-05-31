"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Search, X, Info, Plus } from "lucide-react";
import type { BrokerInfo } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";

const CLUSTER_LABEL: Record<string, string> = {
  market_maker: "Market Maker",
  institutional: "Institusi",
  retail: "Retail",
  corporate: "Corporate",
  zombie: "Zombie",
};

const CLUSTER_ORDER = [
  "foreign",
  "market_maker",
  "institutional",
  "retail",
  "corporate",
  "zombie",
];

const CLUSTER_VARIANT: Record<
  string,
  "success" | "danger" | "info" | "warning" | "default"
> = {
  foreign: "info",
  market_maker: "warning",
  institutional: "info",
  retail: "success",
  corporate: "default",
  zombie: "danger",
};

interface Props {
  brokers: BrokerInfo[];
  selected: string[];
  onSelectedChange: (codes: string[]) => void;
}

export function MultiBrokerPicker({
  brokers,
  selected,
  onSelectedChange,
}: Props) {
  const [query, setQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Group brokers by cluster (foreign first)
  const grouped = useMemo(() => {
    const g: Record<string, BrokerInfo[]> = {};
    brokers.forEach((b) => {
      const key = b.is_foreign ? "foreign" : b.cluster_label || "other";
      if (!g[key]) g[key] = [];
      g[key].push(b);
    });
    Object.keys(g).forEach((k) =>
      g[k].sort((a, b) => a.code.localeCompare(b.code))
    );
    return g;
  }, [brokers]);

  // Build broker map for fast lookup
  const brokerMap = useMemo(() => {
    const m: Record<string, BrokerInfo> = {};
    brokers.forEach((b) => (m[b.code] = b));
    return m;
  }, [brokers]);

  // Filter suggestions based on query
  const suggestions = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return brokers.filter((b) => !selected.includes(b.code)).slice(0, 8);
    return brokers
      .filter(
        (b) =>
          !selected.includes(b.code) &&
          (b.code.includes(q) || b.name.toUpperCase().includes(q))
      )
      .slice(0, 12);
  }, [query, brokers, selected]);

  // Click outside to close dropdown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const addBroker = (code: string) => {
    if (!selected.includes(code)) {
      onSelectedChange([...selected, code]);
    }
    setQuery("");
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const removeBroker = (code: string) => {
    onSelectedChange(selected.filter((c) => c !== code));
  };

  const clearAll = () => {
    onSelectedChange([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && suggestions.length > 0) {
      e.preventDefault();
      addBroker(suggestions[0].code);
    } else if (e.key === "Backspace" && query === "" && selected.length > 0) {
      // Remove last chip on backspace when input is empty
      removeBroker(selected[selected.length - 1]);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  // Keyboard shortcut to open info modal: press "?" or info button
  return (
    <div className="space-y-3">
      {/* Search bar with chips */}
      <div className="relative" ref={dropdownRef}>
        <div className="flex items-center gap-2">
          <div className="flex-1 flex flex-wrap items-center gap-1.5 bg-bg-subtle border border-border rounded-lg px-3 py-2 min-h-[44px] focus-within:border-accent-blue">
            <Search className="h-4 w-4 text-text-muted shrink-0" />

            {/* Selected broker chips */}
            {selected.map((code) => {
              const b = brokerMap[code];
              return (
                <span
                  key={code}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono font-semibold border",
                    b?.is_foreign
                      ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                      : b?.cluster_label === "retail"
                      ? "bg-accent-green/15 text-accent-green border-accent-green/30"
                      : b?.cluster_label === "market_maker"
                      ? "bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30"
                      : b?.cluster_label === "zombie"
                      ? "bg-accent-pink/15 text-accent-pink border-accent-pink/30"
                      : "bg-bg-card text-text-primary border-border-muted"
                  )}
                  title={b?.name || code}
                >
                  {code}
                  <button
                    onClick={() => removeBroker(code)}
                    className="hover:text-accent-red"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              );
            })}

            {/* Input */}
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value.toUpperCase());
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              onKeyDown={handleKeyDown}
              placeholder={
                selected.length === 0
                  ? "Tambah broker (CC, RG, YP, ...)"
                  : "Tambah broker lain..."
              }
              className="flex-1 bg-transparent border-0 outline-none text-sm placeholder:text-text-muted min-w-[120px]"
            />

            {selected.length > 0 && (
              <button
                onClick={clearAll}
                className="text-[10px] text-text-muted hover:text-accent-red ml-1"
              >
                Clear
              </button>
            )}
          </div>

          {/* Info button — opens broker directory modal */}
          <button
            onClick={() => setShowInfoModal(true)}
            className="shrink-0 h-[44px] w-[44px] rounded-lg bg-bg-subtle border border-border text-text-secondary hover:text-accent-blue hover:border-accent-blue/30 flex items-center justify-center"
            title="Daftar lengkap broker"
          >
            <Info className="h-4 w-4" />
          </button>
        </div>

        {/* Autocomplete dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-[52px] mt-1 max-h-[280px] overflow-y-auto bg-bg-card border border-border rounded-lg shadow-xl shadow-black/40 z-30 animate-fade-in">
            {suggestions.map((b) => (
              <button
                key={b.code}
                onClick={() => addBroker(b.code)}
                className="w-full text-left flex items-center justify-between px-3 py-2 hover:bg-bg-subtle text-xs border-b border-border/30 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-accent-blue w-10">
                    {b.code}
                  </span>
                  <span className="text-text-secondary">{b.name}</span>
                </div>
                <Badge
                  variant={
                    b.is_foreign
                      ? "info"
                      : CLUSTER_VARIANT[b.cluster_label] || "default"
                  }
                  className="text-[9px]"
                >
                  {b.is_foreign
                    ? "FOREIGN"
                    : CLUSTER_LABEL[b.cluster_label] || b.cluster_label}
                </Badge>
              </button>
            ))}
          </div>
        )}

        {showSuggestions && suggestions.length === 0 && query && (
          <div className="absolute top-full left-0 right-[52px] mt-1 bg-bg-card border border-border rounded-lg p-3 text-xs text-text-muted z-30">
            Tidak ada broker yang match "{query}"
          </div>
        )}
      </div>

      {/* Selection summary */}
      {selected.length > 0 && (
        <div className="text-xs text-text-secondary">
          <strong className="text-text-primary">{selected.length}</strong>{" "}
          broker dipilih ·{" "}
          <span className="text-text-muted">
            Tekan Enter untuk add cepat · Backspace untuk hapus chip terakhir
          </span>
        </div>
      )}

      {/* Info Modal */}
      {showInfoModal && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
          onClick={() => setShowInfoModal(false)}
        >
          <div
            className="bg-bg-card border border-border rounded-xl shadow-2xl max-w-3xl w-full max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-border">
              <div>
                <h3 className="text-base font-semibold flex items-center gap-2">
                  <Info className="h-4 w-4 text-accent-blue" /> Daftar Broker
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  {brokers.length} broker tersedia · Klik untuk tambahkan ke
                  pilihan
                </p>
              </div>
              <button
                onClick={() => setShowInfoModal(false)}
                className="p-1.5 rounded-lg hover:bg-bg-subtle"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {CLUSTER_ORDER.map((cluster) => {
                const list = grouped[cluster] || [];
                if (list.length === 0) return null;
                const label =
                  cluster === "foreign"
                    ? "Foreign"
                    : CLUSTER_LABEL[cluster] || cluster;
                return (
                  <div key={cluster}>
                    <div className="flex items-center gap-2 mb-2">
                      <Badge
                        variant={
                          cluster === "foreign"
                            ? "info"
                            : CLUSTER_VARIANT[cluster] || "default"
                        }
                        className="text-[10px]"
                      >
                        {label}
                      </Badge>
                      <span className="text-xs text-text-muted">
                        {list.length} broker
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1.5">
                      {list.map((b) => {
                        const isSelected = selected.includes(b.code);
                        return (
                          <button
                            key={b.code}
                            onClick={() => {
                              if (isSelected) {
                                removeBroker(b.code);
                              } else {
                                addBroker(b.code);
                              }
                            }}
                            className={cn(
                              "flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-left transition border",
                              isSelected
                                ? "bg-accent-blue/15 border-accent-blue text-accent-blue"
                                : "bg-bg-subtle border-border hover:border-border-muted"
                            )}
                          >
                            <span className="font-mono font-bold w-10 shrink-0">
                              {b.code}
                            </span>
                            <span className="truncate flex-1 text-text-secondary">
                              {b.name}
                            </span>
                            {isSelected ? (
                              <X className="h-3 w-3 shrink-0" />
                            ) : (
                              <Plus className="h-3 w-3 shrink-0 text-text-muted" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="px-5 py-3 border-t border-border flex items-center justify-between text-xs text-text-secondary">
              <span>
                {selected.length > 0 ? (
                  <>
                    <strong className="text-text-primary">
                      {selected.length}
                    </strong>{" "}
                    broker dipilih
                  </>
                ) : (
                  "Belum ada broker dipilih"
                )}
              </span>
              <div className="flex gap-2">
                {selected.length > 0 && (
                  <button
                    onClick={clearAll}
                    className="px-3 py-1.5 rounded-md text-xs hover:bg-bg-subtle text-text-secondary"
                  >
                    Clear
                  </button>
                )}
                <button
                  onClick={() => setShowInfoModal(false)}
                  className="px-3 py-1.5 rounded-md text-xs bg-accent-blue text-white"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
