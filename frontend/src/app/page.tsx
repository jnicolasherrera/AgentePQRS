"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { useAuthStore } from "@/store/authStore";
import { motion } from "framer-motion";
import { LogOut, Activity, Users, Settings, Database, Server, Send, Radio, ChevronDown, Inbox } from "lucide-react";
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

  const tabs = isAbogado
    ? ["Dashboard", "Mis Casos", "Enviados", "Configuración"]
    : ["Dashboard", "Casos", "Enviados", "Bandeja", "Rendimiento", "Configuración"];

  const abogadoIcons = [
    <Activity key={0} className="w-5 h-5" />,
    <Database key={1} className="w-5 h-5" />,
    <Send key={2} className="w-5 h-5" />,
    <Settings key={3} className="w-5 h-5" />,
  ];
  const adminIcons = [
    <Activity key={0} className="w-5 h-5" />,
    <Radio key={1} className="w-5 h-5" />,
    <Send key={2} className="w-5 h-5" />,
    <Inbox key={3} className="w-5 h-5" />,
    <Users key={4} className="w-5 h-5" />,
    <Settings key={5} className="w-5 h-5" />,
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

  const icons = isAbogado ? abogadoIcons : adminIcons;

  return (
    <div className="h-screen w-full bg-background-dark text-white agente overflow-hidden">

      <div className="absolute top-[-200px] left-1/2 -translate-x-1/2 w-[900px] h-[600px] bg-gradient-to-b from-primary/12 to-transparent blur-[140px] rounded-full pointer-events-none z-0" />

      {/* SIDEBAR */}
      <aside className="w-64 shrink-0 glass-panel border-r border-white/5 agente agente-col items-center py-8 z-10 relative shadow-[10px_0_40px_rgba(0,0,0,0.6)]">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-transparent to-transparent pointer-events-none rounded-r-none" />
        <div className="text-2xl font-black tracking-tight mb-12 agente items-center gap-2 relative">
          <Image src="/logo.png" alt="Flex" width={28} height={28} className="rounded-md ring-2 ring-primary/20" />
          Flex<span className="text-primary drop-shadow-[0_0_8px_rgba(13,89,242,0.4)]">PQR</span>
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
                  ? "bg-primary border border-primary/50 shadow-[0_0_15px_rgba(13,89,242,0.5)] font-bold text-white"
                  : "hover:bg-white/5 text-slate-400 font-medium"
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
            className="w-full p-3 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 agente items-center justify-center gap-2 font-bold transition-colors"
          >
            <LogOut className="w-4 h-4" /> Cerrar Sesión
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
        <header className="agente items-center justify-between mb-10 border-b border-white/5 pb-6 shrink-0">
          <div>
            <h1 className="text-3xl font-extrabold text-white agente items-center gap-3">
              {TAB_TITLE[activeTab] ?? activeTab}
              <span className="px-3 py-1 bg-green-500/10 border border-green-500/30 text-green-400 text-xs rounded-full agente items-center gap-1">
                <Server className="w-3 h-3 animate-pulse" /> En línea
              </span>
            </h1>
            <p className="text-slate-400 mt-2 font-medium">Actualizaciones en tiempo real · Datos aislados por tenant</p>
          </div>

          <div className="agente items-center gap-3">
            {isSuperAdmin && clientes.length > 0 && (
              <div className="relative">
                <select
                  value={selectedClienteId}
                  onChange={(e) => setSelectedClienteId(e.target.value)}
                  className="appearance-none bg-[#161b26] border border-white/15 hover:border-primary/50 rounded-xl px-4 py-2 pr-8 text-sm text-white outline-none focus:border-primary transition-all cursor-pointer [&>option]:bg-[#161b26] [&>option]:text-white"
                >
                  <option value="">Todos los clientes</option>
                  {clientes.map(c => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              </div>
            )}
            <div className="agente items-center gap-4 glass-kpi px-4 py-2 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-purple-600 agente items-center justify-center font-bold text-xs ring-2 ring-primary/30 uppercase shadow-[0_0_12px_rgba(13,89,242,0.3)]">
                {user?.nombre ? user.nombre.split(" ").map((n: string) => n[0]).join("") : "NH"}
              </div>
              <div className="text-sm font-medium">{user?.nombre || "Usuario"}</div>
            </div>
          </div>
        </header>

        {activeTab === "Dashboard" && <DashboardMetrics selectedClienteId={selectedClienteId} />}

        {activeTab === "Casos" && (
          <div className="agente-1 w-full min-h-0">
            <LiveFeed tickets={tickets} connected={connected} onCasoStatusChange={handleCasoStatusChange} enableResponse selectedClienteId={selectedClienteId} />
          </div>
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
