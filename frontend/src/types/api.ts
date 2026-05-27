export interface User {
  id: string;
  email: string;
  nombre: string;
  rol: "analista" | "coordinador" | "admin" | "auditor" | "super_admin";
  tenant_uuid: string;
  usuario_id?: string;
  cliente_nombre?: string;
}

export interface Caso {
  id: string;
  email_origen: string;
  asunto: string;
  cuerpo: string;
  estado: string;
  prioridad: string;
  tipo: string;
  fecha: string | null;
  fecha_vencimiento: string | null;
  canal?: string;
  comentarios?: Comentario[];
  archivos?: Adjunto[];
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
