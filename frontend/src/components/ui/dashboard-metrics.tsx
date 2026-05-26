"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, Clock, Inbox, ArrowRight, Scale,
  Layers, Send, Database, Activity, TrendingUp,
} from "lucide-react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useAuthStore } from "@/store/authStore";
import { useDashboardStats } from "@/hooks/useDashboardStats";
import { useTendencia } from "@/hooks/useTendencia";
import { KpiCard } from "@/components/ui/kpi-card";
import { SectionLabel } from "@/components/ui/section-label";
import { formatNumber as nf, formatDateShort as fmtFecha } from "@/lib/format";
import { PERIODOS, TIPO_COLOR_HEX, type Periodo } from "@/lib/casos-constants";

export function DashboardMetrics({
  selectedClienteId = "", onVerTodos,
}: { selectedClienteId?: string; onVerTodos?: () => void }) {
  const { user } = useAuthStore();
  const { stats, loading } = useDashboardStats(selectedClienteId);
  const [periodo, setPeriodo] = useState<Periodo>("semana");
  const isAdmin = user?.rol === "admin" || user?.rol === "super_admin";
  const { data: tendencia } = useTendencia(periodo, selectedClienteId, isAdmin);

  if (loading && !stats) {
    return (
      <div className="space-y-6 pb-10">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass-kpi rounded-2xl p-5">
              <div className="skeleton-pulse h-3 w-20 rounded-full mb-4" />
              <div className="skeleton-pulse h-8 w-24 rounded-lg" />
            </div>
          ))}
        </div>
        <div className="skeleton-pulse glass-panel rounded-3xl h-72" />
      </div>
    );
  }
  if (!stats) return null;

  const k = stats.kpis;
  const activos = k.activos ?? ((k.abiertos || 0) + (k.en_proceso || 0));
  const total = k.total_casos || 0;
  const tipos = stats.distribucion_tipo || {};
  const totalTipos = Object.values(tipos).reduce((a, b) => a + b, 0) || 1;
  const tutelas = tipos["TUTELA"] || 0;
  const tutelasPct = Math.round((tutelas / (total || 1)) * 100);

  const recibidosPeriodo = tendencia.reduce((a, p) => a + (p.recibidos || 0), 0);
  const tutelasPeriodo = tendencia.reduce((a, p) => a + (p.tutelas || 0), 0);
  const tutelasPeriodoPct = recibidosPeriodo > 0 ? Math.round((tutelasPeriodo / recibidosPeriodo) * 100) : 0;

  const tiposOrdenados = Object.entries(tipos).sort((a, b) => b[1] - a[1]);

  const ingresos = stats.ingresos_semana;
  const ingresosTotal = ingresos?.total ?? 0;
  const pqrPct = ingresosTotal > 0 ? Math.round(((ingresos?.pqr ?? 0) / ingresosTotal) * 100) : 0;
  const tutelaPct = ingresosTotal > 0 ? Math.round(((ingresos?.tutela ?? 0) / ingresosTotal) * 100) : 0;
  const pulsoTutelas = stats.tutelas;

  return (
    <div className="space-y-6 pb-10">

      {/* ===== SELECTOR DE PERÍODO ===== */}
      <div className="agente items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          Operación al <span className="text-foreground font-semibold">{new Date().toLocaleDateString("es-CO", { day: "numeric", month: "long" })}</span>
        </p>
        <div className="agente items-center gap-1 bg-muted rounded-xl p-1 border border-border">
          {PERIODOS.map(p => (
            <button key={p.key} onClick={() => setPeriodo(p.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                periodo === p.key ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}>{p.label}</button>
          ))}
        </div>
      </div>

      {/* ===== INGRESOS DEL CORREO — PQR vs TUTELA (últimos 7 días) ===== */}
      {ingresos && (
        <div>
          <SectionLabel icon={<Inbox className="w-3.5 h-3.5 text-primary" />}>
            Lo que entró al correo · últimos 7 días
          </SectionLabel>
          <div className="glass-panel rounded-3xl p-6">
            <div className="agente items-end justify-between gap-6 mb-5">
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Total ingresos</p>
                <h3 className="text-5xl font-black tracking-tight text-foreground mt-1 tabular-nums">{nf(ingresosTotal)}</h3>
                <p className="text-xs text-muted-foreground mt-1">correos clasificados por IA al ingresar</p>
              </div>
              <div className="agente agente-col items-end gap-1">
                <div className="agente items-center gap-2 text-xs text-muted-foreground">
                  <span className="w-2 h-2 rounded-full bg-primary"></span> PQR (petición · queja · reclamo · solicitud)
                </div>
                <div className="agente items-center gap-2 text-xs text-muted-foreground">
                  <Scale className="w-3 h-3 text-red-600" /> Tutela
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-primary/5 p-5">
                <div className="absolute inset-y-0 left-0 bg-primary/10" style={{ width: `${pqrPct}%` }} />
                <div className="relative">
                  <p className="text-[11px] font-bold text-primary uppercase tracking-widest">PQR</p>
                  <div className="agente items-baseline gap-3 mt-2">
                    <span className="text-4xl font-black text-foreground tabular-nums">{nf(ingresos.pqr)}</span>
                    <span className="text-base font-bold text-primary">{pqrPct}%</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">peticiones, quejas, reclamos y solicitudes</p>
                </div>
              </div>
              <div className="relative overflow-hidden rounded-2xl border border-red-500/25 bg-red-500/5 p-5">
                <div className="absolute inset-y-0 left-0 bg-red-500/10" style={{ width: `${tutelaPct}%` }} />
                <div className="relative">
                  <p className="text-[11px] font-bold text-red-600 uppercase tracking-widest agente items-center gap-1.5">
                    <Scale className="w-3 h-3" /> Tutela
                  </p>
                  <div className="agente items-baseline gap-3 mt-2">
                    <span className="text-4xl font-black text-foreground tabular-nums">{nf(ingresos.tutela)}</span>
                    <span className="text-base font-bold text-red-600">{tutelaPct}%</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">acciones de tutela (SLA legal 10 días)</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===== PULSO DE TUTELAS + ESCALADAS DE PQR PREVIO (calidad de servicio) ===== */}
      {pulsoTutelas && (
        <div>
          <SectionLabel icon={<Scale className="w-3.5 h-3.5 text-red-600" />}>
            Pulso de tutelas — SLA legal 10 días
          </SectionLabel>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3 grid grid-cols-3 gap-4">
              <KpiCard label="Tutelas activas" value={nf(pulsoTutelas.activas)} accent="red"
                icon={<Scale className="w-5 h-5" />} sub={`${pulsoTutelas.total} totales`} />
              <KpiCard label="Vencidas" value={nf(pulsoTutelas.vencidas)} accent="red"
                alert={pulsoTutelas.vencidas > 0}
                icon={<AlertTriangle className="w-5 h-5" />} sub="SLA legal incumplido" />
              <KpiCard label="Por vencer" value={nf(pulsoTutelas.por_vencer)} accent="orange"
                icon={<Clock className="w-5 h-5" />} sub="≤48h restantes" />
            </div>
            {/* KPI ESTRELLA: tasa de escalamiento de PQR a Tutela */}
            <div className="lg:col-span-2 glass-panel rounded-3xl p-5 agente agente-col justify-between">
              <div>
                <div className="agente items-center gap-2 mb-2">
                  <div className="p-1.5 rounded-lg bg-red-500/15 text-red-600">
                    <Scale className="w-4 h-4" />
                  </div>
                  <p className="text-[11px] font-bold text-red-600 uppercase tracking-widest">
                    Escaladas de PQR previo
                  </p>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  Tutelas cuyo demandante ya había enviado un PQR sobre el mismo asunto
                  en los últimos 90 días. <span className="text-foreground/80 font-medium">Métrica de calidad de servicio</span>:
                  si crece, estamos respondiendo mal y la gente termina en la justicia.
                </p>
              </div>
              <div>
                <div className="agente items-baseline gap-3">
                  <span className="text-5xl font-black text-red-600 tabular-nums leading-none">
                    {pulsoTutelas.tasa_escalamiento}%
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {nf(pulsoTutelas.escaladas_de_pqr)} de {nf(pulsoTutelas.total)} tutelas
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-muted mt-3 overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${pulsoTutelas.tasa_escalamiento}%` }}
                    transition={{ duration: 0.9 }}
                    className="h-full bg-gradient-to-r from-red-500 to-red-600 rounded-full" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===== OPERACIÓN ACTUAL  vs  HISTÓRICO ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <SectionLabel icon={<Activity className="w-3.5 h-3.5 text-primary" />}>Operación actual</SectionLabel>
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="Activos" value={nf(activos)} accent="primary" icon={<Layers className="w-5 h-5" />}
              sub={<span className="text-primary font-semibold">{k.abiertos || 0} abiertos · {k.en_proceso || 0} en proceso</span>} />
            <KpiCard label="Vencidos" value={nf(k.vencidos || 0)} accent="red" alert={(k.vencidos || 0) > 0}
              icon={<AlertTriangle className="w-5 h-5" />} sub="SLA incumplido" />
            <KpiCard label="Por vencer" value={nf(k.por_vencer || 0)} accent="orange"
              icon={<Clock className="w-5 h-5" />} sub="Vence en ≤48h" />
          </div>
        </div>
        <div className="lg:col-span-2">
          <SectionLabel icon={<Database className="w-3.5 h-3.5 text-muted-foreground" />}>Histórico acumulado</SectionLabel>
          <div className="grid grid-cols-2 gap-4">
            <KpiCard label="Total casos" value={nf(total)} accent="slate" icon={<Inbox className="w-5 h-5" />} sub="Desde el inicio" />
            <div className="glass-kpi rounded-2xl p-5">
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Resueltos</p>
              <h3 className="text-3xl font-black text-foreground tracking-tight mt-2 tabular-nums">{k.porcentaje_resueltos || 0}%</h3>
              <div className="w-full h-1.5 rounded-full bg-muted mt-3 overflow-hidden">
                <motion.div initial={{ width: 0 }} animate={{ width: `${k.porcentaje_resueltos || 0}%` }}
                  transition={{ duration: 0.9 }} className="h-full bg-green-500 rounded-full" />
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">{nf(k.cerrados || 0)} cerrados</p>
            </div>
          </div>
        </div>
      </div>

      {/* ===== ENTRADA DE CASOS  +  COMPOSICIÓN ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Tendencia de ingresos */}
        <div className="lg:col-span-2 glass-panel rounded-3xl p-6">
          <div className="agente items-start justify-between mb-4">
            <div>
              <SectionLabel icon={<TrendingUp className="w-3.5 h-3.5 text-primary" />}>Entrada de casos</SectionLabel>
              <div className="agente items-baseline gap-4">
                <span className="text-2xl font-black text-foreground tabular-nums">{nf(recibidosPeriodo)}</span>
                <span className="text-sm text-muted-foreground">recibidos en el período</span>
              </div>
            </div>
            <div className="text-right">
              <div className="agente items-center gap-1.5 justify-end text-red-600 font-bold">
                <Scale className="w-4 h-4" /> {nf(tutelasPeriodo)}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">tutelas ({tutelasPeriodoPct}% de ingresos)</p>
            </div>
          </div>

          <div className="h-56 -ml-2">
            {tendencia.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={tendencia} margin={{ top: 5, right: 8, bottom: 0, left: -10 }}>
                  <defs>
                    <linearGradient id="gRecibidos" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#035aa7" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#035aa7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="fecha" tickFormatter={fmtFecha} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    axisLine={false} tickLine={false} minTickGap={20} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={28} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12, color: "var(--foreground)" }}
                    labelFormatter={(l) => fmtFecha(l as string)} />
                  <Area type="monotone" dataKey="recibidos" name="Recibidos" stroke="#035aa7" strokeWidth={2.5} fill="url(#gRecibidos)" />
                  <Line type="monotone" dataKey="cerrados" name="Cerrados" stroke="#16a34a" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="tutelas" name="Tutelas" stroke="#dc2626" strokeWidth={2} strokeDasharray="4 3" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="agente agente-col items-center justify-center h-full text-muted-foreground">
                <TrendingUp className="w-8 h-8 mb-2 opacity-40" />
                <p className="text-sm">Sin ingresos en el período</p>
              </div>
            )}
          </div>
          <div className="agente items-center gap-5 mt-3 text-xs text-muted-foreground">
            <span className="agente items-center gap-1.5"><span className="w-3 h-0.5 bg-primary rounded" /> Recibidos</span>
            <span className="agente items-center gap-1.5"><span className="w-3 h-0.5 bg-green-500 rounded" /> Cerrados</span>
            <span className="agente items-center gap-1.5"><span className="w-3 h-0.5 bg-red-600 rounded" /> Tutelas</span>
          </div>
        </div>

        {/* Composición por tipo */}
        <div className="glass-panel rounded-3xl p-6 agente agente-col">
          <SectionLabel icon={<Layers className="w-3.5 h-3.5 text-primary" />}>Composición por tipo</SectionLabel>
          <div className="space-y-3 agente-1">
            {tiposOrdenados.map(([tipo, count]) => {
              const pct = Math.round(((count as number) / totalTipos) * 100);
              const color = TIPO_COLOR_HEX[tipo] || "#64748b";
              return (
                <div key={tipo}>
                  <div className="agente items-center justify-between mb-1">
                    <span className="text-xs font-bold text-foreground/80 tracking-wide agente items-center gap-1.5">
                      {tipo === "TUTELA" && <Scale className="w-3.5 h-3.5 text-red-600" />}{tipo}
                    </span>
                    <span className="text-xs text-muted-foreground tabular-nums">{nf(count as number)} · {pct}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.8 }}
                      className="h-full rounded-full" style={{ background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-5 p-4 rounded-2xl bg-red-500/5 border border-red-500/15 agente items-center gap-3">
            <div className="p-2 rounded-xl bg-red-500/10 text-red-600"><Scale className="w-5 h-5" /></div>
            <div>
              <p className="text-2xl font-black text-red-600 tabular-nums leading-none">{tutelasPct}%</p>
              <p className="text-xs text-muted-foreground mt-1">de los casos son tutelas ({nf(tutelas)})</p>
            </div>
          </div>
        </div>
      </div>

      {/* ===== TRAZABILIDAD ===== */}
      {stats.trazabilidad && (
        <div className="glass-panel p-6 rounded-3xl">
          <SectionLabel icon={<Send className="w-3.5 h-3.5 text-primary" />}>Trazabilidad del proceso</SectionLabel>
          <div className="agente items-center gap-3 overflow-x-auto pb-2 scrollbar-hide">
            {[
              { label: "Recibidos", value: stats.trazabilidad.recibidos, color: "#035aa7" },
              { label: "Asignados", value: stats.trazabilidad.asignados, color: "#f59e0b" },
              { label: "Acuse env.", value: stats.trazabilidad.con_acuse, color: "#06b6d4" },
              { label: "Respondidos", value: stats.trazabilidad.respondidos, color: "#16a34a" },
            ].map((step, i, arr) => {
              const prev = i === 0 ? step.value : arr[i - 1].value;
              const pct = prev > 0 ? Math.round((step.value / prev) * 100) : 0;
              return (
                <div key={step.label} className="agente items-center gap-2 shrink-0">
                  <div className="agente agente-col items-center px-6 py-4 rounded-2xl glass-kpi min-w-[130px]">
                    <span className="text-3xl font-black tracking-tighter tabular-nums" style={{ color: step.color }}>{nf(step.value)}</span>
                    <span className="text-[10px] text-muted-foreground font-bold mt-1 uppercase tracking-widest">{step.label}</span>
                    {i > 0 && (
                      <div className={`text-[10px] font-black mt-2 px-2 py-0.5 rounded-full ${pct >= 80 ? "bg-green-500/15 text-green-600" : pct >= 50 ? "bg-orange-500/15 text-orange-600" : "bg-red-500/15 text-red-600"}`}>{pct}%</div>
                    )}
                  </div>
                  {i < arr.length - 1 && <ArrowRight className="w-5 h-5 text-muted-foreground/40 mx-1 shrink-0" />}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ===== CASOS RECIENTES ===== */}
      <div className="glass-panel rounded-3xl overflow-hidden">
        <div className="p-5 border-b border-border agente items-center justify-between">
          <div className="agente items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg text-primary"><Database className="w-5 h-5" /></div>
            <div>
              <h4 className="text-base font-bold text-foreground">Casos recientes</h4>
              <p className="text-xs text-muted-foreground">Últimos ingresos sincronizados</p>
            </div>
          </div>
          <button onClick={onVerTodos}
            className="px-4 py-2 bg-muted hover:bg-secondary rounded-xl text-sm font-semibold transition-colors border border-border text-foreground agente items-center gap-2">
            Ver todos <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-muted/40 text-muted-foreground uppercase text-[11px] font-bold tracking-widest">
                <th className="px-5 py-3">Asunto / Origen</th>
                <th className="px-5 py-3">Tipo</th>
                <th className="px-5 py-3">Estado</th>
                <th className="px-5 py-3">Vencimiento</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(stats.ultimos_casos || []).slice(0, 8).map((caso: any) => {
                const isVencido = caso.vencimiento && new Date(caso.vencimiento) < new Date() && caso.estado !== "CERRADO";
                return (
                  <tr key={caso.id} className="hover:bg-muted/40 transition-colors">
                    <td className="px-5 py-3">
                      <p className="text-foreground font-medium text-sm truncate max-w-[340px]">{caso.asunto}</p>
                      <p className="text-muted-foreground text-xs truncate">{caso.email}</p>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${caso.tipo === "TUTELA" ? "bg-red-500/10 text-red-600" : "bg-primary/10 text-primary"}`}>{caso.tipo || "PQR"}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="agente items-center gap-2 text-xs font-semibold text-foreground/70">
                        <span className={`w-1.5 h-1.5 rounded-full ${caso.estado === "CERRADO" ? "bg-green-500" : "bg-orange-500"}`} />{caso.estado}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs font-medium ${isVencido ? "text-red-600 font-bold" : "text-muted-foreground"}`}>
                        {caso.vencimiento ? new Date(caso.vencimiento).toLocaleDateString("es-CO") : "—"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
