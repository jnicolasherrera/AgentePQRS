"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, Clock, Inbox, ArrowRight, Scale,
  Layers, Send, Database, Activity, TrendingUp, MessageCircle, Target,
} from "lucide-react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar,
} from "recharts";
import { useAuthStore } from "@/store/authStore";
import { useDashboardStats } from "@/hooks/useDashboardStats";
import { useTendencia } from "@/hooks/useTendencia";
import { useTenantWorkflows } from "@/hooks/useTenantWorkflows";
import { KpiCard } from "@/components/ui/kpi-card";
import { SectionLabel } from "@/components/ui/section-label";
import { formatNumber as nf, formatDateShort as fmtFecha } from "@/lib/format";
import { PERIODOS, TIPO_COLOR_HEX, type Periodo } from "@/lib/casos-constants";
import { WORKFLOWS, WORKFLOW_FILTER_ITEMS, workflowParam, type WorkflowFilter } from "@/lib/workflow-constants";
import { getProblematicaMeta } from "@/lib/problematica-constants";

export function DashboardMetrics({
  selectedClienteId = "", onVerTodos,
}: { selectedClienteId?: string; onVerTodos?: () => void }) {
  const { user } = useAuthStore();
  const [periodo, setPeriodo] = useState<Periodo>("semana");
  // Sprint FF bloque 12: filtro pill workflow [Todo|PQRS|AC]. Solo visible si tieneAC.
  // Default "all" para mostrar agregado al entrar (Recovery/Demo siempre quedan en "all").
  const [workflowFilter, setWorkflowFilter] = useState<WorkflowFilter>("all");
  const { tieneAC } = useTenantWorkflows();
  const wfParam = workflowParam(workflowFilter);
  const { stats, loading } = useDashboardStats(selectedClienteId, periodo, wfParam);
  const isAdmin = user?.rol === "admin" || user?.rol === "super_admin";
  const { data: tendencia } = useTendencia(periodo, selectedClienteId, isAdmin, wfParam);

  // Modos derivados para condicionar UI
  const isModoAC    = workflowFilter === "ATENCION_CLIENTE";
  const isModoPQRS  = workflowFilter === "PQRS";

  // Si el tenant pierde AC mid-session (raro), normalizamos a "all".
  useEffect(() => {
    if (!tieneAC && workflowFilter !== "all") setWorkflowFilter("all");
  }, [tieneAC, workflowFilter]);

  // Etiqueta humana del período actual (para títulos dinámicos)
  const periodoLabel = periodo === "dia" ? "hoy" : periodo === "semana" ? "últimos 7 días" : "últimos 30 días";

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

  const ingresos = stats.ingresos_periodo ?? stats.ingresos_semana;
  const ingresosTotal = ingresos?.total ?? 0;
  const pqrPct = ingresosTotal > 0 ? Math.round(((ingresos?.pqr ?? 0) / ingresosTotal) * 100) : 0;
  const tutelaPct = ingresosTotal > 0 ? Math.round(((ingresos?.tutela ?? 0) / ingresosTotal) * 100) : 0;
  const pulsoTutelas = stats.tutelas;

  return (
    <div className="space-y-6 pb-10">

      {/* ===== SELECTOR DE PERÍODO + (sprint FF) FILTRO WORKFLOW ===== */}
      <div className="agente items-center justify-between gap-4 agente-wrap">
        <p className="text-sm text-muted-foreground">
          Operación al <span className="text-foreground font-semibold">{new Date().toLocaleDateString("es-CO", { day: "numeric", month: "long" })}</span>
          {isModoAC && <span className="ml-2 text-xs text-primary font-semibold">· solo Atención al Cliente</span>}
          {isModoPQRS && <span className="ml-2 text-xs text-red-600 font-semibold">· solo PQRS</span>}
        </p>
        <div className="agente items-center gap-2 agente-wrap">
          {/* Filtro workflow: solo visible si el tenant tiene AC (sprint FF bloque 12) */}
          {tieneAC && (
            <div className="agente items-center gap-1 bg-muted rounded-xl p-1 border border-border">
              {WORKFLOW_FILTER_ITEMS.slice().reverse().map(it => {
                const active = workflowFilter === it.key;
                return (
                  <button
                    key={it.key}
                    onClick={() => setWorkflowFilter(it.key)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >{it.label}</button>
                );
              })}
            </div>
          )}
          <div className="agente items-center gap-1 bg-muted rounded-xl p-1 border border-border">
            {PERIODOS.map(p => (
              <button key={p.key} onClick={() => setPeriodo(p.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  periodo === p.key ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                }`}>{p.label}</button>
            ))}
          </div>
        </div>
      </div>

      {/* ===== INGRESOS DEL CORREO — PQR vs TUTELA (período dinámico) =====
           Sprint FF bloque 12: oculto en modo AC (los AC no tienen tipo_caso PQR ni TUTELA). */}
      {ingresos && !isModoAC && (
        <div>
          <SectionLabel icon={<Inbox className="w-3.5 h-3.5 text-primary" />}>
            Lo que entró al correo · {periodoLabel}
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

      {/* ===== PULSO DE TUTELAS + ESCALADAS DE PQR PREVIO (calidad de servicio) =====
           Sprint FF bloque 12: oculto en modo AC (las tutelas son legales, no aplican). */}
      {pulsoTutelas && !isModoAC && (
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

      {/* ===== ENTRADA DE CASOS  +  COMPOSICIÓN =====
           Sprint FF bloque 12: en modo AC ocultamos "Composición por tipo" (los AC
           tienen tipo_caso=NULL); la tendencia se expande a todo el ancho. */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Tendencia de ingresos */}
        <div className={`${isModoAC ? "lg:col-span-3" : "lg:col-span-2"} glass-panel rounded-3xl p-6`}>
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

        {/* Composición por tipo (oculta en modo AC: tipo_caso es NULL en AC) */}
        {!isModoAC && (
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
        )}
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

      {/* ===== Sprint FF bloque 11: SECCIÓN ATENCIÓN AL CLIENTE =====
           Solo visible si el tenant tiene workflow AC + el backend devuelve breakdown.
           Para Recovery/Demo: cero render (workflow_breakdown vendrá null).
           Sprint FF bloque 12: oculto en modo PQRS (el donut es redundante con el filtro). */}
      {tieneAC && !isModoPQRS && stats.workflow_breakdown && (() => {
        const wb = stats.workflow_breakdown;
        const totalWf = wb.pqrs_count + wb.ac_count;
        const donutData = [
          { name: WORKFLOWS.PQRS.label,             value: wb.pqrs_count, hex: WORKFLOWS.PQRS.hex },
          { name: WORKFLOWS.ATENCION_CLIENTE.label, value: wb.ac_count,   hex: WORKFLOWS.ATENCION_CLIENTE.hex },
        ];
        const barData = wb.plantillas_top5.map(p => {
          const meta = getProblematicaMeta(p.problematica);
          return { name: p.problematica, label: meta.label, value: p.usos, hex: meta.hex };
        });
        const acPct = totalWf > 0 ? Math.round(wb.ac_count / totalWf * 100) : 0;
        return (
          <div>
            <SectionLabel icon={<MessageCircle className="w-3.5 h-3.5 text-primary" />}>
              Atención al Cliente · operativa sin SLA
            </SectionLabel>
            <div className="glass-panel rounded-3xl p-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* IZQUIERDA: donut PQRS vs AC + KPI % match */}
                <div className="space-y-5">
                  <div>
                    <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                      Distribución del período
                    </p>
                    {totalWf > 0 ? (
                      <div className="agente items-center gap-6">
                        <ResponsiveContainer width={160} height={160}>
                          <PieChart>
                            <Pie
                              data={donutData}
                              dataKey="value"
                              cx="50%" cy="50%"
                              innerRadius={48} outerRadius={72}
                              paddingAngle={2}
                              stroke="none"
                            >
                              {donutData.map((d, i) => <Cell key={i} fill={d.hex} />)}
                            </Pie>
                            <Tooltip
                              contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }}
                              formatter={(v) => [nf(Number(v)), "casos"]}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="agente-1 space-y-2.5">
                          {donutData.map((d, i) => {
                            const pct = totalWf > 0 ? Math.round(d.value / totalWf * 100) : 0;
                            return (
                              <div key={i} className="agente items-center justify-between gap-3">
                                <div className="agente items-center gap-2">
                                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: d.hex }} />
                                  <span className="text-xs font-semibold text-foreground">{d.name}</span>
                                </div>
                                <div className="agente items-baseline gap-2">
                                  <span className="text-base font-black text-foreground tabular-nums">{nf(d.value)}</span>
                                  <span className="text-[11px] text-muted-foreground tabular-nums">{pct}%</span>
                                </div>
                              </div>
                            );
                          })}
                          <p className="text-[10px] text-muted-foreground italic pt-1">
                            AC = {acPct}% del volumen del período
                          </p>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">Sin casos en el período.</p>
                    )}
                  </div>

                  {/* KPI % match plantilla exacta vs IA fallback */}
                  <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
                    <div className="agente items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold text-primary uppercase tracking-wider">% match plantilla exacta</p>
                        <h3 className="text-4xl font-black text-foreground tabular-nums mt-1">
                          {wb.pct_match_exacto}<span className="text-xl text-muted-foreground">%</span>
                        </h3>
                        <p className="text-[11px] text-muted-foreground mt-1.5">
                          de los AC del período tienen plantilla exacta (resto va por IA fallback)
                        </p>
                      </div>
                      <div className="p-2.5 rounded-xl bg-primary/10 text-primary shrink-0">
                        <Target className="w-5 h-5" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* DERECHA: top 5 plantillas más usadas (bar horizontal) */}
                <div>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                    Top 5 plantillas usadas
                  </p>
                  {barData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={Math.max(180, barData.length * 44)}>
                      <BarChart data={barData} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
                        <CartesianGrid horizontal={false} stroke="var(--border)" />
                        <XAxis type="number" stroke="var(--muted-foreground)" fontSize={11} allowDecimals={false} />
                        <YAxis
                          type="category"
                          dataKey="label"
                          stroke="var(--muted-foreground)"
                          fontSize={10}
                          width={120}
                          tickFormatter={(t: string) => t.length > 18 ? t.slice(0, 16) + "…" : t}
                        />
                        <Tooltip
                          contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }}
                          formatter={(v, _n, p) => {
                            const name = (p as { payload?: { name?: string } })?.payload?.name || "";
                            return [`${v} usos`, name];
                          }}
                        />
                        <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                          {barData.map((d, i) => <Cell key={i} fill={d.hex} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">
                      Sin plantillas aplicadas en el período.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
