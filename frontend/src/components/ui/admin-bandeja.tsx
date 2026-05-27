"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, RefreshCw, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ChevronsUpDown, Trash2, CheckSquare, Square, XCircle, AlertTriangle, Scale, MessageCircle } from "lucide-react";
import { api } from "@/store/authStore";
import { CasoDetailOverlay } from "./caso-detail-overlay";
import { useTenantWorkflows } from "@/hooks/useTenantWorkflows";
import { WORKFLOW_FILTER_ITEMS, WORKFLOWS, workflowParam, type WorkflowFilter } from "@/lib/workflow-constants";
import { getProblematicaMeta } from "@/lib/problematica-constants";
import type { WorkflowType } from "@/types/api";

interface CasoAdmin {
  id: string;
  numero_radicado: string;
  asunto: string;
  email_origen: string;
  tipo_caso: string;
  /** Sprint FF bloque 7: discriminador PQRS vs ATENCION_CLIENTE */
  tipo_workflow?: WorkflowType;
  problematica_detectada?: string | null;
  estado: string;
  nivel_prioridad: string;
  fecha_recibido: string | null;
  fecha_vencimiento: string | null;
  es_pqrs: boolean;
  acuse_enviado: boolean;
  asignado_nombre: string | null;
  asignado_email: string | null;
}

interface BandejaResponse {
  items: CasoAdmin[];
  total: number;
  page: number;
  page_size: number;
}

const TIPOS = ["", "TUTELA", "PETICION", "QUEJA", "RECLAMO", "SOLICITUD"];
const ESTADOS = ["", "ABIERTO", "EN_PROCESO", "CERRADO"];

const PRIORIDAD_CLS: Record<string, string> = {
  CRITICA: "text-red-400 bg-red-500/10 border-red-500/30",
  ALTA: "text-orange-400 bg-orange-500/10 border-orange-500/30",
  MEDIA: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
  BAJA: "text-green-400 bg-green-500/10 border-green-500/30",
};
const ESTADO_CLS: Record<string, string> = {
  ABIERTO: "text-orange-400",
  EN_PROCESO: "text-blue-400",
  CERRADO: "text-green-400",
};
const TIPO_CLS: Record<string, string> = {
  TUTELA: "text-red-400 border-red-500/40",
  PETICION: "text-blue-400 border-blue-500/40",
  QUEJA: "text-yellow-400 border-yellow-500/40",
  RECLAMO: "text-orange-400 border-orange-500/40",
  SOLICITUD: "text-green-400 border-green-500/40",
};

const PAGE_SIZES = [20, 50] as const;

type BandejaSortKey = "radicado" | "asunto" | "tipo" | "estado" | "asignado" | "prioridad" | "recibido" | "vencimiento";

export function AdminBandeja({ selectedClienteId }: { selectedClienteId?: string }) {
  const { tieneAC } = useTenantWorkflows();
  const [items, setItems] = useState<CasoAdmin[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [tipo, setTipo] = useState("");
  const [estado, setEstado] = useState("");
  // Sprint FF bloque 7: filtro pill PQRS|AC|Ambos. Solo visible si tieneAC.
  // Default "PQRS" para FF (vista por defecto = lo legal), "all" para resto.
  const [workflowFilter, setWorkflowFilter] = useState<WorkflowFilter>("PQRS");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<BandejaSortKey>("recibido");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filtroNoPqrs, setFiltroNoPqrs] = useState(false);
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Cuando descubrimos que el tenant NO tiene AC, el filtro se neutraliza
  // (asumimos PQRS = todo). Cuando SÍ tiene, dejamos default PQRS.
  useEffect(() => {
    if (!tieneAC && workflowFilter !== "PQRS") setWorkflowFilter("PQRS");
  }, [tieneAC, workflowFilter]);

  const isModoAC     = workflowFilter === "ATENCION_CLIENTE";
  const isModoAmbos  = workflowFilter === "all" && tieneAC;

  const toggleSort = (key: BandejaSortKey) => {
    if (sortBy === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortBy(key); setSortDir("desc"); }
    setPage(1);
  };

  const SortIcon = ({ k }: { k: BandejaSortKey }) =>
    sortBy === k
      ? sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
      : <ChevronsUpDown className="w-3 h-3 opacity-30" />;

  const fetchCasos = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page), page_size: String(pageSize),
        sort_by: sortBy, sort_dir: sortDir,
      });
      if (q) params.append("q", q);
      if (tipo) params.append("tipo", tipo);
      if (estado) params.append("estado", estado);
      if (selectedClienteId) params.append("cliente_id", selectedClienteId);
      if (filtroNoPqrs) params.append("es_pqrs", "false");
      const wf = workflowParam(workflowFilter);
      if (wf) params.append("workflow", wf);
      const res = await api.get<BandejaResponse>(`/admin/casos?${params}`);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, q, tipo, estado, selectedClienteId, sortBy, sortDir, filtroNoPqrs, workflowFilter]);

  const handleStatusChange = useCallback((casoId: string, changes: Record<string, unknown>) => {
    setItems((prev) => prev.map((c) =>
      c.id === casoId ? { ...c, ...changes } as CasoAdmin : c
    ));
  }, []);

  useEffect(() => {
    const t = setTimeout(fetchCasos, 300);
    return () => clearTimeout(t);
  }, [fetchCasos]);

  // Clear selection when filter changes
  useEffect(() => {
    setSeleccionados(new Set());
  }, [filtroNoPqrs, page, q, tipo, estado, selectedClienteId, workflowFilter]);

  const totalPages = Math.ceil(total / pageSize);

  const toggleSeleccion = (id: string) => {
    setSeleccionados(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (seleccionados.size === items.length) {
      setSeleccionados(new Set());
    } else {
      setSeleccionados(new Set(items.map(c => c.id)));
    }
  };

  const handleDeleteLote = async () => {
    if (seleccionados.size === 0) return;
    setDeleting(true);
    try {
      const endpoint = filtroNoPqrs ? "/admin/casos/no-pqrs/lote" : "/admin/casos/lote";
      await api.delete(endpoint, {
        data: { caso_ids: Array.from(seleccionados) },
      });
      setItems(prev => prev.filter(c => !seleccionados.has(c.id)));
      setTotal(prev => prev - seleccionados.size);
      setSeleccionados(new Set());
      setShowDeleteModal(false);
    } catch (e) {
      console.error(e);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Sprint FF bloque 7: pill PQRS|AC|Ambos. Solo visible si el tenant
          tiene buzones ATENCION_CLIENTE activos. Recovery/Demo no lo ven. */}
      {tieneAC && (
        <div className="agente items-center gap-2">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mr-2">Vista:</span>
          <div className="agente items-center gap-1 bg-muted rounded-xl p-1 border border-border">
            {WORKFLOW_FILTER_ITEMS.map(it => (
              <button
                key={it.key}
                onClick={() => { setWorkflowFilter(it.key); setPage(1); }}
                className={`agente items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  workflowFilter === it.key
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {it.key === "PQRS" && <Scale className="w-3 h-3" />}
                {it.key === "ATENCION_CLIENTE" && <MessageCircle className="w-3 h-3" />}
                {it.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Barra de filtros */}
      <div className="agente items-center gap-3 agente-wrap">
        <div className="relative agente-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            placeholder="Buscar por asunto o email..."
            value={q}
            onChange={e => { setQ(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 bg-muted border border-border rounded-xl text-sm text-foreground focus:outline-none focus:border-primary placeholder:text-muted-foreground transition-colors"
          />
        </div>
        {/* Filtro Tipo: no aplica en modo AC (los AC tienen tipo_caso=NULL). */}
        {!isModoAC && (
          <select value={tipo} onChange={e => { setTipo(e.target.value); setPage(1); }}
            className="bg-muted border border-border rounded-xl px-3 py-2 text-sm text-foreground outline-none focus:border-primary cursor-pointer">
            {TIPOS.map(t => <option key={t} value={t}>{t || "Todos los tipos"}</option>)}
          </select>
        )}
        <select value={estado} onChange={e => { setEstado(e.target.value); setPage(1); }}
          className="bg-muted border border-border rounded-xl px-3 py-2 text-sm text-foreground outline-none focus:border-primary cursor-pointer">
          {ESTADOS.map(s => <option key={s} value={s}>{s || "Todos los estados"}</option>)}
        </select>
        {/* Filtro "No PQRS": ya no expone el botón en modo AC (no es válido el cruce). */}
        {!isModoAC && (
          <button
            onClick={() => { setFiltroNoPqrs(f => !f); setPage(1); }}
            className={`agente items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-bold transition-all ${
              filtroNoPqrs
                ? "bg-red-500/20 border border-red-500/40 text-red-400 shadow-[0_0_10px_rgba(239,68,68,0.2)]"
                : "bg-muted border border-border text-muted-foreground hover:bg-secondary"
            }`}
          >
            <XCircle className="w-3.5 h-3.5" />
            No PQRS
          </button>
        )}
        <button onClick={fetchCasos}
          className="p-2 bg-muted border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
        <span className="text-xs text-muted-foreground ml-auto">{total} casos</span>
      </div>

      {/* Action bar when items selected */}
      <AnimatePresence>
        {seleccionados.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="agente items-center justify-between px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl"
          >
            <span className="text-sm text-red-400 font-bold">
              {seleccionados.size} caso{seleccionados.size > 1 ? "s" : ""} seleccionado{seleccionados.size > 1 ? "s" : ""}
            </span>
            <button
              onClick={() => setShowDeleteModal(true)}
              className="agente items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-bold rounded-xl transition-all"
            >
              <Trash2 className="w-4 h-4" />
              Eliminar seleccionados
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Tabla */}
      <div className="glass-panel rounded-2xl overflow-hidden">
        {loading ? (
          <div className="agente items-center justify-center py-20">
            <div className="w-8 h-8 rounded-full border-t-2 border-primary animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground text-sm">No se encontraron casos.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-muted text-muted-foreground text-[10px] font-black uppercase tracking-widest border-b border-border">
                  <th className="px-3 py-3 w-10">
                    <button onClick={toggleSelectAll} className="text-muted-foreground hover:text-foreground transition-colors">
                      {seleccionados.size === items.length && items.length > 0
                        ? <CheckSquare className="w-4 h-4 text-red-400" />
                        : <Square className="w-4 h-4" />
                      }
                    </button>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("radicado")}>
                    <span className="agente items-center gap-1">Radicado <SortIcon k="radicado" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("asunto")}>
                    <span className="agente items-center gap-1">Asunto <SortIcon k="asunto" /></span>
                  </th>
                  {/* Modo Ambos: chip workflow para distinguir PQRS de AC. */}
                  {isModoAmbos && (
                    <th className="px-4 py-3 text-muted-foreground">Workflow</th>
                  )}
                  {/* Modo AC: "Problemática" reemplaza Tipo. Resto: Tipo. */}
                  {isModoAC ? (
                    <th className="px-4 py-3 text-muted-foreground">Problemática</th>
                  ) : (
                    <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("tipo")}>
                      <span className="agente items-center gap-1">Tipo <SortIcon k="tipo" /></span>
                    </th>
                  )}
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("estado")}>
                    <span className="agente items-center gap-1">Estado <SortIcon k="estado" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("asignado")}>
                    <span className="agente items-center gap-1">Asignado a <SortIcon k="asignado" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("prioridad")}>
                    <span className="agente items-center gap-1">Prioridad <SortIcon k="prioridad" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("recibido")}>
                    <span className="agente items-center gap-1">Recibido <SortIcon k="recibido" /></span>
                  </th>
                  {/* Vencimiento: oculto en AC (sin SLA legal). */}
                  {!isModoAC && (
                    <th className="px-4 py-3 cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => toggleSort("vencimiento")}>
                      <span className="agente items-center gap-1">Vencimiento <SortIcon k="vencimiento" /></span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((caso, i) => (
                  <motion.tr key={caso.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.015 }}
                    onClick={() => setSelectedId(caso.id)}
                    className={`cursor-pointer hover:bg-muted transition-colors ${!caso.es_pqrs ? "border-l-2 border-l-red-500/50" : ""} ${seleccionados.has(caso.id) ? "bg-red-500/5" : ""}`}
                  >
                    <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                      <button onClick={() => toggleSeleccion(caso.id)} className="text-muted-foreground hover:text-foreground transition-colors">
                        {seleccionados.has(caso.id)
                          ? <CheckSquare className="w-4 h-4 text-red-400" />
                          : <Square className="w-4 h-4" />
                        }
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-primary/80">
                        {caso.numero_radicado || caso.id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="px-4 py-3 max-w-[220px]">
                      <p className="text-foreground font-medium truncate">{caso.asunto}</p>
                      <p className="text-muted-foreground text-[10px] truncate">{caso.email_origen}</p>
                      {!caso.es_pqrs && (
                        <span className="inline-block mt-0.5 text-[9px] px-1.5 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded">
                          No PQRS
                        </span>
                      )}
                    </td>
                    {/* Modo Ambos: chip workflow (⚖️/💬) */}
                    {isModoAmbos && (() => {
                      const wfKey = caso.tipo_workflow ?? "PQRS";
                      const wf = WORKFLOWS[wfKey];
                      return (
                        <td className="px-4 py-3">
                          <span className={`agente items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg border ${wf.badgeTw}`}>
                            {wf.icon === "scale" ? <Scale className="w-3 h-3" /> : <MessageCircle className="w-3 h-3" />}
                            {wf.shortLabel}
                          </span>
                        </td>
                      );
                    })()}
                    {/* Modo AC: Problemática reemplaza Tipo. */}
                    {isModoAC ? (
                      <td className="px-4 py-3 max-w-[180px]">
                        {(() => {
                          const meta = getProblematicaMeta(caso.problematica_detectada);
                          return (
                            <span
                              className={`inline-block text-[10px] font-bold px-2 py-1 rounded-lg border truncate max-w-full ${meta.badgeTw}`}
                              title={caso.problematica_detectada || "Sin clasificar"}
                            >
                              {meta.label}
                            </span>
                          );
                        })()}
                      </td>
                    ) : (
                      <td className="px-4 py-3">
                        <span className={`text-[10px] font-bold px-2 py-1 rounded-lg border bg-transparent ${TIPO_CLS[caso.tipo_caso] ?? "text-muted-foreground border-border"}`}>
                          {caso.tipo_caso || "—"}
                        </span>
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <span className={`text-xs font-bold ${ESTADO_CLS[caso.estado] ?? "text-muted-foreground"}`}>
                        {caso.estado}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {caso.asignado_nombre ? (
                        <div>
                          <p className="text-foreground text-xs font-medium">{caso.asignado_nombre}</p>
                          <p className="text-muted-foreground text-[10px]">{caso.asignado_email}</p>
                        </div>
                      ) : (
                        <span className="text-muted-foreground/70 text-xs italic">Sin asignar</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${PRIORIDAD_CLS[caso.nivel_prioridad] ?? "text-muted-foreground border-border"}`}>
                        {caso.nivel_prioridad}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {caso.fecha_recibido ? new Date(caso.fecha_recibido).toLocaleDateString() : "\u2014"}
                    </td>
                    {/* Vencimiento: oculta en modo AC (sin SLA legal). */}
                    {!isModoAC && (
                      <td className="px-4 py-3">
                        {caso.fecha_vencimiento ? (
                          <span className={`text-xs font-bold ${new Date(caso.fecha_vencimiento) < new Date() ? "text-red-400" : "text-muted-foreground"}`}>
                            {new Date(caso.fecha_vencimiento).toLocaleDateString()}
                          </span>
                        ) : (
                          <span className="text-muted-foreground/70 text-xs">{"\u2014"}</span>
                        )}
                      </td>
                    )}
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="agente items-center justify-between px-5 py-3 border-t border-border">
          <div className="agente items-center gap-2">
            <span className="text-[10px] text-muted-foreground/70 uppercase tracking-wider font-semibold">Mostrar:</span>
            {PAGE_SIZES.map(s => (
              <button
                key={s}
                onClick={() => { setPageSize(s); setPage(1); }}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                  pageSize === s ? "bg-primary/20 text-primary border border-primary/30" : "bg-muted text-muted-foreground hover:text-foreground border border-border"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="agente items-center gap-3">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              className="p-2 rounded-lg bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-muted-foreground">Pagina {page} de {totalPages || 1}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              className="p-2 rounded-lg bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <CasoDetailOverlay casoId={selectedId} onClose={() => setSelectedId(null)} onStatusChange={handleStatusChange} />

      {/* Delete confirmation modal */}
      <AnimatePresence>
        {showDeleteModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 agente items-center justify-center"
            style={{ background: "rgba(0, 0, 0, 0.8)" }}
            onClick={() => !deleting && setShowDeleteModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={e => e.stopPropagation()}
              className="bg-card border border-red-500/30 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl"
            >
              <div className="agente items-center gap-3 mb-4">
                <div className="p-2 bg-red-500/10 rounded-xl">
                  <AlertTriangle className="w-6 h-6 text-red-400" />
                </div>
                <h3 className="text-lg font-bold text-foreground">Confirmar eliminacion</h3>
              </div>
              <p className="text-sm text-foreground/80 mb-6">
                Se eliminar{seleccionados.size > 1 ? "an" : "a"}{" "}
                <strong className="text-red-400">{seleccionados.size} caso{seleccionados.size > 1 ? "s" : ""}</strong>.
                Esta accion no se puede deshacer.
              </p>
              <div className="agente gap-3 justify-end">
                <button
                  onClick={() => setShowDeleteModal(false)}
                  disabled={deleting}
                  className="px-4 py-2 bg-muted border border-border text-foreground/80 text-sm font-bold rounded-xl hover:bg-secondary transition-all disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleDeleteLote}
                  disabled={deleting}
                  className="agente items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-bold rounded-xl transition-all disabled:opacity-50"
                >
                  {deleting
                    ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    : <Trash2 className="w-4 h-4" />
                  }
                  {deleting ? "Eliminando..." : "Eliminar"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
