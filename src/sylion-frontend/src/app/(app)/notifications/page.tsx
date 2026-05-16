"use client";

import { useState, useCallback, useMemo } from "react";
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
import { useHealth, useNotificationsList } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Bell,
  WifiOff,
  RefreshCw,
  Activity,
  Mail,
  MailOpen,
  Radio,
  Search,
  AlertTriangle,
  CheckCircle2,
  Info,
  Megaphone,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Notification {
  notification_id: string;
  timestamp?: number;
  title?: string;
  severity?: string;
  status?: string;
  read?: boolean;
  channel?: string;
  body?: string;
}

/* ============================================================
   Severity styling
   ============================================================ */

const severityStyles: Record<string, { badge: string; dot: string; text: string }> = {
  critical: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    dot: "bg-sylion-red",
    text: "text-sylion-red",
  },
  high: {
    badge: "border-orange-400/30 text-orange-400 bg-orange-400/5",
    dot: "bg-orange-400",
    text: "text-orange-400",
  },
  warning: {
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    dot: "bg-sylion-amber",
    text: "text-sylion-amber",
  },
  info: {
    badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    dot: "bg-sylion-blue",
    text: "text-sylion-blue",
  },
  success: {
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    dot: "bg-sylion-green",
    text: "text-sylion-green",
  },
};

/* ============================================================
   Helpers
   ============================================================ */

function formatTimestamp(ts: number | undefined): string {
  if (!ts) return "---";
  const date = typeof ts === "number" && ts > 1e12 ? new Date(ts) : new Date(ts);
  return date.toLocaleDateString("pl-PL", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getSeverityStyles(severity: string) {
  const normalized = (severity || "info").toLowerCase();
  return severityStyles[normalized] || severityStyles.info;
}

function getSeverityIcon(severity: string) {
  const normalized = (severity || "info").toLowerCase();
  if (normalized === "critical" || normalized === "high") return AlertTriangle;
  if (normalized === "warning") return AlertTriangle;
  if (normalized === "success") return CheckCircle2;
  return Info;
}

/* ============================================================
   Page Component
   ============================================================ */

export default function NotificationsPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const healthData = healthRaw as { status: string; version: string; modules: number; endpoints: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const { data: notificationsData, refresh: refreshNotifications } = useNotificationsList();

  const notifications: Notification[] = (notificationsData as any).notifications ?? [];

  /* ---------- Read/unread local tracking ---------- */
  const [readMap, setReadMap] = useState<Record<string, boolean>>({});

  /* ---------- Derived stats ---------- */
  const unreadCount = useMemo(() => {
    return notifications.filter((n) => {
      const localRead = readMap[n.notification_id];
      if (localRead !== undefined) return !localRead;
      return !n.read;
    }).length;
  }, [notifications, readMap]);

  const channelSet = useMemo(() => {
    const channels = new Set<string>();
    notifications.forEach((n) => {
      if (n.channel) channels.add(n.channel);
    });
    return channels;
  }, [notifications]);

  const handleRefreshAll = () => {
    fetchHealth();
    refreshNotifications();
  };

  /* ---------- Toggle read/unread ---------- */
  const toggleRead = useCallback((notificationId: string, currentRead: boolean) => {
    const newRead = !currentRead;
    setReadMap((prev) => ({ ...prev, [notificationId]: newRead }));

    if (newRead) {
      api.markNotificationRead(notificationId).catch(() => {});
    } else {
      api.markNotificationUnread(notificationId).catch(() => {});
    }
  }, []);

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
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
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
            <Bell className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Powiadomienia
              <HelpTip text="Strumień alert?w systemowych: zdarze?ia security, regresje, wyczerpanie budżetu, anomalie. Stan przeczytania synchronizowany lokalnie i z backendem." />
            </h1>
            <p className="text-sm text-muted-foreground">Zarzadzanie alertami i kanalami powiadomien</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend nieosięgalny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Powiadomienia, kana?y i status odczytu wymagaj? dzialajacego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
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
          <div className="w-9 h-9 rounded-lg bg-sylion-amber/10 border border-sylion-amber/20 flex items-center justify-center">
            <Bell className="w-4 h-4 text-sylion-amber" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Powiadomienia
              <HelpTip text="Strumień alert?w systemowych: zdarze?ia security, regresje, wyczerpanie budżetu, anomalie. Stan przeczytania synchronizowany lokalnie i z backendem." />
            </h1>
            <p className="text-sm text-muted-foreground">Zarzadzanie alertami i kanalami powiadomien</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {unreadCount > 0 && (
            <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5">
              {unreadCount} nieprzeczytanych
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS (3) ====== */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            label: "Wszystkich powiadomien",
            value: notifications.length,
            icon: Bell,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
            help: "Suma wszystkich powiadomien w systemie (przeczytanych i nieprzeczytanych). Powiadomienia starsze niz 30 dni archiwizowane automatycznie.",
          },
          {
            label: "Nieprzeczytane",
            value: unreadCount,
            icon: Mail,
            color: unreadCount > 0 ? "text-sylion-amber" : "text-sylion-green",
            bgColor: unreadCount > 0 ? "bg-sylion-amber/10" : "bg-sylion-green/10",
            help: "Liczba powiadomien wymagaj?cych uwagi operatora. Status przeczytania synchronizowany z backendem; oznaczenie znika dopiero po explicit klik.",
          },
          {
            label: "Kanaly",
            value: channelSet.size,
            icon: Radio,
            color: "text-purple-400",
            bgColor: "bg-purple-400/10",
            help: "Liczba aktywnych kanałów dystrybucji (np. system, security, budget, council). Konfigurowane w settings — każdy kanal ma osobny prog krytyczno?ci.",
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
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                      {stat.label}
                      <HelpTip text={stat.help} />
                    </p>
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

      {/* ====== NOTIFICATIONS TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.15 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-sylion-amber" />
              <h3 className="text-xs font-semibold">
                Powiadomienia
                <HelpTip text="Tabelaryczna lista wszystkich powiadomien posortowana po timestamp (najnowsze pierwsze). Klik ikony koperty przelacza stan przeczytany/nieprzeczytany." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {notifications.length} pozycji
              </Badge>
            </div>
          </div>

          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Search className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-xs">Brak dostepnych powiadomien</p>
              <p className="text-[10px] mt-1 opacity-60">Powiadomienia pojawia sie tutaj gdy zostana wygenerowane przez system</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border/20 hover:bg-transparent">
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Timestamp</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Tytul</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Krytycznosc</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Status</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Odczytane</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notifications.map((notif, idx) => {
                  const styles = getSeverityStyles(notif.severity || "info");
                  const SIcon = getSeverityIcon(notif.severity || "info");
                  const isRead = readMap[notif.notification_id] !== undefined
                    ? readMap[notif.notification_id]
                    : notif.read ?? false;

                  return (
                    <TableRow
                      key={notif.notification_id ?? idx}
                      className={cn(
                        "border-border/10 hover:bg-muted/10",
                        !isRead && "bg-sylion-amber/[0.02]"
                      )}
                    >
                      <TableCell className="text-[11px] text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <Activity className="w-3 h-3 text-muted-foreground/40" />
                          {formatTimestamp(notif.timestamp)}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="flex items-center gap-1.5 max-w-[300px]">
                          <SIcon className={cn("w-3 h-3 shrink-0", styles.text)} />
                          <span className={cn("truncate", !isRead && "font-medium")}>{notif.title || "---"}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("text-[9px]", styles.badge)}>
                          <span className={cn("w-1.5 h-1.5 rounded-full mr-1", styles.dot)} />
                          {(notif.severity || "info").toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[9px]",
                            isRead
                              ? "border-sylion-green/30 text-sylion-green bg-sylion-green/5"
                              : "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5"
                          )}
                        >
                          {isRead ? "PRZECZYTANE" : "NIEPRZECZYTANE"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => toggleRead(notif.notification_id, isRead)}
                          title={isRead ? "Oznacz jako nieprzeczytane" : "Oznacz jako przeczytane"}
                        >
                          {isRead ? (
                            <MailOpen className="w-3.5 h-3.5 text-muted-foreground" />
                          ) : (
                            <Mail className="w-3.5 h-3.5 text-sylion-amber" />
                          )}
                        </Button>
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
