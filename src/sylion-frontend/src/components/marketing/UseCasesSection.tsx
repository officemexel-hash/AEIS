"use client";

import { motion } from "framer-motion";
import {
  Shield, Smartphone, Globe, Building2, Bot, Cpu,
} from "lucide-react";

const useCases = [
  {
    icon: Shield,
    title: "Sylion Secure",
    desc: "Enterprise security platform with autonomous threat detection, incident response, and compliance monitoring. AEIS governs every security decision with full evidence trail.",
    tags: ["Security", "Compliance", "Real-time"],
    color: "#EF4444",
  },
  {
    icon: Smartphone,
    title: "Mobile Application",
    desc: "Cross-platform mobile app with intelligent user experiences, offline-first architecture, and adaptive UI driven by cognitive skill modules.",
    tags: ["Mobile", "iOS/Android", "Adaptive"],
    color: "#8B5CF6",
  },
  {
    icon: Globe,
    title: "Web SaaS Platform",
    desc: "Multi-tenant SaaS with autonomous scaling, self-healing infrastructure, and governance-backed feature rollout with A/B testing pipelines.",
    tags: ["SaaS", "Multi-tenant", "Self-healing"],
    color: "#2F6BFF",
  },
  {
    icon: Building2,
    title: "Intelligent Buildings",
    desc: "IoT-driven building management with predictive maintenance, energy optimization, and autonomous environmental controls governed by decision ladder.",
    tags: ["IoT", "Energy", "Predictive"],
    color: "#10B981",
  },
  {
    icon: Bot,
    title: "Business Automation",
    desc: "End-to-end business process automation from invoice processing to HR workflows. Every automated decision produces auditable evidence packs.",
    tags: ["RPA", "Workflow", "Audit"],
    color: "#F59E0B",
  },
  {
    icon: Cpu,
    title: "AI Multi-Agent Systems",
    desc: "Orchestrate multiple AI agents with council voting, skill sharing, and coordinated execution. Agents self-organize around complex objectives.",
    tags: ["Multi-Agent", "Council", "Orchestration"],
    color: "#06B6D4",
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.1 },
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

export default function UseCasesSection() {
  return (
    <section id="use-cases" className="py-24 px-6 md:px-12">
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
            Real-World Applications
          </p>
          <h2
            className="text-4xl md:text-5xl font-bold tracking-tight mb-4"
            style={{ color: "#E2E8F0" }}
          >
            Built for Production
          </h2>
          <p
            className="text-base max-w-xl mx-auto"
            style={{ color: "#94A3B8" }}
          >
            SYLION AEIS powers diverse production systems. Each use case
            leverages different module classes with full governance and
            evidence backing.
          </p>
        </motion.div>

        <motion.div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-60px" }}
        >
          {useCases.map((uc) => (
            <motion.div
              key={uc.title}
              variants={cardVariants}
              className="group relative p-7 rounded-2xl transition-all duration-300"
              style={{
                background: "#0f1629",
                border: "1px solid rgba(148, 163, 184, 0.08)",
                boxShadow: "0 4px 32px rgba(0, 0, 0, 0.3)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = `${uc.color}30`;
                e.currentTarget.style.boxShadow = `0 4px 32px rgba(0,0,0,0.3), 0 0 40px ${uc.color}08`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                e.currentTarget.style.boxShadow = "0 4px 32px rgba(0, 0, 0, 0.3)";
              }}
            >
              {/* Icon */}
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                style={{
                  background: `${uc.color}12`,
                  border: `1px solid ${uc.color}25`,
                }}
              >
                <uc.icon className="w-6 h-6" style={{ color: uc.color }} />
              </div>

              <h3
                className="text-lg font-semibold mb-3"
                style={{ color: "#E2E8F0" }}
              >
                {uc.title}
              </h3>
              <p
                className="text-sm leading-relaxed mb-4"
                style={{ color: "#94A3B8" }}
              >
                {uc.desc}
              </p>

              {/* Tags */}
              <div className="flex flex-wrap gap-2">
                {uc.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2.5 py-1 rounded-md text-[10px] font-semibold"
                    style={{
                      background: `${uc.color}10`,
                      color: uc.color,
                      border: `1px solid ${uc.color}20`,
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* Hover glow overlay */}
              <div
                className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{
                  background: `radial-gradient(circle at 30% 30%, ${uc.color}06, transparent 70%)`,
                }}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
