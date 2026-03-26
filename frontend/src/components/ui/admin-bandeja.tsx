"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Search, RefreshCw, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { api } from "@/store/authStore";
import { CasoDetailOverlay } from "./caso-detail-overlay";

interface CasoAdmin {
  id: string;
  numero_radicado: string;
  asunto: string;
  email_origen: string;
  tipo_caso: string;
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
  const [items, setItems] = useState<CasoAdmin[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [tipo, setTipo] = useState("");
  const [estado, setEstado] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<BandejaSortKey>("recibido");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

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
      const res = await api.get<BandejaResponse>(`/admin/casos?${params}`);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, q, tipo, estado, selectedClienteId, sortBy, sortDir]);

  const handleStatusChange = useCallback((casoId: string, changes: Record<string, unknown>) => {
    setItems((prev) => prev.map((c) =>
      c.id === casoId ? { ...c, ...changes } as CasoAdmin : c
    ));
  }, []);

  useEffect(() => {
    const t = setTimeout(fetchCasos, 300);
    return () => clearTimeout(t);
  }, [fetchCasos]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      {/* Barra de filtros */}
      <div className="agente items-center gap-3 agente-wrap">
        <div className="relative agente-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Buscar por asunto o email..."
            value={q}
            onChange={e => { setQ(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-primary placeholder-slate-600 transition-colors"
          />
        </div>
        <select value={tipo} onChange={e => { setTipo(e.target.value); setPage(1); }}
          className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-primary cursor-pointer">
          {TIPOS.map(t => <option key={t} value={t}>{t || "Todos los tipos"}</option>)}
        </select>
        <select value={estado} onChange={e => { setEstado(e.target.value); setPage(1); }}
          className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-primary cursor-pointer">
          {ESTADOS.map(s => <option key={s} value={s}>{s || "Todos los estados"}</option>)}
        </select>
        <button onClick={fetchCasos}
          className="p-2 bg-white/5 border border-white/10 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
        <span className="text-xs text-slate-500 ml-auto">{total} casos</span>
      </div>

      {/* Tabla */}
      <div className="bg-white/[0.03] border border-white/8 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="agente items-center justify-center py-20">
            <div className="w-8 h-8 rounded-full border-t-2 border-primary animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 text-slate-500 text-sm">No se encontraron casos.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-white/[0.02] text-slate-400 text-[10px] font-black uppercase tracking-widest border-b border-white/5">
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("radicado")}>
                    <span className="agente items-center gap-1">Radicado <SortIcon k="radicado" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("asunto")}>
                    <span className="agente items-center gap-1">Asunto <SortIcon k="asunto" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("tipo")}>
                    <span className="agente items-center gap-1">Tipo <SortIcon k="tipo" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("estado")}>
                    <span className="agente items-center gap-1">Estado <SortIcon k="estado" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("asignado")}>
                    <span className="agente items-center gap-1">Asignado a <SortIcon k="asignado" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("prioridad")}>
                    <span className="agente items-center gap-1">Prioridad <SortIcon k="prioridad" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("recibido")}>
                    <span className="agente items-center gap-1">Recibido <SortIcon k="recibido" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none hover:text-white transition-colors" onClick={() => toggleSort("vencimiento")}>
                    <span className="agente items-center gap-1">Vencimiento <SortIcon k="vencimiento" /></span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {items.map((caso, i) => (
                  <motion.tr key={caso.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.015 }}
                    onClick={() => setSelectedId(caso.id)}
                    className={`cursor-pointer hover:bg-white/[0.03] transition-colors ${!caso.es_pqrs ? "border-l-2 border-l-red-500/50" : ""}`}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-primary/80">
                        {caso.numero_radicado || caso.id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="px-4 py-3 max-w-[220px]">
                      <p className="text-white font-medium truncate">{caso.asunto}</p>
                      <p className="text-slate-500 text-[10px] truncate">{caso.email_origen}</p>
                      {!caso.es_pqrs && (
                        <span className="inline-block mt-0.5 text-[9px] px-1.5 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded">
                          No PQRS
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[10px] font-bold px-2 py-1 rounded-lg border bg-transparent ${TIPO_CLS[caso.tipo_caso] ?? "text-slate-400 border-white/10"}`}>
                        {caso.tipo_caso}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-bold ${ESTADO_CLS[caso.estado] ?? "text-slate-400"}`}>
                        {caso.estado}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {caso.asignado_nombre ? (
                        <div>
                          <p className="text-white text-xs font-medium">{caso.asignado_nombre}</p>
                          <p className="text-slate-500 text-[10px]">{caso.asignado_email}</p>
                        </div>
                      ) : (
                        <span className="text-slate-600 text-xs italic">Sin asignar</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${PRIORIDAD_CLS[caso.nivel_prioridad] ?? "text-slate-400 border-white/10"}`}>
                        {caso.nivel_prioridad}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {caso.fecha_recibido ? new Date(caso.fecha_recibido).toLocaleDateString() : "\u2014"}
                    </td>
                    <td className="px-4 py-3">
                      {caso.fecha_vencimiento ? (
                        <span className={`text-xs font-bold ${new Date(caso.fecha_vencimiento) < new Date() ? "text-red-400" : "text-slate-400"}`}>
                          {new Date(caso.fecha_vencimiento).toLocaleDateString()}
                        </span>
                      ) : (
                        <span className="text-slate-600 text-xs">{"\u2014"}</span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="agente items-center justify-between px-5 py-3 border-t border-white/5">
          <div className="agente items-center gap-2">
            <span className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">Mostrar:</span>
            {PAGE_SIZES.map(s => (
              <button
                key={s}
                onClick={() => { setPageSize(s); setPage(1); }}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                  pageSize === s ? "bg-primary/20 text-primary border border-primary/30" : "bg-white/5 text-slate-500 hover:text-white border border-white/10"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="agente items-center gap-3">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              className="p-2 rounded-lg bg-white/5 text-slate-400 hover:text-white disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-slate-500">Pagina {page} de {totalPages || 1}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              className="p-2 rounded-lg bg-white/5 text-slate-400 hover:text-white disabled:opacity-30 transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <CasoDetailOverlay casoId={selectedId} onClose={() => setSelectedId(null)} onStatusChange={handleStatusChange} />
    </div>
  );
}
