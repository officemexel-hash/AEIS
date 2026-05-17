export type FaqCategory =
  | "operator"
  | "governance"
  | "testing"
  | "execution"
  | "security"
  | "troubleshooting";

export type FaqEntry = {
  id: string;
  category: FaqCategory;
  question: string;
  shortAnswer: string;
  fullAnswer: string;
  tags: string[];
  relatedIds: string[];
  contextHints: string[];
};

export const FAQ_CATEGORY_LABELS: Record<FaqCategory, string> = {
  operator: "Operator",
  governance: "Governance",
  testing: "Testy",
  execution: "Wykonanie",
  security: "Bezpieczenstwo",
  troubleshooting: "Diagnostyka",
};

export const FAQ_ENTRIES: FaqEntry[] = [
  {
    id: "human-dashboard-test-command",
    category: "testing",
    question: "Jak testowac dashboard jak operator?",
    shortAnswer: "Klikaj realne akcje, wpisuj dane projektu i uznawaj pass dopiero po efekcie backendu, reloadzie i braku bledow.",
    fullAnswer:
      "Test dashboardu ma traktowac toast jako sygnal pomocniczy, nie dowod. Dla kazdej akcji sprawdz efekt w API, stan po reloadzie oraz logi konsoli. Jesli pojawi sie blad, false success, stale state albo brak persystencji, zatrzymaj flow, napraw przyczyne, wykonaj dwa retesty i dopiero wtedy zamroz wynik.",
    tags: ["dashboard", "2x-pass", "freeze"],
    relatedIds: ["failed-fetch", "freeze-rule"],
    contextHints: ["dashboard", "testing", "operator-flow"],
  },
  {
    id: "freeze-rule",
    category: "testing",
    question: "Co znaczy zamrozenie flow?",
    shortAnswer: "Freeze wymaga identyfikatora projektu, dowodu UI, dowodu API, reload proof i listy zmienionych plikow.",
    fullAnswer:
      "Zamrozenie zapisuje stan jako evidence: projekt, fazy, endpointy, artefakty, reload proof oraz weryfikacje statyczne. Dla bledu wymagane sa dwa powtorzone przejscia PASS po poprawce. Dopiero wtedy mozna przejsc do kolejnej powierzchni.",
    tags: ["freeze", "evidence", "qa"],
    relatedIds: ["human-dashboard-test-command"],
    contextHints: ["freeze", "evidence", "qa"],
  },
  {
    id: "decision-levels",
    category: "governance",
    question: "Do czego sluzy drabina D0-D5?",
    shortAnswer: "Klasyfikuje ryzyko decyzji i okresla, kiedy potrzebna jest Rada, Human Gate lub silniejszy audit.",
    fullAnswer:
      "D0-D2 obejmuje decyzje rutynowe i lokalne. D3 oznacza istotny projekt lub koszt. D4 dotyczy decyzji zewnetrznych, prawnych albo finansowania. D5 obejmuje produkcje, wysokie ryzyko i wiele domen. Dashboard powinien egzekwowac te klasy w backendzie, nie tylko w UI.",
    tags: ["D0-D5", "human-gate", "council"],
    relatedIds: ["human-gate"],
    contextHints: ["governance", "decision-class", "human-gate"],
  },
  {
    id: "human-gate",
    category: "governance",
    question: "Kiedy wymagana jest Human Gate?",
    shortAnswer: "Przed akcjami D3+ zaleznymi od operatora, a szczegolnie przed submit, deploy, kosztem i skutkiem zewnetrznym.",
    fullAnswer:
      "Human Gate musi blokowac wykonanie na backendzie. Sam disabled button albo komunikat w UI nie wystarcza. Ticket powinien miec scope, klase decyzji, wlasciciela, status i audit_event_id. Dla external submit decyzja jest finalna, wiec preview i payload hash sa czescia dowodu.",
    tags: ["approval", "audit", "external-action"],
    relatedIds: ["decision-levels", "funding-submit"],
    contextHints: ["human-gate", "approval", "funding"],
  },
  {
    id: "funding-submit",
    category: "governance",
    question: "Jak bezpiecznie testowac funding submit?",
    shortAnswer: "W testach wykonuj tylko rehearsal lub dummy receipt; prawdziwy submit musi miec D4 Human Gate.",
    fullAnswer:
      "Flow funding powinien przejsc profil, nabor, matching, aplikacje, preview, gate, submit rehearsal, receipt i CRM tracking. Bez approval nie wolno wyslac realnego wniosku. Preview ma pokazac dokladnie payload/PDF, ktory zostalby wyslany.",
    tags: ["funding", "submit", "D4"],
    relatedIds: ["human-gate"],
    contextHints: ["funding", "submit", "crm"],
  },
  {
    id: "local-release-rehearsal",
    category: "execution",
    question: "Czym jest lokalny release rehearsal?",
    shortAnswer: "To zamiennik produkcyjnego deployu w testach: artefakty, canary i rollback sa symulowane bez zewnetrznych wywolan.",
    fullAnswer:
      "Dla local-first testow faza deploy powinna zapisac evidence, raport, canary stages, obserwacje 24h i rollback triggers, ale external calls, platny VPS, domena i prawdziwy ruch produkcyjny musza pozostac zablokowane do osobnej zgody.",
    tags: ["deploy", "local-first", "rollback"],
    relatedIds: ["human-gate", "quality-gates"],
    contextHints: ["deploy", "execution", "local-first"],
  },
  {
    id: "quality-gates",
    category: "testing",
    question: "Co powinny pokrywac bramki jakosci?",
    shortAnswer: "L1-L5, security, cost, coherence, performance i human-like UI, z automatyczna naprawa oraz rerunem.",
    fullAnswer:
      "Bramki jakosci lacza testy jednostkowe, integracyjne, E2E, performance i scenariusze operatora. Kazdy blad powinien przejsc fix -> rerun -> drugi pass. Wynik powinien zawierac pass rate, critical findings, waived cases i koszt rerunow.",
    tags: ["L1-L5", "quality", "rerun"],
    relatedIds: ["human-dashboard-test-command", "freeze-rule"],
    contextHints: ["quality", "testing", "phase37"],
  },
  {
    id: "failed-fetch",
    category: "troubleshooting",
    question: "Co oznacza `Failed to fetch` po preflight?",
    shortAnswer: "Najpierw sprawdz, czy backend dostal tylko OPTIONS bez GET; wtedy to zwykle anulowany GET po stronie przegladarki.",
    fullAnswer:
      "Jesli backend health dziala, a log pokazuje OPTIONS bez nastepnego GET, UI nie powinien kasowac stanu projektu. Krytyczne dane laduj najpierw, dane pomocnicze izoluj, a idempotentne GET mozna powtorzyc raz. Mutujacych POST nie powtarzaj automatycznie.",
    tags: ["cors", "preflight", "retry"],
    relatedIds: ["human-dashboard-test-command"],
    contextHints: ["failed-fetch", "api-client", "troubleshooting"],
  },
];
