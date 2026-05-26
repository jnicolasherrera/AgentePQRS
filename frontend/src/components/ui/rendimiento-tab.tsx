"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { api } from "@/store/authStore";
import { useAuthStore } from "@/store/authStore";
import { TrendingUp, ChevronUp, ChevronDown, ChevronsUpDown, Edit3, Sparkles, Scale, ShieldCheck } from "lucide-react";

type Periodo = "dia" | "semana" | "mes";
type RendSortKey = "nombre" | "asignados_periodo" | "asignados_total" | "cerrados_total"
  | "tasa_resolucion" | "vencidos" | "criticos" | "avg_horas_resolucion"
  | "ratio_edicion" | "similarity_avg" | "tutelas_evitadas" | "tasa_prevencion";

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
  // Eficiencia (Fase 1+2)
  borradores_generados?: number;
  borradores_editados?: number;
  borradores_enviados?: number;
  ratio_edicion?: number;          // % de borradores que tocó (editados/generados)
  similarity_avg?: number | null;  // 0..1 (alto = poco cambio = IA bien usada)
  review_time_avg_min?: number | null;
  pqrs_gestionados?: number;
  pqrs_escalaron_a_tutela?: number;
  tutelas_evitadas?: number;       // pqrs_gestionados - escalaron (positivo)
  tasa_prevencion?: number;        // % evitadas / gestionados
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
          <h2 className="text-2xl font-black text-foreground">Rendimiento por Abogado</h2>
          <p className="text-muted-foreground text-sm mt-1">Metricas operativas del equipo — {user?.cliente_nombre}</p>
        </div>
        <div className="flex gap-2">
          {periodos.map(p => (
            <button
              key={p.key}
              onClick={() => setPeriodo(p.key)}
              className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                periodo === p.key
                  ? "bg-primary text-white shadow-[0_0_15px_rgba(13,89,242,0.4)]"
                  : "bg-muted text-muted-foreground hover:bg-secondary border border-border"
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
        <div className="text-center py-20 text-muted-foreground">
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
                className={`p-5 rounded-2xl bg-gradient-to-br ${kpi.bg} to-transparent border border-border`}
              >
                <p className={`text-[10px] font-bold uppercase tracking-wider ${kpi.color} mb-2`}>{kpi.label}</p>
                <p className="text-3xl font-black text-foreground">{kpi.value}</p>
              </motion.div>
            ))}
          </div>

          {/* ===== EFICIENCIA DEL EQUIPO — resultado/recurso ===== */}
          {(() => {
            const totBG = data.reduce((s, a) => s + (a.borradores_generados || 0), 0);
            const totBE = data.reduce((s, a) => s + (a.borradores_editados || 0), 0);
            const totBN = data.reduce((s, a) => s + (a.borradores_enviados || 0), 0);
            const ratioEdGlobal = totBG > 0 ? Math.round((totBE / totBG) * 100) : 0;
            const simAvgGlobal = data.filter(a => a.similarity_avg != null)
              .reduce((s, a, _, arr) => s + (a.similarity_avg || 0) / arr.length, 0);
            const totGest = data.reduce((s, a) => s + (a.pqrs_gestionados || 0), 0);
            const totEsc = data.reduce((s, a) => s + (a.pqrs_escalaron_a_tutela || 0), 0);
            const totEvit = Math.max(totGest - totEsc, 0);
            const tasaPrevGlobal = totGest > 0 ? Math.round((totEvit / totGest) * 100) : 0;
            return (
              <div>
                <div className="flex items-baseline justify-between mb-4">
                  <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.15em] agente items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-primary" /> Eficiencia del equipo
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Resultado / recurso — calidad de respuesta y prevención de escalamiento
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="glass-kpi rounded-2xl p-5">
                    <div className="agente items-center gap-2 mb-2">
                      <div className="p-1.5 rounded-lg bg-primary/10 text-primary"><Edit3 className="w-4 h-4" /></div>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Borradores IA</p>
                    </div>
                    <h4 className="text-3xl font-black text-foreground tabular-nums">{totBN}<span className="text-base text-muted-foreground font-medium"> enviados</span></h4>
                    <p className="text-xs text-muted-foreground mt-1">{totBG} generados · {totBE} editados</p>
                  </div>
                  <div className="glass-kpi rounded-2xl p-5">
                    <div className="agente items-center gap-2 mb-2">
                      <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-600"><Edit3 className="w-4 h-4" /></div>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Ratio edición</p>
                    </div>
                    <h4 className="text-3xl font-black text-foreground tabular-nums">{ratioEdGlobal}%</h4>
                    <p className="text-xs text-muted-foreground mt-1">de borradores IA editados antes de enviar</p>
                  </div>
                  <div className="glass-kpi rounded-2xl p-5">
                    <div className="agente items-center gap-2 mb-2">
                      <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-700"><Sparkles className="w-4 h-4" /></div>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Similarity prom.</p>
                    </div>
                    <h4 className="text-3xl font-black text-foreground tabular-nums">
                      {simAvgGlobal > 0 ? `${Math.round(simAvgGlobal * 100)}%` : "—"}
                    </h4>
                    <p className="text-xs text-muted-foreground mt-1">texto enviado vs IA (alto = poco cambio)</p>
                  </div>
                  <div className="glass-kpi rounded-2xl p-5">
                    <div className="agente items-center gap-2 mb-2">
                      <div className="p-1.5 rounded-lg bg-green-500/10 text-green-600"><ShieldCheck className="w-4 h-4" /></div>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Tutelas evitadas</p>
                    </div>
                    <h4 className="text-3xl font-black text-foreground tabular-nums">
                      {totEvit}<span className="text-base text-green-600 font-bold ml-2">{tasaPrevGlobal}%</span>
                    </h4>
                    <p className="text-xs text-muted-foreground mt-1">{totEsc} de {totGest} PQRs escalaron a tutela</p>
                  </div>
                </div>
              </div>
            );
          })()}

          <div className="glass-panel rounded-3xl border border-border overflow-hidden">
            <div className="p-6 border-b border-border flex items-center gap-3">
              <div className="p-2 bg-primary/20 rounded-lg text-primary">
                <TrendingUp className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-foreground">Detalle por Abogado</h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-muted text-muted-foreground text-[10px] font-black uppercase tracking-widest">
                    <th className="px-6 py-4 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("nombre")}>
                      <span className="agente items-center gap-1">Abogado <SortIcon k="nombre" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("asignados_periodo")}>
                      <span className="agente items-center justify-center gap-1">Asignados (periodo) <SortIcon k="asignados_periodo" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("asignados_total")}>
                      <span className="agente items-center justify-center gap-1">Total <SortIcon k="asignados_total" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("cerrados_total")}>
                      <span className="agente items-center justify-center gap-1">Cerrados <SortIcon k="cerrados_total" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("tasa_resolucion")}>
                      <span className="agente items-center justify-center gap-1">Tasa Resolucion <SortIcon k="tasa_resolucion" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("vencidos")}>
                      <span className="agente items-center justify-center gap-1">Vencidos <SortIcon k="vencidos" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("criticos")}>
                      <span className="agente items-center justify-center gap-1">Criticos <SortIcon k="criticos" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("avg_horas_resolucion")}>
                      <span className="agente items-center justify-center gap-1">Prom. Horas <SortIcon k="avg_horas_resolucion" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("ratio_edicion")}>
                      <span className="agente items-center justify-center gap-1">% Edición IA <SortIcon k="ratio_edicion" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("similarity_avg")}>
                      <span className="agente items-center justify-center gap-1">Similarity <SortIcon k="similarity_avg" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("tutelas_evitadas")}>
                      <span className="agente items-center justify-center gap-1">Tutelas evitadas <SortIcon k="tutelas_evitadas" /></span>
                    </th>
                    <th className="px-6 py-4 text-center cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("tasa_prevencion")}>
                      <span className="agente items-center justify-center gap-1">Prevención <SortIcon k="tasa_prevencion" /></span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sortedData.map((a, i) => {
                    const esTop = topResolucion > 0 && a.tasa_resolucion === topResolucion && a.cerrados_total > 0;
                    return (
                      <motion.tr
                        key={a.id}
                        initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.05 }}
                        className="hover:bg-muted transition-colors"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-purple-600 flex items-center justify-center text-xs font-bold text-foreground uppercase">
                              {a.nombre.split(" ").map(n => n[0]).join("").slice(0, 2)}
                            </div>
                            <div>
                              <p className="text-foreground font-semibold text-sm flex items-center gap-2">
                                {a.nombre}
                                {esTop && <span className="text-[9px] px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-full border border-yellow-500/30 font-bold">TOP</span>}
                              </p>
                              <p className="text-muted-foreground text-[10px]">{a.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-blue-400 font-bold">{a.asignados_periodo}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-foreground/80 font-semibold">{a.asignados_total}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-green-400 font-bold">{a.cerrados_total}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="flex flex-col items-center gap-1">
                            <span className={`font-black text-sm ${a.tasa_resolucion >= 70 ? "text-green-400" : a.tasa_resolucion >= 40 ? "text-orange-400" : "text-red-400"}`}>
                              {a.tasa_resolucion}%
                            </span>
                            <div className="w-16 h-1 bg-secondary rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${a.tasa_resolucion >= 70 ? "bg-green-500" : a.tasa_resolucion >= 40 ? "bg-orange-500" : "bg-red-500"}`}
                                style={{ width: `${a.tasa_resolucion}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`font-bold ${a.vencidos > 0 ? "text-red-400" : "text-muted-foreground"}`}>{a.vencidos}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`font-bold ${a.criticos > 0 ? "text-orange-400" : "text-muted-foreground"}`}>{a.criticos}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-foreground/80 font-medium text-sm">
                            {a.avg_horas_resolucion != null ? `${a.avg_horas_resolucion}h` : "\u2014"}
                          </span>
                        </td>
                        {/* % Edici\u00f3n IA */}
                        <td className="px-6 py-4 text-center">
                          {(a.borradores_generados || 0) > 0 ? (
                            <div className="flex flex-col items-center gap-0.5">
                              <span className="text-foreground/80 font-semibold text-sm tabular-nums">{a.ratio_edicion ?? 0}%</span>
                              <span className="text-[10px] text-muted-foreground">{a.borradores_editados ?? 0}/{a.borradores_generados ?? 0}</span>
                            </div>
                          ) : <span className="text-muted-foreground">\u2014</span>}
                        </td>
                        {/* Similarity avg (0..1 \u2192 %) */}
                        <td className="px-6 py-4 text-center">
                          {a.similarity_avg != null ? (
                            <span className={`font-bold tabular-nums ${a.similarity_avg >= 0.85 ? "text-green-600" : a.similarity_avg >= 0.5 ? "text-orange-500" : "text-red-500"}`}>
                              {Math.round(a.similarity_avg * 100)}%
                            </span>
                          ) : <span className="text-muted-foreground">\u2014</span>}
                        </td>
                        {/* Tutelas evitadas */}
                        <td className="px-6 py-4 text-center">
                          {(a.pqrs_gestionados || 0) > 0 ? (
                            <div className="flex flex-col items-center gap-0.5">
                              <span className="text-green-600 font-bold tabular-nums">{a.tutelas_evitadas ?? 0}</span>
                              <span className="text-[10px] text-muted-foreground">de {a.pqrs_gestionados}</span>
                            </div>
                          ) : <span className="text-muted-foreground">\u2014</span>}
                        </td>
                        {/* Tasa de prevenci\u00f3n */}
                        <td className="px-6 py-4 text-center">
                          {(a.pqrs_gestionados || 0) > 0 ? (
                            <div className="flex flex-col items-center gap-1">
                              <span className={`font-black text-sm tabular-nums ${(a.tasa_prevencion ?? 0) >= 90 ? "text-green-600" : (a.tasa_prevencion ?? 0) >= 70 ? "text-orange-500" : "text-red-500"}`}>
                                {a.tasa_prevencion ?? 0}%
                              </span>
                              <div className="w-12 h-1 bg-secondary rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${(a.tasa_prevencion ?? 0) >= 90 ? "bg-green-500" : (a.tasa_prevencion ?? 0) >= 70 ? "bg-orange-500" : "bg-red-500"}`}
                                  style={{ width: `${a.tasa_prevencion ?? 0}%` }} />
                              </div>
                            </div>
                          ) : <span className="text-muted-foreground">\u2014</span>}
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
