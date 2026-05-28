"use client";

import { Settings as SettingsIcon } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <SettingsIcon className="h-6 w-6" /> Settings
        </h1>
      </div>

      <Card>
        <CardHeader
          title="Theme"
          subtitle="Currently locked to Dark Mode (more themes coming)"
        />
        <div className="grid grid-cols-2 gap-3 max-w-md">
          <div className="rounded-lg border-2 border-accent-blue bg-bg-subtle p-3">
            <div className="h-12 rounded bg-bg mb-2 border border-border" />
            <div className="text-sm font-semibold">Dark (active)</div>
          </div>
          <div className="rounded-lg border border-border-muted bg-bg-subtle p-3 opacity-60">
            <div className="h-12 rounded bg-white mb-2 border" />
            <div className="text-sm">Light (soon)</div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Data Source" subtitle="Connect your IDX feed provider" />
        <div className="space-y-3 text-sm">
          {[
            { name: "RTI Business", status: "not_connected" },
            { name: "Stockbit Premium", status: "not_connected" },
            { name: "ESPT / BEI Bilateral", status: "not_connected" },
          ].map((p) => (
            <div
              key={p.name}
              className="flex items-center justify-between rounded-lg bg-bg-subtle border border-border p-3"
            >
              <span className="font-medium">{p.name}</span>
              <button className="px-3 py-1 text-xs rounded-md bg-accent-blue text-white">
                Connect
              </button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
