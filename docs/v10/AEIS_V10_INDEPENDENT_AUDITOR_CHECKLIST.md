
# AEIS V10 — Auditor Checklist for Independent Alternate Corpus

Dla każdego projektu V10 wykonaj poniższą checklistę. Każdy punkt musi mieć screenshot, W18 ref albo audit ref.

## 1. Intake

- [ ] Otwórz Dashboard i utwórz nowy projekt/ideę.
- [ ] Wpisz krótkie streszczenie w pole tekstowe, nie wklejając całego załącznika.
- [ ] Uploaduj szczegółowy załącznik `.md`.
- [ ] Sprawdź, czy AEIS pokazuje source trace: text field vs attachment.
- [ ] Wprowadź jedną literówkę albo brak danych i sprawdź pytania clarification.

## 2. Council i modele

- [ ] Sprawdź skład Council i role.
- [ ] Wymuś co najmniej jedną krytykę między modelami.
- [ ] Sprawdź Model Response Barrier.
- [ ] Spróbuj kliknąć dalej przed odpowiedzią wszystkich blocking modeli.
- [ ] Sprawdź dissent map i critic signature.
- [ ] W18: `report council`, `report model-barriers`, `report dissent`.

## 3. HumanGate

- [ ] Ręcznie wybierz kierunek projektu.
- [ ] Ręcznie zatwierdź/odrzuć co najmniej jeden wybór modeli.
- [ ] Ręcznie zatwierdź/odrzuć co najmniej jedno środowisko.
- [ ] Ręcznie zatwierdź/odrzuć risky action właściwe dla projektu.
- [ ] Sprawdź, czy API/W18 nie omija HumanGate.

## 4. W1-W19

- [ ] Otwórz warstwę w Dashboardzie albo zapisz finding UI gap.
- [ ] W18 report dla warstwy.
- [ ] Test negatywny dla warstwy.
- [ ] Evidence w W14/audit chain.
- [ ] Retest po naprawie.

## 5. Build i produkt

- [ ] AEIS tworzy Masterplan z ownerami, kosztami i testami.
- [ ] Skills/Workers są przypisane i widoczne w W18.
- [ ] Build ma cost cap i guardy.
- [ ] Gotowa aplikacja ma UI.
- [ ] Audytor klika produkt jak człowiek.
- [ ] AEIS generuje product test plan i release evidence.

## 6. Funding

- [ ] Funding uruchomiony przez Dashboard.
- [ ] Query wpisane ręcznie.
- [ ] Wyniki mają URL/source/date albo signal aktualności.
- [ ] Zły wynik odrzucony ręcznie.
- [ ] Candidate wybrany ręcznie.
- [ ] External submit/export blokowany HumanGate.

## 7. Bug loop

- [ ] Każdy błąd ma finding.
- [ ] Root cause opisany.
- [ ] Fix wykonany.
- [ ] Ta sama ścieżka Dashboardowa powtórzona.
- [ ] W18/W14/audit chain pokazują retest.
