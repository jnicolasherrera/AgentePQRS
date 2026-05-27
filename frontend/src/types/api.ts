export interface User {
  id: string;
  email: string;
  nombre: string;
  rol: "analista" | "coordinador" | "admin" | "auditor" | "super_admin";
  tenant_uuid: string;
  usuario_id?: string;
  cliente_nombre?: string;
}

// Sprint FF bloque 7: discriminador de los "dos universos" FlexFintech.
export type WorkflowType = "PQRS" | "ATENCION_CLIENTE";

export interface DestinatarioOverrideAudit {
  fecha: string;
  usuario_nombre: string | null;
  anterior: string | null;
  nuevo: string | null;
  tipo_cambio: "SET_OVERRIDE" | "QUITAR_OVERRIDE" | null;
}

export interface Caso {
  id: string;
  email_origen: string;
  /** Si fue editado por admin via PATCH /casos/{id}/destinatario */
  email_respuesta_override?: string | null;
  /** Lo que el backend usará al enviar (override || email_origen) */
  email_destinatario_efectivo?: string;
  destinatario_override_audit?: DestinatarioOverrideAudit | null;
  asunto: string;
  cuerpo: string;
  estado: string;
  prioridad: string;
  tipo: string;
  /** PQRS legal vs ATENCION_CLIENTE operativa (sprint FF) */
  tipo_workflow?: WorkflowType;
  /** Cédula del peticionante extraída del cuerpo/histórico */
  documento_peticionante?: string | null;
  /** Path SharePoint del archivado (solo PQRS post-envío) */
  sp_archivo?: string | null;
  metadata_especifica?: Record<string, unknown>;
  problematica_detectada?: string | null;
  borrador_respuesta?: string | null;
  borrador_estado?: string | null;
  fecha: string | null;
  fecha_vencimiento: string | null;
  canal?: string;
  comentarios?: Comentario[];
  archivos?: Adjunto[];
}

export interface CasoLista {
  id: string;
  numero_radicado?: string | null;
  asunto: string;
  email_origen: string;
  tipo_caso: string;
  tipo_workflow?: WorkflowType;
  problematica_detectada?: string | null;
  estado: string;
  nivel_prioridad: string;
  fecha_recibido: string | null;
  fecha_vencimiento: string | null;
  es_pqrs?: boolean;
  acuse_enviado?: boolean;
  asignado_nombre?: string | null;
  asignado_email?: string | null;
}

export interface Plantilla {
  id: string;
  cliente_id: string;
  problematica: string;
  contexto: string | null;
  cuerpo: string;
  keywords: string[];
  tipo_workflow: WorkflowType;
  created_at: string | null;
}

export interface AuthMeResponse {
  usuario_id: string;
  email: string;
  nombre: string | null;
  rol: User["rol"];
  tenant: { id: string; nombre: string } | null;
  workflows_disponibles: WorkflowType[];
}

export interface WorkflowBreakdown {
  pqrs_count: number;
  ac_count: number;
  plantillas_top5: { problematica: string; usos: number }[];
  pct_match_exacto: number;
}

export interface Comentario {
  id: string;
  texto: string;
  autor: string;
  fecha: string;
  es_sistema: boolean;
}

export interface Adjunto {
  id: string;
  nombre: string;
  size: string;
  type: string;
  url: string;
}

export interface KPIs {
  total_casos: number;
  casos_criticos: number;
  porcentaje_resueltos: number;
  abiertos: number;
  en_proceso: number;
  contestados: number;
  cerrados: number;
  casos_hoy: number;
  casos_semana: number;
  vencidos: number;
  por_vencer?: number;
  activos?: number;
}

export interface IngresosSemana {
  pqr: number;
  tutela: number;
  total: number;
}

export interface PulsoTutelas {
  activas: number;
  vencidas: number;
  por_vencer: number;
  total: number;
  escaladas_de_pqr: number;
  tasa_escalamiento: number;
}

export interface CasoResumen {
  id: string;
  email: string;
  asunto: string;
  prioridad: string;
  estado: string;
  tipo: string;
  fecha: string | null;
  vencimiento: string | null;
  cliente_id?: string;
  cliente_nombre?: string;
}

export interface Trazabilidad {
  recibidos: number;
  asignados: number;
  con_acuse: number;
  respondidos: number;
}

export interface DashboardStats {
  periodo?: "dia" | "semana" | "mes";
  dias?: number;
  kpis: KPIs;
  ingresos_periodo?: IngresosSemana;
  /** @deprecated usar ingresos_periodo */
  ingresos_semana?: IngresosSemana;
  tutelas?: PulsoTutelas;
  /** Sprint FF bloque 7: null cuando el tenant no tiene buzones ATENCION_CLIENTE */
  workflow_breakdown?: WorkflowBreakdown | null;
  trazabilidad: Trazabilidad;
  distribucion: Record<string, number>;
  distribucion_tipo: Record<string, number>;
  ultimos_casos: CasoResumen[];
}

export interface ClienteTenant {
  id: string;
  nombre: string;
  tenant_uuid: string;
}
