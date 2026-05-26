// Formatters es-CO unificados. Reemplaza variantes ad-hoc en distintos componentes.

export const formatNumber = (n: number | null | undefined): string =>
  (n ?? 0).toLocaleString("es-CO");

export const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-CO");
};

export const formatTime = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
};

export const formatDateTime = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CO");
};

// Fecha "DD MMM" para ejes de gráficos
export const formatDateShort = (iso: string): string => {
  const d = iso.length === 10 ? new Date(iso + "T00:00:00") : new Date(iso);
  return d.toLocaleDateString("es-CO", { day: "2-digit", month: "short" });
};
