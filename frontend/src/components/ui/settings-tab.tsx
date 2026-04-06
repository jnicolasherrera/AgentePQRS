"use client";

import { useAuthStore, api } from "@/store/authStore";
import {
  UserCog, MailOpen, LockKeyhole, BellRing, Users,
  CheckCircle2, XCircle, Eye, EyeOff, Save, Key, Shield, Info
} from "lucide-react";
import { useState, useEffect } from "react";

interface Buzon { email: string; proveedor: string; is_active: boolean }
interface TeamMember { id: string; nombre: string; email: string; rol: string; is_active: boolean; created_at: string | null }

function initials(name: string) {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

interface SettingsTabProps {
  initialSection?: string | null;
  onSectionViewed?: () => void;
}

export function SettingsTab({ initialSection, onSectionViewed }: SettingsTabProps) {
  const { user } = useAuthStore();
  const isAdmin = user?.rol === "admin" || user?.rol === "super_admin";

  const allSections = isAdmin
    ? ["profile", "buzones", "team", "notifications", "security", "about"]
    : ["profile", "notifications", "about"];

  const sectionLabels: Record<string, { label: string; icon: React.ReactNode }> = {
    profile:       { label: "Perfil",          icon: <UserCog className="w-4 h-4" /> },
    buzones:       { label: "Buzones",          icon: <MailOpen className="w-4 h-4" /> },
    team:          { label: "Equipo",           icon: <Users className="w-4 h-4" /> },
    notifications: { label: "Notificaciones",  icon: <BellRing className="w-4 h-4" /> },
    security:      { label: "Seguridad",        icon: <Shield className="w-4 h-4" /> },
    about:         { label: "Acerca de",        icon: <Info className="w-4 h-4" /> },
  };

  const [active, setActive] = useState("profile");

  useEffect(() => {
    if (initialSection) {
      setActive(initialSection);
      onSectionViewed?.();
    }
  }, [initialSection, onSectionViewed]);

  // --- Perfil ---
  const [nombre, setNombre] = useState(user?.nombre || "");
  const [savingNombre, setSavingNombre] = useState(false);
  const [nombreMsg, setNombreMsg] = useState<{ok: boolean; text: string} | null>(null);

  // --- Cambiar contraseña ---
  const [showPwForm, setShowPwForm] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showPws, setShowPws] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ok: boolean; text: string} | null>(null);
  const [savingPw, setSavingPw] = useState(false);

  // --- Buzones ---
  const [buzones, setBuzones] = useState<Buzon[]>([]);
  const [loadingBuzones, setLoadingBuzones] = useState(false);

  // --- Equipo ---
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [loadingTeam, setLoadingTeam] = useState(false);

  // --- Notificaciones (localStorage) ---
  const [notifSound, setNotifSound] = useState(() => localStorage.getItem("notif_sound") !== "false");
  const [notifCritical, setNotifCritical] = useState(() => localStorage.getItem("notif_critical") !== "false");
  const [notifSummary, setNotifSummary] = useState(() => localStorage.getItem("notif_summary") === "true");

  useEffect(() => { localStorage.setItem("notif_sound", String(notifSound)); }, [notifSound]);
  useEffect(() => { localStorage.setItem("notif_critical", String(notifCritical)); }, [notifCritical]);
  useEffect(() => { localStorage.setItem("notif_summary", String(notifSummary)); }, [notifSummary]);

  useEffect(() => {
    if (active === "buzones" && isAdmin && buzones.length === 0) {
      setLoadingBuzones(true);
      api.get("/admin/config/buzones").then(r => setBuzones(r.data)).catch(() => {}).finally(() => setLoadingBuzones(false));
    }
    if (active === "team" && isAdmin && team.length === 0) {
      setLoadingTeam(true);
      api.get("/admin/team").then(r => setTeam(r.data)).catch(() => {}).finally(() => setLoadingTeam(false));
    }
  }, [active, isAdmin, buzones.length, team.length]);

  async function saveNombre() {
    if (!nombre.trim()) return;
    setSavingNombre(true);
    try {
      await api.put("/admin/me/nombre", { nombre });
      setNombreMsg({ ok: true, text: "Nombre actualizado" });
    } catch {
      setNombreMsg({ ok: false, text: "Error al guardar" });
    }
    setSavingNombre(false);
    setTimeout(() => setNombreMsg(null), 3000);
  }

  async function changePassword() {
    if (newPw !== confirmPw) { setPwMsg({ ok: false, text: "Las contraseñas no coinciden" }); return; }
    if (newPw.length < 8) { setPwMsg({ ok: false, text: "Mínimo 8 caracteres" }); return; }
    setSavingPw(true);
    try {
      await api.post("/admin/me/password", { current_password: currentPw, new_password: newPw });
      setPwMsg({ ok: true, text: "Contraseña actualizada correctamente" });
      setCurrentPw(""); setNewPw(""); setConfirmPw(""); setShowPwForm(false);
    } catch (e: any) {
      setPwMsg({ ok: false, text: e?.response?.data?.detail || "Error al cambiar contraseña" });
    }
    setSavingPw(false);
    setTimeout(() => setPwMsg(null), 4000);
  }

  const inputCls = "w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary transition-colors";
  const labelCls = "text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block";

  return (
    <div className="agente gap-8 pb-10 min-h-[600px]">
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r border-white/5 pr-4 space-y-1">
        <h4 className="text-xs font-black text-slate-500 uppercase tracking-widest pl-3 mb-4">Ajustes</h4>
        {allSections.map(id => (
          <button
            key={id}
            onClick={() => setActive(id)}
            className={`w-full text-left px-3 py-2.5 rounded-xl font-medium agente items-center gap-3 transition-colors text-sm ${active === id ? "bg-primary text-white shadow-[0_0_15px_rgba(13,89,242,0.4)]" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}
          >
            {sectionLabels[id].icon} {sectionLabels[id].label}
          </button>
        ))}
      </div>

      {/* Contenido */}
      <div className="agente-1 min-w-0">

        {/* PERFIL */}
        {active === "profile" && (
          <div className="glass-panel p-8 rounded-3xl border border-white/5 space-y-8 max-w-lg">
            <div className="agente items-center gap-4 pb-6 border-b border-white/10">
              <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-primary to-purple-600 agente items-center justify-center font-black text-xl shadow-lg ring-4 ring-white/10">
                {initials(nombre || user?.nombre || "U")}
              </div>
              <div>
                <p className="text-white font-bold text-lg">{nombre || user?.nombre}</p>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/20 text-primary">{user?.rol}</span>
              </div>
            </div>

            <div className="space-y-5">
              <div>
                <label className={labelCls}>Nombre Completo</label>
                <input value={nombre} onChange={e => setNombre(e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Correo de Acceso</label>
                <input type="email" disabled value={user?.email || ""} className={`${inputCls} opacity-50`} />
              </div>
              <div>
                <label className={labelCls}>Tenant</label>
                <input disabled value={user?.cliente_nombre || user?.tenant_uuid || ""} className={`${inputCls} opacity-50`} />
              </div>
            </div>

            <div className="agente items-center gap-3">
              <button onClick={saveNombre} disabled={savingNombre} className="agente items-center gap-2 px-5 py-2.5 bg-primary text-white font-bold rounded-xl hover:bg-blue-600 transition-colors shadow-[0_4px_20px_rgba(13,89,242,0.3)] disabled:opacity-60">
                <Save className="w-4 h-4" /> {savingNombre ? "Guardando..." : "Guardar"}
              </button>
              <button onClick={() => setShowPwForm(v => !v)} className="agente items-center gap-2 px-5 py-2.5 border border-white/10 text-slate-300 font-bold rounded-xl hover:bg-white/5 transition-colors">
                <Key className="w-4 h-4" /> Cambiar Contraseña
              </button>
            </div>

            {nombreMsg && (
              <p className={`text-sm font-medium ${nombreMsg.ok ? "text-green-400" : "text-red-400"}`}>{nombreMsg.text}</p>
            )}

            {showPwForm && (
              <div className="space-y-4 pt-4 border-t border-white/10">
                <h4 className="font-bold text-white">Nueva Contraseña</h4>
                <div className="relative">
                  <input type={showPws ? "text" : "password"} placeholder="Contraseña actual" value={currentPw} onChange={e => setCurrentPw(e.target.value)} className={inputCls} />
                  <button onClick={() => setShowPws(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                    {showPws ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <input type={showPws ? "text" : "password"} placeholder="Nueva contraseña (mín. 8 chars)" value={newPw} onChange={e => setNewPw(e.target.value)} className={inputCls} />
                <input type={showPws ? "text" : "password"} placeholder="Confirmar nueva contraseña" value={confirmPw} onChange={e => setConfirmPw(e.target.value)} className={inputCls} />
                <div className="agente items-center gap-3">
                  <button onClick={changePassword} disabled={savingPw} className="px-5 py-2.5 bg-primary text-white font-bold rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-60">
                    {savingPw ? "Guardando..." : "Confirmar"}
                  </button>
                  <button onClick={() => setShowPwForm(false)} className="px-5 py-2.5 border border-white/10 text-slate-400 font-bold rounded-xl hover:bg-white/5 transition-colors">
                    Cancelar
                  </button>
                </div>
                {pwMsg && <p className={`text-sm font-medium ${pwMsg.ok ? "text-green-400" : "text-red-400"}`}>{pwMsg.text}</p>}
              </div>
            )}
          </div>
        )}

        {/* BUZONES */}
        {active === "buzones" && (
          <div className="space-y-4">
            <h2 className="text-xl font-black text-white agente items-center gap-2">
              <MailOpen className="w-5 h-5 text-primary" /> Buzones configurados
            </h2>
            {loadingBuzones ? (
              <p className="text-slate-400 text-sm">Cargando...</p>
            ) : buzones.length === 0 ? (
              <p className="text-slate-400 text-sm">No hay buzones configurados para este tenant.</p>
            ) : (
              <div className="grid gap-3">
                {buzones.map(b => (
                  <div key={b.email} className="glass-panel p-5 rounded-2xl border border-white/5 agente items-center justify-between">
                    <div className="agente items-center gap-4">
                      <div className={`w-10 h-10 rounded-xl agente items-center justify-center font-bold text-xs ${b.proveedor === "OUTLOOK" ? "bg-blue-500/20 text-blue-400" : "bg-orange-500/20 text-orange-400"}`}>
                        {b.proveedor === "OUTLOOK" ? "OL" : "ZH"}
                      </div>
                      <div>
                        <p className="text-white font-semibold text-sm">{b.email}</p>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${b.proveedor === "OUTLOOK" ? "bg-blue-500/10 text-blue-400" : "bg-orange-500/10 text-orange-400"}`}>{b.proveedor}</span>
                      </div>
                    </div>
                    <div className="agente items-center gap-2">
                      {b.is_active ? (
                        <><CheckCircle2 className="w-4 h-4 text-green-400" /><span className="text-green-400 text-xs font-bold">Activo</span></>
                      ) : (
                        <><XCircle className="w-4 h-4 text-red-400" /><span className="text-red-400 text-xs font-bold">Inactivo</span></>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* EQUIPO */}
        {active === "team" && (
          <div className="space-y-4">
            <h2 className="text-xl font-black text-white agente items-center gap-2">
              <Users className="w-5 h-5 text-primary" /> Equipo de Abogados
            </h2>
            {loadingTeam ? (
              <p className="text-slate-400 text-sm">Cargando...</p>
            ) : team.length === 0 ? (
              <p className="text-slate-400 text-sm">No hay abogados registrados en este tenant.</p>
            ) : (
              <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="text-left px-5 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Nombre</th>
                      <th className="text-left px-5 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Email</th>
                      <th className="text-left px-5 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {team.map(m => (
                      <tr key={m.id} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                        <td className="px-5 py-3">
                          <div className="agente items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-purple-600 agente items-center justify-center font-bold text-xs">
                              {initials(m.nombre)}
                            </div>
                            <span className="text-white font-medium">{m.nombre}</span>
                          </div>
                        </td>
                        <td className="px-5 py-3 text-slate-400">{m.email}</td>
                        <td className="px-5 py-3">
                          {m.is_active
                            ? <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 text-xs font-bold">Activo</span>
                            : <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 text-xs font-bold">Inactivo</span>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* NOTIFICACIONES */}
        {active === "notifications" && (
          <div className="glass-panel p-8 rounded-3xl border border-white/5 max-w-lg space-y-6">
            <h2 className="text-xl font-black text-white agente items-center gap-2">
              <BellRing className="w-5 h-5 text-primary" /> Notificaciones
            </h2>
            {[
              { label: "Notificación visual al recibir caso", desc: "Mostrar alerta en pantalla al ingresar un nuevo PQR", value: notifSound, set: setNotifSound },
              { label: "Alerta de caso crítico / tutela", desc: "Notificación visual para casos de alta prioridad", value: notifCritical, set: setNotifCritical },
              { label: "Resumen diario por email", desc: "Recibir un resumen de actividad al final del día", value: notifSummary, set: setNotifSummary },
            ].map(({ label, desc, value, set }) => (
              <div key={label} className="agente items-center justify-between py-3 border-b border-white/5 last:border-0">
                <div>
                  <p className="text-white font-semibold text-sm">{label}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{desc}</p>
                </div>
                <button
                  onClick={() => set(v => !v)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${value ? "bg-primary" : "bg-white/10"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform shadow ${value ? "translate-x-5" : "translate-x-0"}`} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* SEGURIDAD */}
        {active === "security" && (
          <div className="glass-panel p-8 rounded-3xl border border-white/5 max-w-lg space-y-6">
            <h2 className="text-xl font-black text-white agente items-center gap-2">
              <LockKeyhole className="w-5 h-5 text-primary" /> Seguridad y RLS
            </h2>
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-green-500/10 border border-green-500/20 agente items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-green-400 shrink-0" />
                <div>
                  <p className="text-white font-bold text-sm">RLS Activo</p>
                  <p className="text-green-400 text-xs">Row-Level Security habilitado en todas las tablas</p>
                </div>
              </div>
              <div>
                <label className={labelCls}>Tenant UUID</label>
                <input disabled value={user?.tenant_uuid || ""} className={`${inputCls} opacity-50 font-mono text-xs`} />
              </div>
              <div>
                <label className={labelCls}>Rol</label>
                <input disabled value={user?.rol || ""} className={`${inputCls} opacity-50`} />
              </div>
              <div>
                <label className={labelCls}>Política de aislamiento</label>
                <p className="text-slate-400 text-xs bg-white/5 rounded-xl p-3 font-mono">
                  cliente_id = current_tenant_id OR is_superuser = true
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ACERCA DE */}
        {active === "about" && (
          <div className="glass-panel p-8 rounded-3xl border border-white/5 max-w-lg space-y-8">
            <div className="agente items-center gap-4 pb-6 border-b border-white/10">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-primary to-purple-600 agente items-center justify-center shadow-lg ring-4 ring-primary/20">
                <span className="text-2xl">&#9878;</span>
              </div>
              <div>
                <h2 className="text-2xl font-black text-white">FlexPQR</h2>
                <p className="text-sm text-slate-400">Powered by <span className="text-primary font-bold">Aequitas Engine</span></p>
              </div>
            </div>

            <div className="space-y-3">
              {[
                { label: "Versión",       value: "1.0.0" },
                { label: "Build",         value: "2026.03.18" },
                { label: "Engine",        value: "Aequitas" },
                { label: "Stack",         value: "FastAPI + Next.js" },
                { label: "Base de Datos", value: "PostgreSQL 15 (RLS)" },
                { label: "AI Engine",     value: "Claude (Anthropic)" },
              ].map(({ label, value }) => (
                <div key={label} className="agente items-center justify-between py-2 px-4 rounded-xl bg-white/3 border border-white/5">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{label}</span>
                  <span className="text-sm text-white font-semibold">{value}</span>
                </div>
              ))}
            </div>

            <div>
              <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3">Módulos activos</h3>
              <div className="grid grid-cols-1 gap-2">
                {[
                  "Clasificación IA híbrida",
                  "SSE Real-time streaming",
                  "Multi-tenant RLS",
                  "Kafka Event Pipeline",
                  "Webhook Ingestor (MS/Google)",
                  "Smart Templates Engine",
                ].map((mod) => (
                  <div key={mod} className="agente items-center gap-2 text-sm">
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0" />
                    <span className="text-slate-300">{mod}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-white/5 space-y-2">
              <p className="text-[11px] text-slate-400 text-center font-semibold">
                Una creación de <span className="text-white">FlexFintech S.A.S</span>
              </p>
              <p className="text-[11px] text-slate-500 text-center">
                Creador: Juan Nicolás Herrera
              </p>
              <p className="text-[10px] text-slate-600 text-center">
                &copy; 2026 FlexFintech S.A.S. Todos los derechos reservados.
              </p>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
