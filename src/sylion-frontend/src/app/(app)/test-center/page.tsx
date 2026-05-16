"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useHealth } from "@/lib/api/hooks";
import { motion } from "framer-motion";
import {
  TestTube, Network, Activity, Shield, GitBranch,
  Beaker, FileCheck, Users, AlertCircle, WifiOff, ShieldAlert,
} from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const SECTIONS = [
  {
    href: "/test-center/dashboard",
    icon: Activity,
    title: "Pulpit testów projektu",
    desc: "Status karty testówej, pokrycie, ostatnie uruchomienia, blokery i stan bramki wdrożenia.",
    help: "Centralny widok zdrowia projektu testówego: karta testów, KPI pokrycia, ostatnie wyniki, blokery i bramka wydania. Wejdź, gdy chcesz szybko sprawdźić, czy można wypuszczać wersję.",
  },
  {
    href: "/test-center/truth-alignment",
    icon: Network,
    title: "Wyrównanie prawdy",
    desc: "Macierz Źródło Prawdy vs Masterplan vs środowisko wykonania vs API vs UI vs testy vs dokumentacja.",
    help: "SprawdŹa spójność 7 warstw prawdy: Źródła Prawdy, Masterplanu, środowiska wykonania, API, UI, testów i dokumentacji. Jeżeli warstwy się rozjeżdżają, powstaje drift blokujący wydanie.",
  },
  {
    href: "/test-center/simulation",
    icon: Beaker,
    title: "Centrum symulacji",
    desc: "Gałęzie, warstwy L0-L4, persony, wstrzykiwanie błędów i śledzenie trace'ów.",
    help: "Uruchamia symulacje L0-L4 (kontrakt, sandbox, workflow, decyzja, błąd) na izolowanych gałęziach. Pozwala testówać scenariusze bez ryzyka dla produkcji. Domyślnie: model_mode=isolated, persistence=audit-profile.",
  },
  {
    href: "/test-center/auto-repair",
    icon: GitBranch,
    title: "Rejestr autonaprawy",
    desc: "Znaleziska, statusy R0-R9, raporty regulatora pętli i dowody regresji.",
    help: "Pokazuje aktywne sesje autonaprawy testów w cyklu R0-R9 oraz raporty regulatora pętli: limity prób i eskalacje. Domyślnie: maksymalnie 3 próby na znalezisko, potem eskalacja do operatora.",
  },
  {
    href: "/test-center/human-lab",
    icon: Users,
    title: "Laboratorium operatora",
    desc: "Persony, scenariusze, ocena zrozumiałości i heatmapy zachowań.",
    help: "Zarządza katalogiem person operatora i scenariuszy. Symuluje osoby o różnym poziomie wiedzy, tolerancji ryzyka i podatności na błędy. Użyj do ewaluacji UX i zrozumiałości.",
  },
  {
    href: "/test-center/release-gate",
    icon: Shield,
    title: "Bramka wdrożenia",
    desc: "Lista kontrolna 12+6, promocja RC, zatwierdzenie produkcji i rollback.",
    help: "Bramka decyzyjna między kandydatem wydania a produkcją. Blokuje wydanie, dopóki wszystkie warunki nie są spełnione. Wejdź przed każdą promocją środowiska.",
  },
  {
    href: "/test-center/theater",
    icon: Network,
    title: "Teatr modeli i agentów",
    desc: "Topologia modeli, agentów, ról, rozmów, zadań i snapshot runtime przez WebSocket.",
    help: "Osobny widok W11/W14 dla Teatru modeli i agentów. SprawdŹa czy zespoły, role, rozmowy i zadania są widoczne w UI, a dane płyną z runtime przez WebSocket zamiast z atrap.",
  },
  {
    href: "/test-center/no-mock-scan",
    icon: ShieldAlert,
    title: "Bez mocków i stubów",
    desc: "Skan produkcyjnej powierzchni UI/API pod dane demonstracyjne, banery mocków, ekrany szkieletowe i puste Promise.resolve.",
    help: "Twardy test uczciwości środowiska wykonania. Produkcyjne ekrany nie mogą udawać gotowej funkcji mockiem, stubem ani fallbackiem demo. Trafienie blokujące powinno zatrzymać wydanie do poprawki.",
  },
  {
    href: "/test-center/catalog",
    icon: FileCheck,
    title: "Katalog testów",
    desc: "Wszystkie testy T0-T19, status, ostatnie wyniki i akcja uruchom teraz.",
    help: "Pełny katalog klas testów T0-T19 z procentem zaliczenia, liczbą uruchomień i historią. Filtruj po project_id, aby zobaczyć kontekst projektu. Kliknij wiersz, aby uruchomić ponownie.",
  },
];

export default function TestCenterHubPage() {
  const { data: healthRaw, loading: healthLoading } = useHealth();
  const health = healthRaw as { status?: string };
  const backendLive = health?.status === "ok";
  const backendPending = healthLoading || health?.status === "unknown";

  return (
    <div className="space-y-6 p-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <TestTube className="w-6 h-6" />
              Centrum Testów
              <HelpTip text="Hub W14: testówanie, symulacja, autonaprawa i bramka wdrożenia. Jedno miejsce do oceny gotowości projektu do wydania. Każdy kafelek niżej prowadzi do oddzielnego narzędzia." />
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              W14 - testówanie, symulacja, naprawa i zarządzanie wdrożeniem
            </p>
          </div>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "BACKEND DZIAŁA" : backendPending ? "ŁĄCZENIE Z BACKENDEM" : "BACKEND NIEDOSTĘPNY"}
          </Badge>
        </div>
      </motion.div>

      {!backendLive && !backendPending && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-4 flex items-center gap-3">
            <WifiOff className="w-5 h-5 text-amber-600" />
            <span className="text-sm text-amber-700">
              Backend niedostępny - akcje destrukcyjne wyłączone. Ekran nie podstawia danych przykładowych.
            </span>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {SECTIONS.map((s) => (
          <Link key={s.href} href={s.href}>
            <Card className="p-4 hover:bg-accent/50 cursor-pointer transition-colors h-full">
              <div className="flex items-start gap-3">
                <s.icon className="w-5 h-5 text-primary mt-0.5" />
                <div className="flex-1">
                  <div className="font-semibold flex items-center">
                    {s.title}
                    <HelpTip text={s.help} />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {s.desc}
                  </div>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="p-4">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            Status W14: backend kompletny (E1-E8), UI Centrum Testów działa na danych backendu
            (domknięcie E9), projekty referencyjne E11, Teatr modeli i agentów przez
            WebSocket + topologia SVG (E12). Zobacz docs/CLAUDE_AEIS_W14_TESTING.md
            dla pełnej specyfikacji.
          </span>
        </div>
      </Card>
    </div>
  );
}
