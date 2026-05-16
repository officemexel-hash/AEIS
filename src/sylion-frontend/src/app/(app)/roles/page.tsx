"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useHealth, useRoles } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import {
  Shield,
  WifiOff,
  RefreshCw,
  Users,
  KeyRound,
  Lock,
  Activity,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Role {
  role_id: string;
  name: string;
  description?: string;
  permissions?: string[];
  users?: string[];
  created_at?: number;
}

/* ============================================================
   Helpers
   ============================================================ */

function formatTimestamp(ts: number | undefined): string {
  if (!ts) return "---";
  const date = typeof ts === "number" && ts > 1e12 ? new Date(ts) : new Date(ts);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ============================================================
   Page Component
   ============================================================ */

export default function RolesPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const healthData = healthRaw as { status: string; version: string; modules: number; endpoints: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const { data: rolesData, refresh: refreshRoles } = useRoles();

  const roles: Role[] = (rolesData as any).roles ?? [];

  /* ---------- Derived stats ---------- */
  const totalPermissions = useMemo(() => {
    const permSet = new Set<string>();
    roles.forEach((r) => {
      (r.permissions || []).forEach((p) => permSet.add(p));
    });
    return permSet.size;
  }, [roles]);

  const totalUsers = useMemo(() => {
    const userSet = new Set<string>();
    roles.forEach((r) => {
      (r.users || []).forEach((u) => userSet.add(u));
    });
    return userSet.size;
  }, [roles]);

  const handleRefreshAll = () => {
    fetchHealth();
    refreshRoles();
  };

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-36 bg-muted animate-pulse rounded" />
            <div className="h-4 w-52 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-64 bg-muted animate-pulse rounded-lg" />
      </div>
    );
  }

  /* ---------- Backend unreachable ---------- */
  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Role i uprawnienia</h1>
            <p className="text-sm text-muted-foreground">Access control and role management</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend Not Reachable</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            The SYLION backend is not responding. Roles, permissions, and user assignments require a running backend.
          </p>
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Retry Connection
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Main content ---------- */
  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Role i uprawnienia</h1>
            <p className="text-sm text-muted-foreground">Access control and role management</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS (2) ====== */}
      <div className="grid grid-cols-2 gap-3">
        {[
          {
            label: "Total Roles",
            value: roles.length,
            icon: Lock,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
          },
          {
            label: "Total Permissions",
            value: totalPermissions,
            icon: KeyRound,
            color: "text-sylion-amber",
            bgColor: "bg-sylion-amber/10",
          },
        ].map((stat, i) => {
          const SIcon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
            >
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{stat.label}</p>
                    <p className={cn("text-xl font-semibold mt-1 font-mono", stat.color)}>{stat.value}</p>
                  </div>
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", stat.bgColor)}>
                    <SIcon className={cn("w-4 h-4", stat.color)} />
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* ====== ROLES TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.15 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">Roles</h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {roles.length} roles
              </Badge>
            </div>
          </div>

          {roles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Shield className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-xs">No roles available</p>
              <p className="text-[10px] mt-1 opacity-60">Roles will appear here when configured through the security module</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border/20 hover:bg-transparent">
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Name</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Description</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Permissions</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Users</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {roles.map((role, idx) => {
                  return (
                    <TableRow key={role.role_id ?? idx} className="border-border/10 hover:bg-muted/10">
                      <TableCell className="text-xs font-medium">
                        <div className="flex items-center gap-1.5">
                          <Lock className="w-3 h-3 text-sylion-blue/60 shrink-0" />
                          <span>{role.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[250px]">
                        <span className="truncate block">{role.description || "---"}</span>
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="flex items-center gap-1.5">
                          <KeyRound className="w-3 h-3 text-sylion-amber/60" />
                          <span className="font-mono">{(role.permissions || []).length}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="flex items-center gap-1.5">
                          <Users className="w-3 h-3 text-sylion-green/60" />
                          <span className="font-mono">{(role.users || []).length}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-[11px] text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <Activity className="w-3 h-3 text-muted-foreground/40" />
                          {formatTimestamp(role.created_at)}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
