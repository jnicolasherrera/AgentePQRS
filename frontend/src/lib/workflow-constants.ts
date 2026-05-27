// Sprint FlexFintech 2026-05-27 bloque 7 — labels/colores/iconos de los
// "dos universos" de pqrs_casos.tipo_workflow.
//
// PQRS  = caso legal (tutela / petición / queja / reclamo) con SLA.
// AC    = consulta operativa de atención al cliente, sin SLA legal,
//         responde con plantillas predefinidas.

import type { WorkflowType } from "@/types/api";

/** Filtro UI: incluye "all" para "ambos universos" (default Recovery/Demo). */
export type WorkflowFilter = WorkflowType | "all";

export interface WorkflowMeta {
  key: WorkflowType;
  label: string;
  shortLabel: string;       // pill compacta
  icon: "scale" | "message"; // lucide-react: Scale / MessageCircle
  /** Color principal (Tailwind class group para badge/pill). */
  badgeTw: string;
  /** Color hex (charts, dataviz, SVG). */
  hex: string;
  description: string;
}

export const WORKFLOWS: Record<WorkflowType, WorkflowMeta> = {
  PQRS: {
    key: "PQRS",
    label: "PQRS",
    shortLabel: "PQRS",
    icon: "scale",
    badgeTw: "text-red-600 border-red-500/40 bg-red-500/10",
    hex: "#dc2626",
    description: "Caso legal con plazo: tutela, petición, queja, reclamo, solicitud.",
  },
  ATENCION_CLIENTE: {
    key: "ATENCION_CLIENTE",
    label: "Atención al Cliente",
    shortLabel: "Atención",
    icon: "message",
    badgeTw: "text-blue-600 border-blue-500/40 bg-blue-500/10",
    hex: "#035aa7",
    description: "Consulta operativa: paz y salvo, comprobantes, datos de pago, etc.",
  },
};

/** Items para el filtro pill en la Bandeja (orden importa: PQRS primero). */
export const WORKFLOW_FILTER_ITEMS: { key: WorkflowFilter; label: string }[] = [
  { key: "PQRS",             label: "PQRS" },
  { key: "ATENCION_CLIENTE", label: "Atención cliente" },
  { key: "all",              label: "Ambos" },
];

/** Cuando el tenant NO tiene buzones AC, el filtro queda oculto y se asume PQRS. */
export function tieneWorkflowAC(workflows: WorkflowType[] | undefined): boolean {
  return !!workflows?.includes("ATENCION_CLIENTE");
}

/** Helper para mapear "all" → undefined al construir query params del backend. */
export function workflowParam(f: WorkflowFilter): WorkflowType | undefined {
  return f === "all" ? undefined : f;
}
