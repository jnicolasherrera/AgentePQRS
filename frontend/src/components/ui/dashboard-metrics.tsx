"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Activity, AlertTriangle, CheckCircle, Clock, Mail, ArrowRight, Zap, Database, Send, Timer, BarChart3, Users, Inbox } from "lucide-react";
import { useAuthStore, api } from "@/store/authStore";
import { useDashboardStats } from "@/hooks/useDashboardStats";

const timeAgo = (isoDate: string) => {
  if (!isoDate) return "Desconocido";
  const date = new Date(isoDate);
  return date.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
};

interface MetricasRespuestas {
  respondidos_hoy: number;
  respondidos_semana: number;
  tiempo_promedio_horas: number;
  tasa_cobertura_plantilla: number;
  por_abogado: { nombre: string; enviados: number }[];
}

export function DashboardMetrics({ selectedClienteId = "" }: { selectedClienteId?: string }) {
  const { user } = useAuthStore();
  const [metricasResp, setMetricasResp] = useState<MetricasRespuestas | null>(null);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const handleKpiClick = (filter: string) => {
    setActiveFilter(prev => prev === filter ? null : filter);
  };

  const isAdmin = user?.rol === "admin" || user?.rol === "super_admin";

  useEffect(() => {
    if (!isAdmin) return;
    const url = selectedClienteId
      ? `/casos/metricas/respuestas?cliente_id=${selectedClienteId}`
      : "/casos/metricas/respuestas";
    api.get<MetricasRespuestas>(url)
      .then(r => setMetricasResp(r.data))
      .catch(() => {});
  }, [isAdmin, selectedClienteId]);
  const { stats, loading } = useDashboardStats(selectedClienteId);

  if (loading && !stats) {
    return (
      <div className="space-y-8 pb-10">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass-kpi rounded-2xl p-7">
              <div className="skeleton-pulse h-3 w-20 rounded-full mb-5" />
              <div className="skeleton-pulse h-9 w-24 rounded-lg" />
            </div>
          ))}
        </div>
        <div className="skeleton-pulse glass-panel rounded-3xl h-44" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="glass-kpi rounded-3xl p-7">
              <div className="skeleton-pulse h-3 w-24 rounded-full mb-4" />
              <div className="skeleton-pulse h-8 w-16 rounded-lg" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!stats) return null;

  const filteredCases = activeFilter && activeFilter !== "ALL"
    ? (stats.ultimos_casos || []).filter((c: any) => c.estado === activeFilter)
    : (stats.ultimos_casos || []);

  return (
    <div className="space-y-8 pb-10">
      
      {/* SECCIÓN 1: KPIs de Alto Impacto */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-5">

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0 }}
          role="button" tabIndex={0}
          onClick={() => handleKpiClick("ALL")}
          className={`relative glass-kpi p-7 rounded-2xl overflow-hidden group transition-all duration-300 border border-blue-500/15 hover:border-blue-500/40 hover:shadow-[0_0_40px_rgba(59,130,246,0.12)] cursor-pointer ${activeFilter === "ALL" ? "ring-2 ring-blue-400/50" : ""}`}>
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/8 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="agente items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-blue-400" />
              <p className="text-blue-200/80 font-semibold text-[11px] tracking-widest uppercase">Total Casos</p>
            </div>
            <h3 className="text-4xl font-black text-white tracking-tight">{(stats.kpis.total_casos || 0).toLocaleString()}</h3>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
          role="button" tabIndex={0}
          onClick={() => handleKpiClick("ABIERTO")}
          className={`relative glass-kpi p-7 rounded-2xl overflow-hidden group transition-all duration-300 border border-red-500/15 hover:border-red-500/40 hover:shadow-[0_0_40px_rgba(239,68,68,0.12)] cursor-pointer ${activeFilter === "ABIERTO" ? "ring-2 ring-red-400/50" : ""}`}>
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/8 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="agente items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              <p className="text-red-200/80 font-semibold text-[11px] tracking-widest uppercase">Abiertos / Nuevos</p>
            </div>
            <h3 className="text-4xl font-black text-white tracking-tight">{(stats.kpis.abiertos || 0).toLocaleString()}</h3>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16 }}
          role="button" tabIndex={0}
          onClick={() => handleKpiClick("EN_PROCESO")}
          className={`relative glass-kpi p-7 rounded-2xl overflow-hidden group transition-all duration-300 border border-orange-500/15 hover:border-orange-500/40 hover:shadow-[0_0_40px_rgba(249,115,22,0.12)] cursor-pointer ${activeFilter === "EN_PROCESO" ? "ring-2 ring-orange-400/50" : ""}`}>
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500/8 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="agente items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-orange-400" />
              <p className="text-orange-200/80 font-semibold text-[11px] tracking-widest uppercase">En Proceso</p>
            </div>
            <h3 className="text-4xl font-black text-white tracking-tight">{(stats.kpis.en_proceso || 0).toLocaleString()}</h3>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24 }}
          role="button" tabIndex={0}
          onClick={() => handleKpiClick("CONTESTADO")}
          className={`relative glass-kpi p-7 rounded-2xl overflow-hidden group transition-all duration-300 border border-purple-500/15 hover:border-purple-500/40 hover:shadow-[0_0_40px_rgba(168,85,247,0.12)] cursor-pointer ${activeFilter === "CONTESTADO" ? "ring-2 ring-purple-400/50" : ""}`}>
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/8 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="agente items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-purple-400" />
              <p className="text-purple-200/80 font-semibold text-[11px] tracking-widest uppercase">Contestados</p>
            </div>
            <h3 className="text-4xl font-black text-white tracking-tight">{(stats.kpis.contestados || 0).toLocaleString()}</h3>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.32 }}
          role="button" tabIndex={0}
          onClick={() => handleKpiClick("CERRADO")}
          className={`relative glass-kpi p-7 rounded-2xl overflow-hidden group transition-all duration-300 border border-green-500/15 hover:border-green-500/40 hover:shadow-[0_0_40px_rgba(34,197,94,0.12)] cursor-pointer ${activeFilter === "CERRADO" ? "ring-2 ring-green-400/50" : ""}`}>
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/8 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="agente items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-green-400" />
              <p className="text-green-200/80 font-semibold text-[11px] tracking-widest uppercase">Cerrados</p>
            </div>
            <h3 className="text-4xl font-black text-white tracking-tight agente items-baseline gap-2">
              {(stats.kpis.cerrados || 0).toLocaleString()}
              <span className="text-base text-green-400 font-semibold">{stats.kpis.porcentaje_resueltos}%</span>
            </h3>
          </div>
        </motion.div>

      </div>

      {/* TRAZABILIDAD: Funnel punto a punto del proceso */}
      {stats.trazabilidad && (
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="glass-panel p-6 rounded-3xl border border-white/10"
        >
          <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-5 agente items-center gap-2">
            <Activity className="w-4 h-4 text-primary" /> Trazabilidad del proceso
          </h4>          <div className="agente items-center gap-3 overflow-x-auto pb-2 scrollbar-hide">
            {[
              { label: "Recibidos",  value: stats.trazabilidad.recibidos,   color: "text-blue-400",   bg: "bg-blue-500/10 border-blue-500/20", glow: "shadow-[0_0_20px_rgba(59,130,246,0.1)]" },
              { label: "Asignados",  value: stats.trazabilidad.asignados,   color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20", glow: "shadow-[0_0_20px_rgba(249,115,22,0.1)]" },
              { label: "Acuse env.", value: stats.trazabilidad.con_acuse,   color: "text-cyan-400",   bg: "bg-cyan-500/10 border-cyan-500/20", glow: "shadow-[0_0_20px_rgba(6,182,212,0.1)]" },
              { label: "Respondidos",value: stats.trazabilidad.respondidos, color: "text-green-400",  bg: "bg-green-500/10 border-green-500/20", glow: "shadow-[0_0_20px_rgba(34,197,94,0.1)]" },
            ].map((step, i, arr) => {
              const prev = i === 0 ? step.value : arr[i - 1].value;
              const pct = prev > 0 ? Math.round((step.value / prev) * 100) : 0;
              return (
                <div key={step.label} className="agente items-center gap-2 shrink-0">
                  <div className={`agente agente-col items-center px-6 py-5 rounded-2xl border transition-all duration-500 ${step.bg} ${step.glow} min-w-[130px] hover:scale-105`}>
                    <span className={`text-4xl font-black ${step.color} tracking-tighter`}>{step.value.toLocaleString()}</span>
                    <span className="text-[10px] text-slate-400 font-bold mt-1 uppercase tracking-widest">{step.label}</span>
                    {i > 0 && (
                      <div className={`text-[10px] font-black mt-2 px-2 py-0.5 rounded-full ${pct >= 80 ? 'bg-green-500/20 text-green-400' : pct >= 50 ? 'bg-orange-500/20 text-orange-400' : 'bg-red-500/20 text-red-400'}`}>
                        {pct}%
                      </div>
                    )}
                  </div>
                  {i < arr.length - 1 && (
                    <motion.div 
                      animate={{ x: [0, 5, 0] }}
                      transition={{ repeat: Infinity, duration: 2 }}
                    >
                      <ArrowRight className="w-5 h-5 text-slate-700 mx-2" />
                    </motion.div>
                  )}
                </div>
              );
            })}
          </div>

        </motion.div>
      )}

      {/* SECCIÓN 2: Resumen Operativo Detallado (NUEVO: Resumen de Todo) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <motion.div 
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
            className="glass-panel p-6 rounded-3xl border border-white/10 bg-blue-500/5 agente items-center justify-between"
        >
            <div>
                <p className="text-blue-400 text-xs font-bold uppercase tracking-widest mb-1">Ingresos Hoy</p>
                <h4 className="text-3xl font-black text-white">{stats.kpis.casos_hoy || 0}</h4>
            </div>
            <div className="p-3 bg-blue-500/20 rounded-2xl text-blue-400">
                <Zap className="w-6 h-6" />
            </div>
        </motion.div>

        <motion.div 
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3 }}
            className="glass-panel p-6 rounded-3xl border border-white/10 bg-purple-500/5 agente items-center justify-between"
        >
            <div>
                <p className="text-purple-400 text-xs font-bold uppercase tracking-widest mb-1">Carga Semanal</p>
                <h4 className="text-3xl font-black text-white">{stats.kpis.casos_semana || 0}</h4>
            </div>
            <div className="p-3 bg-purple-500/20 rounded-2xl text-purple-400">
                <Clock className="w-6 h-6" />
            </div>
        </motion.div>

        <motion.div 
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.4 }}
            className="glass-panel p-6 rounded-3xl border border-red-500/10 bg-red-500/5 agente items-center justify-between shadow-[0_0_20px_rgba(239,68,68,0.05)]"
        >
            <div>
                <p className="text-red-400 text-xs font-bold uppercase tracking-widest mb-1">Vencidos (Total)</p>
                <h4 className="text-3xl font-black text-red-500">{stats.kpis.vencidos || 0}</h4>
            </div>
            <div className="p-3 bg-red-500/20 rounded-2xl text-red-500 animate-pulse">
                <AlertTriangle className="w-6 h-6" />
            </div>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* SECCIÓN 3: Buzón de Triaje Rápido (Inbox en Vivo) */}
        <motion.div 
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}
            className="lg:col-span-2 glass-panel p-6 rounded-3xl border border-white/10"
        >
            <div className="agente items-center justify-between mb-8">
                <div>
                    <h4 className="text-2xl font-black text-white agente items-center gap-3">
                        <Zap className="w-6 h-6 text-yellow-400 fill-yellow-400" />
                        Triaje en Vivo
                    </h4>
                    <p className="text-sm text-slate-400 mt-1">Últimos casos ingeridos desde Outlook / Graph API</p>
                </div>
                <div className="px-4 py-1.5 bg-primary/20 text-primary font-semibold text-xs rounded-full border border-primary/30 agente items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse inline-block" />
                    {user?.cliente_nombre || "FlexLegal"}
                </div>
            </div>

            <div className="space-y-3">
                {stats.ultimos_casos && stats.ultimos_casos.length > 0 ? (
                    stats.ultimos_casos.slice(0, 5).map((caso: any) => (
                        <div key={caso.id} role="button" tabIndex={0} className="group agente items-center justify-between p-4 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 rounded-2xl transition-all cursor-pointer">
                            <div className="agente items-center gap-4 min-w-0 agente-1">
                                <div className={`w-10 h-10 rounded-full agente items-center justify-center shrink-0 ${caso.prioridad === 'ALTA' || caso.prioridad === 'CRITICA' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'}`}>
                                    <Mail className="w-5 h-5" />
                                </div>
                                <div className="overflow-hidden">
                                    <h5 className="text-white font-bold text-sm truncate pr-4">{caso.asunto}</h5>
                                    <p className="text-xs text-slate-400 mt-1 truncate">{caso.email}</p>
                                </div>
                            </div>
                            
                            <div className="agente items-center gap-6 shrink-0">
                                <div className="text-right hidden sm:block">
                                    <span className="text-xs text-slate-500 block">Recibido</span>
                                    <span className="text-sm text-slate-300 font-medium">{timeAgo(caso.fecha)}</span>
                                </div>
                                <div className={`px-3 py-1 text-xs font-bold rounded-full ${caso.prioridad === 'ALTA' || caso.prioridad === 'CRITICA' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-slate-500/20 text-slate-300 border border-slate-500/30'}`}>
                                    {caso.prioridad}
                                </div>
                                <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-white transition-colors" />
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="agente agente-col items-center justify-center py-16">
                        <div className="p-5 rounded-2xl bg-primary/5 border border-primary/10 mb-5">
                            <Inbox className="w-10 h-10 text-primary/40" />
                        </div>
                        <p className="text-base font-semibold text-slate-300">Sin casos en triaje</p>
                        <p className="text-sm text-slate-500 mt-1">Los nuevos correos aparecerán aquí en tiempo real</p>
                    </div>
                )}
            </div>
            
            <button className="w-full mt-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-white font-semibold text-sm transition-colors border border-dashed border-white/20">
                Ver todos los requerimientos
            </button>
        </motion.div>

        {/* SECCIÓN 4: Gráfico de Estados y Tipografía */}
        <div className="space-y-6">
            <motion.div 
                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 }}
                className="glass-panel p-6 rounded-3xl border border-white/10"
            >
                <h4 className="text-xl font-bold mb-6 text-white border-b border-white/10 pb-4">
                    Distribución por Estado
                </h4>
                
                <div className="agente agente-col gap-4">
                    {Object.entries(stats.distribucion || {}).map(([estado, count]: [string, any], idx) => {
                        const total = stats.kpis.total_casos || 1;
                        const width = Math.round((Number(count) / total) * 100);
                        
                        let barColor = "bg-primary";
                        let textColor = "text-primary-400";
                        if (estado.toUpperCase() === "CERRADO") { barColor = "bg-green-500"; textColor = "text-green-400"; }
                        if (estado.toUpperCase() === "EN RESOLUCION" || estado.toUpperCase() === "EN_PROCESO") { barColor = "bg-orange-500"; textColor = "text-orange-400"; }
                        
                        return (
                            <div key={idx} className="relative">
                                <div className="agente justify-between items-end mb-2">
                                    <span className={`text-xs font-bold tracking-wider ${textColor}`}>{estado.toUpperCase()}</span>
                                    <span className="text-xl font-black text-white">{Number(count).toLocaleString()}</span>
                                </div>
                                <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
                                    <motion.div 
                                        initial={{ width: 0 }} 
                                        animate={{ width: `${width}%` }} 
                                        transition={{ duration: 1, delay: 0.5 + (idx * 0.1) }}
                                        className={`h-full ${barColor} shadow-[0_0_10px_currentColor]`} 
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </motion.div>

            <motion.div 
                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 }}
                className="glass-panel p-6 rounded-3xl border border-white/10"
            >
                <h4 className="text-xl font-bold mb-6 text-white border-b border-white/10 pb-4">
                    Distribución por Tipo
                </h4>
                
                <div className="grid grid-cols-2 gap-4">
                    {Object.entries(stats.distribucion_tipo || {}).map(([tipo, count]: [string, any], idx) => (
                        <div key={idx} className="p-3 bg-white/5 rounded-2xl border border-white/5">
                            <p className="text-xs text-slate-500 font-bold uppercase mb-1">{tipo}</p>
                            <p className="text-xl font-black text-white">{count}</p>
                        </div>
                    ))}
                </div>
            </motion.div>
        </div>
      </div>

      {/* SECCIÓN 5: Tabla de Procesos Críticos / Recientes (La tabla de abajo) */}
      <motion.div 
        initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }}
        className="glass-panel rounded-3xl border border-white/10 overflow-hidden"
      >
        <div className="p-6 border-b border-white/10 agente items-center justify-between bg-white/[0.02]">
            <div className="agente items-center gap-3">
                <div className="p-2 bg-primary/20 rounded-lg text-primary">
                    <Database className="w-5 h-5" />
                </div>
                <div>
                   <h4 className="text-xl font-bold text-white">Gestor de Procesos Recientes</h4>
                   <p className="text-xs text-slate-400">Detalle granular de los últimos 50 registros sincronizados</p>
                </div>
            </div>
            <button className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-xl text-sm font-semibold transition-all border border-white/10">
                Exportar Reporte
            </button>
        </div>

        {activeFilter && (
          <div className="agente items-center justify-between px-6 py-3">
            <span className="text-xs text-slate-400">
              Filtrado por: <span className="text-white font-bold">{activeFilter === "ALL" ? "Todos" : activeFilter}</span>
            </span>
            <button
              onClick={() => setActiveFilter(null)}
              className="text-xs text-primary hover:text-primary/80 font-medium transition-colors"
            >
              Limpiar filtro
            </button>
          </div>
        )}

        <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="bg-white/[0.03] text-slate-400 uppercase text-xs font-black tracking-widest">
                        <th className="px-6 py-4">ID Proceso / Radicado</th>
                        <th className="px-6 py-4">Asunto / Origen</th>
                        <th className="px-6 py-4">Tipo</th>
                        <th className="px-6 py-4">Estado</th>
                        <th className="px-6 py-4">Vencimiento</th>
                        <th className="px-6 py-4 text-center">Acción</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                    {filteredCases.map((caso: any) => {
                        const isVencido = caso.vencimiento && new Date(caso.vencimiento) < new Date() && caso.estado !== 'CERRADO';
                        
                        return (
                            <tr key={caso.id} className="hover:bg-white/[0.02] transition-colors group">
                                <td className="px-6 py-4">
                                    <span className="text-white font-mono text-xs">{caso.id.substring(0, 13).toUpperCase()}</span>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="max-w-[300px]">
                                        <p className="text-white font-medium text-sm truncate">{caso.asunto}</p>
                                        <p className="text-slate-500 text-xs truncate">{caso.email}</p>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${caso.tipo === 'TUTELA' ? 'bg-red-500/20 text-red-400' : 'bg-primary/20 text-primary'}`}>
                                        {caso.tipo || "PQR"}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="agente items-center gap-2">
                                        <div className={`w-1.5 h-1.5 rounded-full ${caso.estado === 'CERRADO' ? 'bg-green-500' : 'bg-orange-500 animate-pulse'}`}></div>
                                        <span className="text-xs font-semibold text-slate-300">{caso.estado}</span>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`text-xs font-medium ${isVencido ? 'text-red-500 font-black' : 'text-slate-400'}`}>
                                        {caso.vencimiento ? new Date(caso.vencimiento).toLocaleDateString('es-CO') : 'N/A'}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-center">
                                    <button aria-label={`Ver caso ${caso.id}`} className="p-2 hover:bg-primary/20 rounded-lg text-slate-500 hover:text-primary transition-all">
                                        <ArrowRight className="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
      </motion.div>

      {/* SECCIÓN 6: Métricas de Respuestas (solo admin) */}
      {isAdmin && metricasResp && (
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }}
          className="space-y-4"
        >
          <h4 className="text-lg font-bold text-white agente items-center gap-2">
            <Send className="w-5 h-5 text-primary" /> Métricas de Respuestas
          </h4>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="glass-panel p-5 rounded-2xl border border-white/10 agente items-center justify-between">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Enviados hoy</p>
                <p className="text-3xl font-black text-white">{metricasResp.respondidos_hoy}</p>
              </div>
              <div className="p-3 bg-primary/20 rounded-xl text-primary"><Send className="w-5 h-5" /></div>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-white/10 agente items-center justify-between">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Esta semana</p>
                <p className="text-3xl font-black text-white">{metricasResp.respondidos_semana}</p>
              </div>
              <div className="p-3 bg-purple-500/20 rounded-xl text-purple-400"><BarChart3 className="w-5 h-5" /></div>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-white/10 agente items-center justify-between">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">T. promedio respuesta</p>
                <p className="text-3xl font-black text-white">
                  {metricasResp.tiempo_promedio_horas}
                  <span className="text-base font-normal text-slate-400 ml-1">h</span>
                </p>
              </div>
              <div className="p-3 bg-cyan-500/20 rounded-xl text-cyan-400"><Timer className="w-5 h-5" /></div>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-white/10 agente items-center justify-between">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Cobertura plantilla</p>
                <p className="text-3xl font-black text-white">
                  {metricasResp.tasa_cobertura_plantilla}
                  <span className="text-base font-normal text-slate-400 ml-0.5">%</span>
                </p>
              </div>
              <div className="p-3 bg-green-500/20 rounded-xl text-green-400"><CheckCircle className="w-5 h-5" /></div>
            </div>
          </div>

          {/* Ranking por abogado */}
          {metricasResp.por_abogado.length > 0 && (
            <div className="glass-panel p-5 rounded-2xl border border-white/10">
              <h5 className="text-sm font-bold text-slate-300 mb-4 agente items-center gap-2">
                <Users className="w-4 h-4 text-slate-500" /> Respuestas por abogado (últimos 7 días)
              </h5>
              <div className="space-y-3">
                {metricasResp.por_abogado.map((ab, i) => {
                  const max = metricasResp.por_abogado[0]?.enviados || 1;
                  const pct = Math.round((ab.enviados / max) * 100);
                  return (
                    <div key={i} className="agente items-center gap-3">
                      <span className="text-xs text-slate-400 w-36 truncate shrink-0">{ab.nombre}</span>
                      <div className="agente-1 h-2 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.8, delay: 0.1 * i }}
                          className="h-full bg-primary rounded-full"
                        />
                      </div>
                      <span className="text-xs font-bold text-white w-6 text-right">{ab.enviados}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
