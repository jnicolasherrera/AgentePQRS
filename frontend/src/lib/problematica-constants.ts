// Sprint FlexFintech 2026-05-27 bloque 7 — categorización visual de
// `problematica_detectada` (slug del clasificador/seed de plantillas FF).
//
// Las 49 plantillas FF cargadas via seed agrupan en 9 categorías. Usamos
// prefijo del slug para mapear a color/icon. Cualquier slug fuera del mapa
// cae a "otros" (gris).

export type ProblematicaCategoria =
  | "paz_y_salvo"
  | "comprobante"
  | "caso"
  | "datos_pago"
  | "agencia"
  | "convenio"
  | "desconoce_deuda"
  | "documentacion"
  | "otros";

export interface ProblematicaMeta {
  categoria: ProblematicaCategoria;
  /** Label legible (capitalize del slug). */
  label: string;
  /** Tailwind classes para badge/pill (border + text + bg). */
  badgeTw: string;
  /** Hex color para charts. */
  hex: string;
}

const CATEGORIAS: Record<ProblematicaCategoria, { badgeTw: string; hex: string; label: string }> = {
  paz_y_salvo:     { badgeTw: "text-emerald-700 border-emerald-500/40 bg-emerald-500/10", hex: "#10b981", label: "Paz y salvo" },
  comprobante:     { badgeTw: "text-blue-700 border-blue-500/40 bg-blue-500/10",          hex: "#035aa7", label: "Comprobante" },
  caso:            { badgeTw: "text-slate-700 border-slate-500/40 bg-slate-500/10",       hex: "#64748b", label: "Gestión de caso" },
  datos_pago:      { badgeTw: "text-cyan-700 border-cyan-500/40 bg-cyan-500/10",          hex: "#06b6d4", label: "Datos de pago" },
  agencia:         { badgeTw: "text-violet-700 border-violet-500/40 bg-violet-500/10",    hex: "#8b5cf6", label: "Agencia" },
  convenio:        { badgeTw: "text-indigo-700 border-indigo-500/40 bg-indigo-500/10",    hex: "#6366f1", label: "Convenio" },
  desconoce_deuda: { badgeTw: "text-orange-700 border-orange-500/40 bg-orange-500/10",    hex: "#f97316", label: "Desconoce deuda" },
  documentacion:   { badgeTw: "text-teal-700 border-teal-500/40 bg-teal-500/10",          hex: "#14b8a6", label: "Documentación" },
  otros:           { badgeTw: "text-gray-600 border-gray-500/30 bg-gray-500/10",          hex: "#6b7280", label: "Otros" },
};

// Reglas de prefijo → categoría (orden importa: prefijos más específicos primero).
const REGLAS: { match: (slug: string) => boolean; categoria: ProblematicaCategoria }[] = [
  { match: s => s.startsWith("PAZ_Y_SALVO") || s.startsWith("ADJUNTAMOS_PAZ_Y_SALVO") || s.startsWith("CONFIRMACION_RECEPCION_PYS") || s === "PEDIDO_PAZ_Y_SALVO", categoria: "paz_y_salvo" },
  { match: s => s.startsWith("COMPROBANTE"), categoria: "comprobante" },
  { match: s => s.startsWith("DESCONOCE_DEUDA"), categoria: "desconoce_deuda" },
  { match: s => s.startsWith("DATOS_PAGO"), categoria: "datos_pago" },
  { match: s => s.startsWith("AGENCIA") || s.startsWith("MSJ_AGENCIAS"), categoria: "agencia" },
  { match: s => s.startsWith("CONVENIO"), categoria: "convenio" },
  { match: s => s.startsWith("CASO_"), categoria: "caso" },
  { match: s => s.startsWith("PEDIDO_DOCUMENTACION") || s.startsWith("PEDIR_DOCUMENTO") || s === "CLIENTE_PIDE_INFO" || s === "CARTERA_RECUPERADA", categoria: "documentacion" },
];

/** Devuelve metadata visual de una problematica. NULL/undefined → "otros". */
export function getProblematicaMeta(slug: string | null | undefined): ProblematicaMeta {
  if (!slug) {
    const { badgeTw, hex } = CATEGORIAS.otros;
    return { categoria: "otros", label: "Sin clasificar", badgeTw, hex };
  }
  const upper = slug.toUpperCase();
  const regla = REGLAS.find(r => r.match(upper));
  const categoria = regla?.categoria ?? "otros";
  const { badgeTw, hex } = CATEGORIAS[categoria];
  return { categoria, label: humanizeSlug(slug), badgeTw, hex };
}

/** Convierte slug → label legible. PAZ_Y_SALVO_AT → "Paz y salvo at". */
export function humanizeSlug(slug: string): string {
  return slug
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

/** Lista de categorías con su meta (para leyenda de dashboard). */
export const CATEGORIAS_LIST: { key: ProblematicaCategoria; label: string; hex: string }[] =
  (Object.entries(CATEGORIAS) as [ProblematicaCategoria, typeof CATEGORIAS[ProblematicaCategoria]][])
    .map(([key, v]) => ({ key, label: v.label, hex: v.hex }));
