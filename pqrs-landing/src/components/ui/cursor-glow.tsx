"use client";

import { useEffect } from "react";
import { motion, useSpring } from "framer-motion";

export const InteractiveCursorGlow = () => {
  const springX = useSpring(0, { stiffness: 50, damping: 20 });
  const springY = useSpring(0, { stiffness: 50, damping: 20 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      springX.set(e.clientX - 300);
      springY.set(e.clientY - 300);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [springX, springY]);

  return (
    <motion.div
      style={{
        left: springX,
        top: springY,
        position: "fixed",
        width: "600px",
        height: "600px",
        background: "radial-gradient(circle, rgba(13, 89, 242, 0.15) 0%, rgba(13, 89, 242, 0) 70%)",
        borderRadius: "50%",
        pointerEvents: "none",
        zIndex: 0,
      }}
    />
  );
};
