"use client";

import { motion } from "framer-motion";
import {
  Cpu, Brain, Rocket, Database, ShieldCheck, Lock,
  Gauge, Eye, Wrench, LayoutDashboard, RotateCcw, CheckCircle2,
} from "lucide-react";

const classes = [
  { letter: "A", name: "Core", count: 8, icon: Cpu, color: "#2F6BFF", desc: "Foundation modules: environment, config, logging, health" },
  { letter: "B", name: "Cognitive", count: 7, icon: Brain, color: "#8B5CF6", desc: "Model routing, skill discovery, inference engine" },
  { letter: "C", name: "Execution", count: 6, icon: Rocket, color: "#10B981", desc: "Pipeline engine, job queues, workflow orchestration" },
  { letter: "D", name: "Memory", count: 7, icon: Database, color: "#3B82F6", desc: "Knowledge store, context cache, vector retrieval" },
  { letter: "E", name: "Governance", count: 7, icon: ShieldCheck, color: "#F59E0B", desc: "Decision ladder, council voting, evidence packs" },
  { letter: "F", name: "Security", count: 8, icon: Lock, color: "#EF4444", desc: "Auth, encryption, audit trail, threat detection" },
  { letter: "G", name: "Efficiency", count: 4, icon: Gauge, color: "#06B6D4", desc: "Rate limiting, caching, resource optimization" },
  { letter: "H", name: "AEIS", count: 5, icon: Eye, color: "#2F6BFF", desc: "Self-observe, improve, limit, preserve, explain" },
  { letter: "I", name: "Skills", count: 3, icon: Wrench, color: "#8B5CF6", desc: "Lifecycle management, skill registry, execution" },
  { letter: "J", name: "Surface", count: 8, icon: LayoutDashboard, color: "#10B981", desc: "Dashboard, console UI, command bus, artifact control" },
  { letter: "K", name: "Rebuild", count: 4, icon: RotateCcw, color: "#F59E0B", desc: "System rebuild, migration, state recovery" },
  { letter: "L", name: "Quality", count: 3, icon: CheckCircle2, color: "#06B6D4", desc: "Testing, validation, quality gates" },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.4 },
  },
} as const;

export default function CapabilityGrid() {
  return (
    <section id="capabilities" className="py-24 px-6 md:px-12">
      <div className="max-w-7xl mx-auto">
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
            12 Classes. 65 Modules.
          </p>
          <h2
            className="text-4xl md:text-5xl font-bold tracking-tight mb-4"
            style={{ color: "#E2E8F0" }}
          >
            LEGO Module Architecture
          </h2>
          <p
            className="text-base max-w-xl mx-auto"
            style={{ color: "#94A3B8" }}
          >
            Every module is contract-frozen, swappable, and connected through
            the event bus spine. Mix, match, and deploy with confidence.
          </p>
        </motion.div>

        <motion.div
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-60px" }}
        >
          {classes.map((cls) => (
            <motion.div
              key={cls.letter}
              variants={cardVariants}
              className="group relative p-6 rounded-2xl transition-all duration-300 cursor-default"
              style={{
                background: "#0f1629",
                border: "1px solid rgba(148, 163, 184, 0.08)",
                boxShadow: "0 4px 24px rgba(0, 0, 0, 0.2)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = `${cls.color}30`;
                e.currentTarget.style.boxShadow = `0 4px 24px rgba(0,0,0,0.2), 0 0 40px ${cls.color}10`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                e.currentTarget.style.boxShadow = "0 4px 24px rgba(0, 0, 0, 0.2)";
              }}
            >
              {/* Letter badge */}
              <div className="flex items-start justify-between mb-5">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold"
                  style={{
                    background: `${cls.color}15`,
                    color: cls.color,
                    border: `1px solid ${cls.color}25`,
                  }}
                >
                  {cls.letter}
                </div>
                <span
                  className="text-3xl font-bold"
                  style={{ color: `${cls.color}20` }}
                >
                  {String(cls.count).padStart(2, "0")}
                </span>
              </div>

              {/* Icon */}
              <cls.icon
                className="w-5 h-5 mb-3 transition-transform duration-300 group-hover:scale-110"
                style={{ color: cls.color }}
              />

              <h3
                className="text-base font-semibold mb-1"
                style={{ color: "#E2E8F0" }}
              >
                {cls.name}
              </h3>
              <p
                className="text-xs font-medium mb-2"
                style={{ color: cls.color }}
              >
                {cls.count} modules
              </p>
              <p
                className="text-xs leading-relaxed"
                style={{ color: "#94A3B8" }}
              >
                {cls.desc}
              </p>

              {/* Hover glow overlay */}
              <div
                className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{
                  background: `radial-gradient(circle at 50% 50%, ${cls.color}06, transparent 70%)`,
                }}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
