import { CanonicalSurface } from "../_canonical-surface";

export default function SourceOfTruthPage() {
  return (
    <CanonicalSurface
      title="Źródło Prawdy"
      subtitle="Kanoniczna warstwa prawdy projektu: cel, zakres, poza zakresem, ryzyka, ograniczenia, kryteria sukcesu i zatwierdzone założenia."
      canonicalStatus="Ten ekran jest mostem do Księgi projektu, obszaru pracy i powierzchni wiedzy. Pełne zachowanie Źródła Prawdy wymaga szkicu, zgody operatora, propozycji zmiany, zamrożenia i testów ścieżki audytu."
      aeisImpact="Jeśli Źródła Prawdy nie da się tworzyć i zmieniać przez bramkę człowieka, system nie jest jeszcze pełnym przepływem kontrolowanej autonomii AEIS."
      links={[
        { href: "/projects", label: "Projekty", description: "Lista projektów i kanoniczny stan każdego projektu." },
        { href: "/workspace", label: "Obszar pracy", description: "Obszar operatora dla przyjęcia, planowania i wykonania." },
        { href: "/book", label: "Księga / Kanon", description: "Wiedza, sekcje kanonu, złote zestawy i wpisy modelu systemu." },
        { href: "/audit", label: "Ścieżka audytu", description: "Ślad dowodowy decyzji kanonicznych i zmian." },
      ]}
    />
  );
}
