# Sidebar overview - SYLION v2 console pages (PL)

> Krótki opis (4 zdania PL) dla sześciu głównych stron sidebara konsoli operatora.
> Curated from `docs/v2/_drafts/ollama_batch/batch_G/g8_sidebar_descriptions.md`.

> Uwaga: **Policy Plane (W19) jest tymczasowo zaparkowany** zgodnie z ADR-001 -
> opis pozostaje dla referencji, ale strona nie jest aktywna w bieżącym wydaniu v2.

## Ontologia (W15)

Strona prezentuje model ontologiczny używany w platformie, definiując klasy, atrybuty oraz relacje między zasobami.
Umożliwia wizualne tworzenie i modyfikowanie struktury danych bez konieczności pisania kodu.
Zaktualizowane definicje są automatycznie propagowane do wszystkich komponentów systemu, zapewniając spójność.
Dzięki temu użytkownicy mogą szybko dopasować ontologię do specyficznych potrzeb biznesowych.

## Apps Builder (W16)

Apps Builder to narzędzie do tworzenia aplikacji przy pomocy interfejsu typu drag-and-drop.
Pozwala na definiowanie przepływów pracy, logiki biznesowej oraz interfejsu użytkownika w kilku kliknięciach.
Wbudowane szablony i gotowe komponenty skracają czas wdrożenia nowych rozwiązań.
Zintegrowane środowisko umożliwia natychmiastowe podglądanie i testowanie aplikacji na platformie.

## Terminal (W18)

Strona Terminal udostępnia interfejs wiersza poleceń do bezpośredniego zarządzania zasobami platformy.
Zawiera zestaw komend pozwalających na monitorowanie stanu systemu, wykonywanie skryptów oraz debugowanie.
Użytkownicy mogą podłączać się przez SSH lub korzystać z wbudowanej konsoli w przeglądarce.
Dodatkowo terminal oferuje automatyczne podpowiedzi i historię poleceń, co zwiększa efektywność pracy.

## Katalog ról (W7)

Katalog ról umożliwia zarządzanie rolami i uprawnieniami użytkowników w systemie.
Dzięki intuicyjnemu interfejsowi można tworzyć, modyfikować i przypisywać role do grup lub pojedynczych osób.
Strona wyświetla hierarchię ról oraz związane z nimi zasady dostępności, ułatwiając audyt bezpieczeństwa.
Automatyczne powiadomienia informują administratorów o zmianach w przydziałach ról.

## Federacja (W17)

Federacja integruje usługi uwierzytelniania zewnętrznych dostawców, takich jak SAML czy OAuth.
Pozwala na skonfigurowanie jednolitego logowania (SSO) dla wielu aplikacji w ekosystemie.
Strona umożliwia zarządzanie konfiguracją trust-anchorów oraz mapowaniem atrybutów użytkowników.
Dzięki temu organizacja może łatwo rozszerzać dostępność usług, zachowując przy tym wysokie standardy bezpieczeństwa.

## Policy Plane (W19) - PARKED (ADR-001)

Policy Plane to centralny punkt zarządzania regułami polityki dostępu w całej infrastrukturze.
Użytkownicy mogą definiować warunki, które muszą być spełnione, aby przyznać lub odrzucić dostęp.
Interfejs wizualny pozwala na tworzenie złożonych warunków przy użyciu logiki boolean i wyrażeń regulacyjnych.
Zaktualizowane polityki są natychmiast propagowane do wszystkich komponentów, zapewniając spójność i zgodność z regulacjami.

> **Uwaga ADR-001:** W19 jest zaparkowany w bieżącym cyklu v2. Strona pojawi się ponownie po decyzji o uwolnieniu.

## Powiązane

- **FAQ** - `FAQ.md`
- **Glossary** - `glossary.md`
- **Tooltips** - `tooltips.md`
- **ADR-001** - decyzje architektoniczne (parking W19, format manifestu)
- **ADR-002** - macierz multi-model routingu
