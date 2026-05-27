"use client";

// Sprint FlexFintech 2026-05-27 bloque 7 — listado de plantillas activas del
// tenant, cacheado por workflow. Usado en:
//   - caso-detail-overlay (sección "Plantillas disponibles" del modo AC).
//   - dashboard-metrics (workflow_breakdown.plantillas_top5 cruza con esta lista
//     para enriquecer label/categoría).

import { useEffect, useState } from "react";
import { api, useAuthStore } from "@/store/authStore";
import type { Plantilla, WorkflowType } from "@/types/api";

// Cache por workflow + token. Las plantillas no cambian seguido (admin las
// edita raramente), así que cachear toda la sesión es seguro.
type CacheKey = string; // `${token}::${workflow ?? "all"}`
const CACHE = new Map<CacheKey, Plantilla[]>();
const INFLIGHT = new Map<CacheKey, Promise<Plantilla[]>>();

function key(token: string, workflow?: WorkflowType): CacheKey {
  return `${token}::${workflow ?? "all"}`;
}

async function fetchPlantillas(token: string, workflow?: WorkflowType): Promise<Plantilla[]> {
  const k = key(token, workflow);
  const cached = CACHE.get(k);
  if (cached) return cached;
  const pending = INFLIGHT.get(k);
  if (pending) return pending;
  const url = workflow ? `/plantillas?workflow=${workflow}` : "/plantillas";
  const promise = api.get<Plantilla[]>(url)
    .then((r) => {
      CACHE.set(k, r.data || []);
      INFLIGHT.delete(k);
      return r.data || [];
    })
    .catch((e) => {
      INFLIGHT.delete(k);
      throw e;
    });
  INFLIGHT.set(k, promise);
  return promise;
}

export interface UsePlantillasResult {
  plantillas: Plantilla[];
  loading: boolean;
  error: string | null;
}

export function usePlantillas(workflow?: WorkflowType, enabled = true): UsePlantillasResult {
  const token = useAuthStore((s) => s.token);
  const [plantillas, setPlantillas] = useState<Plantilla[]>(
    token && CACHE.get(key(token, workflow)) ? CACHE.get(key(token, workflow))! : []
  );
  const [loading, setLoading] = useState(enabled && !!token && !CACHE.get(key(token ?? "", workflow)));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !token) return;
    const k = key(token, workflow);
    const cached = CACHE.get(k);
    if (cached) { setPlantillas(cached); setLoading(false); return; }
    setLoading(true); setError(null);
    fetchPlantillas(token, workflow)
      .then((p) => { setPlantillas(p); setLoading(false); })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Error cargando plantillas";
        setError(msg); setLoading(false);
      });
  }, [enabled, token, workflow]);

  return { plantillas, loading, error };
}

/** Llamar tras editar/crear plantillas para forzar refetch. */
export function invalidatePlantillas() {
  CACHE.clear();
  INFLIGHT.clear();
}
