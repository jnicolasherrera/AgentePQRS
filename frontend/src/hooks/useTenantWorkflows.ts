"use client";

// Sprint FlexFintech 2026-05-27 bloque 7 — info extendida del tenant del
// usuario actual (workflows disponibles, nombre, id). Llama una sola vez al
// boot por sesión y cachea en módulo (no necesita zustand: la respuesta no
// cambia durante una sesión a menos que cambien los buzones del tenant).

import { useEffect, useState } from "react";
import { api, useAuthStore } from "@/store/authStore";
import type { AuthMeResponse, WorkflowType } from "@/types/api";
import { tieneWorkflowAC } from "@/lib/workflow-constants";

// Cache de módulo: una sola request por sesión (clave = token).
let CACHE: { token: string; data: AuthMeResponse } | null = null;
let INFLIGHT: Promise<AuthMeResponse> | null = null;

async function fetchMe(token: string): Promise<AuthMeResponse> {
  if (CACHE && CACHE.token === token) return CACHE.data;
  if (INFLIGHT) return INFLIGHT;
  INFLIGHT = api.get<AuthMeResponse>("/auth/me")
    .then((r) => {
      CACHE = { token, data: r.data };
      INFLIGHT = null;
      return r.data;
    })
    .catch((e) => {
      INFLIGHT = null;
      throw e;
    });
  return INFLIGHT;
}

export interface UseTenantWorkflowsResult {
  data: AuthMeResponse | null;
  loading: boolean;
  /** True si el tenant tiene buzones con workflow ATENCION_CLIENTE activos. */
  tieneAC: boolean;
  workflows: WorkflowType[];
}

export function useTenantWorkflows(): UseTenantWorkflowsResult {
  const token = useAuthStore((s) => s.token);
  const [data, setData] = useState<AuthMeResponse | null>(
    CACHE && CACHE.token === token ? CACHE.data : null
  );
  const [loading, setLoading] = useState(!data);

  useEffect(() => {
    if (!token) return;
    if (CACHE && CACHE.token === token) {
      setData(CACHE.data);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchMe(token)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  return {
    data,
    loading,
    tieneAC: tieneWorkflowAC(data?.workflows_disponibles),
    workflows: data?.workflows_disponibles ?? ["PQRS"],
  };
}

/** Invalida el cache (llamar tras logout o cambio de buzones). */
export function invalidateTenantWorkflows() {
  CACHE = null;
  INFLIGHT = null;
}
