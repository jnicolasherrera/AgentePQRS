"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { useAuthStore } from "@/store/authStore";
import { motion } from "framer-motion";
import { LogOut, Activity, Users, Settings, Database, Server, Send, ChevronDown, Inbox } from "lucide-react";
import { LiveFeed } from "@/components/ui/live-feed";
import { DashboardMetrics } from "@/components/ui/dashboard-metrics";
import { SettingsTab } from "@/components/ui/settings-tab";
import { RendimientoTab } from "@/components/ui/rendimiento-tab";
import { EnviadosTab } from "@/components/ui/enviados-tab";
import { AdminBandeja } from "@/components/ui/admin-bandeja";
import { useAdminClientes } from "@/hooks/useDashboardStats";
import { ToastContainer } from "@/components/ui/toast-urgente";
import { ChangePasswordModal } from "@/components/ui/change-password-modal";
import { useSSEStream } from "@/hooks/useSSEStream";
import type { ToastData } from "@/components/ui/toast-urgente";

const TAB_TITLE: Record<string, string> = {
  "Dashboard":     "Resumen Operativo",
  "Casos":         "Todos los Casos",
  "Mis Casos":     "Mis Casos Activos",

  "Enviados":      "Historial de Enviados",
  "Bandeja":       "Bandeja Administrativa",
  "Rendimiento":   "Rendimiento del Equipo",
  "Configuración": "Configuración",
};

export default function DashboardPage() {
  const { isAuthenticated, user, logout, setAuth } = useAuthStore();
  const [mounted, setMounted] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  useEffect(() => {
    if (!mounted) return;
    if (!isAuthenticated) window.location.href = "/login";
  }, [mounted, isAuthenticated]);

  // Mostrar modal de cambio de password si es primer inicio
  useEffect(() => {
    if (mounted && user?.debe_cambiar_password) {
      setShowChangePassword(true);
    }
  }, [mounted, user?.debe_cambiar_password]);

  const isAbogado = user?.rol === "analista";
  // Operador (rol `abogado`, p.ej. Recovery): usa la Bandeja con SU cartera, sin
  // acciones admin ni Rendimiento/Configuración del tenant.
  const esOperador = user?.rol === "abogado";

  const tabs = isAbogado
    ? ["Dashboard", "Mis Casos", "Enviados", "Configuración"]
    : esOperador
    ? ["Dashboard", "Bandeja", "Enviados"]
    : ["Dashboard", "Bandeja", "Enviados", "Rendimiento", "Configuración"];

  const abogadoIcons = [
    <Activity key={0} className="w-5 h-5" />,
    <Database key={1} className="w-5 h-5" />,
    <Send key={2} className="w-5 h-5" />,
    <Settings key={3} className="w-5 h-5" />,
  ];
  const adminIcons = [
    <Activity key={0} className="w-5 h-5" />,
    <Inbox key={1} className="w-5 h-5" />,
    <Send key={2} className="w-5 h-5" />,
    <Users key={3} className="w-5 h-5" />,
    <Settings key={4} className="w-5 h-5" />,
  ];

  const [activeTab, setActiveTab] = useState("Dashboard");
  const [settingsSection, setSettingsSection] = useState<string | null>(null);
  const isSuperAdmin = user?.rol === "super_admin";
  const [selectedClienteId, setSelectedClienteId] = useState("");
  const clientes = useAdminClientes(isSuperAdmin);

  const [toasts, setToasts] = useState<ToastData[]>([]);

  const handleTutelaUrgente = useCallback(
    ({ caso_id, asunto }: { caso_id: string; asunto: string }) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, mensaje: asunto, casoId: caso_id }]);
    },
    []
  );

  const { tickets, connected, removeTicket } = useSSEStream({ onTutelaUrgente: handleTutelaUrgente });

  const handleCasoStatusChange = useCallback((casoId: string, changes: Record<string, unknown>) => {
    if (changes.es_pqrs === false || changes._deleted) removeTicket(casoId);
  }, [removeTicket]);

  if (!mounted || !isAuthenticated) return null;

  // Operador reusa los 3 primeros íconos admin (Dashboard, Bandeja, Enviados).
  const icons = isAbogado ? abogadoIcons : esOperador ? adminIcons.slice(0, 3) : adminIcons;

  return (
    <div className="h-screen w-full metallic-surface text-foreground agente overflow-hidden relative">

      {/* Aurora orbs detrás del sidebar — el liquid glass los refracta */}
      <span aria-hidden className="liquid-aurora liquid-aurora-1" />
      <span aria-hidden className="liquid-aurora liquid-aurora-2" />
      <span aria-hidden className="liquid-aurora liquid-aurora-3" />

      {/* SIDEBAR — Liquid Glass navy de marca */}
      <aside className="w-64 shrink-0 liquid-glass-nav text-white agente agente-col items-center py-8 z-10 relative">
        <div className="text-2xl font-black tracking-tight mb-12 agente items-center gap-2 relative">
          <Image src="/logo.png" alt="Flex" width={28} height={28} className="rounded-md ring-2 ring-white/20" />
          Flex<span className="text-brand-cyan drop-shadow-[0_0_8px_rgba(6,182,212,0.5)]">PQR</span>
        </div>

        <nav className="agente-1 w-full px-4 space-y-2">
          {tabs.map((item, i) => (
            <motion.button
              key={item}
              whileHover={{ x: 4 }}
              onClick={() => setActiveTab(item)}
              aria-current={activeTab === item ? "page" : undefined}
              className={`w-full p-3 rounded-lg agente items-center gap-3 transition-colors text-left ${
                activeTab === item
                  ? "bg-primary border border-primary/50 shadow-[0_0_15px_rgba(3,90,167,0.55)] font-bold text-white"
                  : "hover:bg-white/10 text-white/60 font-medium"
              }`}
            >
              {icons[i]}
              {item}
            </motion.button>
          ))}
        </nav>

        <div className="w-full px-4 mt-auto space-y-3">
          <button
            onClick={logout}
            aria-label="Cerrar sesión"
            className="w-full px-3 py-2.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 agente items-center justify-center gap-2 text-sm font-medium transition-all duration-200 group"
          >
            <LogOut className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" /> Cerrar sesión
          </button>
          <button
            onClick={() => { setActiveTab("Configuración"); setSettingsSection("about"); }}
            className="w-full text-center py-2 text-[10px] text-white/25 hover:text-white/50 transition-colors cursor-pointer"
          >
            Aequitas Engine · v1.0.0
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <main className="agente-1 min-h-0 px-12 py-10 z-10 overflow-y-auto agente agente-col custom-scrollbar">
        <header className="agente items-center justify-between mb-8 pb-6 shrink-0 relative">
          <div className="min-w-0">
            {activeTab === "Dashboard" ? (
              <>
                <p className="text-[13px] text-muted-foreground/80 font-medium tracking-wide">
                  {(() => {
                    const h = new Date().getHours();
                    const saludo = h < 12 ? "Buen día" : h < 19 ? "Buenas tardes" : "Buenas noches";
                    const firstName = (user?.nombre || "").split(" ")[0] || "";
                    return `${saludo}${firstName ? `, ${firstName}` : ""}`;
                  })()}
                </p>
                <h1 className="text-[2.25rem] leading-tight font-black tracking-tight text-foreground mt-1">
                  Resumen <span className="bg-gradient-to-r from-primary via-blue-500 to-brand-cyan bg-clip-text text-transparent">operativo</span>
                </h1>
                <div className="agente items-center gap-3 mt-2.5 text-xs text-muted-foreground">
                  <span className="agente items-center gap-1.5">
                    <span className="relative agente items-center justify-center w-2 h-2">
                      <span className="absolute inset-0 rounded-full bg-green-500 animate-ping opacity-60"></span>
                      <span className="relative w-2 h-2 rounded-full bg-green-500"></span>
                    </span>
                    En vivo
                  </span>
                  <span className="text-border">·</span>
                  <span className="font-medium text-foreground/70">{user?.cliente_nombre || "Tenant"}</span>
                  <span className="text-border">·</span>
                  <span>Datos aislados por cliente</span>
                </div>
              </>
            ) : (
              <>
                <h1 className="text-3xl font-extrabold text-foreground agente items-center gap-3">
                  {TAB_TITLE[activeTab] ?? activeTab}
                  <span className="px-3 py-1 bg-green-500/10 border border-green-500/30 text-green-600 text-xs rounded-full agente items-center gap-1">
                    <Server className="w-3 h-3 animate-pulse" /> En línea
                  </span>
                </h1>
                <p className="text-muted-foreground mt-2 font-medium">Actualizaciones en tiempo real · Datos aislados por tenant</p>
              </>
            )}
          </div>

          <div className="agente items-center gap-3">
            {isSuperAdmin && clientes.length > 0 && (
              <div className="relative">
                <select
                  value={selectedClienteId}
                  onChange={(e) => setSelectedClienteId(e.target.value)}
                  className="appearance-none bg-card border border-border hover:border-primary/50 rounded-xl px-4 py-2 pr-8 text-sm text-foreground outline-none focus:border-primary transition-all cursor-pointer [&>option]:bg-card [&>option]:text-foreground"
                >
                  <option value="">Todos los clientes</option>
                  {clientes.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              </div>
            )}
            <div className="agente items-center gap-4 bg-card border border-border px-4 py-2 rounded-xl shadow-sm">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-brand-cyan text-white agente items-center justify-center font-bold text-xs ring-2 ring-primary/20 uppercase shadow-[0_0_12px_rgba(3,90,167,0.3)]">
                {user?.nombre ? user.nombre.split(" ").map((n: string) => n[0]).join("") : "NH"}
              </div>
              <div className="text-sm font-medium">{user?.nombre || "Usuario"}</div>
            </div>
          </div>
        </header>

        {activeTab === "Dashboard" && (
          <DashboardMetrics
            selectedClienteId={selectedClienteId}
            onVerTodos={() => setActiveTab(isAbogado ? "Mis Casos" : "Bandeja")}
          />
        )}

        {activeTab === "Mis Casos" && (
          <div className="agente-1 w-full min-h-0">
            <LiveFeed tickets={tickets} connected={connected} onCasoStatusChange={handleCasoStatusChange} enableResponse />
          </div>
        )}


        {activeTab === "Enviados" && (
          <div className="agente-1 w-full min-h-0">
            <EnviadosTab selectedClienteId={selectedClienteId} />
          </div>
        )}

        {activeTab === "Bandeja" && (
          <div className="agente-1 w-full min-h-0">
            <AdminBandeja selectedClienteId={selectedClienteId} />
          </div>
        )}

        {activeTab === "Rendimiento" && (
          <div className="agente-1 w-full min-h-0">
            <RendimientoTab selectedClienteId={selectedClienteId} />
          </div>
        )}

        {activeTab === "Configuración" && (
          <div className="agente-1 w-full min-h-0">
            <SettingsTab initialSection={settingsSection} onSectionViewed={() => setSettingsSection(null)} />
          </div>
        )}
      </main>

      <ToastContainer
        toasts={toasts}
        onRemove={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
      />

      {showChangePassword && (
        <ChangePasswordModal onSuccess={() => setShowChangePassword(false)} />
      )}
    </div>
  );
}
