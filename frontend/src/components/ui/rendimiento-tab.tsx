"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { api } from "@/store/authStore";
import { useAuthStore } from "@/store/authStore";
import { TrendingUp, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

type Periodo = "dia" | "semana" | "mes";
type RendSortKey = "nombre" | "asignados_periodo" | "asignados_total" | "cerrados_total" | "tasa_resolucion" | "vencidos" | "criticos" | "avg_horas_resolucion";

interface AbogadoMetrica {
  id: string;
  nombre: string;
  email: string;
  asignados_periodo: number;
  asignados_total: number;
  cerrados_total: number;
  cerrados_periodo: number;
  vencidos: number;
  criticos: number;
  tasa_resolucion: number;
  avg_horas_resolucion: number | null;
}

export function RendimientoTab({ selectedClienteId }: { selectedClienteId?: string }) {
  const { user } = useAuthStore();
  const [periodo, setPeriodo] = useState<Periodo>("semana");
  const [data, setData] = useState<AbogadoMetrica[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<RendSortKey>("tasa_resolucion");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const fetchData = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ periodo });
    if (selectedClienteId) params.append("cliente_id", selectedClienteId);
    api.get<{ periodo: string; abogados: AbogadoMetrica[] }>(`/stats/rendimiento?${params}`)
      .then(res => { setData(res.data.abogados); setLoading(false); })
      .catch(() => setLoading(false));
  }, [periodo, selectedClienteId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggleSort = (key: RendSortKey) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
  };

  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (typeof va === "string" && typeof vb === "string")
        return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortDir === "asc" ? ((va as number) ?? 0) - ((vb as number) ?? 0) : ((vb as number) ?? 0) - ((va as number) ?? 0);
    });
  }, [data, sortKey, sortDir]);

  const SortIcon = ({ k }: { k: RendSortKey }) =>
    sortKey === k
      ? sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
      : <ChevronsUpDown className="w-3 h-3 opacity-30" />;

  const periodos: { key: Periodo; label: string }[] = [
    { key: "dia", label: "Hoy" },
    { key: "semana", label: "7 dias" },
    { key: "mes", label: "30 dias" },
  ];

  const topResolucion = useMemo(() => data.reduce((max, a) => a.tasa_resolucion > max ? a.tasa_resolucion : max, 0), [data]);

  return (
    <div className="space-y-8 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-black text-white">Rendimiento por Abogado</h2>
          <p className="text-slate-400 text-sm mt-1">Metricas operativas del equipo — {user?.cliente_nombre}</p>
        </div>
        <div className="flex gap-2">
          {periodos.map(p => (
            <button
              key={p.key}
              onClick={() => setPeriodo(p.key)}
              className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                periodo === p.key
                  ? "bg-primary text-white shadow-[0_0_15px_rgba(13,89,242,0.4)]"
                  : "bg-white/5 text-slate-400 hover:bg-white/10 border border-white/10"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 opacity-50">
          <div className="w-10 h-10 rounded-full border-t-2 border-primary animate-spin" />
        </div>
      ) : data.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          No hay abogados con casos asignados todavia.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Casos en periodo", value: data.reduce((s, a) => s + a.asignados_periodo, 0), color: "text-blue-400", bg: "from-blue-500/10" },
              { label: "Cerrados en periodo", value: data.reduce((s, a) => s + a.cerrados_periodo, 0), color: "text-green-400", bg: "from-green-500/10" },
              { label: "Vencidos totales", value: data.reduce((s, a) => s + a.vencidos, 0), color: "text-red-400", bg: "from-red-500/10" },
              { label: "Casos criticos", value: data.reduce((s, a) => s + a.criticos, 0), color: "text-orange-400", bg: "from-orange-500/10" },
            ].map((kpi, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                className={`p-5 rounded-2xl bg-gradient-to-br ${kpi.bg} to-transparent border border-white/5`}
              >
                <p className={`text-[10px] font-bold uppercase tracking-wider ${kpi.color} mb-2`}>{kpi.label}</p>
                <p className="text-3xl font-black text-white">{kpi.value}</p>
              </motion.div>
            ))}
          </div>

          <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
            <div className="p-6 border-b border-white/10 flex items-center gap-3">
              <div className="p-2 bg-primary/20 rounded-lg text-primary">
                <TrendingUp className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-white">Detalle por Abogado</h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-white/[0.03] text-slate-400 text-[10px] font-black uppercase tracking-widest">
                    <th className="px-6 py-4 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("nombre")}>
                      <span className="agente items-center gap-1">Abogado <SortIcon k="nombre" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("asignados_periodo")}>
                      <span className="agente items-center justify-center gap-1">Asignados (periodo) <SortIcon k="asignados_periodo" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("asignados_total")}>
                      <span className="agente items-center justify-center gap-1">Total <SortIcon k="asignados_total" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("cerrados_total")}>
                      <span className="agente items-center justify-center gap-1">Cerrados <SortIcon k="cerrados_total" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("tasa_resolucion")}>
                      <span className="agente items-center justify-center gap-1">Tasa Resolucion <SortIcon k="tasa_resolucion" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("vencidos")}>
                      <span className="agente items-center justify-center gap-1">Vencidos <SortIcon k="vencidos" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("criticos")}>
                      <span className="agente items-center justify-center gap-1">Criticos <SortIcon k="criticos" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("avg_horas_resolucion")}>
                      <span className="agente items-center justify-center gap-1">Prom. Horas <SortIcon k="avg_horas_resolucion" /></span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {sortedData.map((a, i) => {
                    const esTop = topResolucion > 0 && a.tasa_resolucion === topResolucion && a.cerrados_total > 0;
                    return (
                      <motion.tr
                        key={a.id}
                        initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.05 }}
                        className="hover:bg-white/[0.02] transition-colors"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-purple-600 flex items-center justify-center text-xs font-bold text-white uppercase">
                              {a.nombre.split(" ").map(n => n[0]).join("").slice(0, 2)}
                            </div>
                            <div>
                              <p className="text-white font-semibold text-sm flex items-center gap-2">
                                {a.nombre}
                                {esTop && <span className="text-[9px] px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-full border border-yellow-500/30 font-bold">TOP</span>}
                              </p>
                              <p className="text-slate-500 text-[10px]">{a.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-blue-400 font-bold">{a.asignados_periodo}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-slate-300 font-semibold">{a.asignados_total}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-green-400 font-bold">{a.cerrados_total}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="flex flex-col items-center gap-1">
                            <span className={`font-black text-sm ${a.tasa_resolucion >= 70 ? "text-green-400" : a.tasa_resolucion >= 40 ? "text-orange-400" : "text-red-400"}`}>
                              {a.tasa_resolucion}%
                            </span>
                            <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${a.tasa_resolucion >= 70 ? "bg-green-500" : a.tasa_resolucion >= 40 ? "bg-orange-500" : "bg-red-500"}`}
                                style={{ width: `${a.tasa_resolucion}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`font-bold ${a.vencidos > 0 ? "text-red-400" : "text-slate-500"}`}>{a.vencidos}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`font-bold ${a.criticos > 0 ? "text-orange-400" : "text-slate-500"}`}>{a.criticos}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-slate-300 font-medium text-sm">
                            {a.avg_horas_resolucion != null ? `${a.avg_horas_resolucion}h` : "\u2014"}
                          </span>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
