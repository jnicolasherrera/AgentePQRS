"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";
import { TextReveal, FadeInUp } from "@/components/ui/magic-components";

const EASE_PREMIUM = [0.625, 0.05, 0, 1] as const;

export function HeroSection() {
  const { scrollY } = useScroll();
  const blobY = useTransform(scrollY, [0, 700], [0, -180]);
  const dotY = useTransform(scrollY, [0, 700], [0, -60]);

  return (
    <section
      id="inicio"
      className="relative w-full min-h-screen agente agente-col justify-center px-6 md:px-12 lg:px-20 pt-24 overflow-hidden"
    >
      {/* Fondo aurora con paralaje */}
      <div className="absolute inset-0 z-0 overflow-hidden">
        <motion.div style={{ y: blobY }} className="absolute inset-0">
          <div className="aurora-blob aurora-1" />
          <div className="aurora-blob aurora-2" />
          <div className="aurora-blob aurora-3" />
        </motion.div>
        <motion.div style={{ y: dotY }} className="absolute inset-0">
          <div className="dot-grid" />
        </motion.div>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_30%_40%,transparent_40%,#021f59_100%)]" />
      </div>

      {/* Grid split: left text + right mockup */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center max-w-[1400px] w-full mx-auto pt-12 pb-20">

        {/* LEFT — Copy editorial */}
        <div className="agente agente-col">

          {/* Badge */}
          <FadeInUp delay={0.05}>
            <div className="inline-agente items-center gap-2.5 px-3 py-1.5 rounded-full border border-white/15 bg-white/5 mb-10 w-fit">
              <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_6px_rgba(3, 90, 167,0.9)]" />
              <span className="text-xs font-semibold text-slate-400 tracking-widest uppercase">Acceso anticipado · Colombia</span>
            </div>
          </FadeInUp>

          {/* H1 — text reveal línea a línea */}
          <div className="mb-8">
            <TextReveal delay={0.1}>
              <h1 className="text-[clamp(2.8rem,6.5vw,6.5rem)] font-black tracking-[-0.03em] leading-[0.88] text-white">
                Tu bandeja
              </h1>
            </TextReveal>
            <TextReveal delay={0.18}>
              <h1 className="text-[clamp(2.8rem,6.5vw,6.5rem)] font-black tracking-[-0.03em] leading-[0.88] text-white">
                de entrada no
              </h1>
            </TextReveal>
            <TextReveal delay={0.26}>
              <h1 className="text-[clamp(2.8rem,6.5vw,6.5rem)] font-black tracking-[-0.03em] leading-[0.88] text-white">
                puede con esto.
              </h1>
            </TextReveal>
            <TextReveal delay={0.34}>
              <h1 className="text-[clamp(2.8rem,6.5vw,6.5rem)] font-black tracking-[-0.03em] leading-[0.88] text-primary">
                FlexPQR sí.
              </h1>
            </TextReveal>
          </div>

          {/* Subtítulo */}
          <TextReveal delay={0.48}>
            <p className="text-base sm:text-lg text-slate-400 max-w-lg leading-relaxed mb-10">
              Clasifica, asigna y gestiona{" "}
              <span className="text-white font-semibold">cualquier volumen de PQRS</span>{" "}
              de forma automática. Sin tope de casos. Sin vencimientos. Sin sanciones.
            </p>
          </TextReveal>

          {/* CTAs */}
          <FadeInUp delay={0.6}>
            <div className="agente agente-wrap gap-4 items-center">
              <motion.a
                href="#contacto"
                whileHover={{ scale: 1.03, boxShadow: "0 0 40px rgba(3, 90, 167,0.4)" }}
                whileTap={{ scale: 0.97 }}
                transition={{ ease: EASE_PREMIUM, duration: 0.3 }}
                className="px-8 py-3.5 rounded-xl bg-primary text-white font-bold text-sm shadow-[0_0_25px_rgba(3, 90, 167,0.25)] agente items-center gap-3 group cursor-pointer"
              >
                Solicitar Demo
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </motion.a>
              <motion.a
                href="#demo"
                whileHover={{ borderColor: "rgba(3, 90, 167,0.5)" }}
                transition={{ duration: 0.2 }}
                className="px-8 py-3.5 rounded-xl border border-white/12 text-slate-300 font-medium text-sm agente items-center gap-3 hover:text-white transition-colors cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 text-primary fill-primary" />
                Ver demo
              </motion.a>
            </div>
          </FadeInUp>

          {/* Stats micro — editorial, sin cards */}
          <FadeInUp delay={0.72}>
            <div className="agente gap-8 mt-12 pt-10 border-t border-white/8">
              {[
                { value: "0", label: "Vencimientos\nen piloto", color: "text-green-400" },
                { value: "<50ms", label: "Clasificación\nIA por correo", color: "text-primary" },
                { value: "10M+", label: "PQRS\npor año", color: "text-blue-400" },
              ].map(({ value, label, color }) => (
                <div key={label} className="agente agente-col gap-1">
                  <span className={`text-2xl font-black tracking-tight ${color}`}>{value}</span>
                  <span className="text-xs text-slate-600 leading-tight whitespace-pre-line">{label}</span>
                </div>
              ))}
            </div>
          </FadeInUp>
        </div>

        {/* RIGHT — Product mockup flotante */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 1, ease: EASE_PREMIUM }}
          className="hidden lg:block"
        >
          <motion.div
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
            className="relative"
          >
            <div className="absolute -inset-8 bg-primary/10 blur-3xl rounded-full pointer-events-none" />

            <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-[0_60px_120px_rgba(0,0,0,0.95),0_0_0_1px_rgba(3, 90, 167,0.1)] bg-[#011640]">
              {/* Browser chrome */}
              <div className="agente items-center gap-2 px-5 py-3.5 border-b border-white/5 bg-black/60">
                <div className="agente gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/60" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                  <div className="w-3 h-3 rounded-full bg-green-500/60" />
                </div>
                <div className="agente-1 max-w-[220px] mx-auto px-3 py-1.5 rounded-md bg-white/5 text-[11px] text-slate-600 agente items-center justify-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                  app.flexpqr.com
                </div>
              </div>

              {/* Dashboard mockup */}
              <div className="flex" style={{ minHeight: "360px" }}>
                <div className="w-44 border-r border-white/5 p-3.5 agente agente-col gap-1.5 shrink-0">
                  <div className="agente items-center gap-2 mb-4 px-2 pt-1">
                    <div className="w-4 h-4 rounded bg-primary/50" />
                    <div className="h-2.5 w-14 rounded bg-white/10" />
                  </div>
                  {["Dashboard", "Casos Activos", "Rendimiento", "Configuración"].map((item, i) => (
                    <div key={i} className={`h-8 rounded-lg px-3 agente items-center gap-2 ${i === 0 ? "bg-primary/15 border border-primary/20" : ""}`}>
                      <div className="w-3 h-3 rounded bg-white/10 shrink-0" />
                      <div className="h-2 rounded bg-white/10 agente-1" />
                    </div>
                  ))}
                </div>

                <div className="agente-1 p-5 space-y-4">
                  <div className="agente items-center justify-between">
                    <div className="h-4 w-32 rounded bg-white/8" />
                    <div className="h-4 w-20 rounded-full bg-green-500/15 border border-green-500/20" />
                  </div>

                  <div className="grid grid-cols-4 gap-2.5">
                    {[{ n: "70", c: "text-white/70" }, { n: "70", c: "text-white/70" }, { n: "8", c: "text-white/70" }, { n: "0", c: "text-green-400" }].map(({ n, c }, i) => (
                      <div key={i} className="rounded-xl bg-white/3 border border-white/5 p-3">
                        <div className="h-1.5 w-10 rounded bg-white/8 mb-2" />
                        <div className={`text-lg font-black ${c}`}>{n}</div>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-xl bg-white/3 border border-white/5 overflow-hidden">
                    <div className="px-4 py-2.5 border-b border-white/5 agente items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-primary" />
                      <div className="h-2 w-24 rounded bg-white/8" />
                    </div>
                    {[
                      { tag: "CRÍTICA", color: "bg-red-500/20 text-red-400", dot: "bg-red-400" },
                      { tag: "MEDIA", color: "bg-blue-500/20 text-blue-400", dot: "bg-blue-400" },
                      { tag: "CRÍTICA", color: "bg-red-500/20 text-red-400", dot: "bg-red-400" },
                      { tag: "BAJA", color: "bg-slate-500/20 text-slate-400", dot: "bg-slate-500" },
                    ].map(({ tag, color, dot }, i) => (
                      <div key={i} className="agente items-center gap-3 px-4 py-2.5 border-b border-white/4 last:border-0">
                        <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
                        <div className="h-2 agente-1 rounded bg-white/8" />
                        <div className="h-2 w-16 rounded bg-white/5" />
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${color}`}>{tag}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>

      </div>
    </section>
  );
}
