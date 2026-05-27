"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Clock, Save, Send, ShieldAlert, Mail, MessageSquare, Download, CheckCircle, BrainCircuit, XCircle, UserCheck, Scale, Link2, Search, Plus, Edit3, FolderOpen, AlertTriangle, FileText, ChevronDown } from "lucide-react";
import { api, useAuthStore } from "@/store/authStore";
import { usePlantillas } from "@/hooks/usePlantillas";
import { getProblematicaMeta } from "@/lib/problematica-constants";
import type { Plantilla } from "@/types/api";

// Regex email moderado (espejo del backend RFC 5322 light)
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

interface CasoDetailOverlayProps {
  casoId: string | null;
  onClose: () => void;
  onStatusChange?: (casoId: string, changes: Record<string, unknown>) => void;
}

export function CasoDetailOverlay({ casoId, onClose, onStatusChange }: CasoDetailOverlayProps) {
  const { user } = useAuthStore();
  const isAdmin = user?.rol === "admin" || user?.rol === "super_admin";
  const canReassign = isAdmin || user?.rol === "coordinador";
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [comentarioTexto, setComentarioTexto] = useState("");
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackDone, setFeedbackDone] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [savingDraft, setSavingDraft] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const lastSavedTextRef = useRef("");
  const [replyFiles, setReplyFiles] = useState<{id: string; nombre: string; tamano: number}[]>([]);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [teamMembers, setTeamMembers] = useState<{id: string; nombre: string; email: string}[]>([]);
  const [showAssignDropdown, setShowAssignDropdown] = useState(false);
  // Estrategia D: vincular PQR a tutela
  const [vincularOpen, setVincularOpen] = useState(false);
  const [vincularQuery, setVincularQuery] = useState("");
  const [vincularResults, setVincularResults] = useState<any[]>([]);
  const [vincularLoading, setVincularLoading] = useState(false);

  // Sprint FF bloque 10: editor de destinatario (admin only)
  const [destOpen, setDestOpen] = useState(false);
  const [destValue, setDestValue] = useState("");
  const [destSaving, setDestSaving] = useState(false);
  const [destError, setDestError] = useState<string | null>(null);

  // Sprint FF bloque 10: plantillas (solo workflow AC + admin)
  const esAC = data?.tipo_workflow === "ATENCION_CLIENTE";
  const { plantillas } = usePlantillas("ATENCION_CLIENTE", esAC && isAdmin);
  const [plantillasOpen, setPlantillasOpen] = useState(false);
  const [aplicandoPlantillaId, setAplicandoPlantillaId] = useState<string | null>(null);

  // Plantillas agrupadas por categoría visual (paz_y_salvo, comprobante, ...)
  const plantillasPorCategoria = useMemo(() => {
    const groups = new Map<string, { label: string; items: Plantilla[] }>();
    for (const p of plantillas) {
      const meta = getProblematicaMeta(p.problematica);
      const g = groups.get(meta.categoria);
      if (g) g.items.push(p);
      else groups.set(meta.categoria, { label: meta.label.split(" ").slice(0, 2).join(" "), items: [p] });
    }
    return Array.from(groups.entries()).map(([key, v]) => ({ key, ...v }));
  }, [plantillas]);

  useEffect(() => {
    if (canReassign) {
      api.get("/admin/team")
        .then(res => setTeamMembers(res.data))
        .catch(err => console.error("Error cargando equipo:", err));
    }
  }, [canReassign]);

  useEffect(() => {
    setFeedbackDone(false);
    setFeedbackLoading(false);
    setData(null);
    setDraftText("");
    setReplyFiles([]);
    setAutoSaveStatus("idle");
    lastSavedTextRef.current = "";
    if (casoId) {
      setLoading(true);
      api.get(`/casos/${casoId}`)
        .then(res => {
          setData(res.data);
          setLoading(false);
          if (res.data.borrador_respuesta) {
            setDraftText(res.data.borrador_respuesta);
            lastSavedTextRef.current = res.data.borrador_respuesta;
          }
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    }
  }, [casoId]);

  useEffect(() => {
    if (!data?.id) return;
    if (!draftText) return;
    if (draftText === lastSavedTextRef.current) return;
    setAutoSaveStatus("saving");
    const handle = setTimeout(async () => {
      try {
        await api.put(`/casos/${data.id}/borrador`, { texto: draftText });
        lastSavedTextRef.current = draftText;
        setData((prev: any) => prev ? { ...prev, borrador_respuesta: draftText, borrador_estado: "PENDIENTE" } : prev);
        onStatusChange?.(data.id, { borrador_estado: "PENDIENTE" });
        setAutoSaveStatus("saved");
      } catch (e) {
        console.error("Auto-save falló:", e);
        setAutoSaveStatus("idle");
      }
    }, 2000);
    return () => clearTimeout(handle);
  }, [draftText, data?.id, onStatusChange]);

  const handleUpdate = async (field: string, value: string) => {
    try {
      await api.patch(`/casos/${casoId}`, { [field]: value });
      setData((prev: any) => ({ ...prev, [field]: value }));
      onStatusChange?.(casoId!, { [field]: value });
    } catch (error) {
       console.error("Error updating", error);
    }
  };

  const handleReassign = async (userId: string) => {
    try {
      await api.patch(`/casos/${casoId}`, { asignado_a: userId });
      const member = teamMembers.find(m => m.id === userId);
      setData((prev: any) => ({
        ...prev,
        asignado_a: userId,
        asignado_nombre: member?.nombre || null,
      }));
      onStatusChange?.(casoId!, { asignado_nombre: member?.nombre || null });
      setShowAssignDropdown(false);
    } catch (error) {
      console.error("Error reasignando caso", error);
    }
  };

  const handleNoPQRS = async () => {
    if (!casoId || feedbackDone) return;
    setFeedbackLoading(true);
    try {
      await api.post(`/admin/casos/${casoId}/feedback`, { es_pqrs: false });
      setData((prev: any) => ({ ...prev, es_pqrs: false }));
      setFeedbackDone(true);
      onStatusChange?.(casoId, { es_pqrs: false });
    } catch (e) {
      console.error(e);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const handleGenerate = async () => {
    setLoadingDraft(true);
    try {
      const res = await api.post(`/ai/draft/${data.id}`, { save: true });
      const text = res.data.draft || "";
      setDraftText(text);
      setData((prev: any) => ({ ...prev, borrador_respuesta: text, borrador_estado: "PENDIENTE" }));
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDraft(false);
    }
  };

  const handleSaveDraft = async () => {
    setSavingDraft(true);
    try {
      const currentText = draftText || data.borrador_respuesta || "";
      await api.put(`/casos/${data.id}/borrador`, { texto: currentText });
      setData((prev: any) => ({ ...prev, borrador_respuesta: currentText, borrador_estado: "PENDIENTE" }));
      onStatusChange?.(data.id, { borrador_estado: "PENDIENTE" });
    } catch (e) {
      console.error(e);
    } finally {
      setSavingDraft(false);
    }
  };

  const handleSendResponse = () => {
    const pw = prompt("Ingrese su contraseña para enviar:");
    if (!pw) return;
    api.post("/casos/aprobar-lote", { caso_ids: [data.id], password: pw })
      .then(res => {
        if (res.data.enviados > 0) {
          setData((prev: any) => ({ ...prev, borrador_estado: "ENVIADO", estado: "CERRADO" }));
          onStatusChange?.(data.id, { borrador_estado: "ENVIADO", estado: "CERRADO" });
        }
      })
      .catch(e => console.error(e));
  };

  const handleDeleteReplyFile = async (fileId: string) => {
    try {
      await api.delete(`/casos/${data.id}/reply-adjuntos/${fileId}`);
      setReplyFiles(prev => prev.filter(x => x.id !== fileId));
    } catch (e) {
      console.error(e);
    }
  };

  const handleUploadReplyFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFile(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post(`/casos/${data.id}/reply-adjuntos`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setReplyFiles(prev => [...prev, {
        id: res.data.adjunto_id,
        nombre: res.data.nombre,
        tamano: res.data.tamano,
      }]);
    } catch (err) {
      console.error(err);
    } finally {
      setUploadingFile(false);
    }
    e.target.value = "";
  };

  // Estrategia D: vincular/desvincular PQRs a TUTELA
  const refetchCaso = async () => {
    if (!casoId) return;
    try { const r = await api.get(`/casos/${casoId}`); setData(r.data); } catch {}
  };
  const buscarPqrsVinculables = async (q: string) => {
    if (!data?.id) return;
    setVincularLoading(true);
    try {
      const res = await api.get(`/casos/${data.id}/pqrs-vinculables`, { params: q ? { q } : {} });
      setVincularResults(res.data.items || []);
    } catch (e) { console.error(e); setVincularResults([]); }
    finally { setVincularLoading(false); }
  };
  const handleVincularPqr = async (pqrId: string) => {
    if (!data?.id) return;
    try {
      await api.post(`/casos/${data.id}/vincular-pqr`, { pqr_id: pqrId });
      setVincularOpen(false); setVincularQuery(""); setVincularResults([]);
      await refetchCaso();
    } catch (e) { console.error(e); }
  };
  const handleDesvincularPqr = async (pqrId: string) => {
    if (!data?.id) return;
    try {
      await api.delete(`/casos/${data.id}/vincular-pqr/${pqrId}`);
      await refetchCaso();
    } catch (e) { console.error(e); }
  };

  // Sprint FF bloque 10: PATCH destinatario (admin only)
  const openDestEditor = () => {
    if (!data) return;
    setDestValue(data.email_respuesta_override || "");
    setDestError(null);
    setDestOpen(true);
  };
  const handleSaveDestinatario = async () => {
    if (!data?.id) return;
    const raw = destValue.trim();
    // Validación cliente: vacío = quitar override; no vacío = debe matchear regex
    if (raw && !EMAIL_RE.test(raw)) {
      setDestError("Email inválido");
      return;
    }
    setDestSaving(true); setDestError(null);
    try {
      const res = await api.patch(`/casos/${data.id}/destinatario`, { email: raw || null });
      // Actualización optimista local + refetch para traer el audit
      setData((prev: any) => prev ? {
        ...prev,
        email_respuesta_override: raw || null,
        email_destinatario_efectivo: res.data.email_destinatario_efectivo,
      } : prev);
      setDestOpen(false);
      await refetchCaso();
    } catch (e: any) {
      setDestError(e?.response?.data?.detail || "Error al guardar");
    } finally {
      setDestSaving(false);
    }
  };

  // Sprint FF bloque 10: aplicar plantilla al borrador (admin AC)
  const handleAplicarPlantilla = async (plantillaId: string) => {
    if (!data?.id) return;
    setAplicandoPlantillaId(plantillaId);
    try {
      const res = await api.post(`/casos/${data.id}/aplicar-plantilla`, { plantilla_id: plantillaId });
      setDraftText(res.data.borrador_respuesta);
      lastSavedTextRef.current = res.data.borrador_respuesta;
      setData((prev: any) => prev ? {
        ...prev,
        borrador_respuesta: res.data.borrador_respuesta,
        borrador_estado: res.data.borrador_estado,
      } : prev);
      setPlantillasOpen(false);
    } catch (e) {
      console.error("Error aplicando plantilla:", e);
    } finally {
      setAplicandoPlantillaId(null);
    }
  };

  const handleDownloadFile = async (adjuntoId: string, nombre: string) => {
    try {
      const res = await api.get(`/casos/${data.id}/adjuntos/${adjuntoId}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = nombre;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Error descargando adjunto:", e);
    }
  };

  const isHtml = (/<[a-z][\s\S]*>/i.test(data?.cuerpo || "") || (data?.cuerpo || "").trim().startsWith("<!DOCTYPE"));
  const hasDraft = !!(draftText || data?.borrador_respuesta);

  return (
    <AnimatePresence>
      {casoId && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 agente agente-col"
          style={{ background: "var(--background)" }}
        >
          {loading ? (
            <div className="agente-1 agente items-center justify-center">
              <div className="w-10 h-10 border-t-2 border-primary rounded-full animate-spin"></div>
            </div>
          ) : data ? (
            <>
              {/* TOP HEADER BAR */}
              <header className="agente items-center justify-between px-6 py-3 border-b border-border bg-muted shrink-0">
                <div className="agente items-center gap-3 agente-1 min-w-0">
                  <span className="text-xs font-black uppercase tracking-widest text-muted-foreground bg-muted px-3 py-1 rounded-full border border-border shrink-0">
                    ID: {data.id.split("-")[0]}...
                  </span>

                  <div className={`agente items-center gap-1.5 px-3 py-1 rounded-lg border font-bold text-sm shrink-0 ${data.tipo === 'TUTELA' ? 'border-red-500/50 text-red-500 bg-red-500/10' : 'border-blue-500/50 text-blue-400 bg-blue-500/10'}`}>
                    {data.tipo === 'TUTELA' ? 'TUTELA' : data.tipo}
                  </div>

                  <div className={`agente items-center gap-1.5 px-3 py-1 rounded-lg border text-sm shrink-0 ${data.prioridad === 'ALTA' || data.prioridad === 'CRITICA' ? 'border-orange-500/30 text-orange-400 bg-orange-500/10' : 'border-green-500/30 text-green-400 bg-green-500/10'}`}>
                    {data.prioridad === 'ALTA' || data.prioridad === 'CRITICA' ? <ShieldAlert className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
                    {data.prioridad}
                  </div>

                  {data.problematica_detectada && (
                    <span className="text-sm text-muted-foreground truncate min-w-0">{data.problematica_detectada}</span>
                  )}
                </div>

                <div className="agente items-center gap-3 shrink-0">
                  <div className="agente gap-2">
                    {(["ABIERTO", "EN_PROCESO", "CERRADO"] as const).map(est => (
                      <button
                        key={est}
                        onClick={() => handleUpdate("estado", est)}
                        className={`px-3 py-1 rounded-lg text-xs font-bold border transition-all ${
                          data.estado === est
                            ? est === "ABIERTO"
                              ? "bg-orange-500/20 border-orange-500/50 text-orange-400"
                              : est === "EN_PROCESO"
                                ? "bg-blue-500/20 border-blue-500/50 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]"
                                : "bg-green-500/20 border-green-500/50 text-green-400 shadow-[0_0_15px_rgba(34,197,94,0.3)]"
                            : "bg-transparent border-border text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {est === "CERRADO" ? "Resuelto" : est === "EN_PROCESO" ? "En Proceso" : "Abierto"}
                      </button>
                    ))}
                  </div>

                  {canReassign && (
                    <div className="relative">
                      <button
                        onClick={() => setShowAssignDropdown(!showAssignDropdown)}
                        className="agente items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold border border-border bg-muted text-foreground/80 hover:bg-secondary transition-all"
                      >
                        <UserCheck className="w-3.5 h-3.5" />
                        {data.asignado_nombre || "Sin asignar"}
                      </button>
                      {showAssignDropdown && (
                        <div className="absolute top-full mt-1 right-0 w-64 bg-card border border-border rounded-xl shadow-2xl z-50 py-1 max-h-60 overflow-y-auto">
                          {teamMembers.map(m => (
                            <button
                              key={m.id}
                              onClick={() => handleReassign(m.id)}
                              className={`w-full text-left px-4 py-2 text-sm hover:bg-muted transition-colors ${
                                data.asignado_a === m.id ? "text-primary font-bold" : "text-foreground/80"
                              }`}
                            >
                              <p className="font-medium">{m.nombre}</p>
                              <p className="text-xs text-muted-foreground">{m.email}</p>
                            </button>
                          ))}
                          {teamMembers.length === 0 && (
                            <p className="px-4 py-3 text-xs text-muted-foreground">No hay miembros del equipo</p>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {data.fecha_vencimiento && (
                    <span className="text-xs font-bold text-foreground/80 bg-muted px-3 py-1 rounded-lg border border-border">
                      SLA: <span className="text-orange-400">{new Date(data.fecha_vencimiento).toLocaleDateString()}</span>
                    </span>
                  )}

                  <button
                    onClick={() => setShowComments(!showComments)}
                    className={`p-2 rounded-full transition-colors ${showComments ? 'bg-primary/20 text-primary' : 'bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground'}`}
                    title="Comentarios"
                  >
                    <MessageSquare className="w-5 h-5" />
                  </button>

                  <button onClick={onClose} className="p-2 bg-muted hover:bg-secondary rounded-full text-muted-foreground hover:text-foreground transition-colors">
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </header>

              {/* SPLIT PANE CONTENT */}
              <div className="agente-1 agente overflow-hidden">

                {/* LEFT PANE: Original Email */}
                <div className="w-1/2 border-r border-border agente agente-col overflow-hidden">
                  <div className="px-6 py-3 border-b border-border bg-muted shrink-0">
                    <h3 className="text-xs font-black text-red-400 uppercase tracking-widest">Correo Recibido</h3>
                  </div>

                  <div className="agente-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
                    <div>
                      {/* Sprint FF bloque 10: tag problemática prominente (solo AC).
                          Lo mostramos arriba del asunto como eyebrow para que el admin
                          vea de un vistazo qué tipo de consulta es (ej. "Paz y salvo"). */}
                      {esAC && data.problematica_detectada && (() => {
                        const meta = getProblematicaMeta(data.problematica_detectada);
                        return (
                          <div className={`inline-flex items-center gap-1.5 mb-2 px-2.5 py-1 rounded-lg border text-[11px] font-bold ${meta.badgeTw}`}>
                            <MessageSquare className="w-3 h-3" />
                            {meta.label}
                          </div>
                        );
                      })()}
                      <p className="text-sm font-bold text-foreground">{data.asunto}</p>

                      {/* Email origen + destinatario efectivo (con override) */}
                      <div className="mt-1.5 space-y-1">
                        <p className="text-xs text-muted-foreground agente items-center gap-1.5">
                          <Mail className="w-3.5 h-3.5" /> De: <span className="text-foreground/80">{data.email_origen}</span>
                        </p>

                        {/* Destinatario que se usará al responder. Si admin editó override,
                            mostramos el override + badge "override por X el Y". */}
                        {(data.email_respuesta_override || isAdmin) && (
                          <div className="relative">
                            <div className="agente items-center gap-1.5 text-xs">
                              <Send className="w-3.5 h-3.5 text-muted-foreground" />
                              <span className="text-muted-foreground">Responder a:</span>
                              <span className={`font-medium ${data.email_respuesta_override ? "text-amber-700" : "text-foreground/80"}`}>
                                {data.email_destinatario_efectivo || data.email_origen}
                              </span>
                              {isAdmin && (
                                <button
                                  onClick={openDestEditor}
                                  title="Editar destinatario"
                                  className="ml-1 p-1 rounded hover:bg-muted text-muted-foreground hover:text-primary transition-colors"
                                >
                                  <Edit3 className="w-3 h-3" />
                                </button>
                              )}
                            </div>

                            {/* Badge audit del último override */}
                            {data.destinatario_override_audit && data.email_respuesta_override && (
                              <p className="text-[10px] text-amber-600/80 italic mt-0.5 ml-5">
                                override por {data.destinatario_override_audit.usuario_nombre || "—"} el {new Date(data.destinatario_override_audit.fecha).toLocaleDateString("es-CO")}
                              </p>
                            )}

                            {/* Mini-modal (popover) en la misma posición */}
                            {destOpen && (
                              <div className="absolute z-30 top-full mt-2 left-0 w-[320px] p-4 rounded-xl bg-card border border-border shadow-lg">
                                <p className="text-xs font-bold text-foreground mb-2">Editar destinatario</p>
                                <p className="text-[10px] text-muted-foreground mb-3">
                                  Dejá vacío para volver al email original ({data.email_origen}).
                                </p>
                                <input
                                  type="email"
                                  value={destValue}
                                  onChange={e => { setDestValue(e.target.value); setDestError(null); }}
                                  placeholder="nuevomail@cliente.com"
                                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground outline-none focus:border-primary"
                                />
                                {destError && (
                                  <p className="text-[11px] text-red-600 mt-1">{destError}</p>
                                )}
                                <div className="agente items-center justify-end gap-2 mt-3">
                                  <button
                                    onClick={() => setDestOpen(false)}
                                    className="px-3 py-1.5 rounded-lg text-xs font-semibold text-muted-foreground hover:text-foreground"
                                  >Cancelar</button>
                                  <button
                                    onClick={handleSaveDestinatario}
                                    disabled={destSaving}
                                    className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-bold disabled:opacity-50"
                                  >{destSaving ? "Guardando..." : "Guardar"}</button>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      <p className="text-xs text-muted-foreground agente items-center gap-1.5 mt-1">
                        <Clock className="w-3.5 h-3.5" /> {new Date(data.fecha).toLocaleString()}
                      </p>

                      {/* Sprint FF bloque 10: badge SharePoint. Solo PQRS (AC no se archiva).
                          Si fue enviado y se archivó → verde con link. Si fue enviado y NO se
                          archivó → amarillo (típico: falta cédula). Antes de enviar → silencio. */}
                      {(data.tipo_workflow ?? "PQRS") === "PQRS" && (() => {
                        const enviado = ["CONTESTADO", "CERRADO"].includes(data.estado);
                        if (data.sp_archivo) {
                          return (
                            <a
                              href={data.sp_archivo}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 text-[11px] font-semibold hover:bg-emerald-500/20 transition-colors"
                              title={data.sp_archivo}
                            >
                              <FolderOpen className="w-3.5 h-3.5" />
                              Archivado en SharePoint
                            </a>
                          );
                        }
                        if (enviado) {
                          return (
                            <div className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-700 text-[11px] font-semibold">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              No archivado en SP — {data.documento_peticionante ? "verificar" : "falta cédula"}
                            </div>
                          );
                        }
                        return null;
                      })()}
                    </div>

                    <div className="border-t border-border pt-4">
                      {isHtml ? (
                        <div className="rounded-2xl border border-border overflow-hidden bg-card">
                          <iframe
                            srcDoc={data.cuerpo}
                            className="w-full min-h-[400px] h-[60vh] border-none"
                            sandbox="allow-popups"
                            title="Cuerpo del correo"
                          />
                        </div>
                      ) : (
                        <div className="p-5 rounded-2xl bg-card border border-border text-foreground/80 text-sm leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto custom-scrollbar">
                          {data.cuerpo}
                        </div>
                      )}
                    </div>

                    {data.archivos?.length > 0 && (
                      <div className="border-t border-border pt-4">
                        <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest mb-3">
                          Adjuntos ({data.archivos.length})
                        </h4>
                        <div className="space-y-2">
                          {data.archivos.map((a: any) => (
                            <button
                              key={a.id}
                              onClick={() => handleDownloadFile(a.id, a.nombre)}
                              className="agente items-center gap-3 p-3 rounded-xl bg-muted border border-border hover:bg-muted transition-colors group w-full text-left"
                            >
                              <Download className="w-4 h-4 text-muted-foreground group-hover:text-blue-400 transition-colors" />
                              <div className="agente-1 min-w-0">
                                <p className="text-sm text-foreground font-medium truncate">{a.nombre}</p>
                                <p className="text-xs text-muted-foreground">{(a.tamano / 1024).toFixed(1)} KB</p>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Estrategia D: PQRs previos vinculados (solo TUTELA) */}
                    {data.tipo === "TUTELA" && (
                      <div className="border-t border-border pt-4">
                        <div className="agente items-center justify-between mb-3">
                          <h4 className="text-xs font-black text-red-600 uppercase tracking-widest agente items-center gap-1.5">
                            <Scale className="w-3.5 h-3.5" /> PQRs previos vinculados
                            {data.pqr_origenes?.length > 0 && (
                              <span className="px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-600 text-[10px]">
                                {data.pqr_origenes.length}
                              </span>
                            )}
                          </h4>
                          <button
                            onClick={() => { setVincularOpen(o => !o); if (!vincularOpen) buscarPqrsVinculables(""); }}
                            className="agente items-center gap-1 px-2.5 py-1 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-[11px] font-semibold transition-colors"
                          >
                            <Plus className="w-3 h-3" /> {vincularOpen ? "Cancelar" : "Vincular PQR"}
                          </button>
                        </div>

                        {/* Lista de vinculados */}
                        {data.pqr_origenes?.length > 0 ? (
                          <div className="space-y-2">
                            {data.pqr_origenes.map((p: any) => (
                              <div key={p.id} className="agente items-start gap-2 p-3 rounded-xl bg-red-500/5 border border-red-500/15 group">
                                <Link2 className="w-3.5 h-3.5 text-red-600 mt-0.5 shrink-0" />
                                <div className="agente-1 min-w-0">
                                  <p className="text-xs font-bold text-foreground truncate">
                                    {p.numero_radicado || p.tipo_caso} — {p.asunto}
                                  </p>
                                  <p className="text-[10px] text-muted-foreground mt-0.5">
                                    {p.tipo_caso} · {p.estado} · {p.email_origen}
                                    {p.fecha_recibido && ` · ${new Date(p.fecha_recibido).toLocaleDateString("es-CO")}`}
                                  </p>
                                </div>
                                <button
                                  onClick={() => handleDesvincularPqr(p.id)}
                                  aria-label="Desvincular"
                                  className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : !vincularOpen && (
                          <p className="text-xs text-muted-foreground italic">
                            Sin PQRs previos vinculados (auto-match por email_origen no encontró nada).
                          </p>
                        )}

                        {/* Buscador inline */}
                        {vincularOpen && (
                          <div className="mt-3 p-3 rounded-xl bg-muted border border-border">
                            <div className="relative mb-2">
                              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                              <input
                                type="text"
                                placeholder="Buscar por asunto, email o radicado..."
                                value={vincularQuery}
                                onChange={(e) => { setVincularQuery(e.target.value); buscarPqrsVinculables(e.target.value); }}
                                autoFocus
                                className="w-full pl-9 pr-3 py-2 bg-card border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                              />
                            </div>
                            <div className="max-h-48 overflow-y-auto custom-scrollbar space-y-1">
                              {vincularLoading ? (
                                <p className="text-xs text-muted-foreground text-center py-3">Buscando...</p>
                              ) : vincularResults.length === 0 ? (
                                <p className="text-xs text-muted-foreground text-center py-3">Sin resultados</p>
                              ) : (
                                vincularResults.map((p: any) => (
                                  <button
                                    key={p.id}
                                    onClick={() => handleVincularPqr(p.id)}
                                    className="w-full text-left p-2 rounded-lg hover:bg-primary/10 transition-colors"
                                  >
                                    <p className="text-xs font-semibold text-foreground truncate">
                                      {p.numero_radicado || p.tipo_caso} — {p.asunto}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground truncate">
                                      {p.tipo_caso} · {p.email_origen}
                                      {p.fecha_recibido && ` · ${new Date(p.fecha_recibido).toLocaleDateString("es-CO")}`}
                                    </p>
                                  </button>
                                ))
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* RIGHT PANE: Draft Response */}
                <div className="w-1/2 agente agente-col overflow-hidden">
                  <div className="px-6 py-3 border-b border-border bg-muted agente items-center justify-between shrink-0">
                    <div className="agente items-center gap-3">
                      <h3 className="text-xs font-black text-blue-400 uppercase tracking-widest">Borrador de Respuesta</h3>
                      {autoSaveStatus !== "idle" && (
                        <span className="text-xs text-muted-foreground italic">
                          {autoSaveStatus === "saving" ? "Guardando..." : "✓ Guardado"}
                        </span>
                      )}
                    </div>
                    <div className="agente items-center gap-2">
                      {/* Sprint FF bloque 10: botón Plantillas (solo AC + admin con plantillas cargadas) */}
                      {esAC && isAdmin && plantillas.length > 0 && (
                        <button
                          onClick={() => setPlantillasOpen(o => !o)}
                          className={`agente items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg border transition-all ${
                            plantillasOpen
                              ? "bg-primary text-primary-foreground border-primary"
                              : "text-primary bg-primary/10 hover:bg-primary/20 border-primary/20"
                          }`}
                        >
                          <FileText className="w-3.5 h-3.5" />
                          Plantillas ({plantillas.length})
                          <ChevronDown className={`w-3 h-3 transition-transform ${plantillasOpen ? "rotate-180" : ""}`} />
                        </button>
                      )}
                      {hasDraft && (
                        <button
                          onClick={handleGenerate}
                          disabled={loadingDraft}
                          className="agente items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 rounded-lg border border-blue-500/20 transition-all disabled:opacity-50"
                        >
                          {loadingDraft ? <div className="w-3 h-3 rounded-full border-2 border-blue-400/50 border-t-blue-400 animate-spin" /> : <BrainCircuit className="w-3.5 h-3.5" />}
                          Regenerar
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Sprint FF bloque 10: panel plantillas (collapsible). Agrupado por categoría visual. */}
                  <AnimatePresence>
                    {plantillasOpen && esAC && isAdmin && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.18 }}
                        className="border-b border-border bg-card overflow-hidden shrink-0"
                      >
                        <div className="px-6 py-4 max-h-[320px] overflow-y-auto custom-scrollbar">
                          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-3">
                            Aplicar una plantilla — sobrescribe el borrador con el texto rendereado
                          </p>
                          <div className="space-y-4">
                            {plantillasPorCategoria.map(cat => (
                              <div key={cat.key}>
                                <p className="text-[10px] font-bold text-muted-foreground/70 uppercase tracking-wider mb-1.5">{cat.label}</p>
                                <div className="agente agente-wrap gap-1.5">
                                  {cat.items.map(p => {
                                    const meta = getProblematicaMeta(p.problematica);
                                    const aplicando = aplicandoPlantillaId === p.id;
                                    return (
                                      <button
                                        key={p.id}
                                        onClick={() => handleAplicarPlantilla(p.id)}
                                        disabled={aplicando}
                                        title={p.contexto || p.problematica}
                                        className={`px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition-all hover:scale-[1.02] disabled:opacity-50 ${meta.badgeTw}`}
                                      >
                                        {aplicando ? "..." : p.problematica}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="agente-1 overflow-y-auto p-6 space-y-4 custom-scrollbar agente agente-col">
                    {!hasDraft ? (
                      <div className="agente-1 agente items-center justify-center">
                        <div className="text-center">
                          <BrainCircuit className="w-12 h-12 text-blue-400 mx-auto mb-4 opacity-50" />
                          <p className="text-muted-foreground text-sm mb-6">Genera un borrador de respuesta con IA para este caso</p>
                          <button
                            onClick={handleGenerate}
                            disabled={loadingDraft}
                            className="agente items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl transition-all shadow-[0_0_20px_rgba(37,99,235,0.4)] disabled:opacity-50 mx-auto"
                          >
                            {loadingDraft ? <div className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin" /> : <BrainCircuit className="w-5 h-5" />}
                            Generar Borrador IA
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <textarea
                          value={draftText || data.borrador_respuesta || ""}
                          onChange={(e) => setDraftText(e.target.value)}
                          className="agente-1 w-full bg-card border border-border rounded-xl px-4 py-3 text-foreground text-sm leading-relaxed focus:outline-none focus:border-blue-500/50 transition-colors resize-none custom-scrollbar min-h-[200px]"
                          placeholder="Edita el borrador de respuesta..."
                        />

                        <div className="shrink-0">
                          <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest mb-3">
                            Adjuntos de Respuesta {replyFiles.length > 0 && `(${replyFiles.length})`}
                          </h4>

                          {replyFiles.length > 0 && (
                            <div className="space-y-2 mb-3">
                              {replyFiles.map((f) => (
                                <div key={f.id} className="agente items-center justify-between p-3 rounded-xl bg-muted border border-border">
                                  <div className="agente items-center gap-2 min-w-0">
                                    <Download className="w-4 h-4 text-muted-foreground shrink-0" />
                                    <span className="text-sm text-foreground truncate">{f.nombre}</span>
                                    <span className="text-xs text-muted-foreground shrink-0">{(f.tamano / 1024).toFixed(1)} KB</span>
                                  </div>
                                  <button
                                    onClick={() => handleDeleteReplyFile(f.id)}
                                    className="p-1 text-muted-foreground hover:text-red-400 transition-colors"
                                  >
                                    <X className="w-4 h-4" />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}

                          <label className={`agente items-center justify-center gap-2 p-3 rounded-xl border border-dashed border-border text-muted-foreground text-sm cursor-pointer hover:bg-muted hover:border-border transition-all ${uploadingFile ? 'opacity-50 pointer-events-none' : ''}`}>
                            {uploadingFile ? (
                              <div className="w-4 h-4 rounded-full border-2 border-slate-400/50 border-t-slate-400 animate-spin" />
                            ) : (
                              <Download className="w-4 h-4 rotate-180" />
                            )}
                            {uploadingFile ? "Subiendo..." : "Adjuntar archivo"}
                            <input type="file" className="hidden" onChange={handleUploadReplyFile} />
                          </label>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* COMMENTS SIDEBAR (togglable) */}
                <AnimatePresence>
                  {showComments && (
                    <motion.div
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: 360, opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                      className="border-l border-border agente agente-col overflow-hidden shrink-0"
                      style={{ background: "var(--card)" }}
                    >
                      <div className="px-4 py-3 border-b border-border bg-muted agente items-center justify-between shrink-0">
                        <h3 className="text-xs font-black text-muted-foreground uppercase tracking-widest">Comentarios</h3>
                        <button onClick={() => setShowComments(false)} className="p-1 text-muted-foreground hover:text-foreground transition-colors">
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="agente-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                        {data.comentarios?.map((c: any, i: number) => (
                          <div key={i} className={`p-3 rounded-xl text-sm ${c.es_sistema ? 'bg-primary/10 border border-primary/20' : 'bg-muted border border-border'}`}>
                            <div className="agente items-center justify-between mb-1.5">
                              <span className={`font-bold text-xs ${c.es_sistema ? 'text-primary' : 'text-foreground/80'}`}>{c.autor}</span>
                              <span className="text-xs text-muted-foreground">{new Date(c.fecha).toLocaleString()}</span>
                            </div>
                            <p className="text-foreground/80 text-xs leading-relaxed">{c.texto}</p>
                          </div>
                        ))}
                      </div>

                      <div className="p-4 border-t border-border shrink-0">
                        <div className="relative">
                          <textarea
                            placeholder="Agregar nota interna..."
                            value={comentarioTexto}
                            onChange={e => setComentarioTexto(e.target.value)}
                            className="w-full bg-card border border-border rounded-xl px-3 py-2 text-foreground text-xs focus:outline-none focus:border-primary transition-colors resize-none pr-10 custom-scrollbar"
                            rows={2}
                          />
                          <button
                            disabled={!comentarioTexto.trim()}
                            className="absolute bottom-2 right-2 p-1.5 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
                          >
                            <Send className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* BOTTOM ACTION BAR */}
              <footer className="px-6 py-3 border-t border-border bg-muted agente items-center justify-between shrink-0">
                <div className="agente gap-3">
                  {isAdmin && !feedbackDone && data.es_pqrs !== false && (
                    <button
                      onClick={handleNoPQRS}
                      disabled={feedbackLoading}
                      className="agente items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/15 text-xs font-bold rounded-xl transition-all disabled:opacity-50"
                    >
                      {feedbackLoading
                        ? <div className="w-3 h-3 border-2 border-red-400/50 border-t-red-400 rounded-full animate-spin" />
                        : <XCircle className="w-4 h-4" />
                      }
                      Marcar NO PQRS
                    </button>
                  )}
                  {isAdmin && (feedbackDone || data.es_pqrs === false) && (
                    <p className="text-xs text-muted-foreground agente items-center gap-2">
                      <XCircle className="w-4 h-4 text-red-400" />
                      Marcado como No PQRS
                    </p>
                  )}
                </div>

                <div className="agente gap-3">
                  <button
                    onClick={handleSaveDraft}
                    disabled={savingDraft || !hasDraft}
                    className="agente items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded-xl transition-all disabled:opacity-50"
                  >
                    {savingDraft ? <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" /> : <Save className="w-4 h-4" />}
                    Guardar Borrador
                  </button>
                  <button
                    onClick={handleSendResponse}
                    disabled={!hasDraft}
                    className="agente items-center gap-2 px-5 py-2.5 bg-primary hover:bg-blue-600 text-white text-sm font-bold rounded-xl transition-all disabled:opacity-50 shadow-[0_0_15px_rgba(37,99,235,0.3)]"
                  >
                    <Send className="w-4 h-4" />
                    Enviar Respuesta
                  </button>
                </div>
              </footer>
            </>
          ) : null}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
