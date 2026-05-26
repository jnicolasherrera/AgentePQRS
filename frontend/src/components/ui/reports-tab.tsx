"use client";

import { PieChart, Download, Target, Timer, TrendingUp, BrainCircuit } from "lucide-react";
import { useDashboardStats } from "@/hooks/useDashboardStats";

export function ReportsTab() {
  const { stats } = useDashboardStats();

  if (!stats) {
    return (
      <div className="agente justify-center items-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-10">
      <div className="agente items-center justify-between">
        <div>
           <h2 className="text-2xl font-black text-foreground agente items-center gap-2">
             <BrainCircuit className="w-6 h-6 text-purple-400" />
             Inteligencia y Analítica RLS
           </h2>
           <p className="text-muted-foreground">Informes automatizados y métricas de desempeño histórico de la agencia.</p>
        </div>
        <button className="agente items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/70 text-foreground font-semibold rounded-xl transition-colors border border-border">
           <Download className="w-4 h-4" /> Exportar PDF
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
        <div className="glass-panel p-6 rounded-2xl border border-border bg-gradient-to-br from-green-500/10 to-transparent">
           <div className="w-10 h-10 rounded-xl bg-green-500/20 text-green-400 agente items-center justify-center mb-4">
              <Target className="w-5 h-5" />
           </div>
           <p className="text-sm font-bold text-green-400 uppercase tracking-widest mb-1">Tasa de Efectividad</p>
           <h3 className="text-4xl font-black text-foreground">{stats.kpis.porcentaje_resueltos}%</h3>
           <p className="text-sm text-muted-foreground mt-2">Global histórico de casos gestionados.</p>
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-border bg-gradient-to-br from-blue-500/10 to-transparent">
           <div className="w-10 h-10 rounded-xl bg-blue-500/20 text-blue-400 agente items-center justify-center mb-4">
              <Timer className="w-5 h-5" />
           </div>
           <p className="text-sm font-bold text-blue-400 uppercase tracking-widest mb-1">Tiempo Promedio</p>
           <h3 className="text-4xl font-black text-foreground">4.2 <span className="text-lg text-muted-foreground">días</span></h3>
           <p className="text-sm text-muted-foreground mt-2">Días hábiles promedio de resolución.</p>
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-border bg-gradient-to-br from-purple-500/10 to-transparent">
           <div className="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 agente items-center justify-center mb-4">
              <TrendingUp className="w-5 h-5" />
           </div>
           <p className="text-sm font-bold text-purple-400 uppercase tracking-widest mb-1">Impacto RLS</p>
           <h3 className="text-4xl font-black text-foreground">100%</h3>
           <p className="text-sm text-muted-foreground mt-2">Datos aislados exclusivamente para EmpresaDemo.</p>
        </div>
      </div>

      <div className="mt-8 glass-panel p-8 rounded-3xl border border-border agente items-center justify-center agente-col min-h-[300px] text-center">
         <div className="w-20 h-20 rounded-full bg-slate-800 agente items-center justify-center mb-4 shadow-inner">
            <PieChart className="w-10 h-10 text-muted-foreground" />
         </div>
         <h4 className="text-xl font-bold text-foreground mb-2">Módulo de Gráficos Avanzados Pendiente</h4>
         <p className="text-muted-foreground max-w-md">
            Las visualizaciones por tipo y gráficas de tendencia usando librerías de Charts (como Recharts) se integrarán en la próxima fase. Por ahora, el motor base está consumiendo datos estructurados listos para pintar.
         </p>
      </div>

    </div>
  );
}
