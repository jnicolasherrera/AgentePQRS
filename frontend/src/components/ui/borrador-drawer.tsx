"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Edit3, Save, XCircle, Mail, Tag } from "lucide-react";
import { api } from "@/store/authStore";

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

interface Props {
  caso: CasoPendiente;
  onClose: () => void;
  onActualizado: (id: string, texto: string) => void;
  onRechazado: (id: string) => void;
}

export function BorradorDrawer({ caso, onClose, onActualizado, onRechazado }: Props) {
  const [texto, setTexto] = useState(caso.borrador_respuesta || "");
  const [editando, setEditando] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rechazando, setRechazando] = useState(false);

  const guardar = async () => {
    setSaving(true);
    try {
      await api.put(`/casos/${caso.id}/borrador`, { texto });
      onActualizado(caso.id, texto);
      setEditando(false);
    } finally {
      setSaving(false);
    }
  };

  const rechazar = async () => {
    if (!confirm("¿Rechazar este borrador? Quedará para respuesta manual.")) return;
    setRechazando(true);
    try {
      await api.post(`/casos/${caso.id}/rechazar-borrador`);
      onRechazado(caso.id);
    } finally {
      setRechazando(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex">
        {/* Overlay */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Drawer */}
        <motion.aside
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 28, stiffness: 300 }}
          className="absolute right-0 top-0 bottom-0 w-full max-w-2xl bg-[#0a0a0f] border-l border-white/10 flex flex-col shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-white/8">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
                <Mail className="w-4 h-4 text-primary" />
              </div>
              <div>
                <p className="font-bold text-white text-sm truncate max-w-xs">{caso.asunto}</p>
                <p className="text-xs text-slate-500">{caso.email_origen}</p>
              </div>
            </div>
            <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Meta */}
          <div className="flex items-center gap-3 px-5 py-3 border-b border-white/5">
            <span className="flex items-center gap-1.5 text-xs bg-white/5 border border-white/10 px-2.5 py-1 rounded-full text-slate-300">
              <Tag className="w-3 h-3" />{caso.tipo}
            </span>
            <span className="text-xs text-slate-500 font-mono">
              {caso.problematica?.replace(/_/g, " ") || "Sin problemática"}
            </span>
          </div>

          {/* Borrador */}
          <div className="flex-1 flex flex-col p-5 gap-4 overflow-hidden">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
                Borrador de Respuesta
              </h3>
              {!editando && (
                <button
                  onClick={() => setEditando(true)}
                  className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors font-medium"
                >
                  <Edit3 className="w-3.5 h-3.5" /> Editar
                </button>
              )}
            </div>

            {editando ? (
              <textarea
                value={texto}
                onChange={e => setTexto(e.target.value)}
                className="flex-1 bg-white/5 border border-primary/30 rounded-xl p-4 text-sm text-slate-200 font-mono resize-none outline-none focus:border-primary transition-colors leading-relaxed"
              />
            ) : (
              <div className="flex-1 overflow-y-auto bg-white/3 border border-white/8 rounded-xl p-4">
                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                  {texto || <span className="text-slate-600 italic">Sin borrador</span>}
                </pre>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-5 border-t border-white/8 gap-3">
            <button
              onClick={rechazar}
              disabled={rechazando}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 text-sm font-medium transition-colors disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              {rechazando ? "Rechazando..." : "Rechazar borrador"}
            </button>

            {editando && (
              <div className="flex gap-2 ml-auto">
                <button
                  onClick={() => { setTexto(caso.borrador_respuesta); setEditando(false); }}
                  className="px-3 py-2 text-sm text-slate-400 hover:text-white transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={guardar}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-primary rounded-lg text-sm font-bold hover:bg-primary/80 transition-colors disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            )}

            {!editando && (
              <p className="ml-auto text-xs text-slate-600">
                Seleccionalo en la tabla para incluirlo en el lote
              </p>
            )}
          </div>
        </motion.aside>
      </div>
    </AnimatePresence>
  );
}
