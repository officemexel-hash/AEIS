"use client";

import { motion } from "framer-motion";
import { ShieldCheck, Users, FileCheck, Fingerprint } from "lucide-react";

const tiers = [
  { level: "D0", label: "Auto", desc: "System decides autonomously", color: "#10B981", votes: null },
  { level: "D1", label: "Agent", desc: "Single agent approval", color: "#10B981", votes: "1/1" },
  { level: "D2", label: "Board 3/4", desc: "Board majority + evidence pack", color: "#2F6BFF", votes: "3/4" },
  { level: "D3", label: "Council 4/4", desc: "Full council + evidence pack", color: "#2F6BFF", votes: "4/4" },
  { level: "D4", label: "Council + Human", desc: "Council + human operator gate", color: "#F59E0B", votes: "4/4+H" },
  { level: "D5", label: "External Audit", desc: "Council + human + external auditor", color: "#EF4444", votes: "4/4+H+E" },
];

const features = [
  {
    icon: ShieldCheck,
    title: "Decision Ladder D0-D5",
    desc: "Six governance tiers from fully autonomous to external audit. Each tier has explicit quorum and evidence requirements.",
  },
  {
    icon: Users,
    title: "Council Voting",
    desc: "Multi-agent councils reach consensus through structured voting. Quorum thresholds increase with decision impact.",
  },
  {
    icon: FileCheck,
    title: "Evidence Packs",
    desc: "Every state transition produces an evidence pack: context, rationale, hashes, and chain links. Immutable and auditable.",
  },
  {
    icon: Fingerprint,
    title: "SHA-256 Hash Chain",
    desc: "Tamper-evident audit trail. Each evidence pack links to the previous via cryptographic hash. Full provenance.",
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5 },
  },
};

export default function GovernanceSection() {
  return (
    <section id="governance" className="py-24 px-6 md:px-12">
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
            style={{ color: "#F59E0B" }}
          >
            Trust & Control
          </p>
          <h2
            className="text-4xl md:text-5xl font-bold tracking-tight mb-4"
            style={{ color: "#E2E8F0" }}
          >
            Every Decision is Evidence-Backed
          </h2>
          <p
            className="text-base max-w-xl mx-auto"
            style={{ color: "#94A3B8" }}
          >
            A six-tier decision ladder with escalating quorum, council voting,
            human gates, and immutable cryptographic evidence chains.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          {/* Decision Ladder */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6 }}
          >
            <div className="space-y-3">
              {tiers.map((tier, i) => (
                <motion.div
                  key={tier.level}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: i * 0.08 }}
                  className="group flex items-center gap-4 p-4 rounded-xl transition-all duration-300"
                  style={{
                    background: "#0f1629",
                    border: "1px solid rgba(148, 163, 184, 0.08)",
                    boxShadow: "0 2px 16px rgba(0, 0, 0, 0.2)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = `${tier.color}30`;
                    e.currentTarget.style.boxShadow = `0 2px 16px rgba(0,0,0,0.2), 0 0 20px ${tier.color}08`;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                    e.currentTarget.style.boxShadow = "0 2px 16px rgba(0, 0, 0, 0.2)";
                  }}
                >
                  {/* Level badge */}
                  <div
                    className="w-14 h-14 rounded-xl flex items-center justify-center shrink-0"
                    style={{
                      background: `${tier.color}12`,
                      border: `1px solid ${tier.color}25`,
                    }}
                  >
                    <span className="text-sm font-bold" style={{ color: tier.color }}>
                      {tier.level}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <h3 className="text-sm font-semibold" style={{ color: "#E2E8F0" }}>
                        {tier.label}
                      </h3>
                      {tier.votes && (
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-semibold"
                          style={{
                            background: `${tier.color}15`,
                            color: tier.color,
                          }}
                        >
                          {tier.votes}
                        </span>
                      )}
                    </div>
                    <p className="text-xs" style={{ color: "#94A3B8" }}>
                      {tier.desc}
                    </p>
                  </div>

                  {/* Trust indicator bar */}
                  <div
                    className="w-1 h-8 rounded-full shrink-0"
                    style={{
                      background: `linear-gradient(to top, ${tier.color}20, ${tier.color})`,
                      opacity: 0.4 + (i * 0.1),
                    }}
                  />
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Feature cards */}
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-2 gap-4"
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-60px" }}
          >
            {features.map((feat) => (
              <motion.div
                key={feat.title}
                variants={itemVariants}
                className="group p-6 rounded-2xl transition-all duration-300"
                style={{
                  background: "#0f1629",
                  border: "1px solid rgba(148, 163, 184, 0.08)",
                  boxShadow: "0 4px 24px rgba(0, 0, 0, 0.2)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "rgba(245, 158, 11, 0.2)";
                  e.currentTarget.style.boxShadow = "0 4px 24px rgba(0,0,0,0.2), 0 0 30px rgba(245, 158, 11, 0.06)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "rgba(148, 163, 184, 0.08)";
                  e.currentTarget.style.boxShadow = "0 4px 24px rgba(0, 0, 0, 0.2)";
                }}
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center mb-4"
                  style={{
                    background: "rgba(245, 158, 11, 0.1)",
                    border: "1px solid rgba(245, 158, 11, 0.15)",
                  }}
                >
                  <feat.icon className="w-5 h-5" style={{ color: "#F59E0B" }} />
                </div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: "#E2E8F0" }}>
                  {feat.title}
                </h3>
                <p className="text-xs leading-relaxed" style={{ color: "#94A3B8" }}>
                  {feat.desc}
                </p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
