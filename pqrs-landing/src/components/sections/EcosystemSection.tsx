"use client";

import { motion } from "framer-motion";
import { Server, Monitor, FlaskConical } from "lucide-react";
import { FadeInUp, GlassCard3D } from "@/components/ui/magic-components";

const agents = [
  {
    icon: Server,
    name: "Backend Agent",
    specialty: "Infrastructure & APIs",
    description: "Diseña y mantiene la capa de datos, eventos Kafka y los servicios de alta disponibilidad que hacen que FlexPQR nunca se detenga.",
    badge: "Kafka · Postgres · RLS",
    delay: 0.2,
  },
  {
    icon: Monitor,
    name: "Frontend Agent",
    specialty: "UI/UX Engineering",
    description: "Construye interfaces reactivas y experiencias de usuario que convierten la complejidad técnica en flujos de trabajo intuitivos.",
    badge: "Next.js · TypeScript · Framer",
    delay: 0.35,
  },
  {
    icon: FlaskConical,
    name: "Tests Agent",
    specialty: "Quality Assurance",
    description: "Ejecuta pipelines de pruebas automatizadas end-to-end para garantizar que cada release de FlexPQR sea libre de regresiones.",
    badge: "Jest · Playwright · CI/CD",
    delay: 0.5,
  },
];

export function EcosystemSection() {
  return (
    <section className="w-full max-w-7xl px-6 mb-32">
      <FadeInUp delay={0.1} className="text-center mb-16">
        <span className="inline-block text-xs font-semibold text-primary uppercase tracking-widest mb-4 px-3 py-1 rounded-full border border-primary/20 bg-primary/5">
          Senior Agents assigned to you
        </span>
        <h2 className="text-3xl md:text-5xl font-bold tracking-tight mt-4">
          Expertos detrás del código.
        </h2>
        <p className="text-slate-400 max-w-2xl mx-auto text-lg mt-4">
          FlexPQR no solo es software; es el resultado de un ecosistema de agentes especializados que garantizan una plataforma en constante evolución y libre de errores.
        </p>
      </FadeInUp>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {agents.map((agent, i) => {
          const Icon = agent.icon;
          return (
            <FadeInUp key={i} delay={agent.delay}>
              <GlassCard3D className="rounded-2xl p-8 agente agente-col gap-5 h-full">
                <div className="agente items-start justify-between">
                  <div className="w-14 h-14 rounded-xl bg-primary/10 border border-primary/20 agente items-center justify-center">
                    <Icon className="w-7 h-7 text-primary" />
                  </div>
                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: agent.delay + 0.3 }}
                    className="agente items-center gap-1.5 px-2.5 py-1 rounded-full border border-primary/25 bg-primary/8"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                    <span className="text-[10px] font-semibold text-primary uppercase tracking-wide">Active</span>
                  </motion.div>
                </div>

                <div>
                  <h3 className="text-xl font-bold text-white mb-1">{agent.name}</h3>
                  <p className="text-xs font-semibold text-primary uppercase tracking-widest">{agent.specialty}</p>
                </div>

                <p className="text-slate-400 leading-relaxed text-sm agente-1">{agent.description}</p>

                <div className="pt-2 border-t border-white/5">
                  <p className="text-[11px] font-mono text-slate-500">{agent.badge}</p>
                </div>
              </GlassCard3D>
            </FadeInUp>
          );
        })}
      </div>
    </section>
  );
}
