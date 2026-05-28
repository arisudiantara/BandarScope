"use client";

import { Bell, Sparkles } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const ALERT_TEMPLATES = [
  {
    id: "bandar_breakout",
    name: "Bandar Breakout",
    desc: "Trigger when BandarScore > 80 AND volume anomaly > 2x",
    rule: "bandar_score > 80 AND volume_anomaly > 2.0",
    channel: ["Push", "Telegram"],
  },
  {
    id: "stealth_accumulation",
    name: "Stealth Accumulation",
    desc: "Inventory line breaks new high while price flat",
    rule: "inventory_score > 75 AND momentum_score < 50",
    channel: ["Push", "Email"],
  },
  {
    id: "foreign_inflow_surge",
    name: "Foreign Inflow Surge",
    desc: "20D cumulative foreign net > Rp 100B",
    rule: "foreign_net_20d > 100000000000",
    channel: ["Push", "Telegram"],
  },
  {
    id: "distribution_warning",
    name: "Distribution Warning",
    desc: "Smart money distribution + bearish divergence",
    rule: "smart_money_signal = 'distribution' AND divergence = 'BEARISH'",
    channel: ["Push"],
  },
  {
    id: "rrg_leading",
    name: "Sector Enters Leading",
    desc: "Sector rotation into Leading quadrant",
    rule: "rrg_quadrant CHANGES TO 'leading'",
    channel: ["Push", "Email"],
  },
];

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bell className="h-6 w-6" /> Smart Alerts
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Multi-channel notifications for bandar moves & flow signals
        </p>
      </div>

      <Card className="bg-gradient-to-br from-accent-blue/5 to-accent-purple/5 border-accent-blue/20">
        <div className="flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-accent-yellow shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Alert Engine — Coming Soon</div>
            <p className="text-sm text-text-secondary mt-1">
              Rule-based + ML-detected alert system with delivery to Push, Email,
              Telegram, and WhatsApp. Includes deduplication, cooldown, and
              multi-condition logic.
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Alert Templates"
          subtitle="One-click setup for common bandarmology triggers"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {ALERT_TEMPLATES.map((a) => (
            <div
              key={a.id}
              className="rounded-lg bg-bg-subtle border border-border p-4 hover:border-border-muted transition"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold">{a.name}</div>
                <button className="text-xs text-accent-blue hover:underline">
                  Setup
                </button>
              </div>
              <p className="text-sm text-text-secondary mb-3">{a.desc}</p>
              <div className="rounded bg-bg-card border border-border-muted px-2 py-1.5 font-mono text-[11px] text-accent-cyan mb-3">
                {a.rule}
              </div>
              <div className="flex gap-1">
                {a.channel.map((c) => (
                  <Badge key={c} variant="info" className="text-[10px]">
                    {c}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="My Active Alerts"
          subtitle="No alerts configured yet"
        />
        <div className="text-center py-8 text-text-muted text-sm">
          Set up your first alert from a template above
        </div>
      </Card>
    </div>
  );
}
