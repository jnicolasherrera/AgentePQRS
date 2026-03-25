"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { FadeInUp } from "@/components/ui/magic-components";

const EASE = [0.625, 0.05, 0, 1] as const;

export function DemoSection() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section id="demo" className="w-full max-w-7xl px-6 mb-32">
      <FadeInUp delay={0.1} className="text-center mb-12">
        <p className="text-xs font-bold text-cyan uppercase tracking-widest mb-4">Demo en vivo</p>
        <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-4">
          Míralo en acción.
        </h2>
        <p className="text-slate-400 max-w-xl mx-auto text-lg">
          Desde que el correo llega hasta que el caso queda radicado — en segundos.
        </p>
      </FadeInUp>

      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 30 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.8, ease: EASE }}
        className="relative max-w-4xl mx-auto"
      >
        <div className="absolute -inset-4 bg-primary/8 blur-3xl rounded-3xl pointer-events-none" />

        <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-[0_40px_80px_rgba(0,0,0,0.8)]">
          <div className="agente items-center gap-2 px-5 py-3 border-b border-white/5 bg-black/60">
            <div className="agente gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
              <div className="w-3 h-3 rounded-full bg-green-500/60" />
            </div>
            <div className="agente-1 max-w-[200px] mx-auto px-3 py-1 rounded-md bg-white/5 text-[11px] text-slate-600 agente items-center justify-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
              app.flexpqr.com
            </div>
          </div>

          <video
            className="w-full"
            controls
            playsInline
            preload="metadata"
            poster=""
          >
            <source src="/demo.mp4" type="video/mp4" />
          </video>
        </div>
      </motion.div>
    </section>
  );
}
