"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/store/authStore";
import type { DashboardStats, ClienteTenant } from "@/types/api";

export function useDashboardStats(selectedClienteId?: string) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(() => {
    const url = selectedClienteId
      ? `/stats/dashboard?cliente_id=${selectedClienteId}`
      : "/stats/dashboard";
    api.get<DashboardStats>(url)
      .then((res) => {
        setStats(res.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error al obtener estadísticas del dashboard", err);
        setLoading(false);
      });
  }, [selectedClienteId]);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
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
