"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";

const stats = [
  {
    value: "0",
    sup: "",
    label: "Vencimientos en piloto",
    desc: "Ningún caso cerrado fuera de términos desde el inicio del piloto.",
    color: "text-green-400",
    accent: "bg-green-400",
  },
  {
    value: "<50",
    sup: "ms",
    label: "Clasificación IA por correo",
    desc: "Cada correo entrante es tipificado, priorizado y asignado antes de que un humano lo abra.",
    color: "text-primary",
    accent: "bg-primary",
  },
  {
    value: "10",
    sup: "M+",
    label: "PQRS por año",
    desc: "Basado en arquitectura asíncrona Kafka que procesa millones de eventos sin latencia.",
    color: "text-blue-400",
    accent: "bg-blue-400",
  },
];

const EASE = [0.625, 0.05, 0, 1] as const;

export function StatsSection() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section ref={ref} className="w-full max-w-7xl px-6 mb-32 mt-16">
      {/* Divider line */}
      <div className="w-full h-px bg-white/6 mb-16" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-0 divide-y md:divide-y-0 md:divide-x divide-white/6">
        {stats.map(({ value, sup, label, desc, color, accent }, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 24 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.8, delay: i * 0.12, ease: EASE }}
            className="px-0 md:px-12 py-10 md:py-0 first:pl-0 last:pr-0 agente agente-col gap-4"
          >
            {/* Number */}
            <div className="agente items-end gap-1">
              <span className={`text-[5rem] leading-none font-black tracking-[-0.04em] ${color}`}>
                {value}
              </span>
              {sup && (
                <span className={`text-2xl font-black mb-3 ${color} opacity-70`}>{sup}</span>
              )}
            </div>

            {/* Accent bar */}
            <div className="w-8 h-0.5 rounded-full overflow-hidden bg-white/8">
              <motion.div
                initial={{ width: 0 }}
                animate={inView ? { width: "100%" } : {}}
                transition={{ duration: 0.9, delay: 0.4 + i * 0.12, ease: EASE }}
                className={`h-full ${accent}`}
              />
            </div>

            {/* Label + desc */}
            <div>
              <p className="text-white font-bold text-lg leading-snug mb-1.5">{label}</p>
              <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="w-full h-px bg-white/6 mt-16" />
    </section>
  );
}
