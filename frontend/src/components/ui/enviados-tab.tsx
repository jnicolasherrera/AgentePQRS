"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Send, User, Clock, Package, RefreshCw, Download } from "lucide-react";
import { api } from "@/store/authStore";

interface EnviadoRow {
  id: string;
  caso_id: string;
  lote_id: string | null;
  fecha_envio: string;
  abogado: string;
  email_destino: string;
  asunto: string;
  tipo: string;
  prioridad: string;
}

const TIPO_COLOR: Record<string, string> = {
  TUTELA:   "text-red-400 bg-red-500/10 border-red-500/30",
  PETICION: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  QUEJA:    "text-orange-400 bg-orange-500/10 border-orange-500/30",
  RECLAMO:  "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
  SOLICITUD:"text-green-400 bg-green-500/10 border-green-500/30",
};

const formatFecha = (iso: string) =>
  new Date(iso).toLocaleString("es-CO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

export function EnviadosTab({ selectedClienteId }: { selectedClienteId?: string }) {
  const [rows, setRows] = useState<EnviadoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroAbogado, setFiltroAbogado] = useState("");

  const fetchEnviados = useCallback(() => {
    const url = selectedClienteId
      ? `/casos/enviados/historial?cliente_id=${selectedClienteId}`
      : "/casos/enviados/historial";
    api.get<EnviadoRow[]>(url)
      .then(r => { setRows(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [selectedClienteId]);

  useEffect(() => {
    fetchEnviados();
  }, [fetchEnviados]);

  const abogados = Array.from(new Set(rows.map(r => r.abogado))).sort();
  const filtrados = filtroAbogado ? rows.filter(r => r.abogado === filtroAbogado) : rows;

  // Agrupar visualmente por lote
  const loteColors: Record<string, string> = {};
  const lotesList = Array.from(new Set(rows.map(r => r.lote_id).filter(Boolean)));
  const palette = ["border-l-primary/60", "border-l-purple-500/60", "border-l-cyan-500/60",
                   "border-l-emerald-500/60", "border-l-rose-500/60"];
  lotesList.forEach((lid, i) => { loteColors[lid!] = palette[i % palette.length]; });

  const exportCSV = () => {
    const header = "Fecha,Para,Asunto,Tipo,Abogado,Lote";
    const lines = filtrados.map(r =>
      `"${formatFecha(r.fecha_envio)}","${r.email_destino}","${r.asunto}","${r.tipo}","${r.abogado}","${r.lote_id || ""}"`
    );
    const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "enviados.csv"; a.click();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-20 opacity-50">
        <div className="w-8 h-8 rounded-full border-t-2 border-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Send className="w-5 h-5 text-primary" />
            Historial de Enviados
            <span className="ml-1 px-2 py-0.5 bg-primary/20 text-primary text-sm rounded-full border border-primary/30">
              {rows.length}
            </span>
          </h2>
          <button onClick={fetchEnviados} className="text-slate-500 hover:text-white transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={filtroAbogado}
            onChange={e => setFiltroAbogado(e.target.value)}
            className="bg-black/40 border border-white/15 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-primary transition-all"
          >
            <option value="">Todos los abogados</option>
            {abogados.map(a => <option key={a} value={a}>{a}</option>)}
          </select>

          <button
            onClick={exportCSV}
            className="flex items-center gap-2 px-3 py-1.5 border border-white/15 rounded-lg text-sm text-slate-300 hover:border-white/30 hover:text-white transition-colors"
          >
            <Download className="w-3.5 h-3.5" /> CSV
          </button>
        </div>
      </div>

      {filtrados.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <Send className="w-12 h-12 mb-4 opacity-30" />
          <p className="font-medium text-slate-300">No has enviado respuestas aun</p>
          <p className="text-sm mt-1 text-slate-500">Las respuestas que apruebes apareceran aqui</p>
        </div>
      ) : (
        <div className="bg-white/3 border border-white/8 rounded-2xl overflow-hidden">
          {/* Leyenda de lotes */}
          {lotesList.length > 0 && (
            <div className="flex items-center gap-3 px-4 py-2 border-b border-white/5 text-xs text-slate-500">
              <Package className="w-3.5 h-3.5" />
              Lotes: {lotesList.length} — el borde izquierdo agrupa emails del mismo envío
            </div>
          )}

          {/* Header tabla */}
          <div className="grid grid-cols-[1fr_1fr_6rem_8rem_7rem] gap-4 px-4 py-3 border-b border-white/8 text-xs text-slate-500 uppercase tracking-wider font-semibold">
            <span>Para / Asunto</span>
            <span>Tipo</span>
            <span>Abogado</span>
            <span>Fecha</span>
            <span></span>
          </div>

          {filtrados.map(row => (
            <motion.div
              key={row.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className={`grid grid-cols-[1fr_1fr_6rem_8rem_7rem] gap-4 px-4 py-3 border-b border-white/5 items-center border-l-2 ${row.lote_id ? loteColors[row.lote_id] : "border-l-transparent"}`}
            >
              <div className="min-w-0">
                <p className="text-sm text-white truncate">{row.email_destino}</p>
                <p className="text-xs text-slate-500 truncate">{row.asunto}</p>
              </div>

              <span className={`text-xs px-2 py-0.5 rounded-full border font-bold w-fit ${TIPO_COLOR[row.tipo] || "text-slate-400 border-slate-400/30"}`}>
                {row.tipo}
              </span>

              <div className="flex items-center gap-1.5 text-xs text-slate-300 min-w-0">
                <User className="w-3 h-3 text-slate-500 shrink-0" />
                <span className="truncate">{row.abogado}</span>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <Clock className="w-3 h-3" />
                {formatFecha(row.fecha_envio)}
              </div>

              {row.lote_id && (
                <span className="text-xs text-slate-600 font-mono truncate" title={row.lote_id}>
                  Lote {row.lote_id.substring(0, 8)}
                </span>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
