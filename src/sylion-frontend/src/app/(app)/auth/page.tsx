"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { useApi } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Fingerprint,
  RefreshCw,
  WifiOff,
  Users,
  KeyRound,
  CheckCircle2,
  XCircle,
  Shield,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface AuthProvider {
  id: string;
  name: string;
  type: string;
  status: "active" | "inactive" | "error";
  sessions_count: number;
  last_used?: number;
}

interface AuthSession {
  id: string;
  user_id: string;
  provider_id?: string;
  created_at?: number;
  expires_at?: number;
}

interface ProvidersData {
  providers: AuthProvider[];
}

interface SessionsData {
  sessions: AuthSession[];
}

interface LoginResponse {
  token_id: string;
  token?: string;
  user_id: string;
  expires_at?: number;
}

/* ============================================================
   Helpers
   ============================================================ */

const typeBadgeStyles: Record<string, string> = {
  oauth2: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
  saml: "border-purple-400/30 text-purple-400 bg-purple-400/5",
  ldap: "border-cyan-400/30 text-cyan-400 bg-cyan-400/5",
  api_key: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
  token: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
  local: "border-muted-foreground/30 text-muted-foreground bg-muted/20",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const AUTH_TOKEN_KEY = "aeis_auth_token_id";
const AUTH_USER_KEY = "aeis_auth_user_id";

const providerStatusStyles: Record<string, { badge: string; text: string; iconBg: string }> = {
  active: {
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    text: "text-sylion-green",
    iconBg: "bg-sylion-green/10",
  },
  inactive: {
    badge: "border-muted-foreground/30 text-muted-foreground bg-muted/20",
    text: "text-muted-foreground",
    iconBg: "bg-muted/20",
  },
  error: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    text: "text-sylion-red",
    iconBg: "bg-sylion-red/10",
  },
};

/* ============================================================
   Page Component
   ============================================================ */

export default function AuthPage() {
  const [now] = useState(() => Date.now());
  const [loginUsername, setLoginUsername] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [currentUser, setCurrentUser] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(AUTH_USER_KEY)
  );
  const [loginStatus, setLoginStatus] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: providersData, refresh: refreshProviders } = useApi(
    () => api.listAuthProviders() as Promise<ProvidersData>,
    { providers: [] } as ProvidersData,
    15000
  );

  const { data: sessionsData } = useApi(
    () => api.listAuthSessions() as Promise<SessionsData>,
    { sessions: [] } as SessionsData,
    15000
  );

  const providers = (providersData.providers || []).map((provider: any) => ({
    id: provider.id ?? provider.provider_id ?? "",
    name: provider.name ?? provider.provider_id ?? "Unknown provider",
    type: provider.type ?? provider.provider_type ?? "local",
    status: provider.status ?? (provider.is_active ? "active" : "inactive"),
    sessions_count: provider.sessions_count ?? provider.active_sessions ?? 0,
    last_used: provider.last_used,
  })) as AuthProvider[];
  const sessions = (sessionsData.sessions || []).map((session: any) => ({
    id: session.id ?? session.session_id ?? "",
    user_id: session.user_id ?? "",
    provider_id: session.provider_id,
    created_at: session.created_at && session.created_at < 1e12 ? session.created_at * 1000 : session.created_at,
    expires_at: session.expires_at,
  })) as AuthSession[];

  /* ---------- Derived stats ---------- */
  const activeSessions = useMemo(
    () => sessions.length,
    [sessions]
  );
  const tokensIssued = useMemo(
    () => sessions.filter((s) => s.created_at && now - s.created_at < 86400000).length,
    [now, sessions]
  );

  async function loginOperator(e: React.FormEvent) {
    e.preventDefault();
    setLoggingIn(true);
    setLoginStatus(null);
    try {
      const providersRes = await fetch(`${API_BASE}/api/v1/auth/providers/list?type=local`);
      if (!providersRes.ok) {
        throw new Error(`Nie można pobrać providerów auth: ${providersRes.status}`);
      }
      const providersJson = (await providersRes.json()) as ProvidersData;
      let provider = (providersJson.providers || []).find((item: any) => {
        const type = item.provider_type ?? item.type;
        const active = item.is_active ?? item.status === "active";
        return type === "local" && active;
      }) as any;
      if (!provider) {
        const createRes = await fetch(`${API_BASE}/api/v1/auth/providers`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "local", provider_type: "local", config_json: {} }),
        });
        if (!createRes.ok) {
          throw new Error(`Nie można utworzyć providera local: ${createRes.status}`);
        }
        provider = await createRes.json();
      }
      const providerId = provider.provider_id ?? provider.id;
      const authRes = await fetch(`${API_BASE}/api/v1/auth/authenticate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_id: providerId,
          credentials_json: {
            username: loginUsername,
            user_id: loginUsername,
            password: loginPassword,
          },
        }),
      });
      if (!authRes.ok) {
        const body = await authRes.text().catch(() => "");
        throw new Error(`Logowanie odrzucone: ${authRes.status} ${body.slice(0, 120)}`);
      }
      const authJson = (await authRes.json()) as LoginResponse;
      window.localStorage.setItem(AUTH_TOKEN_KEY, authJson.token_id);
      window.localStorage.setItem(AUTH_USER_KEY, authJson.user_id);
      setCurrentUser(authJson.user_id);
      setLoginStatus("Zalogowano. Token bedzie dolaczany do wywolan API dashboardu.");
      setLoginPassword("");
    } catch (err) {
      setLoginStatus(err instanceof Error ? err.message : "Logowanie nie powiodlo sie");
    } finally {
      setLoggingIn(false);
    }
  }

  function logoutOperator() {
    window.localStorage.removeItem(AUTH_TOKEN_KEY);
    window.localStorage.removeItem(AUTH_USER_KEY);
    setCurrentUser(null);
    setLoginStatus("Wylogowano lokalnego operatora.");
  }

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-44 bg-muted animate-pulse rounded" />
            <div className="h-4 w-56 bg-muted animate-pulse rounded mt-1" />
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
            <Fingerprint className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Uwierzytelnianie</h1>
            <p className="text-sm text-muted-foreground">Dostawcy tożsamości i zarządzanie sesjami</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane uwierzytelniania wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { fetchHealth(); refreshProviders(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Summary cards ---------- */
  const summaryCards = [
    {
      label: "Dostawcy",
      value: providers.length,
      icon: Shield,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Aktywne sesje",
      value: activeSessions,
      icon: Users,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Tokeny wydane (24h)",
      value: tokensIssued,
      icon: KeyRound,
      color: "text-sylion-amber",
      bgColor: "bg-sylion-amber/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-purple-400/10 border border-purple-400/20 flex items-center justify-center">
            <Fingerprint className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Uwierzytelnianie</h1>
            <p className="text-sm text-muted-foreground">Dostawcy tożsamości i zarządzanie sesjami</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refreshProviders()}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Odśwież
        </Button>
      </div>

      {/* ====== SUMMARY CARDS ====== */}
      <div className="grid grid-cols-3 gap-3">
        {summaryCards.map((stat) => {
          const SIcon = stat.icon;
          return (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
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

      <Card className="p-4 bg-[#0f1629] border-sylion-border">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold">Sesja operatora dashboardu</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              W trybie audytu bez bypassow operacje POST/PATCH/DELETE wymagaj? tokenu Bearer.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Aktualny operator: {currentUser ? <span className="text-sylion-green">{currentUser}</span> : "brak aktywnej sesji"}
            </p>
          </div>
          {currentUser && (
            <Button type="button" variant="outline" size="sm" onClick={logoutOperator}>
              Wyloguj
            </Button>
          )}
        </div>
        <form onSubmit={loginOperator} className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <input
            type="text"
            value={loginUsername}
            onChange={(e) => setLoginUsername(e.target.value)}
            placeholder="uzytkownik"
            className="rounded-md border border-border/50 bg-background/60 px-3 py-2 text-sm"
          />
          <input
            type="password"
            value={loginPassword}
            onChange={(e) => setLoginPassword(e.target.value)}
            placeholder="haslo operatora"
            className="rounded-md border border-border/50 bg-background/60 px-3 py-2 text-sm"
          />
          <Button type="submit" disabled={loggingIn || !loginUsername.trim() || !loginPassword}>
            {loggingIn ? "Logowanie..." : "Zaloguj operatora"}
          </Button>
        </form>
        {loginStatus && (
          <p className="mt-3 rounded-md border border-border/40 bg-background/40 px-3 py-2 text-xs text-muted-foreground">
            {loginStatus}
          </p>
        )}
      </Card>

      {/* ====== PROVIDERS TABLE ====== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-xs font-medium text-muted-foreground">Dostawcy uwierzytelniania</h3>
          </div>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            {providers.length} skonfigurowanych
          </span>
        </div>
        <div className="divide-y divide-border/20">
          {providers.map((provider, idx) => {
            const statusStyles = providerStatusStyles[provider.status] || providerStatusStyles.inactive;
            const typeBadge = typeBadgeStyles[provider.type] || "border-border/50 text-muted-foreground bg-muted/20";
            return (
              <motion.div
                key={provider.id || idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.03, duration: 0.2 }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors"
              >
                {/* Provider icon */}
                <div className={cn("w-7 h-7 rounded-md flex items-center justify-center shrink-0", statusStyles.iconBg)}>
                  {provider.status === "active" ? (
                    <CheckCircle2 className={cn("w-3.5 h-3.5", statusStyles.text)} />
                  ) : provider.status === "error" ? (
                    <XCircle className={cn("w-3.5 h-3.5", statusStyles.text)} />
                  ) : (
                    <Shield className="w-3.5 h-3.5 text-muted-foreground" />
                  )}
                </div>

                {/* Name */}
                <span className="text-xs font-medium flex-1 min-w-0 truncate">{provider.name}</span>

                {/* Type badge */}
                <Badge variant="outline" className={cn("text-[9px] shrink-0", typeBadge)}>
                  {provider.type.toUpperCase()}
                </Badge>

                {/* Status badge */}
                <Badge variant="outline" className={cn("text-[9px] shrink-0", statusStyles.badge)}>
                  {provider.status.toUpperCase()}
                </Badge>

                {/* Sessions count */}
                <span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0 w-24 justify-end font-mono">
                  <Users className="w-2.5 h-2.5" />
                  {provider.sessions_count || 0} sesji
                </span>
              </motion.div>
            );
          })}

          {providers.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Fingerprint className="w-6 h-6 text-muted-foreground mb-2" />
              <p className="text-xs text-muted-foreground">Brak skonfigurowanych dostawców</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
