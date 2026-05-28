import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format IDR currency with B/M/K suffix. */
export function formatIDR(value: number, options: { compact?: boolean } = {}): string {
  const { compact = true } = options;
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (!compact) {
    return sign + "Rp " + abs.toLocaleString("id-ID");
  }

  if (abs >= 1_000_000_000_000) {
    return `${sign}Rp ${(abs / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (abs >= 1_000_000_000) {
    return `${sign}Rp ${(abs / 1_000_000_000).toFixed(2)}M`;
  }
  if (abs >= 1_000_000) {
    return `${sign}Rp ${(abs / 1_000_000).toFixed(2)}Jt`;
  }
  if (abs >= 1_000) {
    return `${sign}Rp ${(abs / 1_000).toFixed(1)}rb`;
  }
  return sign + "Rp " + abs.toString();
}

/** Format number with compact suffix (no IDR prefix). */
export function formatNumber(value: number, decimals = 1): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000_000_000) return `${sign}${(abs / 1_000_000_000_000).toFixed(decimals)}T`;
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(decimals)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(decimals)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(decimals)}K`;
  return sign + abs.toFixed(0);
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return value.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}

export function pctClass(value: number): string {
  if (value > 0) return "text-accent-green";
  if (value < 0) return "text-accent-red";
  return "text-text-secondary";
}

export function netClass(value: number): string {
  return value >= 0 ? "text-accent-green" : "text-accent-red";
}

export function scoreClass(score: number): string {
  if (score >= 75) return "text-accent-green";
  if (score >= 60) return "text-accent-cyan";
  if (score >= 40) return "text-accent-yellow";
  if (score >= 25) return "text-accent-orange";
  return "text-accent-red";
}

export function scoreBgClass(score: number): string {
  if (score >= 75) return "bg-accent-green/20 text-accent-green border-accent-green/30";
  if (score >= 60) return "bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30";
  if (score >= 40) return "bg-accent-yellow/20 text-accent-yellow border-accent-yellow/30";
  if (score >= 25) return "bg-accent-orange/20 text-accent-orange border-accent-orange/30";
  return "bg-accent-red/20 text-accent-red border-accent-red/30";
}

export function signalClass(signal: string): string {
  switch (signal) {
    case "accumulation":
      return "bg-accent-green/20 text-accent-green border border-accent-green/30";
    case "distribution":
      return "bg-accent-red/20 text-accent-red border border-accent-red/30";
    default:
      return "bg-bg-subtle text-text-secondary border border-border-muted";
  }
}
