"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  Radio, ShieldCheck, ScanSearch,
  FileAudio, BarChart3, WifiOff,
} from "lucide-react";
import {
  useHealth, useSDRDevices, useCaptures,
  useAnalyses, useRFPolicies,
} from "@/lib/api/hooks";

function fmtFreq(hz: number) {
  if (hz >= 1e9) return `${(hz / 1e9).toFixed(2)} GHz`;
  if (hz >= 1e6) return `${(hz / 1e6).toFixed(1)} MHz`;
  return `${(hz / 1e3).toFixed(0)} kHz`;
}

function fmtBandwidth(hz: number) {
  return fmtFreq(hz);
}

const statusColor: Record<string, string> = {
  active: "text-sylion-green", idle: "text-sylion-amber", error: "text-sylion-red",
  completed: "text-sylion-green", running: "text-sylion-blue", pending: "text-sylion-amber",
  failed: "text-sylion-red",
};

export default function SDRPage() {
  const health = useHealth();
  const backendLive = health.data.status === "ok";

  const { data: devData } = useSDRDevices();
  const { data: capData } = useCaptures();
  const { data: anData } = useAnalyses();
  const { data: polData } = useRFPolicies();

  const devices: any[] = devData?.devices ?? [];
  const captures: any[] = capData?.captures ?? [];
  const analyses: any[] = anData?.analyses ?? [];
  const policies: any[] = polData?.policies ?? [];

  const [selectedTab, setSelectedTab] = useState<"devices" | "captures" | "analysis" | "policies">("devices");

  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Laboratorium SDR i sygnałów</h1>
            <p className="text-sm text-muted-foreground mt-1">Software-defined radio capture, signal analysis, and RF safety governance</p>
          </div>
        </div>
        <div className="rounded-xl border p-8 flex flex-col items-center justify-center gap-3" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <WifiOff className="w-10 h-10 text-muted-foreground" />
          <p className="text-sm font-medium text-foreground">Backend not reachable</p>
          <p className="text-xs text-muted-foreground">Start the SYLION backend to view live SDR data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Laboratorium SDR i sygnałów</h1>
          <p className="text-sm text-muted-foreground mt-1">Software-defined radio capture, signal analysis, and RF safety governance</p>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-sylion-green/10 text-sylion-green">
          Live
        </span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: "rgba(148,163,184,0.06)" }}>
        {(["devices", "captures", "analysis", "policies"] as const).map((tab) => (
          <button key={tab} onClick={() => setSelectedTab(tab)} className={cn("px-4 py-2 rounded-md text-sm font-medium transition-all", selectedTab === tab ? "bg-slate-800 text-foreground" : "text-muted-foreground hover:text-foreground")}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "SDR Devices", value: devices.length, icon: Radio, color: "text-sylion-blue" },
          { label: "Captures", value: captures.length, icon: FileAudio, color: "text-sylion-amber" },
          { label: "Analyses", value: analyses.length, icon: BarChart3, color: "text-sylion-green" },
          { label: "RF Policies", value: policies.length, icon: ShieldCheck, color: "text-primary" },
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

      {selectedTab === "devices" && (
        <div className="rounded-xl border overflow-hidden" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                <th className="text-left px-4 py-2.5">Device</th>
                <th className="text-left px-4 py-2.5">Type</th>
                <th className="text-left px-4 py-2.5">Frequency Range</th>
                <th className="text-right px-4 py-2.5">Sample Rate</th>
                <th className="text-left px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((d: any, i: number) => (
                <motion.tr key={d.sdr_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                  <td className="px-4 py-3"><div className="flex items-center gap-2"><Radio className="w-4 h-4 text-muted-foreground" /><span className="font-medium text-foreground">{d.sdr_id}</span></div></td>
                  <td className="px-4 py-3 text-muted-foreground">{d.device_type}</td>
                  <td className="px-4 py-3 text-muted-foreground">{d.frequency_range}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{d.sample_rate} MSps</td>
                  <td className="px-4 py-3"><span className={cn("text-xs font-medium", statusColor[d.status] || "text-muted-foreground")}>{d.status}</span></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedTab === "captures" && (
        <div className="rounded-xl border overflow-hidden" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                <th className="text-left px-4 py-2.5">Capture</th>
                <th className="text-left px-4 py-2.5">SDR</th>
                <th className="text-right px-4 py-2.5">Frequency</th>
                <th className="text-right px-4 py-2.5">Bandwidth</th>
                <th className="text-right px-4 py-2.5">Duration</th>
                <th className="text-left px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {captures.map((c: any, i: number) => (
                <motion.tr key={c.capture_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                  <td className="px-4 py-3"><div className="flex items-center gap-2"><FileAudio className="w-4 h-4 text-muted-foreground" /><span className="font-mono text-xs text-muted-foreground">{c.capture_id}</span></div></td>
                  <td className="px-4 py-3 text-muted-foreground">{c.sdr_id}</td>
                  <td className="px-4 py-3 text-right text-foreground">{fmtFreq(c.frequency_hz)}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{fmtBandwidth(c.bandwidth_hz)}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{c.duration_s}s</td>
                  <td className="px-4 py-3"><span className={cn("text-xs font-medium", statusColor[c.status] || "text-muted-foreground")}>{c.status}</span></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedTab === "analysis" && (
        <div className="rounded-xl border overflow-hidden" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          {analyses.length === 0 ? (
            <div className="p-6 text-center">
              <ScanSearch className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No signal analyses yet</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                  <th className="text-left px-4 py-2.5">Analysis</th>
                  <th className="text-left px-4 py-2.5">Capture</th>
                  <th className="text-left px-4 py-2.5">Modulation</th>
                  <th className="text-right px-4 py-2.5">SNR (dB)</th>
                  <th className="text-right px-4 py-2.5">Signals</th>
                  <th className="text-left px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((a: any, i: number) => (
                  <motion.tr key={a.analysis_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{a.analysis_id}</td>
                    <td className="px-4 py-3 text-muted-foreground">{a.capture_id}</td>
                    <td className="px-4 py-3 text-foreground">{a.modulation}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{a.snr_db.toFixed(1)}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{a.signals_detected}</td>
                    <td className="px-4 py-3"><span className={cn("text-xs font-medium", statusColor[a.status] || "text-muted-foreground")}>{a.status}</span></td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {selectedTab === "policies" && (
        <div className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <h2 className="text-sm font-semibold text-foreground mb-3">RF Safety Policies</h2>
          {policies.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No RF policies defined</p>
          ) : policies.map((p: any) => (
            <div key={p.policy_id || p.name} className="flex items-center justify-between py-2.5 border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
              <div className="flex items-center gap-3">
                <ShieldCheck className="w-4 h-4 text-primary" />
                <div>
                  <p className="text-sm font-medium text-foreground">{p.name || p.policy_id}</p>
                  <p className="text-xs text-muted-foreground font-mono">{p.rule}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">scope: {p.scope}</span>
                <span className={cn("text-xs px-2 py-0.5 rounded-full", p.active ? "bg-sylion-green/10 text-sylion-green" : "bg-muted/50 text-muted-foreground")}>
                  {p.active ? "Active" : "Inactive"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
