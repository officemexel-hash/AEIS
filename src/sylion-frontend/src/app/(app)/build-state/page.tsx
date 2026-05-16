"use client";

import { useBuildState } from "@/lib/api/hooks";
import { useHealth } from "@/lib/api/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Server, ClipboardList, AlertTriangle, GitCompare, Shield, WifiOff, RefreshCw } from "lucide-react";

export default function BuildStatePage() {
  const { data: health, loading: healthLoading, refresh: refreshHealth } = useHealth();
  const { data, loading, error, refresh } = useBuildState();
  const backendLive = health?.status === "ok";
  const initialLoading = healthLoading || (backendLive && loading);

  if (initialLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Ładowanie stanu budowy...
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((index) => (
            <Card key={index} className="h-28 animate-pulse bg-muted/30" />
          ))}
        </div>
      </div>
    );
  }

  if (!backendLive) {
    return (
      <Card className="p-8 bg-card border-sylion-red/20 text-center" role="alert">
        <WifiOff className="mx-auto h-8 w-8 text-sylion-red/70" />
        <h2 className="mt-3 text-lg font-semibold">Backend offline</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Stan budowy jest niedostępny, dopóki powierzchnia zdrowia backendu nie zgłosi `ok`.
        </p>
        <Button className="mt-4" variant="outline" size="sm" onClick={() => { refreshHealth(); refresh(); }}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Retry connection
        </Button>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-8 bg-card border-sylion-red/20 text-center" role="alert">
        <AlertTriangle className="mx-auto h-8 w-8 text-sylion-red/70" />
        <h2 className="mt-3 text-lg font-semibold">Stan budowy niedostępny</h2>
        <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        <Button className="mt-4" variant="outline" size="sm" onClick={() => refresh()}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Retry build-state query
        </Button>
      </Card>
    );
  }

  const workers = data?.workers || {};
  const assignments = data?.assignments || {};
  const alerts = data?.alerts || {};
  const drift = data?.drift || {};
  const contracts = data?.contracts || {};
  const hasBuildStateData =
    Boolean(workers.total) ||
    Boolean(assignments.total) ||
    Boolean(alerts.total_unresolved) ||
    Boolean(drift.total_open) ||
    Boolean(contracts.frozen) ||
    Array.isArray(alerts.list) && alerts.list.length > 0;

  if (!hasBuildStateData) {
    return (
      <Card className="p-8 bg-card border-sylion-border text-center">
        <Server className="mx-auto h-8 w-8 text-muted-foreground" />
        <h2 className="mt-3 text-lg font-semibold">No build-state records yet</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          This surface stays empty until worker assignments, alerts, drift findings, or contract freeze data are recorded.
        </p>
        <Button className="mt-4" variant="outline" size="sm" onClick={() => refresh()}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Refresh
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Stan budowy</h1>
        <Badge variant={contracts.frozen ? "default" : "secondary"}>
          {contracts.frozen ? "Frozen" : "Unfrozen"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Server className="h-4 w-4 text-muted-foreground" />
              Workers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{workers.total || 0}</div>
            <div className="text-xs text-muted-foreground">
              {workers.active || 0} active · {workers.offline || 0} offline
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <ClipboardList className="h-4 w-4 text-muted-foreground" />
              Assignments
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{assignments.total || 0}</div>
            <div className="text-xs text-muted-foreground">
              {assignments.assigned || 0} assigned · {assignments.in_progress || 0} in progress
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              Alerts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{alerts.total_unresolved || 0}</div>
            <div className="text-xs text-muted-foreground">Unresolved</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <GitCompare className="h-4 w-4 text-muted-foreground" />
              Drift
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{drift.total_open || 0}</div>
            <div className="text-xs text-muted-foreground">
              {drift.critical || 0} critical
            </div>
          </CardContent>
        </Card>
      </div>

      {contracts.frozen && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Shield className="h-4 w-4 text-muted-foreground" />
              Contract Freeze
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <div>Build ID: <span className="font-mono">{contracts.build_id}</span></div>
            <div>Frozen by: {contracts.frozen_by}</div>
            <div>Contracts: {contracts.contract_count}</div>
            <div>Events: {contracts.event_count}</div>
            <div>Dependencies: {contracts.dependency_count}</div>
          </CardContent>
        </Card>
      )}

      {alerts.list && alerts.list.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Recent Alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {alerts.list.map((alert: any) => (
              <div key={alert.alert_id} className="flex items-center justify-between text-sm border-b last:border-0 pb-2 last:pb-0">
                <div>
                  <Badge variant={alert.severity === "critical" ? "destructive" : "secondary"} className="mr-2">
                    {alert.severity}
                  </Badge>
                  {alert.message}
                </div>
                <span className="text-xs text-muted-foreground">{alert.alert_type}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
