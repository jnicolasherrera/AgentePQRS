"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Wifi, WifiOff, ArrowRight, AlertTriangle, Send, CheckSquare, Square, Search, ChevronLeft, ChevronRight, ArrowUpDown } from "lucide-react";
import type { TicketBoard } from "@/hooks/useSSEStream";
import { api } from "@/store/authStore";
import { CasoDetailOverlay } from "./caso-detail-overlay";
import { BorradorDrawer } from "./borrador-drawer";
import { FirmaModal } from "./firma-modal";

const PRIORIDAD: Record<string, { border: string; dot: string; badge: string; text: string }> = {
  CRITICA:  { border: "border-l-red-500",    dot: "bg-red-500 animate-pulse", badge: "bg-red-500/15 border-red-500/30 text-red-400",    text: "text-red-400" },
  ALTA:     { border: "border-l-orange-500", dot: "bg-orange-500",             badge: "bg-orange-500/15 border-orange-500/30 text-orange-400", text: "text-orange-400" },
  MEDIA:    { border: "border-l-yellow-500", dot: "bg-yellow-500",             badge: "bg-yellow-500/15 border-yellow-500/30 text-yellow-400", text: "text-yellow-400" },
  BAJA:     { border: "border-l-green-500",  dot: "bg-green-500",              badge: "bg-green-500/15 border-green-500/30 text-green-400",   text: "text-green-400" },
};

const TIPO_COLOR: Record<string, string> = {
  TUTELA: "text-red-400", PETICION: "text-blue-400", QUEJA: "text-orange-400",
  RECLAMO: "text-yellow-400", SOLICITUD: "text-emerald-400",
};

const PRIO_ORDER: Record<string, number> = { CRITICA: 0, ALTA: 1, MEDIA: 2, BAJA: 3 };
const PAGE_SIZES = [20, 50] as const;

interface CasoPendiente {
  id: string;
  email_origen: string;
  asunto: string;
  tipo: string;
  prioridad: string;
  fecha: string;
  borrador_respuesta: string;
  problematica: string;
}

interface LiveFeedProps {
  tickets: TicketBoard[];
  connected: boolean;
  maxItems?: number;
  onCasoStatusChange?: (casoId: string, changes: Record<string, unknown>) => void;
  enableResponse?: boolean;
  selectedClienteId?: string;
}

type CasoSortKey = "recent" | "tipo" | "severity" | "status";

export function LiveFeed({ tickets, connected, maxItems, onCasoStatusChange, enableResponse, selectedClienteId }: LiveFeedProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerCaso, setDrawerCaso] = useState<CasoPendiente | null>(null);
  const [pendientes, setPendientes] = useState<CasoPendiente[]>([]);
  const [firmaOpen, setFirmaOpen] = useState(false);
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [filtro, setFiltro] = useState<"todos" | "pendientes" | "vencidos">("todos");
  const [estadoFiltro, setEstadoFiltro] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortKey, setSortKey] = useState<CasoSortKey>("recent");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [pageSize, setPageSize] = useState<number>(20);
  const [currentPage, setCurrentPage] = useState(1);
  const recent = maxItems ? tickets.slice(0, maxItems) : tickets;

  const fetchPendientes = useCallback(() => {
    if (!enableResponse) return;
    api.get<CasoPendiente[]>("/casos/borrador/pendientes")
      .then(r => setPendientes(r.data))
      .catch(console.error);
  }, [enableResponse]);

  useEffect(() => {
    fetchPendientes();
    if (!enableResponse) return;
    const iv = setInterval(fetchPendientes, 15_000);
    return () => clearInterval(iv);
  }, [fetchPendientes, enableResponse]);

  useEffect(() => { setCurrentPage(1); }, [filtro, estadoFiltro, searchQuery, selectedClienteId, sortKey, sortDir, pageSize]);

  const getPendiente = (ticketId: string) => pendientes.find(p => p.id === ticketId);

  const toggleSeleccion = (id: string) => {
    setSeleccionados(prev => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); return next; }
      if (next.size >= 10) return prev;
      next.add(id);
      return next;
    });
  };

  const filteredItems = useMemo(() => {
    let items: TicketBoard[];

    if (filtro === "pendientes") {
      items = pendientes.map(p => ({
        id: p.id,
        cedula: "",
        tipo: p.tipo,
        subject: p.asunto,
        client: p.email_origen,
        clienteId: "",
        clienteNombre: "",
        severity: p.prioridad,
        status: "ABIERTO",
        source: "PQR",
        date: p.fecha ? new Date(p.fecha).toLocaleDateString() : "",
        vencimientoRaw: null,
      }));
    } else if (filtro === "vencidos") {
      items = recent.filter(t => t.vencimientoRaw && new Date(t.vencimientoRaw) < new Date());
    } else {
      items = recent;
    }

    if (selectedClienteId) {
      items = items.filter(t => t.clienteId === selectedClienteId);
    }

    if (estadoFiltro) {
      items = items.filter(t => t.status === estadoFiltro);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      items = items.filter(t =>
        t.subject.toLowerCase().includes(q) ||
        t.client.toLowerCase().includes(q) ||
        t.clienteNombre.toLowerCase().includes(q)
      );
    }

    return items;
  }, [filtro, estadoFiltro, searchQuery, recent, pendientes, selectedClienteId]);

  const { paginatedItems, totalPages } = useMemo(() => {
    let sorted: TicketBoard[];
    if (sortKey === "recent") {
      sorted = filteredItems;
    } else {
      sorted = [...filteredItems].sort((a, b) => {
        let cmp = 0;
        switch (sortKey) {
          case "tipo": cmp = (a.tipo || "").localeCompare(b.tipo || ""); break;
          case "severity": cmp = (PRIO_ORDER[a.severity] ?? 9) - (PRIO_ORDER[b.severity] ?? 9); break;
          case "status": cmp = (a.status || "").localeCompare(b.status || ""); break;
        }
        return sortDir === "asc" ? cmp : -cmp;
      });
    }
    const total = Math.ceil(sorted.length / pageSize);
    const start = (currentPage - 1) * pageSize;
    return { paginatedItems: sorted.slice(start, start + pageSize), totalPages: total };
  }, [filteredItems, sortKey, sortDir, pageSize, currentPage]);

  return (
    <div className="w-full agente agente-col gap-5">
      <CasoDetailOverlay casoId={selectedId} onClose={() => setSelectedId(null)} onStatusChange={onCasoStatusChange} />

      {/* Status bar */}
      <div className="agente items-center justify-between">
        <div className="agente items-center gap-3">
          <span className={`agente items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium ${connected ? "text-green-400 bg-green-500/10 border-green-500/20" : "text-slate-500 bg-white/5 border-white/10"}`}>
            {connected
              ? <><Wifi className="w-3 h-3" /> En vivo</>
              : <><WifiOff className="w-3 h-3" /> Sin señal</>}
          </span>
          <span className="text-xs text-slate-600">
            mostrando <span className="text-slate-400 font-semibold">{paginatedItems.length}</span> de <span className="text-slate-400 font-semibold">{filteredItems.length}</span> registros
          </span>
        </div>
        {maxItems && tickets.length > maxItems && (
          <span className="text-xs text-slate-600">+{tickets.length - maxItems} mas en cola</span>
        )}
      </div>

      {enableResponse && (
        <div className="space-y-3">
          {/* Level 1: Main view pills */}
          <div className="agente items-center gap-2">
            {([
              { key: "todos", label: "Todos", count: recent.length },
              { key: "pendientes", label: "Por Responder", count: pendientes.length },
              { key: "vencidos", label: "Vencidos", count: recent.filter(t => t.vencimientoRaw && new Date(t.vencimientoRaw) < new Date()).length },
            ] as const).map(f => (
              <button
                key={f.key}
                onClick={() => { setFiltro(f.key); setEstadoFiltro(null); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  filtro === f.key
                    ? "bg-primary text-white shadow-[0_0_10px_rgba(13,89,242,0.4)]"
                    : "bg-white/5 text-slate-400 hover:bg-white/10 border border-white/10"
                }`}
              >
                {f.label}
                <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] ${
                  filtro === f.key ? "bg-white/20" : "bg-white/10"
                }`}>
                  {f.count}
                </span>
              </button>
            ))}
          </div>

          {/* Level 2: Status sub-filter */}
          <div className="agente items-center gap-2">
            <span className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">Estado:</span>
            {[null, "ABIERTO", "EN_PROCESO", "CERRADO", "CONTESTADO"].map(est => (
              <button
                key={est ?? "all"}
                onClick={() => setEstadoFiltro(est)}
                className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                  estadoFiltro === est
                    ? "bg-white/15 text-white border border-white/20"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {est ?? "Todos"}
              </button>
            ))}
          </div>

          {/* Search + Sort + Page size */}
          <div className="agente items-center gap-3">
            <div className="relative agente-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por asunto o remitente..."
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-slate-600 outline-none focus:border-primary/50 transition-colors"
              />
            </div>
            <div className="agente items-center gap-1.5 shrink-0">
              <ArrowUpDown className="w-3.5 h-3.5 text-slate-500" />
              {([
                { key: "recent" as const, label: "Recientes" },
                { key: "tipo" as const, label: "Tipo" },
                { key: "severity" as const, label: "Prioridad" },
                { key: "status" as const, label: "Estado" },
              ]).map(s => (
                <button
                  key={s.key}
                  onClick={() => {
                    if (sortKey === s.key && s.key !== "recent") setSortDir(d => d === "asc" ? "desc" : "asc");
                    else { setSortKey(s.key); setSortDir("desc"); }
                  }}
                  className={`px-2 py-1 rounded text-[11px] font-bold transition-all ${
                    sortKey === s.key
                      ? "bg-primary/20 text-primary border border-primary/30"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {s.label}
                  {sortKey === s.key && s.key !== "recent" && (sortDir === "asc" ? " \u2191" : " \u2193")}
                </button>
              ))}
            </div>
            <div className="agente items-center gap-1.5 shrink-0">
              <span className="text-[10px] text-slate-600 font-semibold">Mostrar:</span>
              {PAGE_SIZES.map(s => (
                <button
                  key={s}
                  onClick={() => setPageSize(s)}
                  className={`px-2 py-1 rounded text-[11px] font-bold transition-all ${
                    pageSize === s ? "bg-primary/20 text-primary border border-primary/30" : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {enableResponse && seleccionados.size > 0 && (
        <div className="agente items-center justify-between">
          <span className="text-xs text-slate-500">Seleccionados: {seleccionados.size} / 10 max</span>
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={() => setFirmaOpen(true)}
            className="agente items-center gap-2 px-4 py-2 bg-primary rounded-lg font-bold text-sm hover:bg-primary/80 transition-colors"
          >
            <Send className="w-4 h-4" />
            Firmar y Enviar ({seleccionados.size})
          </motion.button>
        </div>
      )}

      {paginatedItems.length === 0 ? (
        <div className="agente agente-col items-center justify-center py-20 gap-4">
          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/5">
            <Mail className="w-10 h-10 text-slate-600" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-400">Sin correos recientes</p>
            <p className="text-xs text-slate-600 mt-1">Los nuevos PQRS apareceran aqui en tiempo real</p>
          </div>
        </div>
      ) : (
        <div className="agente agente-col gap-3">
          <AnimatePresence initial={false}>
            {paginatedItems.map((t, i) => {
              const p = PRIORIDAD[t.severity] ?? PRIORIDAD.MEDIA;
              const isNew = i === 0 && currentPage === 1;
              return (
                <motion.div
                  key={t.id}
                  layout
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2, delay: i * 0.04 }}
                  onClick={() => setSelectedId(t.id)}
                  role="button"
                  tabIndex={0}
                  className={`group w-full text-left border-l-2 ${p.border} bg-white/[0.03] hover:bg-white/[0.06] border border-white/8 hover:border-white/15 rounded-2xl px-5 py-4 agente items-center gap-4 transition-all cursor-pointer`}
                >
                  {/* Indicator */}
                  <div className="agente agente-col items-center gap-1 shrink-0">
                    <div className={`w-2 h-2 rounded-full ${p.dot}`} />
                    {isNew && (
                      <span className="text-[9px] font-bold text-primary uppercase tracking-wider">nuevo</span>
                    )}
                  </div>

                  {/* Content */}
                  <div className="agente-1 min-w-0 space-y-0.5">
                    <div className="agente items-center gap-2">
                      <span className={`text-xs font-bold ${TIPO_COLOR[t.tipo] ?? "text-slate-400"}`}>{t.tipo}</span>
                      {t.tipo === "TUTELA" && t.severity === "CRITICA" && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-600 text-white animate-pulse">
                          URGENTE
                        </span>
                      )}
                      <span className="text-slate-700">{"\u00b7"}</span>
                      <span className="text-xs text-slate-500 truncate">{t.client}</span>
                    </div>
                    <p className="text-sm font-medium text-white truncate">{t.subject}</p>
                  </div>

                  {/* Meta */}
                  <div className="agente items-center gap-3 shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-bold ${p.badge}`}>
                      {t.severity}
                    </span>
                    <span className="text-xs text-slate-500 font-medium min-w-[60px] text-right">{t.date}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-700 group-hover:text-slate-400 transition-colors" />
                  </div>

                  {enableResponse && getPendiente(t.id) && (
                    <div className="agente items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => toggleSeleccion(t.id)}
                        className="p-1 text-slate-500 hover:text-white transition-colors"
                      >
                        {seleccionados.has(t.id)
                          ? <CheckSquare className="w-4 h-4 text-primary" />
                          : <Square className="w-4 h-4" />
                        }
                      </button>
                      <button
                        onClick={() => setDrawerCaso(getPendiente(t.id)!)}
                        className="agente items-center gap-1.5 px-3 py-1.5 bg-primary/10 border border-primary/30 text-primary text-xs font-bold rounded-lg hover:bg-primary/20 transition-all"
                      >
                        <Send className="w-3 h-3" />
                        Responder
                      </button>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="agente items-center justify-center gap-3 py-2">
          <button disabled={currentPage <= 1} onClick={() => setCurrentPage(p => p - 1)}
            className="p-2 rounded-lg bg-white/5 text-slate-400 hover:text-white disabled:opacity-30 transition-colors">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs text-slate-500">Pagina {currentPage} de {totalPages}</span>
          <button disabled={currentPage >= totalPages} onClick={() => setCurrentPage(p => p + 1)}
            className="p-2 rounded-lg bg-white/5 text-slate-400 hover:text-white disabled:opacity-30 transition-colors">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Vencimientos criticos */}
      {filteredItems.some(t => t.vencimientoRaw && new Date(t.vencimientoRaw) < new Date()) && (
        <div className="agente items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Hay casos con <strong>fecha de vencimiento pasada</strong> — requieren atencion inmediata</span>
        </div>
      )}

      {drawerCaso && (
        <BorradorDrawer
          caso={drawerCaso}
          onClose={() => setDrawerCaso(null)}
          onActualizado={(id, texto) => {
            setPendientes(prev => prev.map(c => c.id === id ? { ...c, borrador_respuesta: texto } : c));
          }}
          onRechazado={(id) => {
            setPendientes(prev => prev.filter(c => c.id !== id));
            setDrawerCaso(null);
          }}
        />
      )}

      {firmaOpen && (
        <FirmaModal
          casoIds={Array.from(seleccionados)}
          totalCasos={seleccionados.size}
          onClose={() => setFirmaOpen(false)}
          onEnviado={(ids) => {
            setPendientes(prev => prev.filter(c => !ids.includes(c.id)));
            setSeleccionados(new Set());
            fetchPendientes();
          }}
        />
      )}
    </div>
  );
}
