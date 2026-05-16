"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import { useHealth } from "@/lib/api/hooks";

type LinkItem = {
  href: string;
  label: string;
  description: string;
  helpTip?: string;
};

type CanonicalSurfaceProps = {
  title: string;
  subtitle: string;
  canonicalStatus: string;
  aeisImpact: string;
  links: LinkItem[];
  titleHelpTip?: string;
};

export function CanonicalSurface({
  title,
  subtitle,
  canonicalStatus,
  aeisImpact,
  links,
  titleHelpTip,
}: CanonicalSurfaceProps) {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">
              {title}
              {titleHelpTip && <HelpTip text={titleHelpTip} />}
            </h1>
            <Badge variant="outline" className="border-sylion-amber/30 text-sylion-amber">
              MOSTEK KANONICZNY
            </Badge>
            <Badge
              variant="outline"
              className={backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red"}
            >
              {backendLive ? "BACKEND DZIAŁA" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>

      <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Status kanoniczny
          <HelpTip text="Stan kanonicznej weryfikacji modułu — opis tego co jest a co nie jest gotowe do oceny LIVE_VERIFIED. Pomaga audytorowi zrozumieć zakres bramki." />
        </p>
        <p className="mt-3 text-sm leading-relaxed text-foreground">{canonicalStatus}</p>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{aeisImpact}</p>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {links.map((item) => (
          <Link key={item.href} href={item.href}>
            <Card className="h-full border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5 transition hover:border-sylion-blue/40 hover:bg-[#111b31]">
              <p className="text-sm font-semibold text-foreground">{item.label}</p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{item.description}</p>
              <p className="mt-4 font-mono text-[11px] text-sylion-blue">{item.href}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
