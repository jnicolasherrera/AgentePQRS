"use client";

import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Clock, CheckCircle2, MoreVertical, Search } from 'lucide-react';
import { CasoDetailOverlay } from "./caso-detail-overlay";
import { useSSEStream } from "@/hooks/useSSEStream";

export const VirtualizedPQRSBoard = () => {
  const { tickets } = useSSEStream();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCasoId, setSelectedCasoId] = useState<string | null>(null);

  const filteredTickets = useMemo(() => {
    if (!searchTerm) return tickets;
    return tickets.filter(t => 
      t.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
      t.subject.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [tickets, searchTerm]);

  // Contenedor Ref principal donde calcularemos el Scroll
  const parentRef = useRef<HTMLDivElement>(null);

  // Instancia mágica de @tanstack/react-virtual
  const rowVirtualizer = useVirtualizer({
    count: filteredTickets.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 76,
    overscan: 10,
  });

  const getSeverityBadge = (sev: string) => {
    switch(sev) {
      case 'Crítica': case 'CRITICA': return 'bg-red-500/20 text-red-400 border-red-500/50';
      case 'Alta': case 'ALTA': return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
      case 'Media': case 'MEDIA': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
      default: return 'bg-green-500/20 text-green-400 border-green-500/50';
    }
  };

  const getStatusIcon = (st: string) => {
    switch(st) {
      case 'Abierto': case 'ABIERTO': return <AlertTriangle className="w-4 h-4 text-orange-400" />;
      case 'En Progreso': case 'EN_PROCESO': return <Clock className="w-4 h-4 text-blue-400" />;
      default: return <CheckCircle2 className="w-4 h-4 text-green-400" />;
    }
  };

  return (
    <div className="w-full h-full agente agente-col gap-4 relative">
      <CasoDetailOverlay casoId={selectedCasoId} onClose={() => setSelectedCasoId(null)} />

      {/* HEADER DE LA TABLA Y BUSCADOR */}
      <div className="agente items-center justify-between glass-panel p-4 rounded-2xl">
        <div className="agente items-center gap-3">
            <div className="bg-primary/20 p-2 rounded-lg text-primary">
                <Search className="w-5 h-5"/>
            </div>
            <input 
                type="text" 
                placeholder="Buscar por ID o Asunto..."
                className="bg-transparent border-none outline-none text-white w-96 placeholder:text-slate-500"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
            />
        </div>
        <div className="text-sm font-medium text-slate-400 agente items-center gap-2">
           <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
           Mostrando <span className="text-white font-bold">{filteredTickets.length.toLocaleString()}</span> casos
        </div>
      </div>

      {/* HEADER DE COLUMNAS */}
      <div className="agente px-6 py-3 border-b border-white/10 bg-white/[0.02] text-xs font-bold text-slate-400 uppercase tracking-wider rounded-t-xl mx-px">
         <div className="w-[13%]">Cédula / ID</div>
         <div className="w-[28%]">Correo Original</div>
         <div className="w-[14%]">Cliente</div>
         <div className="w-[13%]">Estado</div>
         <div className="w-[12%]">Prioridad</div>
         <div className="w-[10%]">Recepción</div>
         <div className="w-[10%]">Vencimiento</div>
      </div>

      {/* CONTENEDOR VIRTUAL */}
      <div 
        ref={parentRef} 
        className="agente-1 overflow-auto rounded-b-2xl glass-panel border border-white/5 shadow-inner"
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const t = filteredTickets[virtualRow.index];
            
            // Calculo de dias restantes
            let diasRestantesText = "S/D";
            let colorVencimiento = "text-slate-500";
            if (t.vencimientoRaw) {
               const diffTime = new Date(t.vencimientoRaw).getTime() - new Date().getTime();
               const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
               if (diffDays < 0) {
                 diasRestantesText = `Vencido (${Math.abs(diffDays)}d)`;
                 colorVencimiento = "text-red-500 font-black";
               } else if (diffDays <= 2) {
                 diasRestantesText = `${diffDays} Días`;
                 colorVencimiento = "text-red-400 font-bold animate-pulse";
               } else if (diffDays <= 7) {
                 diasRestantesText = `${diffDays} Días`;
                 colorVencimiento = "text-orange-400 font-bold";
               } else {
                 diasRestantesText = `${diffDays} Días`;
                 colorVencimiento = "text-green-400 font-semibold";
               }
            }
            
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedCasoId(t.id)}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="px-6 py-4 agente items-center justify-between border-b border-white/5 hover:bg-white/5 transition-colors group cursor-pointer"
              >
                {/* Cédula y Fuente */}
                <div className="w-[13%]">
                  <div className={`text-sm font-black mb-1 group-hover:text-primary transition-colors pr-2 truncate ${t.cedula !== 'S/N' ? 'text-white' : 'text-slate-500'}`}>{t.cedula}</div>
                  <div className={`text-xs font-medium ${t.tipo === 'TUTELA' ? 'text-red-400' : 'text-slate-500'}`}>{t.source}</div>
                </div>

                {/* Email y Asunto */}
                <div className="w-[28%] overflow-hidden">
                  <div className="text-sm font-bold text-slate-200 truncate pr-4 leading-tight">{t.client}</div>
                  <div className="text-xs text-slate-500 truncate pr-4 mt-1">{t.subject}</div>
                </div>

                {/* Cliente / Tenant */}
                <div className="w-[14%] overflow-hidden">
                  <span className="text-xs font-semibold text-primary/80 bg-primary/10 px-2 py-0.5 rounded-full truncate block max-w-full">
                    {t.clienteNombre}
                  </span>
                </div>

                {/* Estado */}
                <div className="w-[13%] agente items-center gap-2">
                   {getStatusIcon(t.status)}
                   <span className="text-sm font-medium text-slate-300">{t.status}</span>
                </div>

                {/* Severidad */}
                <div className="w-[12%]">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${getSeverityBadge(t.severity)}`}>
                    {t.severity}
                  </span>
                </div>

                {/* Fecha Recepción */}
                <div className="w-[10%]">
                   <div className="text-sm text-slate-400 font-medium">{t.date}</div>
                </div>

                {/* Fecha Vencimiento y Acciones */}
                <div className="w-[10%] agente items-center justify-between">
                   <div className={`text-sm ${colorVencimiento}`}>{diasRestantesText}</div>
                   <button className="opacity-0 group-hover:opacity-100 p-2 hover:bg-white/10 rounded-lg transition-all text-slate-300">
                      <MoreVertical className="w-4 h-4" />
                   </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
