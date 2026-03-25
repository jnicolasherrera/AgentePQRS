"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { FadeInUp } from "@/components/ui/magic-components";

const blueprints = [
  {
    num: "01",
    badge: "Escalabilidad",
    title: "Inmune a los picos\nde tráfico",
    description:
      "Tu operación nunca se detiene. Mientras otros sistemas colapsan en horas pico, FlexPQR escala elásticamente para procesar cada interacción en tiempo real — sin importar el volumen.",
  },
  {
    num: "02",
    badge: "Seguridad",
    title: "Aislamiento de datos\nde grado bancario",
    description:
      "Cada cliente opera en un entorno completamente aislado a nivel de base de datos. Los datos de una entidad jamás se cruzan con otra, eliminando riesgos legales y de cumplimiento.",
  },
  {
    num: "03",
    badge: "Inteligencia Artificial",
    title: "Núcleo de inteligencia\npredictiva",
    description:
      "Cada correo se clasifica, prioriza y asigna antes de que un humano lo abra. La IA detecta tutelas urgentes, extrae cédulas y radica el caso al analista correcto — en milisegundos.",
  },
];

const EASE = [0.625, 0.05, 0, 1] as const;

export function ArchitectureSection() {
  return (
    <section id="arquitectura" className="w-full max-w-7xl px-6 mb-32">
      <FadeInUp delay={0.1} className="mb-20">
        <p className="text-xs font-semibold text-primary uppercase tracking-[0.2em] mb-5">Confianza empresarial</p>
        <h2 className="text-4xl md:text-[3.25rem] font-bold tracking-[-0.02em] leading-[1.05] max-w-2xl">
          Infraestructura de<br />nivel enterprise.
        </h2>
      </FadeInUp>

      <div>
        {blueprints.map((item, i) => (
          <BlueprintRow key={i} {...item} delay={0.1 + i * 0.12} />
        ))}
        <div className="border-t border-white/8" />
      </div>
    </section>
  );
}

function BlueprintRow({ num, badge, title, description, delay }: {
  num: string; badge: string; title: string; description: string; delay: number;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 16 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, delay, ease: EASE }}
      className="group border-t border-white/8 py-10 grid grid-cols-1 md:grid-cols-[3rem_1fr_auto] gap-6 md:gap-10 items-start hover:border-white/15 transition-colors duration-300"
    >
      <span className="text-[11px] font-mono font-semibold text-primary/70 tracking-widest pt-1.5">{num}</span>

      <div>
        <h3 className="text-2xl md:text-3xl font-bold tracking-[-0.02em] leading-snug text-white mb-4 whitespace-pre-line">
          {title}
        </h3>
        <p className="text-zinc-500 text-[15px] leading-relaxed max-w-xl group-hover:text-zinc-400 transition-colors duration-300">
          {description}
        </p>
      </div>

      <span className="text-[11px] font-mono font-semibold text-primary/50 uppercase tracking-widest whitespace-nowrap pt-1.5 group-hover:text-primary/80 transition-colors duration-300">
        {badge}
      </span>
    </motion.div>
  );
}
