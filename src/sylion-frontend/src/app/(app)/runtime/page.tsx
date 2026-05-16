import { CanonicalSurface } from "../_canonical-surface";

export default function RuntimePage() {
  return (
    <CanonicalSurface
      title="Topologia runtime"
      subtitle="Kanoniczna warstwa wykonania: lokalnie, VPS, kontenery jako rejestr metadanych, workery, urządzenia, automatyzacja przeglądarki i obserwowalność."
      canonicalStatus="Ta trasa łączy zdrowie systemu, workery, środowiska, wdrożenia, kontenery i obserwowalność. Kontenery są tu zawężone do rejestru metadanych i księgowania, bez realnej orkiestracji Docker/Kubernetes. Pełny runtime wymaga dowodu wyboru topologii, akceptacji kosztu/ryzyka oraz kontynuacji workerów pod zablokowanymi bramkami."
      aeisImpact="Audyt musi potwierdzić, że topologią runtime rządzi Human Gate i Rada Modeli, a nie pasywny dashboard."
      links={[
        { href: "/health", label: "Zdrowie", description: "Zdrowie backendu i modułów runtime." },
        { href: "/workers", label: "Workery", description: "Flota workerów, przypisania i topologia." },
        { href: "/environments", label: "Środowiska", description: "Wdrożenia i stan środowisk." },
        { href: "/api/v1/container/*", label: "Rejestr kontenerów", description: "Rejestr metadanych kontenerów, tylko planowanie i księgowanie - bez kontroli Docker/K8s." },
        { href: "/observability", label: "Obserwowalność", description: "Logi, metryki, ślady i snapshot runtime." },
      ]}
    />
  );
}
