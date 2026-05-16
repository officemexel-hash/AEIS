"use client";

import { motion } from "framer-motion";
import { Lightbulb, BookOpen, FolderKanban, Rocket } from "lucide-react";

const steps = [
  {
    icon: Lightbulb,
    label: "IDEA",
    sub: "Raw intent captured",
    color: "#F59E0B",
    description: "Unstructured ideas enter the system and are scoped, classified, and matured.",
  },
  {
    icon: BookOpen,
    label: "BOOK / KSIĘGA",
    sub: "Knowledge codified",
    color: "#2F6BFF",
    description: "Structured knowledge is versioned, contract-frozen, and linked to modules.",
  },
  {
    icon: FolderKanban,
    label: "PROJECT",
    sub: "Modules assembled",
    color: "#8B5CF6",
    description: "LEGO modules are selected, wired through the event bus, and governance tiers set.",
  },
  {
    icon: Rocket,
    label: "EXECUTION",
    sub: "Autonomous delivery",
    color: "#10B981",
    description: "Autonomous pipeline runs with evidence-backed decisions and full audit trail.",
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.2 },
  },
};

const stepVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6 },
  },
};

export default function TransformationFlow() {
  return (
    <section className="py-24 px-6 md:px-12 relative overflow-hidden">
      {/* Subtle horizontal line accent */}
      <div
        className="absolute top-1/2 left-0 right-0 h-px pointer-events-none"
        style={{ background: "linear-gradient(90deg, transparent, rgba(47, 107, 255, 0.1), transparent)" }}
      />

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
            Core Transformation
          </p>
          <h2
            className="text-4xl md:text-5xl font-bold tracking-tight mb-4"
            style={{ color: "#E2E8F0" }}
          >
            Idea to Execution Pipeline
          </h2>
          <p
            className="text-base max-w-xl mx-auto"
            style={{ color: "#94A3B8" }}
          >
            Every project follows this four-stage transformation. Each stage
            produces evidence. Each transition is governed.
          </p>
        </motion.div>

        <motion.div
          className="grid grid-cols-1 md:grid-cols-4 gap-4 relative"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-60px" }}
        >
          {/* Connecting lines (desktop) */}
          <div className="hidden md:block absolute top-1/2 left-0 right-0 h-px -translate-y-1/2 z-0">
            <motion.div
              className="h-full"
              style={{
                background: "linear-gradient(90deg, rgba(47, 107, 255, 0.1), rgba(47, 107, 255, 0.2), rgba(47, 107, 255, 0.1))",
              }}
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 1.2, delay: 0.3 }}
            />
          </div>

          {steps.map((step, i) => (
            <motion.div
              key={step.label}
              variants={stepVariants}
              className="relative z-10"
            >
              <div
                className="group relative p-8 rounded-2xl text-center transition-all duration-300"
                style={{
                  background: "#0f1629",
                  border: "1px solid rgba(148, 163, 184, 0.08)",
                  boxShadow: "0 4px 32px rgba(0, 0, 0, 0.3)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = `${step.color}33`;
                  e.currentTarget.style.boxShadow = `0 4px 32px rgba(0,0,0,0.3), 0 0 30px ${step.color}10`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                  e.currentTarget.style.boxShadow = "0 4px 32px rgba(0, 0, 0, 0.3)";
                }}
              >
                {/* Step number */}
                <div
                  className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[10px] font-bold tracking-widest"
                  style={{
                    background: "#0f1629",
                    border: `1px solid ${step.color}40`,
                    color: step.color,
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </div>

                {/* Icon */}
                <div
                  className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-5"
                  style={{
                    background: `${step.color}12`,
                    border: `1px solid ${step.color}25`,
                  }}
                >
                  <step.icon className="w-7 h-7" style={{ color: step.color }} />
                </div>

                <h3
                  className="text-lg font-bold tracking-wide mb-2"
                  style={{ color: "#E2E8F0" }}
                >
                  {step.label}
                </h3>
                <p
                  className="text-xs font-medium tracking-wide uppercase mb-3"
                  style={{ color: step.color }}
                >
                  {step.sub}
                </p>
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: "#94A3B8" }}
                >
                  {step.description}
                </p>
              </div>

              {/* Arrow connector (desktop) */}
              {i < steps.length - 1 && (
                <div className="hidden md:flex absolute -right-2 top-1/2 -translate-y-1/2 z-20 items-center justify-center w-4 h-4">
                  <div
                    className="w-2 h-2 rotate-45"
                    style={{ background: step.color, opacity: 0.5 }}
                  />
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
