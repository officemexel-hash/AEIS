import { CanonicalSurface } from "../_canonical-surface";

export default function MasterplanPage() {
  return (
    <CanonicalSurface
      title="Masterplan"
      titleHelpTip="Kanoniczny plan wykonania projektu: moduły, zależności, przypisanie modeli/zespołów, umiejętności, topologia runtime, testy i punkty kontrolne Bramki człowieka. Steruje kolejkami wykonania, własnością wykonawców i akceptacjami."
      subtitle="Kanoniczna warstwa planu wykonania: moduły, zależności, przypisanie modeli/zespołów, umiejętności, topologia runtime, testy i punkty kontrolne Bramki człowieka."
      canonicalStatus="Ta trasa jest mostkiem do paneli projektów, pipeline'u, wykonawców i buildów. Pełna funkcjonalność Masterplanu wymaga wykazania, że AEIS tworzy plan ze Źródła Prawdy i skaluje zespoły zależnie od złożoności projektu."
      aeisImpact="Audyt musi sprawdźić, czy masterplany są obiektami operacyjnymi, czy tylko dokumentacją. Prawdziwy masterplan musi sterować kolejkami wykonania, własnością wykonawców, umiejętnościami, testami i akceptacjami."
      links={[
        { href: "/projects", label: "Projekty", description: "Masterplany projektów i kanoniczny stan projektów." },
        { href: "/pipeline", label: "Pipeline", description: "Uruchomienia pipeline'u i kroki wykonania." },
        { href: "/workers", label: "Flota wykonawców", description: "Przydziały wykonawców i topologia runtime." },
        { href: "/builds", label: "Buildy", description: "Buildy kandydujące, drift, walidacja i promocja." },
      ]}
    />
  );
}
