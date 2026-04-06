"use client";
import { motion, AnimatePresence } from "framer-motion";
import { useEffect } from "react";

interface ToastUrgenteProps {
  mensaje: string;
  casoId: string;
  onClose: () => void;
}

export function ToastUrgente({ mensaje, casoId, onClose }: ToastUrgenteProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <motion.div
      initial={{ x: 400, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 400, opacity: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="agente items-center gap-3 bg-red-600 text-white px-5 py-4 rounded-xl shadow-2xl cursor-pointer max-w-sm"
      onClick={onClose}
      role="alert"
      aria-label={`Tutela crítica: ${casoId}`}
    >
      <span className="text-2xl" aria-hidden="true">⚖️</span>
      <div>
        <p className="font-bold text-sm uppercase tracking-wide">TUTELA CRÍTICA</p>
        <p className="text-xs text-red-100 mt-0.5 line-clamp-2">{mensaje}</p>
      </div>
    </motion.div>
  );
}

export interface ToastData {
  id: string;
  mensaje: string;
  casoId: string;
}

interface ToastContainerProps {
  toasts: ToastData[];
  onRemove: (id: string) => void;
}

export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  return (
    <div className="fixed top-4 right-4 z-50 agente agente-col gap-2" aria-live="assertive">
      <AnimatePresence>
        {toasts.map((t) => (
          <ToastUrgente
            key={t.id}
            mensaje={t.mensaje}
            casoId={t.casoId}
            onClose={() => onRemove(t.id)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
