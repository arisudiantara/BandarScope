"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Layers,
  Compass,
  Activity,
  Users,
  Wallet,
  TrendingUp,
  Star,
  Bell,
  Settings,
  Zap,
  Newspaper,
  BookOpen,
  TestTube,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/daily-brief", label: "Daily Brief", icon: Newspaper },
  { href: "/screener", label: "Screener", icon: Search },
  { href: "/patterns", label: "Pattern Library", icon: BookOpen },
  { href: "/backtesting", label: "Backtesting", icon: TestTube },
  { href: "/sectors", label: "Sectors", icon: Layers },
  { href: "/rotation", label: "Rotation (RRG)", icon: Compass },
  { href: "/yearly-heatmap", label: "Yearly Heatmap", icon: Calendar },
  { href: "/heatmap", label: "Daily Heatmap", icon: Activity },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-bg-card">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-blue to-accent-purple">
          <Zap className="h-4 w-4 text-white" />
        </div>
        <div>
          <div className="text-base font-bold leading-none">BandarScope</div>
          <div className="text-[10px] text-text-muted mt-0.5">IDX Analytics</div>
        </div>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent-blue/15 text-accent-blue font-medium"
                  : "text-text-secondary hover:bg-bg-subtle hover:text-text-primary"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-border space-y-2">
        <Link
          href="/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-bg-subtle hover:text-text-primary"
        >
          <Settings className="h-4 w-4" />
          <span>Settings</span>
        </Link>

        <div className="rounded-lg bg-gradient-to-br from-accent-blue/10 to-accent-purple/10 border border-accent-blue/30 p-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="pulse-dot" />
            <span className="text-xs font-medium text-accent-green">LIVE</span>
          </div>
          <div className="text-xs text-text-secondary">
            Mock data — connect real IDX feed in production
          </div>
        </div>
      </div>
    </aside>
  );
}
