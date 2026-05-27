"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/store/authStore";
import type { DashboardStats, ClienteTenant, WorkflowType } from "@/types/api";
import type { Periodo } from "@/lib/casos-constants";

export function useDashboardStats(
  selectedClienteId?: string,
  periodo: Periodo = "semana",
  workflow?: WorkflowType,  // undefined = ambos (sprint FF bloque 12)
) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(() => {
    const params = new URLSearchParams({ periodo });
    if (selectedClienteId) params.set("cliente_id", selectedClienteId);
    if (workflow) params.set("workflow", workflow);
    api.get<DashboardStats>(`/stats/dashboard?${params.toString()}`)
      .then((res) => {
        // Evita re-renders no-op: solo actualiza si el payload cambió.
        setStats((prev) => {
          const next = res.data;
          if (prev && JSON.stringify(prev) === JSON.stringify(next)) return prev;
          return next;
        });
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error al obtener estadísticas del dashboard", err);
        setLoading(false);
      });
  }, [selectedClienteId, periodo, workflow]);

  useEffect(() => {
    fetchStats();
    // Polling pausado cuando la pestaña está oculta (evita carga en background olvidado).
    const tick = () => {
      if (document.visibilityState === "visible") fetchStats();
    };
    const interval = setInterval(tick, 10000);
    const onVisible = () => { if (document.visibilityState === "visible") fetchStats(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [fetchStats]);

  return { stats, loading, refetch: fetchStats };
}

export function useAdminClientes(isAdmin: boolean) {
  const [clientes, setClientes] = useState<ClienteTenant[]>([]);

  useEffect(() => {
    if (!isAdmin) return;
    api.get<ClienteTenant[]>("/admin/clientes")
      .then((res) => setClientes(res.data))
      .catch((err) => console.error("Error cargando clientes admin", err));
  }, [isAdmin]);

  return clientes;
}
