"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";

export default function HeroSection() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let particles: { x: number; y: number; vx: number; vy: number; size: number; alpha: number }[] = [];

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };

    const initParticles = () => {
      particles = [];
      const count = Math.floor((canvas.offsetWidth * canvas.offsetHeight) / 12000);
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * canvas.offsetWidth,
          y: Math.random() * canvas.offsetHeight,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          size: Math.random() * 1.5 + 0.5,
          alpha: Math.random() * 0.4 + 0.1,
        });
      }
    };

    const drawGrid = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.strokeStyle = "rgba(47, 107, 255, 0.03)";
      ctx.lineWidth = 0.5;
      const spacing = 60;
      for (let x = 0; x < w; x += spacing) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += spacing) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
    };

    const animate = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);

      drawGrid();

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(47, 107, 255, ${p.alpha})`;
        ctx.fill();
      });

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(47, 107, 255, ${0.06 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animationId = requestAnimationFrame(animate);
    };

    resize();
    initParticles();
    animate();
    window.addEventListener("resize", () => { resize(); initParticles(); });

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      {/* Particle canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ opacity: 0.7 }}
      />

      {/* Gradient orbs */}
      <div
        className="absolute top-1/4 -left-32 w-96 h-96 rounded-full blur-[128px] pointer-events-none"
        style={{ background: "rgba(47, 107, 255, 0.08)" }}
      />
      <div
        className="absolute bottom-1/4 -right-32 w-96 h-96 rounded-full blur-[128px] pointer-events-none"
        style={{ background: "rgba(245, 158, 11, 0.05)" }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12 pt-24 pb-12 w-full">
        <div className="max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <p
              className="text-xs font-medium tracking-[0.3em] uppercase mb-6"
              style={{ color: "#2F6BFF" }}
            >
              Autonomous Engineering Intelligence System
            </p>
          </motion.div>

          <motion.h1
            className="text-6xl md:text-8xl font-bold tracking-tighter leading-[0.9] mb-4"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.35 }}
          >
            <span style={{ color: "#E2E8F0" }}>SYLION</span>
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage: "linear-gradient(135deg, #2F6BFF 0%, #5B9FFF 40%, #F59E0B 100%)",
              }}
            >
              AEIS
            </span>
          </motion.h1>

          <motion.p
            className="text-2xl md:text-3xl font-light tracking-tight mb-3"
            style={{ color: "#E2E8F0" }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            From Idea to Execution. Autonomously.
          </motion.p>

          <motion.p
            className="text-base leading-relaxed max-w-xl mb-10"
            style={{ color: "#94A3B8" }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
          >
            An elite AI operating console that transforms raw intent into governed,
            evidence-backed, modular execution through 65 LEGO modules and 24
            specialized skills.
          </motion.p>

          <motion.div
            className="flex flex-wrap items-center gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.7 }}
          >
            <Link
              href="/overview"
              className="group inline-flex items-center gap-2.5 px-7 py-3.5 rounded-lg text-sm font-semibold transition-all"
              style={{
                background: "linear-gradient(135deg, #2F6BFF, #1a4fd4)",
                color: "#fff",
                boxShadow: "0 0 30px rgba(47, 107, 255, 0.2)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = "0 0 40px rgba(47, 107, 255, 0.4)";
                e.currentTarget.style.transform = "translateY(-1px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = "0 0 30px rgba(47, 107, 255, 0.2)";
                e.currentTarget.style.transform = "translateY(0)";
              }}
            >
              Enter the Console
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <a
              href="#what"
              className="inline-flex items-center gap-2.5 px-6 py-3.5 rounded-lg text-sm font-medium transition-all border"
              style={{
                color: "#94A3B8",
                borderColor: "rgba(148, 163, 184, 0.15)",
                background: "rgba(15, 22, 41, 0.5)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "rgba(47, 107, 255, 0.3)";
                e.currentTarget.style.color = "#E2E8F0";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.15)";
                e.currentTarget.style.color = "#94A3B8";
              }}
            >
              <Play className="w-3.5 h-3.5" />
              Explore Platform
            </a>
            <span className="text-xs ml-2" style={{ color: "#64748B" }}>
              v3.5 &mdash; live runtime counts in Console
            </span>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
