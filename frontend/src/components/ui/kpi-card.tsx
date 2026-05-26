"use client";

import { ReactNode } from "react";

type KpiAccent = "primary" | "red" | "orange" | "green" | "slate" | "cyan" | "purple";

const ACCENTS: Record<KpiAccent, string> = {
  primary: "text-primary bg-primary/10",
  red:     "text-red-600 bg-red-500/10",
  orange:  "text-orange-600 bg-orange-500/10",
  green:   "text-green-600 bg-green-500/10",
  slate:   "text-muted-foreground bg-muted",
  cyan:    "text-cyan-700 bg-cyan-500/10",
  purple:  "text-purple-700 bg-purple-500/10",
};

export interface KpiCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: KpiAccent;
  icon?: ReactNode;
  alert?: boolean;
  extra?: ReactNode;   // slot opcional (ej. progress bar)
}

/** Card glass de KPI usado en Dashboard, Rendimiento, Reports. */
export function KpiCard({ label, value, sub, accent = "primary", icon, alert = false, extra }: KpiCardProps) {
  return (
    <div className={`glass-kpi rounded-2xl p-5 agente items-start justify-between gap-3 ${alert ? "ring-1 ring-red-500/30" : ""}`}>
      <div className="min-w-0 agente-1">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider truncate">{label}</p>
        <h3 className="text-3xl font-black text-foreground tracking-tight mt-2 tabular-nums">{value}</h3>
        {sub && <p className="text-xs text-muted-foreground mt-1.5">{sub}</p>}
        {extra}
      </div>
      {icon && <div className={`p-2.5 rounded-xl shrink-0 ${ACCENTS[accent]}`}>{icon}</div>}
    </div>
  );
}
