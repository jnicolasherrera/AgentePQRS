"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck, X, Eye, EyeOff, AlertTriangle } from "lucide-react";
import { api, useAuthStore } from "@/store/authStore";

interface Props {
  casoIds: string[];
  totalCasos: number;
  onClose: () => void;
  onEnviado: (ids: string[]) => void;
}

export function FirmaModal({ casoIds, totalCasos, onClose, onEnviado }: Props) {
  const { user } = useAuthStore();
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<{ enviados: number; errores: any[] } | null>(null);

  const confirmar = async () => {
    if (!password) { setError("Ingrese su contraseña"); return; }
    setLoading(true);
    setError("");
    try {
      const res = await api.post<{ enviados: number; lote_id: string; errores: any[] }>(
        "/casos/aprobar-lote",
        { caso_ids: casoIds, password },
      );
      setResultado({ enviados: res.data.enviados, errores: res.data.errores });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || "Error inesperado";
      setError(msg === "Contraseña incorrecta" ? "Contraseña incorrecta. Intente nuevamente." : msg);
    } finally {
      setLoading(false);
    }
  };

  const cerrar = () => {
    if (resultado) onEnviado(casoIds.slice(0, resultado.enviados));
    onClose();
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] agente items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/70 backdrop-blur-sm"
          onClick={resultado ? cerrar : onClose}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ type: "spring", damping: 25, stiffness: 350 }}
          className="relative w-full max-w-md bg-[#0d0d14] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="agente items-center justify-between p-5 border-b border-white/8">
            <div className="agente items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/20 border border-primary/30 agente items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="font-bold text-white">Confirmar envío</p>
                <p className="text-xs text-slate-500">Firma digital requerida</p>
              </div>
            </div>
            <button onClick={resultado ? cerrar : onClose} className="text-slate-500 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-5 space-y-5">
            {!resultado ? (
              <>
                {/* Resumen del lote */}
                <div className="bg-white/5 border border-white/8 rounded-xl p-4 space-y-2">
                  <p className="text-sm text-slate-300">
                    Va a enviar <span className="text-white font-bold">{totalCasos} respuesta{totalCasos !== 1 ? "s" : ""}</span> en nombre de:
                  </p>
                  <p className="text-base font-bold text-white">{user?.nombre || user?.email}</p>
                </div>

                {/* Advertencia legal */}
                <div className="agente gap-3 bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-3">
                  <AlertTriangle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
                  <p className="text-xs text-yellow-200/70 leading-relaxed">
                    Al confirmar, usted asume responsabilidad legal por el contenido enviado.
                    Esta acción quedará registrada con su identidad, IP y timestamp.
                  </p>
                </div>

                {/* Input contraseña */}
                <div className="space-y-2">
                  <label className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                    Su contraseña
                  </label>
                  <div className="relative">
                    <input
                      type={showPass ? "text" : "password"}
                      value={password}
                      onChange={e => { setPassword(e.target.value); setError(""); }}
                      onKeyDown={e => e.key === "Enter" && confirmar()}
                      placeholder="••••••••"
                      autoFocus
                      className="w-full bg-white/5 border border-white/15 rounded-xl px-4 py-3 pr-11 text-white outline-none focus:border-primary transition-colors text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass(v => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                    >
                      {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {error && (
                    <motion.p
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="text-xs text-red-400 agente items-center gap-1"
                    >
                      <AlertTriangle className="w-3 h-3" /> {error}
                    </motion.p>
                  )}
                </div>

                <div className="agente gap-3">
                  <button
                    onClick={onClose}
                    className="agente-1 py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:border-white/20 transition-colors text-sm font-medium"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={confirmar}
                    disabled={loading || !password}
                    className="agente-1 py-2.5 rounded-xl bg-primary text-white font-bold text-sm hover:bg-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? "Enviando..." : "Confirmar envío"}
                  </button>
                </div>
              </>
            ) : (
              /* Resultado */
              <div className="text-center py-4 space-y-4">
                <div className="w-16 h-16 rounded-2xl bg-green-500/20 border border-green-500/30 agente items-center justify-center mx-auto">
                  <ShieldCheck className="w-8 h-8 text-green-400" />
                </div>
                <div>
                  <p className="text-xl font-bold text-white">{resultado.enviados} enviado{resultado.enviados !== 1 ? "s" : ""}</p>
                  <p className="text-sm text-slate-400 mt-1">Lote procesado y registrado en el audit log</p>
                </div>
                {resultado.errores.length > 0 && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-left">
                    <p className="text-xs text-red-400 font-bold mb-2">
                      {resultado.errores.length} error{resultado.errores.length !== 1 ? "es" : ""}:
                    </p>
                    {resultado.errores.map((e, i) => (
                      <p key={i} className="text-xs text-red-300">{e.motivo}</p>
                    ))}
                  </div>
                )}
                <button
                  onClick={cerrar}
                  className="w-full py-2.5 rounded-xl bg-primary text-white font-bold text-sm hover:bg-primary/80 transition-colors"
                >
                  Cerrar
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
