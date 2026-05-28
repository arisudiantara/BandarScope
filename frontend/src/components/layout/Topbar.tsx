"use client";

import { useRouter } from "next/navigation";
import { Search, Bell, ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import { symbolsApi, type SymbolListItem } from "@/lib/api";
import Link from "next/link";

export function Topbar() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SymbolListItem[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await symbolsApi.list({ search: query });
        setResults(r.slice(0, 8));
      } catch (e) {
        setResults([]);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg-card/80 backdrop-blur px-4 md:px-6">
      {/* Search */}
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="Cari saham (BBCA, BBRI, ...)"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value.toUpperCase());
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && results[0]) {
              router.push(`/stock/${results[0].code}`);
              setOpen(false);
            }
          }}
          className="w-full rounded-lg bg-bg-subtle border border-border pl-9 pr-3 py-2 text-sm placeholder:text-text-muted focus:outline-none focus:border-accent-blue"
        />

        {open && results.length > 0 && (
          <div className="absolute top-full mt-1 w-full rounded-lg border border-border bg-bg-card shadow-xl shadow-black/40 overflow-hidden z-50 animate-fade-in">
            {results.map((r) => (
              <Link
                key={r.code}
                href={`/stock/${r.code}`}
                className="flex items-center justify-between px-3 py-2 hover:bg-bg-subtle text-sm"
                onClick={() => setOpen(false)}
              >
                <div>
                  <div className="font-mono font-semibold">{r.code}</div>
                  <div className="text-xs text-text-secondary">{r.name}</div>
                </div>
                <span className="text-xs text-text-muted">{r.sector}</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden md:flex items-center gap-2 text-xs text-text-secondary px-3 py-1.5 rounded-lg bg-bg-subtle border border-border">
          <span className="pulse-dot" />
          <span>IDX • WIB</span>
          <span className="text-text-muted ml-1 tabular">
            {new Date().toLocaleTimeString("id-ID", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>

        <button className="relative p-2 rounded-lg hover:bg-bg-subtle">
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-accent-red" />
        </button>

        <button className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-bg-subtle text-sm">
          <div className="h-7 w-7 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-xs font-bold">
            U
          </div>
          <ChevronDown className="h-3 w-3 text-text-muted" />
        </button>
      </div>
    </header>
  );
}
