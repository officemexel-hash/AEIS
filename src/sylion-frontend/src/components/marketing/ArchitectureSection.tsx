"use client";

import { motion } from "framer-motion";

const layers = [
  {
    name: "Surface Layer",
    classes: ["J — Surface"],
    color: "#10B981",
    desc: "Dashboard, Console UI, Command Bus, Artifact Control",
  },
  {
    name: "Skill Layer",
    classes: ["I — Skills"],
    color: "#8B5CF6",
    desc: "Lifecycle management, skill registry, execution sandbox",
  },
  {
    name: "Self-* Layer (AEIS)",
    classes: ["H — AEIS"],
    color: "#2F6BFF",
    desc: "Self-observe, self-improve, self-limit, self-preserve, self-explain",
  },
  {
    name: "Governance Layer",
    classes: ["E — Governance", "F — Security"],
    color: "#F59E0B",
    desc: "Decision ladder D0-D5, council voting, evidence packs, auth, encryption",
  },
  {
    name: "Execution Layer",
    classes: ["C — Execution", "G — Efficiency"],
    color: "#06B6D4",
    desc: "Pipeline engine, job queues, rate limiting, caching, workflow",
  },
  {
    name: "Cognitive Layer",
    classes: ["B — Cognitive"],
    color: "#8B5CF6",
    desc: "Model router, inference engine, hypothesis engine, NLP",
  },
  {
    name: "Memory Layer",
    classes: ["D — Memory"],
    color: "#3B82F6",
    desc: "Knowledge store, context cache, vector DB, conversation memory",
  },
  {
    name: "Core Layer",
    classes: ["A — Core", "K — Rebuild", "L — Quality"],
    color: "#2F6BFF",
    desc: "Environment, config, logging, health, rebuild, quality gates",
  },
];

export default function ArchitectureSection() {
  return (
    <section id="architecture" className="py-24 px-6 md:px-12 relative overflow-hidden">
      {/* Background accent */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full blur-[200px] pointer-events-none"
        style={{ background: "rgba(47, 107, 255, 0.03)" }}
      />

      <div className="max-w-7xl mx-auto relative z-10">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
        >
          <p
            className="text-xs font-medium tracking-[0.3em] uppercase mb-4"
            style={{ color: "#2F6BFF" }}
          >
            Architecture
          </p>
          <h2
            className="text-4xl md:text-5xl font-bold tracking-tight mb-4"
            style={{ color: "#E2E8F0" }}
          >
            Layered. Modular. Evidence-Backed.
          </h2>
          <p
            className="text-base max-w-xl mx-auto"
            style={{ color: "#94A3B8" }}
          >
            Eight stacked layers connected by the event bus spine. Every
            module-to-module interaction produces evidence. Every state change
            is tracked in a SHA-256 hash chain.
          </p>
        </motion.div>

        {/* Layered visualization */}
        <div className="max-w-4xl mx-auto">
          {/* Event bus spine label */}
          <div className="flex items-center gap-4 mb-8">
            <div className="flex-1 h-px" style={{ background: "rgba(47, 107, 255, 0.2)" }} />
            <div
              className="flex items-center gap-2 px-4 py-1.5 rounded-full"
              style={{
                background: "rgba(47, 107, 255, 0.08)",
                border: "1px solid rgba(47, 107, 255, 0.15)",
              }}
            >
              <div className="w-2 h-2 rounded-full" style={{ background: "#2F6BFF" }} />
              <span className="text-xs font-semibold tracking-wide" style={{ color: "#2F6BFF" }}>
                EVENT BUS SPINE
              </span>
              <span className="text-[10px]" style={{ color: "#94A3B8" }}>
                — connects all layers
              </span>
            </div>
            <div className="flex-1 h-px" style={{ background: "rgba(47, 107, 255, 0.2)" }} />
          </div>

          {/* Layers */}
          <div className="space-y-3">
            {layers.map((layer, i) => (
              <motion.div
                key={layer.name}
                initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.5, delay: i * 0.07 }}
                className="group relative p-5 rounded-xl transition-all duration-300"
                style={{
                  background: "#0f1629",
                  border: "1px solid rgba(148, 163, 184, 0.08)",
                  boxShadow: "0 2px 16px rgba(0, 0, 0, 0.2)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = `${layer.color}30`;
                  e.currentTarget.style.boxShadow = `0 2px 16px rgba(0,0,0,0.2), 0 0 30px ${layer.color}08`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                  e.currentTarget.style.boxShadow = "0 2px 16px rgba(0, 0, 0, 0.2)";
                }}
              >
                <div className="flex items-start gap-5">
                  {/* Color indicator bar */}
                  <div
                    className="w-1 h-full min-h-[40px] rounded-full shrink-0"
                    style={{ background: layer.color }}
                  />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1.5">
                      <h3
                        className="text-sm font-semibold"
                        style={{ color: "#E2E8F0" }}
                      >
                        {layer.name}
                      </h3>
                      <div className="flex gap-1.5">
                        {layer.classes.map((cls) => (
                          <span
                            key={cls}
                            className="px-2 py-0.5 rounded text-[10px] font-semibold"
                            style={{
                              background: `${layer.color}15`,
                              color: layer.color,
                              border: `1px solid ${layer.color}25`,
                            }}
                          >
                            {cls}
                          </span>
                        ))}
                      </div>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: "#94A3B8" }}>
                      {layer.desc}
                    </p>
                  </div>

                  {/* Layer number */}
                  <span
                    className="text-2xl font-bold shrink-0"
                    style={{ color: `${layer.color}15` }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Evidence chain label */}
          <div className="flex items-center gap-4 mt-8">
            <div className="flex-1 h-px" style={{ background: "rgba(245, 158, 11, 0.2)" }} />
            <div
              className="flex items-center gap-2 px-4 py-1.5 rounded-full"
              style={{
                background: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.15)",
              }}
            >
              <div className="w-2 h-2 rounded-full" style={{ background: "#F59E0B" }} />
              <span className="text-xs font-semibold tracking-wide" style={{ color: "#F59E0B" }}>
                EVIDENCE CHAIN
              </span>
              <span className="text-[10px]" style={{ color: "#94A3B8" }}>
                — SHA-256 hash chain, tamper-evident
              </span>
            </div>
            <div className="flex-1 h-px" style={{ background: "rgba(245, 158, 11, 0.2)" }} />
          </div>
        </div>
      </div>
    </section>
  );
}
