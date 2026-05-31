import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  value: number; // 0-5
  size?: "xs" | "sm" | "md";
  showLabel?: boolean;
  setupLabel?: string;
}

const SIZE_CLASS = {
  xs: "h-2.5 w-2.5",
  sm: "h-3 w-3",
  md: "h-4 w-4",
};

const SETUP_COLOR: Record<string, string> = {
  ELITE_SETUP: "text-accent-yellow",
  STRONG_SETUP: "text-accent-green",
  WATCHLIST: "text-accent-cyan",
  AVOID: "text-accent-red",
  IGNORE: "text-text-muted",
  AVOID_ILLIQUID: "text-accent-red",
};

export function StarRating({
  value,
  size = "sm",
  showLabel = false,
  setupLabel,
}: Props) {
  const colorClass = setupLabel
    ? SETUP_COLOR[setupLabel] || "text-text-muted"
    : "text-accent-yellow";

  return (
    <div className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={cn(
            SIZE_CLASS[size],
            i <= value ? colorClass : "text-bg-subtle",
            i <= value && "fill-current"
          )}
          strokeWidth={1.5}
        />
      ))}
      {showLabel && setupLabel && (
        <span className={cn("ml-1.5 text-[10px] font-medium", colorClass)}>
          {setupLabel.replace("_", " ")}
        </span>
      )}
    </div>
  );
}
