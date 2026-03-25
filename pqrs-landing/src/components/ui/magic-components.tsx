"use client";

import React, { useEffect, useRef } from "react";
import { motion, useInView, useAnimation } from "framer-motion";
import { cn } from "@/lib/utils";

/* Easing premium usado en Lugano Living Lab */
const EASE_PREMIUM = [0.625, 0.05, 0, 1] as const;

// ==========================================
// 1. TextReveal — firma de sitios premium
//    Texto desliza desde abajo de overflow:hidden
//    Uso: <TextReveal delay={0.2}>Tu texto aquí</TextReveal>
// ==========================================
export const TextReveal = ({
  children,
  delay = 0,
  className,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: React.ElementType;
}) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <div ref={ref} className={cn("overflow-hidden", className)}>
      <motion.div
        initial={{ y: "102%" }}
        animate={isInView ? { y: 0 } : { y: "102%" }}
        transition={{ duration: 0.9, delay, ease: EASE_PREMIUM }}
      >
        {children}
      </motion.div>
    </div>
  );
};

// ==========================================
// 2. FadeInUp — aparición suave al scrollear
// ==========================================
export const FadeInUp = ({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  const controls = useAnimation();

  useEffect(() => {
    if (isInView) controls.start("visible");
  }, [isInView, controls]);

  return (
    <motion.div
      ref={ref}
      variants={{
        hidden: { opacity: 0, y: 20 },
        visible: { opacity: 1, y: 0 },
      }}
      initial="hidden"
      animate={controls}
      transition={{ duration: 0.7, delay, ease: EASE_PREMIUM }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

// ==========================================
// 3. GlassCard3D — hover tilt card
// ==========================================
export const GlassCard3D = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <motion.div
      whileHover={{ scale: 1.02, rotateX: -2, rotateY: 2 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={cn("glass-panel group relative overflow-hidden", className)}
    >
      <div className="absolute inset-0 bg-gradient-to-tr from-primary/0 via-primary/5 to-primary/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      {children}
    </motion.div>
  );
};

// ==========================================
// 4. AnimatedCounter
// ==========================================
export const AnimatedCounter = ({
  value,
  suffix = "",
}: {
  value: number;
  suffix?: string;
}) => {
  return (
    <motion.span
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.8, type: "spring" }}
      className="text-4xl font-bold tracking-tight text-white"
    >
      {value}{suffix}
    </motion.span>
  );
};
