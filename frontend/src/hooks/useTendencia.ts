"use client";

import { useEffect, useState } from "react";
import { api } from "@/store/authStore";
import type { Periodo } from "@/lib/casos-constants";

export interface TendenciaPoint {
  fecha: string;
  recibidos: number;
  cerrados: number;
  tutelas?: number;
}

/**
 * Hook que trae la serie temporal de ingresos/cerrados/tutelas por día.
 * Espeja el patrón de useDashboardStats (dedup + cleanup).
 * Cancela request en cleanup si cambia período o cliente (evita race).
 */
export function useTendencia(periodo: Periodo, selectedClienteId?: string, enabled = true) {
  const [data, setData] = useState<TendenciaPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const base = `/stats/rendimiento/tendencia?periodo=${periodo}`;
    const url = selectedClienteId ? `${base}&cliente_id=${selectedClienteId}` : base;
    const ctrl = new AbortController();
    setLoading(true);
    api.get<TendenciaPoint[]>(url, { signal: ctrl.signal })
      .then((r) => { setData(r.data || []); setLoading(false); })
      .catch((e) => {
        if (e?.name !== "CanceledError" && e?.code !== "ERR_CANCELED") {
          setData([]); setLoading(false);
        }
      });
    return () => ctrl.abort();
  }, [enabled, periodo, selectedClienteId]);

  return { data, loading };
}
