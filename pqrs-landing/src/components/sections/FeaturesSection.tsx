"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { FadeInUp } from "@/components/ui/magic-components";

const features = [
  {
    num: "01",
    title: "Clasificación automática\nen milisegundos",
    desc: "La IA lee cada correo entrante y lo etiqueta como Tutela, Queja, Petición, Reclamo o Felicitación — sin intervención humana. El caso llega al abogado correcto con prioridad y fecha de vencimiento asignadas.",
    tag: "IA · NLP",
  },
  {
    num: "02",
    title: "Cero vencimientos\nde términos legales",
    desc: "Tutelas: alerta a las 2 horas de llegada. PQRS: alerta antes del vencimiento (15 días). Nunca más una sanción por silencio administrativo o fallo de tutela sin responder.",
    tag: "Alertas · Plazos",
  },
  {
    num: "03",
    title: "Visibilidad total\npara jefes y auditores",
    desc: "Dashboard en tiempo real: quién tiene qué caso, cuánto llevan, qué está vencido. Historial trazable por caso. Listo para auditorías de la Superintendencia o la Defensoría del Pueblo.",
    tag: "Dashboard · Reportes",
  },
];

const EASE = [0.625, 0.05, 0, 1] as const;

export function FeaturesSection() {
  return (
    <section id="funcionalidades" className="w-full max-w-7xl px-6 mb-32">
      <FadeInUp delay={0.1} className="mb-20">
        <p className="text-xs font-semibold text-primary uppercase tracking-[0.2em] mb-5">Por qué FlexPQR</p>
        <h2 className="text-4xl md:text-[3.25rem] font-bold tracking-[-0.02em] leading-[1.05] max-w-2xl">
          Diseñado para<br />el problema real.
        </h2>
      </FadeInUp>

      <div>
        {features.map(({ num, title, desc, tag }, i) => (
          <FeatureRow key={i} num={num} title={title} desc={desc} tag={tag} delay={0.1 + i * 0.12} />
        ))}
        {/* Bottom border */}
        <div className="border-t border-white/8" />
      </div>
    </section>
  );
}

function FeatureRow({ num, title, desc, tag, delay }: {
  num: string; title: string; desc: string; tag: string; delay: number;
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
      {/* Number */}
      <span className="text-[11px] font-mono font-semibold text-primary/70 tracking-widest pt-1.5">{num}</span>

      {/* Content */}
      <div>
        <h3 className="text-2xl md:text-3xl font-bold tracking-[-0.02em] leading-snug text-white mb-4 whitespace-pre-line">
          {title}
        </h3>
        <p className="text-zinc-500 text-[15px] leading-relaxed max-w-xl group-hover:text-zinc-400 transition-colors duration-300">
          {desc}
        </p>
      </div>

      {/* Tag */}
      <span className="text-[11px] font-semibold text-primary/50 uppercase tracking-widest whitespace-nowrap pt-1.5 group-hover:text-primary/80 transition-colors duration-300">
        {tag}
      </span>
    </motion.div>
  );
}
