"use client";

import { FadeInUp } from "@/components/ui/magic-components";
import { Mail, Cpu, CheckCircle } from "lucide-react";

const steps = [
  {
    number: "01",
    icon: <Mail className="w-6 h-6 text-primary" />,
    title: "Conecta tu buzón de correo",
    desc: "Outlook, Gmail, Zoho, correo corporativo o cualquier servidor. Sin migraciones, sin cambiar tu flujo actual. Configuración en menos de 10 minutos.",
    detail: "Outlook · Gmail · Zoho · IMAP",
  },
  {
    number: "02",
    icon: <Cpu className="w-6 h-6 text-primary" />,
    title: "La IA clasifica y asigna automáticamente",
    desc: "Cada correo entrante es analizado en milisegundos: tipo de caso, nivel de prioridad, fecha de vencimiento legal y abogado asignado. Sin intervención manual.",
    detail: "Tutela · Queja · Petición · Reclamo · Felicitación",
  },
  {
    number: "03",
    icon: <CheckCircle className="w-6 h-6 text-primary" />,
    title: "Tu equipo responde antes de que venza el plazo",
    desc: "Cada abogado ve solo sus casos. El sistema alerta 48h antes del vencimiento, registra cada acción y genera el historial de trazabilidad listo para auditorías de la Superintendencia.",
    detail: "Alertas · Historial · Trazabilidad · Reportes",
  },
];

export function HowItWorksSection() {
  return (
    <section id="como-funciona" className="w-full max-w-7xl px-6 mb-32">
      <FadeInUp delay={0.1} className="text-center mb-16">
        <p className="text-xs font-bold text-primary uppercase tracking-widest mb-4">Cómo funciona</p>
        <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-4">
          En funcionamiento en 10 minutos.
        </h2>
        <p className="text-slate-400 max-w-xl mx-auto text-lg">
          Sin instalaciones, sin migraciones, sin meses de onboarding.
        </p>
      </FadeInUp>

      <div className="relative">
        {/* Línea conectora */}
        <div className="hidden md:block absolute top-10 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {steps.map(({ number, icon, title, desc, detail }, i) => (
            <FadeInUp key={i} delay={0.2 + i * 0.15}>
              <div className="agente agente-col gap-5">
                {/* Step number + icon */}
                <div className="agente items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/25 agente items-center justify-center shrink-0 relative">
                    {icon}
                    <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-primary text-white text-[10px] font-black agente items-center justify-center">
                      {i + 1}
                    </span>
                  </div>
                  <span className="text-5xl font-black text-white/5 leading-none select-none">{number}</span>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed mb-3">{desc}</p>
                  <p className="text-xs text-primary/60 font-semibold uppercase tracking-wider">{detail}</p>
                </div>
              </div>
            </FadeInUp>
          ))}
        </div>
      </div>
    </section>
  );
}
