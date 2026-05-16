"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  Signal, ShieldCheck, Smartphone, ScanSearch,
  Activity, AlertTriangle, FileCheck, Radio, WifiOff,
} from "lucide-react";
import {
  useHealth, useRANStacks, useCoreNetworks, useUEDevices,
  useIsolationChecks, useAttackVectors, useCPAnalyses, useCellularEvidence,
} from "@/lib/api/hooks";

const statusColor: Record<string, string> = {
  running: "text-sylion-green", stopped: "text-sylion-red", error: "text-sylion-amber",
  attached: "text-sylion-green", detached: "text-muted-foreground",
  pass: "text-sylion-green", fail: "text-sylion-red", warning: "text-sylion-amber",
  documented: "text-sylion-blue", tested: "text-sylion-green", mitigated: "text-sylion-amber",
};

const severityColor: Record<string, string> = {
  critical: "text-sylion-red", high: "text-orange-400", medium: "text-sylion-amber", low: "text-sylion-green",
};

export default function CellularPage() {
  const health = useHealth();
  const backendLive = health?.data?.status === "ok";

  const { data: ranData } = useRANStacks();
  const { data: coreData } = useCoreNetworks();
  const { data: ueData } = useUEDevices();
  const { data: isoData } = useIsolationChecks();
  const { data: avData } = useAttackVectors();
  const { data: cpData } = useCPAnalyses();
  const { data: evData } = useCellularEvidence();

  const ranStacks: any[] = ranData?.stacks ?? [];
  const cores: any[] = coreData?.cores ?? [];
  const ues: any[] = ueData?.ues ?? [];
  const isolations: any[] = isoData?.checks ?? [];
  const attacks: any[] = avData?.vectors ?? [];
  const analyses: any[] = cpData?.analyses ?? [];
  const evidence: any[] = evData?.evidence ?? [];

  const allPassed = isolations.length > 0 && isolations.every((c: any) => c.result === "pass");

  const [selectedTab, setSelectedTab] = useState<"infrastructure" | "isolation" | "attacks" | "evidence">("infrastructure");

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Laboratorium bezpieczeństwa sieci komórkowej</h1>
          <p className="text-sm text-muted-foreground mt-1">RAN emulation, core network simulation, UE management, and security research</p>
        </div>
        <span className={cn("text-xs px-2.5 py-1 rounded-full", backendLive ? "bg-sylion-green/10 text-sylion-green" : "bg-sylion-red/10 text-sylion-red")}>
          {backendLive ? "Live" : "Offline"}
        </span>
      </div>

      {/* Backend not reachable banner */}
      {!backendLive && (
        <div className="rounded-xl border border-sylion-red/20 p-4 flex items-center gap-3" style={{ background: "rgba(239,68,68,0.05)" }}>
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "rgba(239,68,68,0.1)" }}>
            <WifiOff className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <p className="text-sm font-semibold text-sylion-red">Backend not reachable</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              The SYLION backend is not responding. Start the backend to see live cellular lab data.
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: "rgba(148,163,184,0.06)" }}>
        {(["infrastructure", "isolation", "attacks", "evidence"] as const).map((tab) => (
          <button key={tab} onClick={() => setSelectedTab(tab)} className={cn("px-4 py-2 rounded-md text-sm font-medium transition-all", selectedTab === tab ? "bg-slate-800 text-foreground" : "text-muted-foreground hover:text-foreground")}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "RAN Stacks", value: ranStacks.length, icon: Radio, color: "text-sylion-blue" },
          { label: "Core Networks", value: cores.length, icon: Signal, color: "text-sylion-green" },
          { label: "UE Devices", value: ues.length, icon: Smartphone, color: "text-sylion-amber" },
          { label: "RF Isolation", value: allPassed ? "Secure" : "Check", icon: allPassed ? ShieldCheck : AlertTriangle, color: allPassed ? "text-sylion-green" : "text-sylion-amber" },
        ].map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{s.label}</p>
              <s.icon className={cn("w-4 h-4", s.color)} />
            </div>
            <p className="text-2xl font-bold text-foreground">{s.value}</p>
          </motion.div>
        ))}
      </div>

      {selectedTab === "infrastructure" && (
        <div className="space-y-4">
          {/* RAN Stacks */}
          <div className="rounded-xl border overflow-hidden" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
            <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
              <h2 className="text-sm font-semibold text-foreground">RAN Stacks</h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                  <th className="text-left px-4 py-2.5">Stack</th>
                  <th className="text-left px-4 py-2.5">Technology</th>
                  <th className="text-left px-4 py-2.5">Band</th>
                  <th className="text-right px-4 py-2.5">eNB/gNB</th>
                  <th className="text-left px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {ranStacks.map((r: any, i: number) => (
                  <motion.tr key={r.stack_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                    <td className="px-4 py-3 font-medium text-foreground">{r.stack_id}</td>
                    <td className="px-4 py-3 text-muted-foreground">{r.tech}</td>
                    <td className="px-4 py-3 text-muted-foreground">{r.band}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{r.enb_count}</td>
                    <td className="px-4 py-3"><span className={cn("text-xs font-medium", statusColor[r.status] || "text-muted-foreground")}>{r.status}</span></td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Core Networks + UE side by side */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
              <h2 className="text-sm font-semibold text-foreground mb-3">Core Networks</h2>
              {cores.map((c: any) => (
                <div key={c.core_id} className="flex items-center justify-between py-2 border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                  <div className="flex items-center gap-2"><Signal className="w-4 h-4 text-sylion-green" /><div><p className="text-sm font-medium text-foreground">{c.core_id}</p><p className="text-xs text-muted-foreground">{c.type} / APN: {c.apn}</p></div></div>
                  <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">{c.ue_count} UE</span><span className={cn("text-xs font-medium", statusColor[c.status])}>{c.status}</span></div>
                </div>
              ))}
            </div>
            <div className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
              <h2 className="text-sm font-semibold text-foreground mb-3">User Equipment</h2>
              {ues.map((u: any) => (
                <div key={u.ue_id} className="flex items-center justify-between py-2 border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                  <div className="flex items-center gap-2"><Smartphone className="w-4 h-4 text-muted-foreground" /><div><p className="text-sm font-medium text-foreground">{u.ue_id}</p><p className="text-xs text-muted-foreground font-mono">IMSI {u.imsi}</p></div></div>
                  <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">{u.type}</span><span className={cn("text-xs font-medium", statusColor[u.status] || "text-muted-foreground")}>{u.status}</span></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {selectedTab === "isolation" && (
        <div className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <h2 className="text-sm font-semibold text-foreground mb-3">RF Isolation Checks</h2>
          {isolations.length === 0 ? (
            <div className="text-center py-4"><ShieldCheck className="w-8 h-8 text-muted-foreground mx-auto mb-2" /><p className="text-sm text-muted-foreground">No isolation checks performed yet</p></div>
          ) : isolations.map((c: any) => (
            <div key={c.check_id} className="flex items-center justify-between py-2.5 border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
              <div className="flex items-center gap-3">
                <ShieldCheck className={cn("w-4 h-4", statusColor[c.result] || "text-muted-foreground")} />
                <div>
                  <p className="text-sm font-medium text-foreground">{c.type}</p>
                  <p className="text-xs text-muted-foreground">{c.details}</p>
                </div>
              </div>
              <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", c.result === "pass" ? "bg-sylion-green/10 text-sylion-green" : "bg-sylion-red/10 text-sylion-red")}>
                {c.result.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      )}

      {selectedTab === "attacks" && (
        <div className="rounded-xl border overflow-hidden" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                <th className="text-left px-4 py-2.5">Vector</th>
                <th className="text-left px-4 py-2.5">Category</th>
                <th className="text-left px-4 py-2.5">Severity</th>
                <th className="text-left px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {attacks.map((a: any, i: number) => (
                <motion.tr key={a.vector_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                  <td className="px-4 py-3"><div className="flex items-center gap-2"><AlertTriangle className={cn("w-4 h-4", severityColor[a.severity] || "text-muted-foreground")} /><span className="font-medium text-foreground">{a.name}</span></div></td>
                  <td className="px-4 py-3"><span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-muted-foreground">{a.category}</span></td>
                  <td className="px-4 py-3"><span className={cn("text-xs font-medium", severityColor[a.severity])}>{a.severity}</span></td>
                  <td className="px-4 py-3"><span className={cn("text-xs font-medium", statusColor[a.status] || "text-muted-foreground")}>{a.status}</span></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedTab === "evidence" && (
        <div className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <h2 className="text-sm font-semibold text-foreground mb-3">Cellular Evidence</h2>
          {evidence.length === 0 ? (
            <div className="text-center py-4"><FileCheck className="w-8 h-8 text-muted-foreground mx-auto mb-2" /><p className="text-sm text-muted-foreground">No evidence collected yet</p></div>
          ) : evidence.map((e: any) => (
            <div key={e.evidence_id} className="flex items-center justify-between py-2.5 border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
              <div className="flex items-center gap-3">
                <FileCheck className="w-4 h-4 text-primary" />
                <div>
                  <p className="text-sm font-medium text-foreground">{e.evidence_id}</p>
                  <p className="text-xs text-muted-foreground">Source: {e.source} / Type: {e.type}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-muted-foreground">{e.hash}</span>
                <span className={cn("text-xs px-2 py-0.5 rounded-full", e.integrity ? "bg-sylion-green/10 text-sylion-green" : "bg-sylion-red/10 text-sylion-red")}>
                  {e.integrity ? "Valid" : "Invalid"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
