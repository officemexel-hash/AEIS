"use client";

import { motion } from "framer-motion";
import { MonitorDot, Settings2, Workflow } from "lucide-react";

const cards = [
  {
    icon: MonitorDot,
    title: "An AI Operating Console",
    description:
      "A unified control surface for orchestrating autonomous engineering workflows. Monitor every module, trace every decision, command every pipeline from a single cockpit.",
  },
  {
    icon: Settings2,
    title: "A Strategic Engineering Cockpit",
    description:
      "Configure governance tiers, deploy LEGO modules, manage skill lifecycles, and observe real-time telemetry across the entire autonomous stack.",
  },
  {
    icon: Workflow,
    title: "A Modular Autonomy Pipeline",
    description:
      "65 contract-frozen modules across 12 classes, connected by an event bus spine. From idea intake to autonomous execution, every step is governed and evidence-backed.",
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.15 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6 },
  },
};

export default function WhatIsAEISSection() {
  return (
    <section id="what" className="py-24 px-6 md:px-12">
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
            What is AEIS?
          </p>
          <h2
            className="text-4xl md:text-5xl font-bold tracking-tight mb-6"
            style={{ color: "#E2E8F0" }}
          >
            Not just another framework.
          </h2>
          <p
            className="text-lg max-w-2xl mx-auto leading-relaxed"
            style={{ color: "#94A3B8" }}
          >
            SYLION AEIS is three things at once: an operating console for AI,
            a strategic cockpit for engineering decisions, and a modular pipeline
            that runs autonomously from raw idea to delivered execution.
          </p>
        </motion.div>

        <motion.div
          className="grid grid-cols-1 md:grid-cols-3 gap-6"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-80px" }}
        >
          {cards.map((card) => (
            <motion.div
              key={card.title}
              variants={cardVariants}
              className="group relative p-8 rounded-2xl transition-all duration-300"
              style={{
                background: "#0f1629",
                border: "1px solid rgba(148, 163, 184, 0.08)",
                boxShadow: "0 4px 32px rgba(0, 0, 0, 0.3)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "rgba(47, 107, 255, 0.2)";
                e.currentTarget.style.boxShadow =
                  "0 4px 32px rgba(0, 0, 0, 0.3), 0 0 40px rgba(47, 107, 255, 0.06)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                e.currentTarget.style.boxShadow = "0 4px 32px rgba(0, 0, 0, 0.3)";
              }}
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center mb-6"
                style={{
                  background: "rgba(47, 107, 255, 0.1)",
                  border: "1px solid rgba(47, 107, 255, 0.15)",
                }}
              >
                <card.icon className="w-6 h-6" style={{ color: "#2F6BFF" }} />
              </div>
              <h3
                className="text-xl font-semibold mb-3"
                style={{ color: "#E2E8F0" }}
              >
                {card.title}
              </h3>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "#94A3B8" }}
              >
                {card.description}
              </p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
