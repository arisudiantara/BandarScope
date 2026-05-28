import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  change?: { value: number; suffix?: string };
  icon?: React.ReactNode;
  hint?: string;
  className?: string;
}

export function StatCard({ label, value, change, icon, hint, className }: StatCardProps) {
  return (
    <div className={cn("rounded-xl bg-bg-card border border-border p-4", className)}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-secondary uppercase tracking-wide">
          {label}
        </span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className="text-2xl font-bold tabular">{value}</div>
      {change !== undefined && (
        <div
          className={cn(
            "text-xs mt-1 tabular",
            change.value > 0 && "text-accent-green",
            change.value < 0 && "text-accent-red",
            change.value === 0 && "text-text-secondary"
          )}
        >
          {change.value > 0 && "+"}
          {change.value.toFixed(2)}
          {change.suffix || "%"}
        </div>
      )}
      {hint && (
        <div className="text-[11px] text-text-muted mt-1">{hint}</div>
      )}
    </div>
  );
}
