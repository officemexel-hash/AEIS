"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const STORAGE_KEY = "sylion.operator_mobile.operator_id";
const DEFAULT_OPERATOR_ID = "operator-main";

export interface MobileDevice {
  device_id: string;
  operator_id: string;
  device_token: string;
  platform: string;
  device_label?: string;
  active?: number;
  created_at?: number;
  last_seen_at?: number;
}

export interface MobileTicket {
  ticket_id: string;
  origin: string;
  project_id?: string | null;
  decision_class: string;
  gate_type: string;
  priority: string;
  title: string;
  summary: string;
  payload?: Record<string, unknown>;
  requested_by?: string;
  created_at?: number;
  sla_deadline?: number;
  state: string;
  resolved_by?: string | null;
  resolved_at?: number | null;
  resolution_reason?: string | null;
  delivery_targets?: number;
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  const text = await res.text();
  if (!text.trim()) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

export function formatPriority(priority: string): string {
  return (priority || "P2").toUpperCase();
}

export function formatTimestamp(timestamp?: number | null): string {
  if (!timestamp) return "---";
  return new Date(timestamp * 1000).toLocaleString();
}

export function priorityTone(priority: string): string {
  const normalized = (priority || "P2").toUpperCase();
  if (normalized === "P0" || normalized === "P1") return "border-sylion-red/30 text-sylion-red";
  if (normalized === "P2") return "border-sylion-amber/30 text-sylion-amber";
  return "border-sylion-blue/30 text-sylion-blue";
}

export function stateTone(state: string): string {
  const normalized = (state || "pending").toLowerCase();
  if (normalized === "approved") return "border-sylion-green/30 text-sylion-green";
  if (normalized === "rejected" || normalized === "expired") return "border-sylion-red/30 text-sylion-red";
  return "border-sylion-amber/30 text-sylion-amber";
}

export function useOperatorId() {
  const [operatorId, setOperatorId] = useState(DEFAULT_OPERATOR_ID);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setOperatorId(stored);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const updateOperatorId = (value: string) => {
    const next = value || DEFAULT_OPERATOR_ID;
    setOperatorId(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return { operatorId, setOperatorId: updateOperatorId };
}

function useMobileResource<T>(
  fetcher: () => Promise<T>,
  emptyValue: T,
  refreshMs?: number,
) {
  const [data, setData] = useState<T>(emptyValue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const emptyValueRef = useRef(emptyValue);

  useEffect(() => {
    emptyValueRef.current = emptyValue;
  }, [emptyValue]);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (mountedRef.current) setData(result);
      })
      .catch((err) => {
        if (mountedRef.current) setData(emptyValueRef.current);
        if (mountedRef.current) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
  }, [fetcher]);

  useEffect(() => {
    mountedRef.current = true;
    queueMicrotask(() => refresh());

    let interval: ReturnType<typeof setInterval> | null = null;
    if (refreshMs) {
      interval = setInterval(() => refresh(), refreshMs);
    }

    return () => {
      mountedRef.current = false;
      if (interval) clearInterval(interval);
    };
  }, [refresh, refreshMs]);

  return { data, loading, error, refresh };
}

export function useOperatorMobileQueue(operatorId: string) {
  const fetcher = useCallback(
    () => request<{ tickets: MobileTicket[]; count: number }>(`/api/v1/mobile/queue?operator_id=${encodeURIComponent(operatorId)}`),
    [operatorId],
  );
  return useMobileResource(
    fetcher,
    { tickets: [], count: 0 },
    10000,
  );
}

export function useOperatorMobileDevices(operatorId: string) {
  const fetcher = useCallback(
    () => request<{ devices: MobileDevice[]; count: number }>(`/api/v1/mobile/devices?operator_id=${encodeURIComponent(operatorId)}`),
    [operatorId],
  );
  return useMobileResource(
    fetcher,
    { devices: [], count: 0 },
    15000,
  );
}

export function useOperatorMobileTicket(ticketId: string, operatorId: string) {
  const fetcher = useCallback(
    () => request<MobileTicket>(`/api/v1/mobile/queue/${encodeURIComponent(ticketId)}?operator_id=${encodeURIComponent(operatorId)}`),
    [operatorId, ticketId],
  );
  return useMobileResource<MobileTicket | null>(
    fetcher,
    null,
    10000,
  );
}

export function bindMobileDevice(body: {
  operator_id: string;
  device_token: string;
  platform: string;
  device_label: string;
}) {
  return request<{ ok: boolean; device: MobileDevice | null; count: number }>("/api/v1/mobile/devices/bind", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function unbindMobileDevice(deviceId: string, operatorId: string) {
  return request<{ device_id: string; removed: boolean }>(
    `/api/v1/mobile/devices/${encodeURIComponent(deviceId)}?operator_id=${encodeURIComponent(operatorId)}`,
    { method: "DELETE" },
  );
}

export function decideMobileTicket(ticketId: string, body: {
  decision: "approved" | "rejected";
  reviewer: string;
  reason: string;
}) {
  return request<MobileTicket>(`/api/v1/mobile/queue/${encodeURIComponent(ticketId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
