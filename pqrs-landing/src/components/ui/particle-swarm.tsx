"use client";

import { useEffect, useRef, useState } from "react";

export const ParticleSwarm = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let particles: Particle[] = [];
    const particleCount = 250; // Ajustado para buen rendimiento / look líquido

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    // Mouse tracker
    let mouse = { x: canvas.width / 2, y: canvas.height / 2 };
    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    window.addEventListener("mousemove", handleMouseMove);

    class Particle {
      x: number;
      y: number;
      size: number;
      baseX: number;
      baseY: number;
      density: number;
      color: string;
      angle: number;
      speed: number;

      constructor() {
        this.x = Math.random() * canvas!.width;
        this.y = Math.random() * canvas!.height;
        this.baseX = this.x;
        this.baseY = this.y;
        this.size = Math.random() * 2 + 0.5;
        this.density = (Math.random() * 30) + 1;
        // Paleta fría "Antigravity/PQRS_V2" oscura
        const colors = [
          "rgba(13, 89, 242, 0.8)", // Azul primario
          "rgba(59, 130, 246, 0.6)", // Azul claro
          "rgba(139, 92, 246, 0.8)", // Morado
          "rgba(74, 222, 128, 0.5)", // Verde secundario
          "rgba(255, 255, 255, 0.4)", // Blanco
        ];
        this.color = colors[Math.floor(Math.random() * colors.length)];
        this.angle = Math.random() * 360;
        this.speed = Math.random() * 0.5 + 0.1;
      }

      draw() {
        if (!ctx) return;
        ctx.fillStyle = this.color;
        ctx.beginPath();
        // Le damos una estética difusa / alargada como en el screenshot
        ctx.ellipse(this.x, this.y, this.size * 2, this.size, this.angle, 0, Math.PI * 2);
        ctx.closePath();
        ctx.fill();
        
        ctx.shadowBlur = 10;
        ctx.shadowColor = this.color;
      }

      update() {
        // Movimiento base orbital / remolino lento
        this.angle += this.speed * 0.02;
        this.baseX += Math.cos(this.angle) * this.speed;
        this.baseY += Math.sin(this.angle) * this.speed;

        // Rebote en paredes sutil
        if (this.baseX > canvas!.width || this.baseX < 0) this.speed *= -1;
        if (this.baseY > canvas!.height || this.baseY < 0) this.speed *= -1;

        // Interacción con el mouse (Efecto "Agua" - Repulsión atractiva)
        let dx = mouse.x - this.x;
        let dy = mouse.y - this.y;
        let distance = Math.sqrt(dx * dx + dy * dy);
        let forceDirectionX = dx / distance;
        let forceDirectionY = dy / distance;

        // Distancia en la que reaccionan (rango de 200px)
        let maxDistance = 250;
        let force = (maxDistance - distance) / maxDistance;
        let directionX = forceDirectionX * force * this.density;
        let directionY = forceDirectionY * force * this.density;

        if (distance < maxDistance) {
          // Si están cerca, son empujadas suavemente creando el remolino alrededor del mouse
          this.x -= directionX;
          this.y -= directionY;
        } else {
          // Retornan a su base orgánicamente
          if (this.x !== this.baseX) {
            let dx = this.x - this.baseX;
            this.x -= dx / 20;
          }
          if (this.y !== this.baseY) {
            let dy = this.y - this.baseY;
            this.y -= dy / 20;
          }
        }
      }
    }

    const init = () => {
      particles = [];
      for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
      }
    };

    const animate = () => {
      // Fondo transparente pero limpiando el frame anterior
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < particles.length; i++) {
        particles[i].draw();
        particles[i].update();
      }
      animationFrameId = requestAnimationFrame(animate);
    };

    init();
    animate();

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      window.removeEventListener("mousemove", handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, [mounted]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 opacity-70 mix-blend-screen"
    />
  );
};
