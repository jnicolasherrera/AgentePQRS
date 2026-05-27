"use client";

import { useEffect, useState } from "react";
import { api } from "@/store/authStore";
import type { Periodo } from "@/lib/casos-constants";
import type { WorkflowType } from "@/types/api";

export interface TendenciaPoint {
  fecha: string;
  recibidos: number;
  cerrados: number;
  tutelas?: number;
}

/**
 * Hook que trae la serie temporal de ingresos/cerrados/tutelas por día.
 * Espeja el patrón de useDashboardStats (dedup + cleanup).
 * Cancela request en cleanup si cambia período, cliente o workflow (evita race).
 */
export function useTendencia(
  periodo: Periodo,
  selectedClienteId?: string,
  enabled = true,
  workflow?: WorkflowType,  // undefined = ambos workflows (sprint FF bloque 12)
) {
  const [data, setData] = useState<TendenciaPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const params = new URLSearchParams({ periodo });
    if (selectedClienteId) params.set("cliente_id", selectedClienteId);
    if (workflow) params.set("workflow", workflow);
    const ctrl = new AbortController();
    setLoading(true);
    api.get<TendenciaPoint[]>(`/stats/rendimiento/tendencia?${params.toString()}`, { signal: ctrl.signal })
      .then((r) => { setData(r.data || []); setLoading(false); })
      .catch((e) => {
        if (e?.name !== "CanceledError" && e?.code !== "ERR_CANCELED") {
          setData([]); setLoading(false);
        }
      });
    return () => ctrl.abort();
  }, [enabled, periodo, selectedClienteId, workflow]);

  return { data, loading };
}
