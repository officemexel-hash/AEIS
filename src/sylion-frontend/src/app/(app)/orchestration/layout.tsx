"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  Network,
  Scale,
  Clock,
  Wrench,
  Cpu,
  TestTube,
  Users,
  Share2,
  MessageSquare,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/orchestration/llm-routing",    icon: Network,       label: "Routing LLM Judge",       badge: "J1" },
  { href: "/orchestration/council-rules",  icon: Scale,         label: "Reguły Rady",             badge: "J2" },
  { href: "/orchestration/auditor",        icon: Clock,         label: "Rytm Audytora",           badge: "J3" },
  { href: "/orchestration/fixer",          icon: Wrench,        label: "Protokół Fixera",         badge: "J4" },
  { href: "/orchestration/dispatch",       icon: Cpu,           label: "Dispatch Agentów",        badge: "J5" },
  { href: "/orchestration/tests",          icon: TestTube,      label: "Katalog Testów",          badge: "J6" },
  { href: "/orchestration/teams",          icon: Users,         label: "Formowanie Zespołów",     badge: "J7" },
  { href: "/orchestration/event-map",      icon: Share2,        label: "Mapa Zdarzeń",            badge: "J8" },
  { href: "/orchestration/conversations",  icon: MessageSquare, label: "Rozmowy Modeli",          badge: "J9" },
];

export default function OrchestrationLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex gap-6 min-h-[calc(100vh-120px)]">
      {/* Sidebar */}
      <aside className="w-52 shrink-0">
        <div className="sticky top-6">
          <div className="mb-4">
            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest px-2 mb-2">
              Meta-Orkiestracja
            </p>
          </div>
          <nav className="space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname?.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[11px] transition-colors group",
                    active
                      ? "bg-accent-blue-dim text-sylion-blue"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                  )}
                >
                  <Icon className={cn("w-3.5 h-3.5 shrink-0", active ? "text-sylion-blue" : "text-muted-foreground group-hover:text-foreground")} />
                  <span className="flex-1 font-medium truncate">{item.label}</span>
                  <span className={cn(
                    "text-[8px] font-mono px-1 py-0.5 rounded",
                    active ? "bg-sylion-blue/20 text-sylion-blue" : "bg-muted/50 text-muted-foreground"
                  )}>
                    {item.badge}
                  </span>
                </Link>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
}
