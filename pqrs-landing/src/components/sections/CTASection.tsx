"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { FadeInUp } from "@/components/ui/magic-components";
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react";

export function CTASection() {
  const [form, setForm] = useState({ nombre: "", cargo: "", empresa: "", email: "", telefono: "", volumen: "", mensaje: "" });
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");

  const inputCls = "w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-600 focus:outline-none focus:border-primary/50 transition-colors";
  const selectCls = "w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary/50 transition-colors appearance-none cursor-pointer [&>option]:bg-[#011640] [&>option]:text-white";

  function openMailto() {
    const to = "nicolas.herrera@flexfintech.com";
    const subject = encodeURIComponent(`Solicitar Demo FlexPQR — ${form.empresa}`);
    const lines = [
      `Nombre: ${form.nombre}`,
      form.cargo ? `Cargo: ${form.cargo}` : "",
      `Empresa: ${form.empresa}`,
      `Email: ${form.email}`,
      form.telefono ? `Teléfono: ${form.telefono}` : "",
      form.volumen ? `Volumen PQRS: ${form.volumen}` : "",
      form.mensaje ? `\n${form.mensaje}` : "",
    ].filter(Boolean).join("\n");
    const body = encodeURIComponent(lines);
    window.open(`mailto:${to}?subject=${subject}&body=${body}`, "_self");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.nombre || !form.empresa || !form.email) return;
    setStatus("loading");
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.fallback) {
          openMailto();
        }
        setStatus("ok");
      } else {
        openMailto();
        setStatus("ok");
      }
    } catch {
      openMailto();
      setStatus("ok");
    }
  }

  return (
    <section id="contacto" className="w-full max-w-7xl px-6 py-32 mb-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">

        {/* Left: copy */}
        <FadeInUp delay={0.1}>
          <div className="agente agente-col gap-6">
            <p className="text-xs font-bold text-primary uppercase tracking-widest">Agenda una demo</p>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight leading-tight">
              ¿Cuántos correos llegaron esta semana sin respuesta?
            </h2>
            <p className="text-slate-400 text-lg leading-relaxed">
              30 minutos. Te mostramos FlexPQR funcionando en tu bandeja real —
              clasificando, asignando y alertando sobre vencimientos.
            </p>

            <div className="agente agente-col gap-3 mt-4">
              {[
                "Sin costo. Sin compromiso.",
                "Ves el sistema con tus correos reales",
                "Configuración lista en el mismo día",
                "Soporte en español, equipo colombiano",
              ].map((item, i) => (
                <div key={i} className="agente items-center gap-3 text-slate-300 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </FadeInUp>

        {/* Right: form — 3 campos, fricción mínima */}
        <FadeInUp delay={0.3}>
          <div className="rounded-2xl border border-white/10 p-8 bg-surface-dark/80 backdrop-blur-sm hover:border-primary/20 transition-all duration-500 shadow-[0_20px_60px_rgba(0,0,0,0.5)]">
            {status === "ok" ? (
              <div className="agente agente-col items-center gap-4 py-10 text-center">
                <CheckCircle2 className="w-12 h-12 text-green-400" />
                <h3 className="text-xl font-bold text-white">¡Listo!</h3>
                <p className="text-slate-400 text-sm">Te contactamos en menos de 24 horas para coordinar la demo.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="agente agente-col gap-5">
                <div>
                  <h3 className="text-lg font-bold text-white">Solicitar demo gratuita</h3>
                  <p className="text-slate-500 text-sm mt-1">El resto lo hablamos en la llamada.</p>
                </div>

                <div>
                  <label htmlFor="nombre" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Nombre *</label>
                  <input
                    id="nombre"
                    value={form.nombre}
                    onChange={e => setForm(p => ({ ...p, nombre: e.target.value }))}
                    placeholder="Juan Herrera"
                    required
                    className={inputCls}
                  />
                </div>

                <div>
                  <label htmlFor="empresa" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Entidad / Empresa *</label>
                  <input
                    id="empresa"
                    value={form.empresa}
                    onChange={e => setForm(p => ({ ...p, empresa: e.target.value }))}
                    placeholder="Alcaldía de Medellín"
                    required
                    className={inputCls}
                  />
                </div>

                <div>
                  <label htmlFor="email" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Correo electrónico *</label>
                  <input
                    id="email"
                    type="email"
                    value={form.email}
                    onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                    placeholder="juan@entidad.gov.co"
                    required
                    className={inputCls}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="cargo" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Cargo</label>
                    <input
                      id="cargo"
                      value={form.cargo}
                      onChange={e => setForm(p => ({ ...p, cargo: e.target.value }))}
                      placeholder="Director Jurídico"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label htmlFor="telefono" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Teléfono</label>
                    <input
                      id="telefono"
                      type="tel"
                      value={form.telefono}
                      onChange={e => setForm(p => ({ ...p, telefono: e.target.value }))}
                      placeholder="+57 300 123 4567"
                      className={inputCls}
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="volumen" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Volumen mensual de PQRS</label>
                  <select
                    id="volumen"
                    value={form.volumen}
                    onChange={e => setForm(p => ({ ...p, volumen: e.target.value }))}
                    className={`${selectCls} ${form.volumen ? "text-white" : "text-slate-600"}`}
                  >
                    <option value="">Seleccionar rango</option>
                    <option value="Menos de 100">Menos de 100 / mes</option>
                    <option value="100 - 500">100 – 500 / mes</option>
                    <option value="500 - 2,000">500 – 2,000 / mes</option>
                    <option value="2,000 - 10,000">2,000 – 10,000 / mes</option>
                    <option value="Más de 10,000">Más de 10,000 / mes</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="mensaje" className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">¿Qué problema quieres resolver?</label>
                  <textarea
                    id="mensaje"
                    value={form.mensaje}
                    onChange={e => setForm(p => ({ ...p, mensaje: e.target.value }))}
                    placeholder="Cuéntanos brevemente tu situación actual..."
                    rows={3}
                    className={`${inputCls} resize-none`}
                  />
                </div>

                {status === "error" && (
                  <div className="agente agente-col gap-2">
                    <p className="text-red-400 text-xs">Error al enviar el formulario.</p>
                    <a
                      href="mailto:nicolas.herrera@flexfintech.com?subject=Solicitar Demo FlexPQR"
                      className="text-primary text-xs font-semibold hover:underline"
                    >
                      Escríbenos directamente a nicolas.herrera@flexfintech.com
                    </a>
                  </div>
                )}

                <motion.button
                  type="submit"
                  disabled={status === "loading"}
                  whileHover={{ scale: 1.02, boxShadow: "0 0 30px rgba(3, 90, 167,0.35)" }}
                  whileTap={{ scale: 0.98 }}
                  className="h-12 rounded-xl bg-primary text-white font-bold agente items-center justify-center gap-2 shadow-[0_0_20px_rgba(3, 90, 167,0.2)] disabled:opacity-60 cursor-pointer"
                >
                  {status === "loading" ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Enviando...</>
                  ) : (
                    <>Agendar demo <ArrowRight className="w-4 h-4" /></>
                  )}
                </motion.button>
              </form>
            )}
          </div>
        </FadeInUp>
      </div>
    </section>
  );
}
