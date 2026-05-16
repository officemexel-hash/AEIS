# AEIS API/UI Coverage Map

- Frontend routes: 129
- Client API refs: 570
- Runtime OpenAPI paths: 1642

## Routes

| Route | Classification | Risk Markers | API refs | Runtime refs | Sources | File |
|---|---|---|---:|---:|---|---|
| `/advisor/[cardId]` | `STATIC_API_LINKED` | - | 1 | 1 | local_imports:1 | `src\sylion-frontend\src\app\(app)\advisor\[cardId]\page.tsx` |
| `/advisor/cockpit` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2 | `src\sylion-frontend\src\app\(app)\advisor\cockpit\page.tsx` |
| `/advisor` | `STATIC_API_LINKED` | - | 1 | 1 | local_imports:1 | `src\sylion-frontend\src\app\(app)\advisor\page.tsx` |
| `/agents` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:4, local_imports:547, imported_hooks:8 | `src\sylion-frontend\src\app\(app)\agents\page.tsx` |
| `/ai-models` | `STATIC_API_LINKED` | - | 549 | 549 | direct_literals:1, client_methods:20, local_imports:545 | `src\sylion-frontend\src\app\(app)\ai-models\page.tsx` |
| `/anomalies` | `STATIC_API_LINKED` | - | 3 | 3 | local_imports:3, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\anomalies\page.tsx` |
| `/apps-builder/[appId]` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:2 | `src\sylion-frontend\src\app\(app)\apps-builder\[appId]\page.tsx` |
| `/apps-builder` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:2 | `src\sylion-frontend\src\app\(app)\apps-builder\page.tsx` |
| `/apps-builder/wizard` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:2 | `src\sylion-frontend\src\app\(app)\apps-builder\wizard\page.tsx` |
| `/architecture-layers` | `STATIC_API_LINKED` | - | 1 | 1 | local_imports:1 | `src\sylion-frontend\src\app\(app)\architecture-layers\page.tsx` |
| `/audit` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:1, local_imports:547, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\audit\page.tsx` |
| `/audit-trail` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:1, local_imports:547, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\audit-trail\page.tsx` |
| `/auth` | `STATIC_API_LINKED` | - | 548 | 548 | direct_literals:3, client_methods:2, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\auth\page.tsx` |
| `/autonomy` | `STATIC_API_LINKED` | demo | 546 | 546 | client_methods:12, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\autonomy\page.tsx` |
| `/autoscaler` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:3, local_imports:546, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\autoscaler\page.tsx` |
| `/book` | `STATIC_API_LINKED` | - | 5 | 5 | local_imports:5, imported_hooks:5 | `src\sylion-frontend\src\app\(app)\book\page.tsx` |
| `/budget` | `STATIC_API_LINKED` | - | 546 | 546 | direct_literals:1, client_methods:1, local_imports:546, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\budget\page.tsx` |
| `/build-state` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\build-state\page.tsx` |
| `/builds` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:5, local_imports:546, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\builds\page.tsx` |
| `/bundles` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\bundles\page.tsx` |
| `/capacity` | `STATIC_API_LINKED` | - | 3 | 3 | local_imports:3, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\capacity\page.tsx` |
| `/cellular` | `STATIC_API_LINKED` | - | 8 | 8 | local_imports:8, imported_hooks:8 | `src\sylion-frontend\src\app\(app)\cellular\page.tsx` |
| `/circuits` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\circuits\page.tsx` |
| `/coherence-guard` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:12, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\coherence-guard\page.tsx` |
| `/connectors` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:3, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\connectors\page.tsx` |
| `/contracts` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\contracts\page.tsx` |
| `/cost-guard` | `STATIC_API_LINKED` | - | 9 | 9 | local_imports:9 | `src\sylion-frontend\src\app\(app)\cost-guard\page.tsx` |
| `/costs` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:2, local_imports:546, imported_hooks:5 | `src\sylion-frontend\src\app\(app)\costs\page.tsx` |
| `/council-to-ksiega` | `STATIC_API_LINKED` | - | 11 | 11 | local_imports:11 | `src\sylion-frontend\src\app\(app)\council-to-ksiega\page.tsx` |
| `/dashboard/operator-monitor` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:5, local_imports:546 | `src\sylion-frontend\src\app\(app)\dashboard\operator-monitor\page.tsx` |
| `/decisions` | `STATIC_API_LINKED` | - | 548 | 548 | client_methods:5, local_imports:546, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\decisions\page.tsx` |
| `/demo/crm` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\demo\crm\page.tsx` |
| `/demo/factory` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\demo\factory\page.tsx` |
| `/demo/funding` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\demo\funding\page.tsx` |
| `/demo/marketplace` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\demo\marketplace\page.tsx` |
| `/demo/mobile-inspector` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\demo\mobile-inspector\page.tsx` |
| `/demo/portal` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\demo\portal\page.tsx` |
| `/deploy` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:6, local_imports:546, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\deploy\page.tsx` |
| `/devices` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:1, local_imports:546, imported_hooks:5 | `src\sylion-frontend\src\app\(app)\devices\page.tsx` |
| `/drift` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:1, local_imports:546, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\drift\page.tsx` |
| `/environments` | `STATIC_API_LINKED` | demo | 546 | 546 | client_methods:6, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\environments\page.tsx` |
| `/environments/theater` | `STATIC_API_LINKED` | - | 545 | 545 | client_methods:12, local_imports:545 | `src\sylion-frontend\src\app\(app)\environments\theater\page.tsx` |
| `/evaluator` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:1, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\evaluator\page.tsx` |
| `/events` | `STATIC_API_LINKED` | - | 4 | 4 | local_imports:4, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\events\page.tsx` |
| `/evidence` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\evidence\page.tsx` |
| `/evidence-spine` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:3, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\evidence-spine\page.tsx` |
| `/execution-start` | `STATIC_API_LINKED` | - | 16 | 16 | local_imports:16 | `src\sylion-frontend\src\app\(app)\execution-start\page.tsx` |
| `/faq` | `STATIC_CONTENT` | - | 0 | 0 | - | `src\sylion-frontend\src\app\(app)\faq\page.tsx` |
| `/federation` | `STATIC_API_LINKED` | - | 545 | 545 | client_methods:3, local_imports:545 | `src\sylion-frontend\src\app\(app)\federation\page.tsx` |
| `/funding` | `STATIC_API_LINKED` | - | 550 | 550 | client_methods:38, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\funding\page.tsx` |
| `/gates` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:1, local_imports:546, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\gates\page.tsx` |
| `/golden-tests` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\golden-tests\page.tsx` |
| `/governance` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:3, local_imports:546, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\governance\page.tsx` |
| `/guards` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:2, local_imports:545 | `src\sylion-frontend\src\app\(app)\guards\page.tsx` |
| `/healing` | `STATIC_API_LINKED` | - | 3 | 3 | local_imports:3, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\healing\page.tsx` |
| `/health` | `STATIC_API_LINKED` | - | 1 | 1 | local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\health\page.tsx` |
| `/human-gate` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:6, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\human-gate\page.tsx` |
| `/idea-vault/[id]` | `STATIC_API_LINKED` | - | 10 | 10 | local_imports:10 | `src\sylion-frontend\src\app\(app)\idea-vault\[id]\page.tsx` |
| `/idea-vault` | `STATIC_API_LINKED` | - | 5 | 5 | local_imports:5 | `src\sylion-frontend\src\app\(app)\idea-vault\page.tsx` |
| `/integrations` | `STATIC_API_LINKED` | - | 548 | 548 | direct_literals:1, client_methods:4, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\integrations\page.tsx` |
| `/lifecycle` | `STATIC_API_LINKED` | - | 6 | 6 | local_imports:6, imported_hooks:6 | `src\sylion-frontend\src\app\(app)\lifecycle\page.tsx` |
| `/masterplan` | `STATIC_CONTENT` | - | 0 | 0 | - | `src\sylion-frontend\src\app\(app)\masterplan\page.tsx` |
| `/memory` | `STATIC_API_LINKED` | - | 545 | 545 | client_methods:9, local_imports:545 | `src\sylion-frontend\src\app\(app)\memory\page.tsx` |
| `/mobile` | `STATIC_API_LINKED` | - | 3 | 3 | direct_literals:1, local_imports:2 | `src\sylion-frontend\src\app\(app)\mobile\page.tsx` |
| `/model-council` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:12, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\model-council\page.tsx` |
| `/modules` | `STATIC_API_LINKED` | - | 5 | 5 | local_imports:5, imported_hooks:5 | `src\sylion-frontend\src\app\(app)\modules\page.tsx` |
| `/notifications` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:2, local_imports:546, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\notifications\page.tsx` |
| `/observability` | `STATIC_API_LINKED` | - | 4 | 4 | local_imports:4, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\observability\page.tsx` |
| `/onboarding` | `STATIC_API_LINKED` | demo | 1 | 1 | client_methods:1, local_imports:1 | `src\sylion-frontend\src\app\(app)\onboarding\page.tsx` |
| `/ontology` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:5, local_imports:545 | `src\sylion-frontend\src\app\(app)\ontology\page.tsx` |
| `/operator-mobile/devices` | `STATIC_API_LINKED` | - | 3 | 3 | local_imports:3 | `src\sylion-frontend\src\app\(app)\operator-mobile\devices\page.tsx` |
| `/operator-mobile` | `STATIC_API_LINKED` | - | 3 | 3 | direct_literals:1, local_imports:2 | `src\sylion-frontend\src\app\(app)\operator-mobile\page.tsx` |
| `/operator-mobile/queue/[ticketId]` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2 | `src\sylion-frontend\src\app\(app)\operator-mobile\queue\[ticketId]\page.tsx` |
| `/operator-mobile/queue` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2 | `src\sylion-frontend\src\app\(app)\operator-mobile\queue\page.tsx` |
| `/orchestration/auditor` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\auditor\page.tsx` |
| `/orchestration/conversations` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\conversations\page.tsx` |
| `/orchestration/council-rules` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\council-rules\page.tsx` |
| `/orchestration/dispatch` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\dispatch\page.tsx` |
| `/orchestration/event-map` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\event-map\page.tsx` |
| `/orchestration/fixer` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\fixer\page.tsx` |
| `/orchestration/llm-routing` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:2, local_imports:545 | `src\sylion-frontend\src\app\(app)\orchestration\llm-routing\page.tsx` |
| `/orchestration` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\page.tsx` |
| `/orchestration/teams` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\teams\page.tsx` |
| `/orchestration/tests` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1 | `src\sylion-frontend\src\app\(app)\orchestration\tests\page.tsx` |
| `/overview` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:5, local_imports:547, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\overview\page.tsx` |
| `/performance` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:2, local_imports:547, imported_hooks:8 | `src\sylion-frontend\src\app\(app)\performance\page.tsx` |
| `/pipeline` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:4, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\pipeline\page.tsx` |
| `/planning` | `STATIC_API_LINKED` | - | 11 | 11 | local_imports:11 | `src\sylion-frontend\src\app\(app)\planning\page.tsx` |
| `/policy` | `STATIC_API_LINKED` | - | 1 | 1 | direct_literals:1 | `src\sylion-frontend\src\app\(app)\policy\page.tsx` |
| `/project-start` | `STATIC_API_LINKED` | - | 11 | 11 | local_imports:11 | `src\sylion-frontend\src\app\(app)\project-start\page.tsx` |
| `/projects/[projectId]/lifecycle` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1 | `src\sylion-frontend\src\app\(app)\projects\[projectId]\lifecycle\page.tsx` |
| `/projects/[projectId]/orchestration` | `STATIC_API_LINKED` | - | 545 | 545 | direct_literals:1, client_methods:14, local_imports:545 | `src\sylion-frontend\src\app\(app)\projects\[projectId]\orchestration\page.tsx` |
| `/projects/[projectId]` | `STATIC_API_LINKED` | demo | 546 | 546 | client_methods:23, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\projects\[projectId]\page.tsx` |
| `/projects` | `STATIC_API_LINKED` | - | 4 | 4 | direct_literals:1, local_imports:4, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\projects\page.tsx` |
| `/provenance-guard` | `STATIC_API_LINKED` | - | 9 | 9 | local_imports:9 | `src\sylion-frontend\src\app\(app)\provenance-guard\page.tsx` |
| `/quality` | `REDIRECT` | - | 0 | 0 | - | `src\sylion-frontend\src\app\(app)\quality\page.tsx` |
| `/quality-guard` | `STATIC_API_LINKED` | - | 9 | 9 | local_imports:9 | `src\sylion-frontend\src\app\(app)\quality-guard\page.tsx` |
| `/rebuild` | `STATIC_API_LINKED` | - | 5 | 5 | local_imports:5, imported_hooks:5 | `src\sylion-frontend\src\app\(app)\rebuild\page.tsx` |
| `/risk` | `STATIC_API_LINKED` | - | 3 | 3 | local_imports:3, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\risk\page.tsx` |
| `/role-catalog` | `STATIC_API_LINKED` | - | 548 | 548 | direct_literals:3, client_methods:3, local_imports:545 | `src\sylion-frontend\src\app\(app)\role-catalog\page.tsx` |
| `/roles` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\roles\page.tsx` |
| `/runtime` | `STATIC_API_LINKED` | - | 1 | 1 | direct_literals:1 | `src\sylion-frontend\src\app\(app)\runtime\page.tsx` |
| `/sdr` | `STATIC_API_LINKED` | - | 5 | 5 | local_imports:5, imported_hooks:5 | `src\sylion-frontend\src\app\(app)\sdr\page.tsx` |
| `/secrets` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:7, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\secrets\page.tsx` |
| `/security-guard` | `STATIC_API_LINKED` | - | 9 | 9 | local_imports:9 | `src\sylion-frontend\src\app\(app)\security-guard\page.tsx` |
| `/security-scan` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:2, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\security-scan\page.tsx` |
| `/settings/advisor` | `STATIC_API_LINKED` | - | 7 | 7 | client_methods:1, local_imports:7 | `src\sylion-frontend\src\app\(app)\settings\advisor\page.tsx` |
| `/settings` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:5, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\settings\page.tsx` |
| `/settings/profile` | `STATIC_API_LINKED` | - | 1 | 1 | client_methods:1, local_imports:1 | `src\sylion-frontend\src\app\(app)\settings\profile\page.tsx` |
| `/skills` | `STATIC_API_LINKED` | - | 546 | 546 | client_methods:5, local_imports:546, imported_hooks:4 | `src\sylion-frontend\src\app\(app)\skills\page.tsx` |
| `/sla` | `STATIC_API_LINKED` | - | 2 | 2 | local_imports:2, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\sla\page.tsx` |
| `/source-of-truth` | `STATIC_CONTENT` | - | 0 | 0 | - | `src\sylion-frontend\src\app\(app)\source-of-truth\page.tsx` |
| `/templates-setup` | `STATIC_API_LINKED` | - | 8 | 8 | local_imports:8 | `src\sylion-frontend\src\app\(app)\templates-setup\page.tsx` |
| `/terminal` | `STATIC_API_LINKED` | - | 547 | 547 | direct_literals:3, client_methods:2, local_imports:545 | `src\sylion-frontend\src\app\(app)\terminal\page.tsx` |
| `/terminal/replay` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:2 | `src\sylion-frontend\src\app\(app)\terminal\replay\page.tsx` |
| `/test-center/auto-repair` | `STATIC_API_LINKED` | - | 4 | 4 | direct_literals:3, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\auto-repair\page.tsx` |
| `/test-center/catalog` | `STATIC_API_LINKED` | - | 3 | 3 | direct_literals:2, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\catalog\page.tsx` |
| `/test-center/dashboard` | `STATIC_API_LINKED` | - | 3 | 3 | direct_literals:2, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\dashboard\page.tsx` |
| `/test-center/human-lab` | `STATIC_API_LINKED` | - | 3 | 3 | direct_literals:2, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\human-lab\page.tsx` |
| `/test-center/no-mock-scan` | `STATIC_API_LINKED` | demo | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\no-mock-scan\page.tsx` |
| `/test-center` | `STATIC_API_LINKED` | demo | 1 | 1 | local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\page.tsx` |
| `/test-center/release-gate` | `STATIC_API_LINKED` | demo | 4 | 4 | direct_literals:3, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\release-gate\page.tsx` |
| `/test-center/simulation` | `STATIC_API_LINKED` | - | 3 | 3 | direct_literals:2, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\simulation\page.tsx` |
| `/test-center/theater` | `STATIC_API_LINKED` | - | 4 | 4 | direct_literals:3, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\theater\page.tsx` |
| `/test-center/truth-alignment` | `STATIC_API_LINKED` | - | 2 | 2 | direct_literals:1, local_imports:1, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\test-center\truth-alignment\page.tsx` |
| `/v2/admin` | `STATIC_API_LINKED` | - | 4 | 4 | local_imports:4 | `src\sylion-frontend\src\app\(app)\v2\admin\page.tsx` |
| `/workers` | `STATIC_API_LINKED` | - | 546 | 546 | direct_literals:1, client_methods:5, local_imports:546, imported_hooks:3 | `src\sylion-frontend\src\app\(app)\workers\page.tsx` |
| `/workspace` | `STATIC_API_LINKED` | - | 547 | 547 | client_methods:6, local_imports:547, imported_hooks:2 | `src\sylion-frontend\src\app\(app)\workspace\page.tsx` |
| `/workspace-defaults` | `STATIC_API_LINKED` | demo | 546 | 546 | client_methods:13, local_imports:546, imported_hooks:1 | `src\sylion-frontend\src\app\(app)\workspace-defaults\page.tsx` |

## Client API Refs

| Runtime | Methods | Path | Source |
|---|---|---|---|
| yes | GET | `/api/v1/advisor` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| yes | POST | `/api/v1/advisor/suggest-pipeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/autonomy/stages` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/autonomy/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/explanations` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/improvements` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/limitation/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/agents/executions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/agents/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/agents/register` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/agents/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/agents/{var}/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/key-info/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/local-models/installed` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/ollama/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/openrouter/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/test/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/architecture-layers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/audit/events` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/audit/export` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/audit/integrity` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/auth/providers/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/auth/sessions/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/apply-preset` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/d-level-overrides` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/dimensions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/hard-gates/custom` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/hard-gates/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/configuration/hard-gates/{var}/toggle` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/inheritance/trace` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/overrides` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/wizard/mode` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/wizard/step` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/advance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/event` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/state` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/steer` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/transitions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/brain/models/pull` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/build-state` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/bundles/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/capacity/bottlenecks` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/capacity/resources` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/capacity/resources/{var}/forecast` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/capacity/usage` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/attack-vectors` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/control-plane` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/cores` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/evidence` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/isolation` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/ran` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/ue` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/circuit-breakers/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cloud-connectors` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cloud-connectors/providers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cloud-connectors/{var}/test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/evaluations` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/cognitive/hallucinations` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/cognitive/hallucinations/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/cognitive/hallucinations/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/hallucinations/{var}/verify` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/plans` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/coherence-guard/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/aggregated-panel` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/autonomy-override` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/checks/config` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/checks/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/custom-checks` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/findings` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/coherence-guard/findings/{var}/action` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/performance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/run` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/scope` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/severity/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/triggers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/connectors/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/contracts/{var}/versions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/contracts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/events` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/evidence` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/modules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/council-to-ksiega` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/council-to-ksiega/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/council-to-ksiega/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase20/convene` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase21/initial-verdicts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase22/deliberate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase23/consolidate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase24/generate-book` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase25/finalize-ksiega` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/deliberate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/enable` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/reconcile` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/state` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/hetzner/deployments` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/hetzner/provision` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/deploy/hetzner/{var}/delete` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/deploy/hetzner/{var}/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/topologies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/topologies/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/deployments` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/discovery` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/discovery/scan` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/registry` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/tests` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/budgets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/budgets/over` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/circuits` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/efficiency/cost/alerts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/efficiency/cost/daily` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/efficiency/cost/monthly` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/efficiency/cost/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/drift` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/cleanup` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/cleanup/bulk-plan` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/cleanup/policy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/costs` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/costs/alerts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/edge-devices` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/environments` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/inheritance/resolve` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/local-dev/accept` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/network` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/network/diagnostic` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/network/policy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/providers/detected` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/residency` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/residency/audit` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/residency/check` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/residency/rules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/scan-local` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/sovereignty/evaluate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/theater` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/event-backbone/catalog` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/event-backbone/events` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/event-backbone/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/evidence-timeline/timelines` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/evidence-timeline/timelines/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/evidence-timeline/timelines/{var}/verify` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/execution-start` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/execution-start/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/execution-start/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/audit-truth-map` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/audit-truth-map/rebuild` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase32/initialize-build` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase32/live-spawn-workers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase32/stop-live-workers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase33/start-execution` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase34/reconvene-council` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase35/activate-orchestration` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase36/complete-build` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase37/run-quality-gates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase38/complete-acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase39/authorize-predeploy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase40/execute-production-deploy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase41/close-project` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/runtime-configuration` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/w18-commands` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/jobs` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/retry/attempts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/tools` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/workflows` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/nodes` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/nodes/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/route` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/alerts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/application/create` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/application/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/documents` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/export` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/export/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/calls` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/calls/search` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/calls/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/funding/company-profile` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/company-profile/documents` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST,PUT | `/api/v1/funding/company-profile/readiness` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/company-profile/registry-sync` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/company-profile/state-aid` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/consortium/outreach/generate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/consortium/partners/search` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/consortium/partners/shortlist` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/crm/applications` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/deadlines` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/ideas` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/ideas/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/ideas/{var}/convert-to-project` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/matching/results/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/programmes` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/projects` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/reports/executive` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/scan/trigger` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/scoring/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/sources` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/submission/approvals` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/fill` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/submission/receipt` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/request-approval` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/save-draft` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/submit` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/gates/human/requests` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/gates/human/reviews` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/gates/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/golden-sets/sets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/audit/log` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/audit/timeline/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/cascade-events` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade-events/{var}/acknowledge` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade/analyses` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade/analyses/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade/analyses/{var}/paths` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/checker/checks` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/checker/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/compliance/report/latest` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/compliance/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/conflict-detections` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/conflict-detections/rules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/conflict-detections/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/decision-snapshots` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/decision-snapshots/active-chain` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/decision-snapshots/timeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/decision-snapshots/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/decision-snapshots/{var}/cascade-impact` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/decision-snapshots/{var}/diff/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/gates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/lifecycle/entries` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/lifecycle/stages` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/proposals` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/proposals/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/proposals/{var}/vote` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/spine` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/spine/decision/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/spine/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/spine/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/tickets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/tickets/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/tickets/{var}/resolve` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/guards/aggregated-panel` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/guards/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/autonomy-override` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/config` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/findings` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/findings/{var}/action` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/run` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/hardened-audit/chain/tamper-check` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/hardened-audit/chain/verify` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/hardened-audit/events` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/builds` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/integration/builds/{var}/promote` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/integration/builds/{var}/reject` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/integration/builds/{var}/validate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/drift` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/drift/detect` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/drift/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/integrations` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/evidence` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/evidence-store` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/evidence/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/index/search` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/index/sections` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/kanon/sections` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/obsidian/graph` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/obsidian/notes/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/obsidian/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/obsidian/sync` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/recent` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/retrieval/context` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/metrics` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST,PUT | `/api/v1/mobile/devices` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST,PUT | `/api/v1/mobile/devices/bind` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST,PUT | `/api/v1/mobile/devices/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/mobile/queue` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/mobile/queue/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/mobile/queue/{var}/approve` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/mobile/queue/{var}/reject` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/model-budget/budgets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/model-registry/capabilities` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/model-registry/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/model-registry/models/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/anomalies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/anomalies/baselines/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/bloat/modules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/monitoring/budget` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/budget/configure` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/budget/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/budget/transactions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/monitoring/budget/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/budget/{var}/usage` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/cost/records` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/drift/reports` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/drift/snapshots/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/metrics/latest/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/metrics/{var}/buckets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/performance/anomalies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/performance/leaderboard` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/performance/metrics` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/performance/record` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/performance/summary/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/performance/trend/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/preservation/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/sla` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/sla/policies/{var}/compliance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/notifications` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/notifications/channels` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/notifications/{var}/read` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/notifications/{var}/unread` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/observability/logs` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/observability/metrics` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/observability/snapshot` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/observability/traces` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ontology/reload` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ontology/types` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/ontology/types/{var}/actions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/ontology/types/{var}/ddl` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/pipeline/ideas` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/pipeline/runs` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/pipeline/runs/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/pipeline/runs/{var}/cancel` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/pipeline/runs/{var}/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/pipeline/runs/{var}/steps` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase26/assign-models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase27/synthesize-skills` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase28/generate-masterplan` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase29/generate-test-plan` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase30/preflight-cost` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase31/dry-run` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning/resource-profiles` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects/create` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects/preview` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/council/approve-readiness` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/council/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/goals/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/scope/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/projects` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/artifact/raw` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/attachments` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/audit` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/autonomy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/budget` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/build/authorize` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/canon` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/canon/freeze` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/cost` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/council` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/council/suggest` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/execution-models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/launch` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/masterplan` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/masterplan/freeze` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/modules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/questions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/questions/{var}/answer` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/timeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/provider-catalog` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/provider-catalog/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/provider-catalog/council/rebuild-hierarchy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/provider-catalog/refresh-local` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/quality/golden-sets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/quality/regression/alerts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/rebuild/cutover/plans` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/rebuild/lpw` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/rebuild/orchestrator/plans` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/risk/assessment/{var}/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/risk/scores` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/role-catalog` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/role-catalog/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/roles` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/runtime/truth` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/analysis` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/captures` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/devices` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/rf/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/secrets/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/secrets/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security-audit/findings/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security-audit/scans/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/audit` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/auth/users` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/security/hardened-profiles` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/security/hardened-profiles/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/session-manager/audit` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/session-manager/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/session-manager/users` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/self-healing/rules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/self-healing/rules/{var}/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/self-healing/rules/{var}/trigger` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/self-healing/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/skills/demand/analyze` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/skills/demand/signals` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/executions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/skills/lifecycle/long-run-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/skills` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/{var}/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/{var}/state` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/snapshots` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/snapshots/latest/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/snapshots/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/snapshots/{var}/diff/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/surface/console/endpoints` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/surface/ui/components` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/surface/ws/connections` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/templates-setup/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/custom-artifacts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/simulate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/terminal/exec` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/terminal/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/assignments/rebalance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/evaluate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/history` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/policy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/autoscaler/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/topology/all` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workers/{var}/heartbeat` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace-defaults/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/approvals` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/autonomy/mapping` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/budgets/estimate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/budgets/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/cleanup/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/council/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/inheritance/preview` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/mobile/pair` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/navigation` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/notifications/matrix` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/shortcuts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/smart-defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/test-strategy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/ui` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace-defaults/wizard/step` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/books` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/books/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/books/{var}/export` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/books/{var}/generate/chat` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/books/{var}/generate/council` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/council/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/council/sessions/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/analyze` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/consensus` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/consolidate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/consolidate-gated` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/critic/sign` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/critic/signatures` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/discuss` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/participants` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/sentinels` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/sentinels/evaluate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/nodes/{var}/choose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/nodes/{var}/present` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/current` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/history` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/rollback` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/tree` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/undo` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/ideas` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workspace/ideas/attachments/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE | `/api/v1/workspace/ideas/search` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workspace/ideas/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/ideas/upload` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/workspace/ideas/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments/analyze` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/submit-pipeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/notifications/{var}/unread-count` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST,PUT | `/api/v1/workspace/prompts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST,PUT | `/api/v1/workspace/prompts/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/prompts/{var}/resolve` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/sessions/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/sessions/{var}/messages` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/settings/council-members` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/settings/hierarchies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/settings/keys` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/settings/keys/{var}/activate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/settings/keys/{var}/validate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/ideas` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | POST | `/api/v1/ideas/{var}` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/ideas/{var}/clarification-response` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/ideas/{var}/discuss` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/ideas/{var}/discussion` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/ideas/{var}/history` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/ideas/{var}/promote-to-project` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments/analysis` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments/analyze` | `src\sylion-frontend\src\lib\api\ideas.ts` |
| yes | PUT | `/api/v1/orchestration` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| yes | GET | `/api/v1/projects` | `src\sylion-frontend\src\lib\api\projects.ts` |
| yes | GET | `/api/v1/projects/{var}` | `src\sylion-frontend\src\lib\api\projects.ts` |
| no | GET | `/api/v1/testing/finding` | `src\sylion-frontend\src\lib\api\testing.ts` |
| no | GET | `/api/v1/testing/guardianalert` | `src\sylion-frontend\src\lib\api\testing.ts` |
| yes | GET | `/api/v1/testing/health` | `src\sylion-frontend\src\lib\api\testing.ts` |
| no | GET | `/api/v1/testing/humanpersona` | `src\sylion-frontend\src\lib\api\testing.ts` |
| no | GET | `/api/v1/testing/loopreport` | `src\sylion-frontend\src\lib\api\testing.ts` |
| yes | GET | `/api/v1/testing/objects` | `src\sylion-frontend\src\lib\api\testing.ts` |
| yes | GET | `/api/v1/testing/release-gate/{var}` | `src\sylion-frontend\src\lib\api\testing.ts` |
| no | GET | `/api/v1/testing/repairattempt` | `src\sylion-frontend\src\lib\api\testing.ts` |
| no | GET | `/api/v1/testing/testcharter` | `src\sylion-frontend\src\lib\api\testing.ts` |
| no | GET | `/api/v1/testing/testrun` | `src\sylion-frontend\src\lib\api\testing.ts` |
| yes | GET | `/api/v1/testing/truth-alignment` | `src\sylion-frontend\src\lib\api\testing.ts` |
