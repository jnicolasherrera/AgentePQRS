// Constantes compartidas de casos. Reemplaza definiciones duplicadas en
// admin-bandeja, live-feed, enviados-tab, dashboard-metrics.

export const TIPOS = ["", "TUTELA", "PETICION", "QUEJA", "RECLAMO", "SOLICITUD"] as const;
export const ESTADOS = ["", "ABIERTO", "EN_PROCESO", "CONTESTADO", "CERRADO"] as const;
export const PRIORIDADES = ["", "CRITICA", "ALTA", "MEDIA", "BAJA"] as const;

// Hex para charts (recharts, dataviz).
export const TIPO_COLOR_HEX: Record<string, string> = {
  TUTELA:    "#dc2626", // red-600
  PETICION:  "#035aa7", // primary
  QUEJA:     "#f59e0b", // amber-500
  RECLAMO:   "#8b5cf6", // violet-500
  SOLICITUD: "#06b6d4", // cyan-500
  CONSULTA:  "#64748b", // slate-500
  SUGERENCIA:"#10b981", // emerald-500
};

// Tailwind classes para badges/pills (border + text + bg).
export const TIPO_BADGE_TW: Record<string, string> = {
  TUTELA:    "text-red-600 border-red-500/40 bg-red-500/10",
  PETICION:  "text-blue-700 border-blue-500/40 bg-blue-500/10",
  QUEJA:     "text-amber-600 border-amber-500/40 bg-amber-500/10",
  RECLAMO:   "text-violet-600 border-violet-500/40 bg-violet-500/10",
  SOLICITUD: "text-cyan-700 border-cyan-500/40 bg-cyan-500/10",
};

export const ESTADO_TEXT_TW: Record<string, string> = {
  ABIERTO:    "text-orange-500",
  EN_PROCESO: "text-blue-500",
  CONTESTADO: "text-cyan-600",
  CERRADO:    "text-green-600",
};

export const PRIORIDAD_BADGE_TW: Record<string, string> = {
  CRITICA: "text-red-700 bg-red-500/10 border-red-500/30",
  ALTA:    "text-orange-700 bg-orange-500/10 border-orange-500/30",
  MEDIA:   "text-yellow-700 bg-yellow-500/10 border-yellow-500/30",
  BAJA:    "text-green-700 bg-green-500/10 border-green-500/30",
};

export type Periodo = "dia" | "semana" | "mes";
export const PERIODOS: { key: Periodo; label: string }[] = [
  { key: "dia",    label: "Hoy" },
  { key: "semana", label: "7 días" },
  { key: "mes",    label: "30 días" },
];
