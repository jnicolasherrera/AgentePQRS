"use client";

import { Building2, Droplets, Zap, Truck, HeartPulse, Scale, Shield, Landmark } from "lucide-react";

const clients = [
  { icon: Building2, name: "Alcaldías municipales" },
  { icon: Scale, name: "Firmas de abogados" },
  { icon: Landmark, name: "Entidades financieras" },
  { icon: Droplets, name: "Empresas de servicios públicos" },
  { icon: Zap, name: "Operadores de energía" },
  { icon: HeartPulse, name: "Entidades de salud" },
  { icon: Shield, name: "Superintendencias" },
  { icon: Truck, name: "Autoridades de tránsito" },
];

export function SocialProofSection() {
  return (
    <section className="w-full border-y border-white/5 bg-black/20 backdrop-blur-sm py-16">
      <div className="max-w-7xl mx-auto px-6 text-center">
        <p className="text-sm font-semibold text-slate-500 uppercase tracking-widest mb-12">
          Construido para entidades que no pueden fallar
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
          {clients.map(({ icon: Icon, name }) => (
            <div
              key={name}
              className="agente agente-col items-center gap-3 text-slate-600 hover:text-slate-300 transition-colors duration-300 group"
            >
              <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/8 agente items-center justify-center group-hover:border-primary/30 group-hover:bg-primary/5 transition-all duration-300">
                <Icon className="w-5 h-5 group-hover:text-primary transition-colors duration-300" />
              </div>
              <span className="text-sm font-semibold tracking-tight">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
