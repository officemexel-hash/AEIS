"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function CTASection() {
  return (
    <section className="py-32 px-6 md:px-12 relative overflow-hidden">
      {/* Background glow */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full blur-[150px] pointer-events-none"
        style={{ background: "rgba(47, 107, 255, 0.06)" }}
      />
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[200px] rounded-full blur-[100px] pointer-events-none"
        style={{ background: "rgba(245, 158, 11, 0.04)" }}
      />

      <div className="max-w-7xl mx-auto relative z-10">
        <motion.div
          className="text-center"
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.7 }}
        >
          <p
            className="text-xs font-medium tracking-[0.3em] uppercase mb-6"
            style={{ color: "#2F6BFF" }}
          >
            Ready to Begin?
          </p>
          <h2
            className="text-5xl md:text-6xl font-bold tracking-tight mb-6"
            style={{ color: "#E2E8F0" }}
          >
            Enter the Console
          </h2>
          <p
            className="text-lg max-w-lg mx-auto mb-10 leading-relaxed"
            style={{ color: "#94A3B8" }}
          >
            SYLION AEIS v3.5 &mdash; 65 LEGO modules, 24 skills, 12 classes,
            evidence-backed governance, and one autonomous pipeline.
          </p>

          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Link
              href="/overview"
              className="group inline-flex items-center gap-3 px-8 py-4 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: "linear-gradient(135deg, #2F6BFF, #1a4fd4)",
                color: "#fff",
                boxShadow: "0 0 40px rgba(47, 107, 255, 0.25)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = "0 0 60px rgba(47, 107, 255, 0.4)";
                e.currentTarget.style.transform = "translateY(-2px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = "0 0 40px rgba(47, 107, 255, 0.25)";
                e.currentTarget.style.transform = "translateY(0)";
              }}
            >
              Enter the Console
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Stats row */}
          <motion.div
            className="flex items-center justify-center gap-12 mt-16"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            {[
              { value: "65", label: "Modules" },
              { value: "12", label: "Classes" },
              { value: "24", label: "Skills" },
              { value: "6", label: "Governance Tiers" },
              { value: "SHA-256", label: "Evidence Chain" },
            ].map((stat, i) => (
              <div key={stat.label} className="text-center">
                <p
                  className="text-2xl font-bold mb-1"
                  style={{ color: "#2F6BFF" }}
                >
                  {stat.value}
                </p>
                <p className="text-[10px] tracking-wide uppercase" style={{ color: "#94A3B8" }}>
                  {stat.label}
                </p>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      {/* Footer */}
      <footer
        className="mt-32 pt-8 px-6 md:px-12 border-t"
        style={{ borderColor: "rgba(148, 163, 184, 0.08)" }}
      >
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              className="w-6 h-6 rounded-md flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, #2F6BFF, #1a4fd4)",
              }}
            >
              <span className="text-white font-bold text-[10px]">S</span>
            </div>
            <span className="text-xs tracking-wide" style={{ color: "#94A3B8" }}>
              SYLION AEIS v3.5 &mdash; Autonomous Engineering Intelligence System
            </span>
          </div>
          <p className="text-[10px] tracking-wide" style={{ color: "#64748B" }}>
            Runtime counts, endpoints, and module state are shown in Console.
          </p>
        </div>
      </footer>
    </section>
  );
}
