import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info";
  className?: string;
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  const variants = {
    default: "bg-bg-subtle text-text-secondary border-border-muted",
    success: "bg-accent-green/15 text-accent-green border-accent-green/30",
    warning: "bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30",
    danger: "bg-accent-red/15 text-accent-red border-accent-red/30",
    info: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
