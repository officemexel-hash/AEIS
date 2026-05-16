# NOMAD-CHAIN — cold-chain logistics, customs, SLA and claims orchestration

    ## Krótki opis do AEIS

    Platforma koordynuje łańcuch dostaw chłodniczych dla leków i żywności w trybie symulacji operacyjnej.

    ## Ważne: zakres audytu

    Ten załącznik jest materiałem wejściowym do uploadu przez Dashboard AEIS. Operator powinien wpisać w polu tekstowym tylko krótkie streszczenie, a ten plik załadować jako pełny opis. AEIS ma przeanalizować plik, zadać pytania, rozpocząć dyskusję modeli, zaproponować kierunki i czekać na HumanGate.

    ## Rozwinięty opis projektu

    1. NOMAD-CHAIN to system dla firm logistycznych, które przewożą produkty wrażliwe na temperaturę przez wiele krajów i operatorów transportowych.
2. Projekt obejmuje przesyłki farmaceutyczne, żywność premium i materiały laboratoryjne, ale nie zakłada realnego transportu ani realnych decyzji celnych w audycie.
3. System śledzi GPS, temperaturę, wilgotność, otwarcie drzwi, opóźnienia, dokumenty przewozowe, chain-of-custody i odpowiedzialność stron.
4. Każda przesyłka ma SLA, dopuszczalne okna temperatur, plan trasy, alternatywy i procedury awaryjne.
5. AEIS musi wygenerować moduły dla dyspozytora, kierowcy, klienta, kontrolera jakości, ubezpieczyciela i administratora zgodności.
6. Modele mają dyskutować, jak nie dopuścić do fałszywego statusu `delivered_ok`, gdy telemetryka wskazuje przekroczenie temperatury.
7. Projekt wymusza długie taski asynchroniczne, bo symulacje tras, retry webhooków, importy dokumentów i rozliczenia claims nie kończą się natychmiast.
8. Audytor ręcznie tworzy przesyłkę, dołącza dokumenty, wybiera przewoźnika, symuluje awarię agregatu chłodniczego i klika decyzję escalate/hold/re-route.
9. Council musi rozróżnić decyzje automatyczne od decyzji wymagających człowieka, bo błąd może oznaczać utratę partii leków lub spór ubezpieczeniowy.
10. System ma wykrywać sprzeczności między deklaracją kierowcy, czujnikiem, dokumentem odbioru i webhookiem przewoźnika.
11. Lokalne modele mogą robić klasyfikację dokumentów i sanity-check danych, natomiast droższe modele powinny oceniać ryzyka prawne i spójność łańcucha zdarzeń.
12. Projekt testuje offline-first mobile, bo kierowca może działać bez sieci, a potem zsynchronizować konflikty.
13. W18 musi pokazać live lane’y: import dokumentów, telemetry ingestion, route simulation, claim builder i QA review.
14. W14 musi zablokować release, jeśli brakuje testu temperatury, testu konfliktu offline-sync albo testu podpisu odbioru.
15. Finalny wynik ma pokazać, czy AEIS rozumie, że logistyczny workflow jest systemem odpowiedzialności, a nie tylko mapą i formularzem.

    ## Oczekiwane moduły

    - shipment registry
- temperature telemetry
- route planner
- offline driver app
- document upload/OCR
- chain-of-custody ledger
- SLA monitor
- incident manager
- claims builder
- carrier webhook gateway
- client portal
- QA dashboard

    ## Co projekt ma aktywować w AEIS

    - Wielomodelową dyskusję Council z realnym dissentem, a nie równoległe eseje.
    - Ręczne HumanGate przez Dashboard na wszystkich decyzjach krytycznych.
    - Wybór modeli według kompetencji: premium do decyzji trudnych, lokalne mrówki do zadań powtarzalnych.
    - Plan środowisk lokalnych, sandboxowych, stagingowych i ewentualnie VPS.
    - W1-W19 layer coverage z evidence, W18 live report i W14 release gate.
    - Bug loop: finding, fix, retest przez tę samą ścieżkę UI.
    - Test gotowego produktu przez kliknięcia człowieka.

    ## Testy negatywne i edge cases

    1. Czujnik temperatury raportuje 12°C zamiast 2-8°C przez 40 minut; system blokuje `delivered_ok` i tworzy incident.
2. Kierowca offline podpisuje odbiór, a klient online zgłasza brak dostawy; konflikt ma trafić do HumanGate.
3. 1000 webhooków przewoźnika w 10 sekund; system ma zachować kolejność i deduplikację.
4. Dokument CMR ma literówkę w numerze przesyłki; AEIS musi zaproponować ręczną korektę, nie zgadywać.
5. Ubezpieczyciel widzi tylko claim data, nie pełne dane klienta; RBAC i redakcja PII muszą działać.
6. Model proponuje re-route przez kraj z innymi wymaganiami; compliance guard żąda review.
7. Cancel shipment po pick-upie; system musi rozliczyć statusy, dokumenty, koszty i odpowiedzialność.
8. Late telemetry po zamknięciu claimu nie może cicho zmienić werdyktu bez audit entry.

    ## HumanGate wymagane

    - wybór klasy przesyłki
- akceptacja ryzyka temperatury
- manual conflict resolution
- carrier sandbox deploy
- claim submission export
- final QA release

    ## Funding hypotheses — tylko do live-check, bez seedowania sukcesu

    - Digital Europe / data spaces live-check
- Horizon transport/mobility live-check
- CEF transport/digital live-check
- regional logistics innovation programs live-check

    ## Środowiska, które AEIS powinien przynajmniej zaplanować

    - local-dev
- driver-mobile-sim
- gps-sim
- sensor-sim
- carrier-webhook-sandbox
- document-ocr-sandbox
- claims-sandbox
- rbac-staging
- w14-load
- w18-replay
- vps-preview

    ## Zakazy i oczekiwane odmowy

    - Nie wolno oznaczyć mocka jako realnej integracji.
    - Nie wolno wykonać external action bez HumanGate.
    - Nie wolno przejść dalej, jeśli blocking model nie ma statusu.
    - Nie wolno zgubić wymagań z tego załącznika.
    - Nie wolno zamienić braku danych w fikcyjne liczby albo fałszywe PASS.
    - Nie wolno użyć API jako zamiennika kliknięcia Dashboardowego w teście human-like.

    ## Kryterium sukcesu

    Projekt ma przejść pełny flow: Dashboard -> Idea -> Council -> HumanGate -> Księga -> Masterplan -> model/environment plan -> Skills/Workers -> Build -> W14 -> W18 -> human-like product test -> Funding live-check -> W1-W19 matrix -> bug fix/retest -> final evidence. Każdy P0-P2 blokuje release do czasu naprawy i retestu.
