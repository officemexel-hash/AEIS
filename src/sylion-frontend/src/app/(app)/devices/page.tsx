"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  Smartphone, Wifi, Bluetooth, Usb, Search,
  Package, CheckCircle2, HardDrive, Activity,
  Loader2, WifiOff,
} from "lucide-react";
import {
  useHealth, useRegisteredDevices, useDiscoveredDevices,
  useDeployments, useDeviceTests,
} from "@/lib/api/hooks";
import { api } from "@/lib/api/client";

const transportIcon: Record<string, React.ElementType> = { usb: Usb, wifi: Wifi, bluetooth: Bluetooth };

const statusColor: Record<string, string> = {
  discovered: "text-sylion-blue", registered: "text-sylion-green", available: "text-sylion-amber", deployed: "text-emerald-400", active: "text-sylion-green", retired: "text-muted-foreground",
};

export default function DevicesPage() {
  const health = useHealth();
  const backendLive = health.data.status === "ok";

  const { data: regData, refresh: regRefresh } = useRegisteredDevices();
  const { data: discData, refresh: discRefresh } = useDiscoveredDevices();
  const { data: depData } = useDeployments();
  const { data: testData } = useDeviceTests();

  const [scanning, setScanning] = useState(false);
  const handleScan = async () => {
    setScanning(true);
    try {
      await api.scanDevices();
      regRefresh();
      discRefresh();
    } catch {} finally {
      setScanning(false);
    }
  };

  const registered: any[] = regData?.devices ?? [];
  const discovered: any[] = discData?.devices ?? [];
  const deployments: any[] = depData?.deployments ?? [];
  const tests: any[] = testData?.tests ?? [];

  const liveDevices = [
    ...registered,
    ...discovered.filter(d => !registered.some(r => r.device_id === d.device_id)),
  ];

  const liveDeployments = deployments;
  const liveTests = tests;

  const [selectedTab, setSelectedTab] = useState<"devices" | "deployments" | "tests">("devices");

  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Zarządzanie urządzeniami</h1>
            <p className="text-sm text-muted-foreground mt-1">Device discovery, registry, artifact deployment, and on-device testing</p>
          </div>
        </div>
        <div className="rounded-xl border p-8 flex flex-col items-center justify-center gap-3" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <WifiOff className="w-10 h-10 text-muted-foreground" />
          <p className="text-sm font-medium text-foreground">Backend not reachable</p>
          <p className="text-xs text-muted-foreground">Start the SYLION backend to view live device data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Zarządzanie urządzeniami</h1>
          <p className="text-sm text-muted-foreground mt-1">Device discovery, registry, artifact deployment, and on-device testing</p>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-sylion-green/10 text-sylion-green">
          Live
        </span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: "rgba(148,163,184,0.06)" }}>
        {(["devices", "deployments", "tests"] as const).map((tab) => (
          <button key={tab} onClick={() => setSelectedTab(tab)} className={cn("px-4 py-2 rounded-md text-sm font-medium transition-all", selectedTab === tab ? "bg-slate-800 text-foreground" : "text-muted-foreground hover:text-foreground")}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total Devices", value: liveDevices.length, icon: Smartphone, color: "text-sylion-blue" },
          { label: "Active", value: liveDevices.filter((d: any) => d.lifecycle === "active" || d.status === "active" || d.status === "registered").length, icon: CheckCircle2, color: "text-sylion-green" },
          { label: "Deployments", value: liveDeployments.length, icon: Package, color: "text-sylion-amber" },
          { label: "Tests Run", value: liveTests.length, icon: Activity, color: "text-sylion-blue" },
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
          <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
            <h2 className="text-sm font-semibold text-foreground">Device Registry</h2>
            <button onClick={handleScan} disabled={scanning} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-sylion-blue/10 text-sylion-blue hover:bg-sylion-blue/20 transition-colors disabled:opacity-50">
              {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              {scanning ? "Scanning..." : "Scan"}
            </button>
          </div>
          {liveDevices.length === 0 ? (
            <div className="p-6 text-center"><p className="text-sm text-muted-foreground">No devices found</p></div>
          ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                <th className="text-left px-4 py-2.5">Device</th>
                <th className="text-left px-4 py-2.5">Transport</th>
                <th className="text-left px-4 py-2.5">Firmware</th>
                <th className="text-left px-4 py-2.5">Status</th>
                <th className="text-left px-4 py-2.5">Lifecycle</th>
              </tr>
            </thead>
            <tbody>
              {liveDevices.map((d: any, i: number) => {
                const Icon = transportIcon[d.transport] || HardDrive;
                return (
                  <motion.tr key={d.device_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0 hover:bg-white/[0.02] transition-colors" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                    <td className="px-4 py-3"><div className="flex items-center gap-2"><Smartphone className="w-4 h-4 text-muted-foreground" /><span className="font-medium text-foreground">{d.model || d.device_id}</span><span className="text-xs text-muted-foreground">{d.device_id}</span></div></td>
                    <td className="px-4 py-3"><div className="flex items-center gap-1.5"><Icon className="w-3.5 h-3.5 text-muted-foreground" /><span className="text-muted-foreground capitalize">{d.transport}</span></div></td>
                    <td className="px-4 py-3 text-muted-foreground">{d.firmware || "-"}</td>
                    <td className="px-4 py-3"><span className={cn("text-xs font-medium", statusColor[d.status] || "text-muted-foreground")}>{d.status}</span></td>
                    <td className="px-4 py-3"><span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-muted-foreground">{d.lifecycle || d.status}</span></td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
          )}
        </div>
      )}

      {selectedTab === "deployments" && (
        <div className="rounded-xl border p-4" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          <h2 className="text-sm font-semibold text-foreground mb-3">Recent Deployments</h2>
          {liveDeployments.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No deployments yet</p>
          ) : liveDeployments.map((dep: any) => (
            <div key={dep.deploy_id || dep.id} className="flex items-center justify-between py-2 border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
              <div className="flex items-center gap-3"><Package className="w-4 h-4 text-sylion-amber" /><div><p className="text-sm font-medium text-foreground">{(dep.artifact_type || "apk").toUpperCase()} Deployment</p><p className="text-xs text-muted-foreground">{dep.device_id} / {(dep.artifact_hash || "").slice(0, 16)}</p></div></div>
              <span className={cn("text-xs px-2 py-0.5 rounded-full", dep.status === "deployed" ? "bg-sylion-green/10 text-sylion-green" : "bg-sylion-amber/10 text-sylion-amber")}>{dep.status}</span>
            </div>
          ))}
        </div>
      )}

      {selectedTab === "tests" && (
        <div className="rounded-xl border overflow-hidden" style={{ background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))", borderColor: "rgba(148,163,184,0.08)" }}>
          {liveTests.length === 0 ? (
            <div className="p-6 text-center">
              <Activity className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No on-device tests running</p>
              <button className="mt-3 px-4 py-2 rounded-lg text-xs font-medium bg-sylion-blue/10 text-sylion-blue hover:bg-sylion-blue/20 transition-colors">Run Contract Tests</button>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-[11px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                  <th className="text-left px-4 py-2.5">Test ID</th>
                  <th className="text-left px-4 py-2.5">Device</th>
                  <th className="text-left px-4 py-2.5">Suite</th>
                  <th className="text-left px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {liveTests.map((t: any, i: number) => (
                  <motion.tr key={t.test_id || i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="border-b last:border-0" style={{ borderColor: "rgba(148,163,184,0.04)" }}>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{t.test_id || t.id}</td>
                    <td className="px-4 py-3 text-foreground">{t.device_id}</td>
                    <td className="px-4 py-3 text-muted-foreground">{t.suite || "-"}</td>
                    <td className="px-4 py-3"><span className={cn("text-xs font-medium", t.status === "passed" ? "text-sylion-green" : t.status === "failed" ? "text-sylion-red" : "text-sylion-amber")}>{t.status}</span></td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
