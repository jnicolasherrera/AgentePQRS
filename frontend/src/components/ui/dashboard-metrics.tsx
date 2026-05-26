"use client";

import { useState, useEffect, ReactNode } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, Clock, Inbox, ArrowRight, Scale,
  Layers, Send, Database, Activity, TrendingUp,
} from "lucide-react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useAuthStore, api } from "@/store/authStore";
import { useDashboardStats } from "@/hooks/useDashboardStats";

const nf = (n: number) => (n ?? 0).toLocaleString("es-CO");
const fmtFecha = (f: string) => {
  const d = new Date(f + "T00:00:00");
  return d.toLocaleDateString("es-CO", { day: "2-digit", month: "short" });
};

interface TendenciaPoint { fecha: string; recibidos: number; cerrados: number; tutelas?: number; }

type Periodo = "dia" | "semana" | "mes";
const PERIODOS: { key: Periodo; label: string }[] = [
  { key: "dia", label: "Hoy" },
  { key: "semana", label: "7 días" },
  { key: "mes", label: "30 días" },
];

/* ---------- piezas de UI reutilizables ---------- */

function SectionLabel({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <h4 className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.15em] agente items-center gap-2 mb-4">
      {icon}{children}
    </h4>
  );
}

function KpiCard({
  label, value, sub, accent = "primary", icon, alert = false,
}: {
  label: string; value: ReactNode; sub?: ReactNode;
  accent?: "primary" | "red" | "orange" | "green" | "slate"; icon?: ReactNode; alert?: boolean;
}) {
  const accents: Record<string, string> = {
    primary: "text-primary bg-primary/10",
    red: "text-red-600 bg-red-500/10",
    orange: "text-orange-600 bg-orange-500/10",
    green: "text-green-600 bg-green-500/10",
    slate: "text-muted-foreground bg-muted",
  };
  return (
    <div className={`glass-kpi rounded-2xl p-5 agente items-start justify-between gap-3 ${alert ? "ring-1 ring-red-500/30" : ""}`}>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider truncate">{label}</p>
        <h3 className="text-3xl font-black text-foreground tracking-tight mt-2 tabular-nums">{value}</h3>
        {sub && <p className="text-xs text-muted-foreground mt-1.5">{sub}</p>}
      </div>
      {icon && <div className={`p-2.5 rounded-xl shrink-0 ${accents[accent]}`}>{icon}</div>}
    </div>
  );
}

export function DashboardMetrics({
  selectedClienteId = "", onVerTodos,
}: { selectedClienteId?: string; onVerTodos?: () => void }) {
  const { user } = useAuthStore();
  const { stats, loading } = useDashboardStats(selectedClienteId);
  const [periodo, setPeriodo] = useState<Periodo>("semana");
  const [tendencia, setTendencia] = useState<TendenciaPoint[]>([]);

  const isAdmin = user?.rol === "admin" || user?.rol === "super_admin";

  useEffect(() => {
    if (!isAdmin) return;
    const base = `/stats/rendimiento/tendencia?periodo=${periodo}`;
    const url = selectedClienteId ? `${base}&cliente_id=${selectedClienteId}` : base;
    const ctrl = new AbortController();
    api.get<TendenciaPoint[]>(url, { signal: ctrl.signal })
      .then(r => setTendencia(r.data || []))
      .catch((e) => { if (e?.name !== "CanceledError" && e?.code !== "ERR_CANCELED") setTendencia([]); });
    return () => ctrl.abort();
  }, [isAdmin, periodo, selectedClienteId]);

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

  const k = stats.kpis as unknown as Record<string, number>;
  const activos = k.activos ?? ((k.abiertos || 0) + (k.en_proceso || 0));
  const total = k.total_casos || 0;
  const tipos = (stats.distribucion_tipo || {}) as unknown as Record<string, number>;
  const totalTipos = Object.values(tipos).reduce((a, b) => a + (b as number), 0) || 1;
  const tutelas = tipos["TUTELA"] || 0;
  const tutelasPct = Math.round((tutelas / (total || 1)) * 100);

  const recibidosPeriodo = tendencia.reduce((a, p) => a + (p.recibidos || 0), 0);
  const tutelasPeriodo = tendencia.reduce((a, p) => a + (p.tutelas || 0), 0);
  const tutelasPeriodoPct = recibidosPeriodo > 0 ? Math.round((tutelasPeriodo / recibidosPeriodo) * 100) : 0;

  const tipoColor: Record<string, string> = {
    TUTELA: "#dc2626", PETICION: "#035aa7", QUEJA: "#f59e0b",
    RECLAMO: "#8b5cf6", SOLICITUD: "#06b6d4", CONSULTA: "#64748b",
  };
  const tiposOrdenados = Object.entries(tipos).sort((a, b) => (b[1] as number) - (a[1] as number));

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
              const color = tipoColor[tipo] || "#64748b";
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
