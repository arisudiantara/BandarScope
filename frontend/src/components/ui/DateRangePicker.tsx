"use client";

import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

export type DateRangePreset =
  | "1D"
  | "5D"
  | "10D"
  | "20D"
  | "60D"
  | "MTD"
  | "YTD"
  | "CUSTOM";

const PRESETS: Array<{ key: DateRangePreset; label: string; days?: number }> = [
  { key: "1D", label: "1D", days: 0 },
  { key: "5D", label: "5D", days: 4 },
  { key: "10D", label: "10D", days: 9 },
  { key: "20D", label: "20D", days: 19 },
  { key: "60D", label: "60D", days: 59 },
  { key: "MTD", label: "MTD" },
  { key: "YTD", label: "YTD" },
  { key: "CUSTOM", label: "Custom" },
];

interface Props {
  startDate: string;        // YYYY-MM-DD
  endDate: string;          // YYYY-MM-DD
  preset: DateRangePreset;
  lastTradingDay: string;   // YYYY-MM-DD (anchor for presets)
  onChange: (range: {
    startDate: string;
    endDate: string;
    preset: DateRangePreset;
  }) => void;
}

export function DateRangePicker({
  startDate,
  endDate,
  preset,
  lastTradingDay,
  onChange,
}: Props) {
  const applyPreset = (key: DateRangePreset) => {
    const anchor = new Date(lastTradingDay + "T00:00:00");
    let start = new Date(anchor);

    const cfg = PRESETS.find((p) => p.key === key);
    if (cfg?.days !== undefined) {
      start.setDate(anchor.getDate() - cfg.days);
    } else if (key === "MTD") {
      start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    } else if (key === "YTD") {
      start = new Date(anchor.getFullYear(), 0, 1);
    } else {
      // CUSTOM — keep current values
      onChange({ startDate, endDate, preset: "CUSTOM" });
      return;
    }

    onChange({
      startDate: toIso(start),
      endDate: lastTradingDay,
      preset: key,
    });
  };

  const handleStart = (val: string) => {
    onChange({ startDate: val, endDate, preset: "CUSTOM" });
  };
  const handleEnd = (val: string) => {
    onChange({ startDate, endDate: val, preset: "CUSTOM" });
  };

  return (
    <div className="space-y-2.5">
      {/* Preset buttons */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-text-muted mr-1">Period:</span>
        {PRESETS.map((p) => (
          <button
            key={p.key}
            onClick={() => applyPreset(p.key)}
            className={cn(
              "px-2.5 py-1 rounded text-xs",
              preset === p.key
                ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                : "bg-bg-subtle border border-border text-text-secondary hover:border-border-muted"
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Date inputs */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Calendar className="h-3.5 w-3.5 text-text-muted" />
        <span className="text-text-muted">Dari</span>
        <input
          type="date"
          value={startDate}
          max={endDate}
          onChange={(e) => handleStart(e.target.value)}
          className="bg-bg-subtle border border-border rounded px-2 py-1 text-text-primary tabular focus:outline-none focus:border-accent-blue"
          style={{ colorScheme: "dark" }}
        />
        <span className="text-text-muted">→</span>
        <span className="text-text-muted">Sampai</span>
        <input
          type="date"
          value={endDate}
          min={startDate}
          max={lastTradingDay}
          onChange={(e) => handleEnd(e.target.value)}
          className="bg-bg-subtle border border-border rounded px-2 py-1 text-text-primary tabular focus:outline-none focus:border-accent-blue"
          style={{ colorScheme: "dark" }}
        />
        <span className="text-[10px] text-text-muted ml-auto">
          Last trading day: <span className="tabular text-text-secondary">{lastTradingDay}</span>
        </span>
      </div>
    </div>
  );
}

function toIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
