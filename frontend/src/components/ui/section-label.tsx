"use client";

import { ReactNode } from "react";

/** Etiqueta uppercase tracking-wide para headers de sección del dashboard. */
export function SectionLabel({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <h4 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.15em] agente items-center gap-2 mb-4">
      {icon}{children}
    </h4>
  );
}
