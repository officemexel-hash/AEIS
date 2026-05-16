# AEIS API/UI Coverage Map

- Frontend routes: 125
- Client API refs: 788
- Runtime OpenAPI paths: 1599

## Routes

| Route | Classification | Risk Markers | API refs | File |
|---|---|---|---:|---|
| `/advisor/[cardId]` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\advisor\[cardId]\page.tsx` |
| `/advisor/cockpit` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\advisor\cockpit\page.tsx` |
| `/advisor` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\advisor\page.tsx` |
| `/agents` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\agents\page.tsx` |
| `/ai-models` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\ai-models\page.tsx` |
| `/anomalies` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\anomalies\page.tsx` |
| `/apps-builder/[appId]` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\apps-builder\[appId]\page.tsx` |
| `/apps-builder` | `STATIC_API_LINKED` | - | 5 | `src\sylion-frontend\src\app\(app)\apps-builder\page.tsx` |
| `/apps-builder/wizard` | `STATIC_API_LINKED` | - | 5 | `src\sylion-frontend\src\app\(app)\apps-builder\wizard\page.tsx` |
| `/architecture-layers` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\architecture-layers\page.tsx` |
| `/audit` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\audit\page.tsx` |
| `/auth` | `STATIC_API_LINKED` | - | 6 | `src\sylion-frontend\src\app\(app)\auth\page.tsx` |
| `/autonomy` | `NEEDS_REVIEW` | demo | 1 | `src\sylion-frontend\src\app\(app)\autonomy\page.tsx` |
| `/autoscaler` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\autoscaler\page.tsx` |
| `/book` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\book\page.tsx` |
| `/budget` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\budget\page.tsx` |
| `/build-state` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\build-state\page.tsx` |
| `/builds` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\builds\page.tsx` |
| `/bundles` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\bundles\page.tsx` |
| `/capacity` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\capacity\page.tsx` |
| `/cellular` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\cellular\page.tsx` |
| `/circuits` | `STATIC_API_LINKED` | - | 1 | `src\sylion-frontend\src\app\(app)\circuits\page.tsx` |
| `/coherence-guard` | `NEEDS_REVIEW` | mock, demo | 8 | `src\sylion-frontend\src\app\(app)\coherence-guard\page.tsx` |
| `/connectors` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\connectors\page.tsx` |
| `/contracts` | `STATIC_API_LINKED` | - | 1 | `src\sylion-frontend\src\app\(app)\contracts\page.tsx` |
| `/cost-guard` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\cost-guard\page.tsx` |
| `/costs` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\costs\page.tsx` |
| `/council-to-ksiega` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\council-to-ksiega\page.tsx` |
| `/dashboard/operator-monitor` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\dashboard\operator-monitor\page.tsx` |
| `/decisions` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\decisions\page.tsx` |
| `/demo/crm` | `STATIC_API_LINKED` | - | 4 | `src\sylion-frontend\src\app\(app)\demo\crm\page.tsx` |
| `/demo/factory` | `STATIC_API_LINKED` | - | 6 | `src\sylion-frontend\src\app\(app)\demo\factory\page.tsx` |
| `/demo/funding` | `STATIC_API_LINKED` | - | 5 | `src\sylion-frontend\src\app\(app)\demo\funding\page.tsx` |
| `/demo/marketplace` | `STATIC_API_LINKED` | - | 4 | `src\sylion-frontend\src\app\(app)\demo\marketplace\page.tsx` |
| `/demo/mobile-inspector` | `STATIC_API_LINKED` | - | 7 | `src\sylion-frontend\src\app\(app)\demo\mobile-inspector\page.tsx` |
| `/demo/portal` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\demo\portal\page.tsx` |
| `/deploy` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\deploy\page.tsx` |
| `/devices` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\devices\page.tsx` |
| `/drift` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\drift\page.tsx` |
| `/environments` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\environments\page.tsx` |
| `/evaluator` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\evaluator\page.tsx` |
| `/events` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\events\page.tsx` |
| `/evidence` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\evidence\page.tsx` |
| `/evidence-spine` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\evidence-spine\page.tsx` |
| `/execution-start` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\execution-start\page.tsx` |
| `/faq` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\faq\page.tsx` |
| `/federation` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\federation\page.tsx` |
| `/funding` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\funding\page.tsx` |
| `/gates` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\gates\page.tsx` |
| `/golden-tests` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\golden-tests\page.tsx` |
| `/governance` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\governance\page.tsx` |
| `/healing` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\healing\page.tsx` |
| `/health` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\health\page.tsx` |
| `/human-gate` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\human-gate\page.tsx` |
| `/idea-vault/[id]` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\idea-vault\[id]\page.tsx` |
| `/idea-vault` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\idea-vault\page.tsx` |
| `/integrations` | `STATIC_API_LINKED` | - | 5 | `src\sylion-frontend\src\app\(app)\integrations\page.tsx` |
| `/lifecycle` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\lifecycle\page.tsx` |
| `/masterplan` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\masterplan\page.tsx` |
| `/memory` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\memory\page.tsx` |
| `/model-council` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\model-council\page.tsx` |
| `/modules` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\modules\page.tsx` |
| `/notifications` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\notifications\page.tsx` |
| `/observability` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\observability\page.tsx` |
| `/onboarding` | `NEEDS_REVIEW` | demo | 1 | `src\sylion-frontend\src\app\(app)\onboarding\page.tsx` |
| `/ontology` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\ontology\page.tsx` |
| `/operator-mobile/devices` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\operator-mobile\devices\page.tsx` |
| `/operator-mobile` | `STATIC_API_LINKED` | - | 2 | `src\sylion-frontend\src\app\(app)\operator-mobile\page.tsx` |
| `/operator-mobile/queue/[ticketId]` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\operator-mobile\queue\[ticketId]\page.tsx` |
| `/operator-mobile/queue` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\operator-mobile\queue\page.tsx` |
| `/orchestration/auditor` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\auditor\page.tsx` |
| `/orchestration/conversations` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\conversations\page.tsx` |
| `/orchestration/council-rules` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\council-rules\page.tsx` |
| `/orchestration/dispatch` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\dispatch\page.tsx` |
| `/orchestration/event-map` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\event-map\page.tsx` |
| `/orchestration/fixer` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\fixer\page.tsx` |
| `/orchestration/llm-routing` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\llm-routing\page.tsx` |
| `/orchestration` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\page.tsx` |
| `/orchestration/teams` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\teams\page.tsx` |
| `/orchestration/tests` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\orchestration\tests\page.tsx` |
| `/overview` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\overview\page.tsx` |
| `/performance` | `STATIC_API_LINKED` | - | 1 | `src\sylion-frontend\src\app\(app)\performance\page.tsx` |
| `/pipeline` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\pipeline\page.tsx` |
| `/planning` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\planning\page.tsx` |
| `/policy` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\policy\page.tsx` |
| `/project-start` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\project-start\page.tsx` |
| `/projects/[projectId]/lifecycle` | `STATIC_API_LINKED` | - | 2 | `src\sylion-frontend\src\app\(app)\projects\[projectId]\lifecycle\page.tsx` |
| `/projects/[projectId]/orchestration` | `STATIC_API_LINKED` | - | 2 | `src\sylion-frontend\src\app\(app)\projects\[projectId]\orchestration\page.tsx` |
| `/projects/[projectId]` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\projects\[projectId]\page.tsx` |
| `/projects` | `STATIC_API_LINKED` | - | 4 | `src\sylion-frontend\src\app\(app)\projects\page.tsx` |
| `/provenance-guard` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\provenance-guard\page.tsx` |
| `/quality` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\quality\page.tsx` |
| `/quality-guard` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\quality-guard\page.tsx` |
| `/rebuild` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\rebuild\page.tsx` |
| `/risk` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\risk\page.tsx` |
| `/role-catalog` | `STATIC_API_LINKED` | - | 10 | `src\sylion-frontend\src\app\(app)\role-catalog\page.tsx` |
| `/roles` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\roles\page.tsx` |
| `/runtime` | `STATIC_API_LINKED` | - | 1 | `src\sylion-frontend\src\app\(app)\runtime\page.tsx` |
| `/sdr` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\sdr\page.tsx` |
| `/secrets` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\secrets\page.tsx` |
| `/security-guard` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\security-guard\page.tsx` |
| `/security-scan` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\security-scan\page.tsx` |
| `/settings/advisor` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\settings\advisor\page.tsx` |
| `/settings` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\settings\page.tsx` |
| `/settings/profile` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\settings\profile\page.tsx` |
| `/skills` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\skills\page.tsx` |
| `/sla` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\sla\page.tsx` |
| `/source-of-truth` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\source-of-truth\page.tsx` |
| `/templates-setup` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\templates-setup\page.tsx` |
| `/terminal` | `STATIC_API_LINKED` | - | 10 | `src\sylion-frontend\src\app\(app)\terminal\page.tsx` |
| `/terminal/replay` | `STATIC_API_LINKED` | - | 7 | `src\sylion-frontend\src\app\(app)\terminal\replay\page.tsx` |
| `/test-center/auto-repair` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\test-center\auto-repair\page.tsx` |
| `/test-center/catalog` | `STATIC_API_LINKED` | - | 2 | `src\sylion-frontend\src\app\(app)\test-center\catalog\page.tsx` |
| `/test-center/dashboard` | `STATIC_API_LINKED` | - | 4 | `src\sylion-frontend\src\app\(app)\test-center\dashboard\page.tsx` |
| `/test-center/human-lab` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\test-center\human-lab\page.tsx` |
| `/test-center/no-mock-scan` | `NEEDS_REVIEW` | mock, stub, demo | 2 | `src\sylion-frontend\src\app\(app)\test-center\no-mock-scan\page.tsx` |
| `/test-center` | `NEEDS_REVIEW` | mock, stub, demo | 0 | `src\sylion-frontend\src\app\(app)\test-center\page.tsx` |
| `/test-center/release-gate` | `NEEDS_REVIEW` | mock, stub, demo | 6 | `src\sylion-frontend\src\app\(app)\test-center\release-gate\page.tsx` |
| `/test-center/simulation` | `STATIC_API_LINKED` | - | 2 | `src\sylion-frontend\src\app\(app)\test-center\simulation\page.tsx` |
| `/test-center/theater` | `STATIC_API_LINKED` | - | 1 | `src\sylion-frontend\src\app\(app)\test-center\theater\page.tsx` |
| `/test-center/truth-alignment` | `STATIC_API_LINKED` | - | 2 | `src\sylion-frontend\src\app\(app)\test-center\truth-alignment\page.tsx` |
| `/v2/admin` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\v2\admin\page.tsx` |
| `/workers` | `STATIC_API_LINKED` | - | 3 | `src\sylion-frontend\src\app\(app)\workers\page.tsx` |
| `/workspace` | `UI_ONLY_OR_STATIC` | - | 0 | `src\sylion-frontend\src\app\(app)\workspace\page.tsx` |
| `/workspace-defaults` | `NEEDS_REVIEW` | demo | 1 | `src\sylion-frontend\src\app\(app)\workspace-defaults\page.tsx` |

## Client API Refs

| Runtime | Methods | Path | Source |
|---|---|---|---|
| no | GET | `/api/v1/advisor` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/cards/{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/cards/{var}/actions` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/cards{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST | `{var}/evidence/{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/evidence/{var}/finalize` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/evidence/{var}/sign` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/funding/deadlines` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/funding/grants{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/monitoring/snapshot` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST,PUT | `{var}/onboarding/complete` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | DELETE,POST | `{var}/onboarding/phase1/acceptance-test` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | DELETE,POST | `{var}/onboarding/phase1/complete` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST | `{var}/onboarding/phase1/model-gate{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST | `{var}/onboarding/phase1/storage/validate` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST | `{var}/onboarding/phase1/system-check` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST,PUT | `{var}/onboarding/state` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | POST,PUT | `{var}/onboarding/step/{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/preferences/audit?{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/preferences/counts` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | PUT | `{var}/preferences/{var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | DELETE,PUT | `{var}/preferences?user_id={var}` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| no | GET | `{var}/projects/{var}/lifecycle` | `src\sylion-frontend\src\lib\api\advisor.ts` |
| yes | POST | `/api/v1/advisor/suggest-pipeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/autonomy/stages` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/autonomy/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/explanations` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/improvements` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/aeis/limitation/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/agents/executions{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/agents/executions{var}`);
  },
  registerRuntimeAgent: (body: {
    name: string;
    agent_type?: string;
    provider?: string;
    model_id?: string;
    system_prompt?: string;
    max_tokens?: number;
    temperature?: number;
    tools?: string;
    capabilities?: string;
  }) => {
    const params = new URLSearchParams();
    Object.entries(body).forEach(([key, value]) => {
      if (value !== undefined && value !== null) params.set(key, String(value));
    });
    return request<any>(`/api/v1/agents/register?{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/agents/list{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/agents/list{var}`);
  },
  getAgentRuntimeStats: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | DELETE,POST | `/api/v1/agents/register?{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/agents/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/agents/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/list` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/ollama/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/ai-providers/openrouter/models?limit={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ai-providers/test/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/ai-providers/test/{var}`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/architecture-layers` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/architecture-layers"),
  getArchitectureLayer: (id: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/audit/events{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/audit/events{var}`);
  },
  getAuditSummary: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/audit/export` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/audit/integrity` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/auth/providers/list?type=${type ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/auth/providers/list?type={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/auth/sessions/list?user_id=${userId ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/auth/sessions/list?user_id={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/autonomy/configuration/acceptance-test?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/configuration/acceptance-test?goal={var}`),

  // Phase 6 - Coherence Guard
  getCoherenceGuard: (goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/autonomy/configuration/acceptance?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/configuration/acceptance?goal={var}`),
  runAutonomyConfigurationAcceptanceTest: (goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/apply-preset` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/d-level-overrides` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/dimensions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/hard-gates/custom` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/hard-gates/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/configuration/hard-gates/{var}/toggle` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/configuration/hard-gates/{var}/toggle`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/inheritance/trace` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/overrides` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/wizard/mode` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/autonomy/configuration/wizard/step` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/autonomy/configuration?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/configuration?goal={var}`),
  getAutonomyConfigurationTemplates: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/advance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/event` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/{var}/event`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/state` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/{var}/state`),
  autonomyAdvance: (project_id: string, decision_class?: string) =>
    request<any>(`/api/v1/autonomy/{var}/advance`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/autonomy/{var}/steer` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/{var}/steer`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/{var}/transitions${limit ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/autonomy/{var}/transitions{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/brain/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/brain/models/pull` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/build-state` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/bundles/list?status=${status ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/bundles/list?status={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/capacity/bottlenecks` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/capacity/resources` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/capacity/resources/{var}/forecast` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/capacity/usage` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/attack-vectors` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/control-plane` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/cores` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/evidence` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/isolation` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/ran` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cellular/ue` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/circuit-breakers/list?status=${status ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/circuit-breakers/list?status={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cloud-connectors` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/cloud-connectors (not /connectors which is legacy connector_routes)
  registerConnector: (body: { provider: string; name: string; scope: string; credentials: Record<string, unknown> }) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/cloud-connectors (not /connectors which is legacy connector_routes)
  registerConnector: (body: { provider: string; name: string; scope: string; credentials: Record<string, unknown> }) =>
    request<any>('/api/v1/cloud-connectors', { method: 'POST', body: JSON.stringify(body) }),
  listCloudConnectors: () =>
    request<any>('/api/v1/cloud-connectors'),
  deleteConnector: (connectorId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cloud-connectors/providers` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cloud-connectors/{var}/test` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/cloud-connectors/{var}/test`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/evaluations` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/cognitive/hallucinations/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/cognitive/hallucinations/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/hallucinations/{var}/verify` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/cognitive/hallucinations/{var}/verify`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/cognitive/hallucinations{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/cognitive/hallucinations{var}`);
  },
  getHallucinationCheck: (checkId: string) =>
    request<any>(`/api/v1/cognitive/hallucinations/{var}`),
  checkHallucinationClaim: (sourceType: string, sourceId: string, claim: string, expectedAnswer?: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/cognitive/plans` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/coherence-guard/acceptance-test?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/coherence-guard/acceptance-test?goal={var}`),

  // Phases 7-10 - Cost/Security/Quality/Provenance Guards
  listGuardSuite: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/coherence-guard/acceptance?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/coherence-guard/acceptance?goal={var}`),
  runCoherenceAcceptanceTest: (goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/aggregated-panel` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/autonomy-override` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/checks/config` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/checks/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/custom-checks` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/coherence-guard/findings/{var}/action` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/coherence-guard/findings{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/coherence-guard/findings{var}`);
  },
  actOnCoherenceFinding: (findingId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/coherence-guard/findings/{var}/action`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/performance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/run` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/scope` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/severity/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/coherence-guard/triggers` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/coherence-guard?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/coherence-guard?goal={var}`),
  getCoherenceGuardTemplates: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/connectors/list?type=${type ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/connectors/list?type={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/contracts/{var}/versions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/contracts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/events` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/evidence` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/core/modules` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/core/modules"),
  getModule: (id: string) => request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/core/modules?module_id={var}&module_kind={var}&owner_plan={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/council-to-ksiega` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/council-to-ksiega/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/council-to-ksiega/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase20/convene` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase21/initial-verdicts` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council-to-ksiega/projects/{var}/phase21/initial-verdicts`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase22/deliberate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council-to-ksiega/projects/{var}/phase22/deliberate`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase23/consolidate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council-to-ksiega/projects/{var}/phase23/consolidate`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase24/generate-book` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council-to-ksiega/projects/{var}/phase24/generate-book`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phase25/finalize-ksiega` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council-to-ksiega/projects/{var}/phase25/finalize-ksiega`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council-to-ksiega/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council-to-ksiega/projects/{var}/phases/{var}/acceptance`),
  runCouncilToKsiegaAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/council-to-ksiega/projects/{var}/phases/{var}/acceptance-test`),
  getCouncilToKsiegaEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/council-to-ksiega/projects/{var}/edge-cases`),
  diagnoseCouncilToKsiegaEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/{var}/edge-cases/diagnose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/deliberate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council/{var}/deliberate`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/enable` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council/{var}/enable`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/reconcile` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/council/{var}/state` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/council/{var}/state`),
  councilReconcile: (project_id: string) =>
    request<any>(`/api/v1/council/{var}/reconcile`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/deploy/hetzner/deployments${projectId ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/deploy/hetzner/deployments{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/hetzner/provision` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/deploy/hetzner/provision", { method: "POST", body: JSON.stringify(body) }),
  checkHetznerDeploymentHealth: (deploymentId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/deploy/hetzner/{var}/delete` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/deploy/hetzner/{var}/delete`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/deploy/hetzner/{var}/health`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/topologies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/deploy/topologies/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/deployments` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/devices/deployments"),
  listDeviceTests: () => request<{ tests: any[] }>("/api/v1/devices/tests"),

  // SDR (Class N)
  listSDRDevices: () => request<{ devices: any[] }>("/api/v1/sdr/devices"),
  listCaptures: () => request<{ captures: any[] }>("/api/v1/sdr/captures"),
  listAnalyses: () => request<{ analyses: any[] }>("/api/v1/sdr/analysis"),
  listRFPolicies: () => request<{ policies: any[] }>("/api/v1/sdr/rf/policies"),

  // Cellular (Class O)
  listRANStacks: () => request<{ stacks: any[] }>("/api/v1/cellular/ran"),
  listCoreNetworks: () => request<{ cores: any[] }>("/api/v1/cellular/cores"),
  listUEDevices: () => request<{ ues: any[] }>("/api/v1/cellular/ue"),
  listIsolationChecks: () => request<{ checks: any[] }>("/api/v1/cellular/isolation"),
  listAttackVectors: () => request<{ vectors: any[] }>("/api/v1/cellular/attack-vectors"),
  listCPAnalyses: () => request<{ analyses: any[] }>("/api/v1/cellular/control-plane"),
  listCellularEvidence: () => request<{ evidence: any[] }>("/api/v1/cellular/evidence"),

  // Cost Envelope
  listCostRecords: (provider?: string) => request<{ records: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/discovery` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/devices/discovery/scan${transport ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/registry` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/devices/tests` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/budgets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/budgets/over` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/circuits` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/efficiency/cost/alerts${limit ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/efficiency/cost/alerts{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/efficiency/cost/daily${provider ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/efficiency/cost/daily{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/efficiency/cost/monthly${provider ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/efficiency/cost/monthly{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/efficiency/cost/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | PUT | `/api/v1/efficiency/cost/summary"),

  // Budget Monitoring
  getModelBudgets: () => request<{ budgets: any[] }>("/api/v1/monitoring/budget"),
  getModelBudget: (modelId: string) => request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/efficiency/drift` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/environment-catalog/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/environment-catalog/acceptance-test?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/environment-catalog/acceptance-test?goal={var}`),

  // Phase 4 — Workspace Defaults
  getWorkspaceDefaults: (goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
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
| no | GET | `/api/v1/environment-catalog?view={var}&auto_scan=${autoScan ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/environment-catalog?view={var}&auto_scan={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/event-backbone/catalog` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/event-backbone/events${limit ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/event-backbone/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/evidence-timeline/timelines` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/evidence-timeline/timelines/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/evidence-timeline/timelines/{var}/verify` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/evidence-timeline/timelines/{var}/verify`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/execution-start` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/execution-start/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/execution-start/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase32/initialize-build` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase33/start-execution` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase33/start-execution`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase34/reconvene-council` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase34/reconvene-council`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase35/activate-orchestration` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase35/activate-orchestration`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase36/complete-build` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase36/complete-build`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase37/run-quality-gates` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase37/run-quality-gates`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase38/complete-acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase38/complete-acceptance`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase39/authorize-predeploy` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase39/authorize-predeploy`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase40/execute-production-deploy` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase40/execute-production-deploy`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phase41/close-project` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phase41/close-project`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution-start/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/execution-start/projects/{var}/phases/{var}/acceptance`),
  runExecutionStartAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/execution-start/projects/{var}/phases/{var}/acceptance-test`),
  getExecutionStartEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/{var}/edge-cases`),
  diagnoseExecutionStartEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/{var}/edge-cases/diagnose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/jobs` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/retry/attempts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/tools` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/execution/workflows` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/nodes` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/federation/nodes/active${staleSecs !== undefined ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/federation/route` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/alerts` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/application/create` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/documents` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/export` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/application/{var}/export`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/funding/application/{var}/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/application/{var}`),
  getFundingApplicationDocuments: (applicationId: string) =>
    request<any>(`/api/v1/funding/application/{var}/documents`),
  reviewFundingApplication: (applicationId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/funding/application/{var}/review`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/calls` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/calls/search` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/calls/search", { method: "POST", body: JSON.stringify(body) }),
  getFundingCall: (callId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/calls/{var}`),
  listFundingIdeas: (_companyId?: string) => request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/funding/company-profile` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | PUT | `/api/v1/funding/company-profile"),
  saveFundingCompanyProfile: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/company-profile", { method: "PUT", body: JSON.stringify(body) }),
  getFundingCompanyReadiness: (_companyId?: string) => request<any>("/api/v1/funding/company-profile/readiness"),
  listFundingCompanyDocuments: (_companyId?: string) => request<any>("/api/v1/funding/company-profile/documents"),
  addFundingCompanyDocument: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/company-profile/documents", { method: "POST", body: JSON.stringify(body) }),
  getFundingStateAid: (_companyId?: string) => request<any>("/api/v1/funding/company-profile/state-aid"),
  getFundingCompanyRegistrySync: (_companyId?: string) => request<any>("/api/v1/funding/company-profile/registry-sync"),
  syncFundingCompanyRegistry: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/company-profile/registry-sync", { method: "POST", body: JSON.stringify(body) }),
  listFundingSources: () => request<any>("/api/v1/funding/sources"),
  listFundingProgrammes: () => request<any>("/api/v1/funding/programmes"),
  createFundingProgramme: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/programmes", { method: "POST", body: JSON.stringify(body) }),
  listFundingCalls: () => request<any>("/api/v1/funding/calls"),
  createFundingCall: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/calls", { method: "POST", body: JSON.stringify(body) }),
  triggerFundingScan: (params?: { force_refresh?: boolean; since_days?: number }) =>
    request<any>(
      ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST,PUT | `/api/v1/funding/company-profile/documents` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST,PUT | `/api/v1/funding/company-profile/readiness` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/company-profile/registry-sync` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/company-profile/state-aid` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/consortium/analyze", { method: "POST", body: JSON.stringify(body) }),
  searchFundingPartners: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/partners/search", { method: "POST", body: JSON.stringify(body) }),
  shortlistFundingPartners: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/partners/shortlist", { method: "POST", body: JSON.stringify(body) }),
  generateFundingOutreach: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/outreach/generate", { method: "POST", body: JSON.stringify(body) }),
  createFundingApplication: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/application/create", { method: "POST", body: JSON.stringify(body) }),
  getFundingApplication: (applicationId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/consortium/outreach/generate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/consortium/partners/search` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/consortium/partners/shortlist` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/crm/applications` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/deadlines` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/ideas"),
  getFundingIdea: (ideaId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/ideas/generate", { method: "POST", body: JSON.stringify(body) }),
  convertFundingIdeaToProject: (ideaId: string, body: Record<string, unknown>) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/ideas/{var}/convert-to-project`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/ideas/{var}`),
  generateFundingIdeas: (body: Record<string, unknown>) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/matching/run` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/matching/run", { method: "POST", body: JSON.stringify(body) }),
  getFundingScoring: (projectId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/programmes` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/projects` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/projects"),
  getFundingMatchingResults: (projectId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/reports/executive` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/scan/trigger?force_refresh={var}&since_days={var}`,
      { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/scoring/{var}`),
  analyzeFundingConsortium: (body: Record<string, unknown>) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/sources` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/submission/approvals${applicationId ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/submission/approvals{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/fill` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/prepare` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/submission/receipt${sessionId ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/submission/receipt{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/request-approval` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/save-draft` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/funding/submission/sessions${applicationId ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/funding/submission/sessions{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/funding/submission/submit` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/gates/human/requests?status=${status ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/gates/human/requests?status={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/gates/human/reviews` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/gates/list?gate_type=${gateType ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/gates/list?gate_type={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/golden-sets/sets?category=${category ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/golden-sets/sets?category={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/audit/log{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/audit/log{var}`);
  },
  getAuditTimeline: (decisionId: string) =>
    request<{ timeline: any[] }>(`/api/v1/governance/audit/timeline/{var}`),
  getAuditStats: () =>
    request<{ stats: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/audit/timeline/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/cascade-events${requiresHuman !== undefined ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade-events/{var}/acknowledge` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/cascade-events{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade/analyses/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/cascade/analyses/{var}/paths` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/cascade/analyses{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/cascade/analyses{var}`);
  },
  getCascadeAnalysis: (analysisId: string) =>
    request<any>(`/api/v1/governance/cascade/analyses/{var}`),
  getCascadePaths: (analysisId: string) =>
    request<{ paths: any[] }>(`/api/v1/governance/cascade/analyses/{var}/paths`),
  getCascadeStats: () =>
    request<{ stats: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/checker/checks{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/checker/checks{var}`);
  },
  getComplianceStats: () =>
    request<{ stats: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/checker/policies{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/checker/policies{var}`);
  },
  listComplianceChecks: (moduleId?: string, policyId?: string, status?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (moduleId) params.set(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/compliance/report/latest` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/compliance/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/compliance/{var}`),
  listComplianceRules: () =>
    request<{ rules: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/conflict-detections/rules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/conflict-detections/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/conflict-detections{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/conflict-detections{var}`);
  },
  getConflict: (conflictId: string) =>
    request<any>(`/api/v1/governance/conflict-detections/{var}`),
  getConflictStats: () =>
    request<{ stats: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/decision-snapshots` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/decision-snapshots", { method: "POST", body: JSON.stringify(data) }),
  getDecisionSnapshot: (snapshotId: string) =>
    request<{ snapshot: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/decision-snapshots${params ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/decision-snapshots/active-chain` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/decision-snapshots/active-chain"),
  changeDecision: (snapshotId: string, data: { new_choice: string; new_consequences?: Record<string, unknown> }) =>
    request<{ new_snapshot: any; cascade_events: any[]; invalidated_decisions: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/decision-snapshots/timeline${params ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/decision-snapshots/timeline${params ? `?${new URLSearchParams(Object.entries(params).filter(([,_]) => _ !== undefined && _ !== ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/decision-snapshots/{var}/cascade-impact` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/decision-snapshots/{var}/cascade-impact`),
  getSnapshotDiff: (id1: string, id2: string) =>
    request<{ diff: any }>(`/api/v1/governance/decision-snapshots/{var}/diff/{var}`),
  acknowledgeCascade: (eventId: string, actionTaken?: string) =>
    request<{ event: any }>(`/api/v1/governance/cascade-events/{var}/acknowledge`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/decision-snapshots/{var}/diff/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/decision-snapshots/{var}`),
  listDecisionSnapshots: (params?: { decision_class?: string; is_active?: boolean; limit?: number }) =>
    request<{ snapshots: any[] }>(`/api/v1/governance/decision-snapshots{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/gates` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/gates"),
  evaluateGate: (gateId: string, context: Record<string, unknown>) =>
    request<{ gate_id: string; result: string; details: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/lifecycle/entries${moduleId ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/lifecycle/stages` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/proposals` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/proposals/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/proposals/{var}/vote` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/proposals/{var}/vote`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/spine/decision/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/spine/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/spine/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/spine/{var}`),
  getSpineForDecision: (decisionId: string) =>
    request<{ entries: any[] }>(`/api/v1/governance/spine/decision/{var}`),
  verifySpineChain: () =>
    request<{ valid: boolean; total_entries: number; tampered_count: number; broken_at: string | null }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/spine{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/tickets` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/tickets${params.toString() ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/governance/tickets/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/governance/tickets/{var}/resolve` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/tickets/{var}/resolve`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/governance/tickets/{var}`),
  governanceTicketSubmit: (body: Record<string, unknown>) => {
    if (body.kind === ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/tickets`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/governance/tickets{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/guards/aggregated-panel` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/acceptance-test?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/acceptance-test?goal={var}`),

  // Phases 11-15 - Skills Library and Templates Setup
  getTemplatesSetupOverview: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/acceptance?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/acceptance?goal={var}`),
  runGuardAcceptanceTest: (guardId: string, goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/autonomy-override` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/autonomy-override`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/config` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/config`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/edge-cases`),
  diagnoseGuardEdgeCase: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/{var}/edge-cases/diagnose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/findings/{var}/action` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/findings{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/findings{var}`);
  },
  actOnGuardFinding: (guardId: string, findingId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/{var}/findings/{var}/action`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/review`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/run` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}/run`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/guards/{var}/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/guards/{var}?goal={var}`),
  getGuardTemplates: (guardId: string) =>
    request<any>(`/api/v1/guards/{var}/templates`),
  applyGuardDefaults: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/{var}/defaults/apply`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/hardened-audit/chain/tamper-check` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/hardened-audit/chain/verify` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/hardened-audit/events?event_type=${eventType ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/hardened-audit/events?event_type={var}&actor={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/builds` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/integration/builds/{var}/promote` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/integration/builds/{var}/promote`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/integration/builds/{var}/reject` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/integration/builds/{var}/reject`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/integration/builds/{var}/validate`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/drift` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/drift/detect` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/integration/drift/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/integrations?type=${type ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/integrations?type={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/memory/evidence-store` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/memory/evidence/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/memory/evidence/stats`),
  memorySearchSimilar: (query: string, limit?: number) =>
    request<any>(`/api/v1/memory/index/search?query={var}{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/memory/index/search?query={var}${limit ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/memory/kanon/sections` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/metrics` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/metrics`).then((r) => r.text()),

  // Phase 2 D-INTEGRATE: Skills runtime (B1)
  skillsRuntimeList: () => request<{ skills: any[] }>(`/api/v1/skills`),
  skillsRuntimeState: (skill_id: string) =>
    request<any>(`/api/v1/skills/{var}/state`),
  skillsRuntimeExecute: (skill_id: string, context: Record<string, unknown>) =>
    request<any>(`/api/v1/skills/{var}/execute`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | DELETE,POST | `/api/v1/mobile/devices${operator_id ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST,PUT | `/api/v1/mobile/devices/bind` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | DELETE,POST,PUT | `/api/v1/mobile/devices/bind`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST,PUT | `/api/v1/mobile/devices/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/devices/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/devices{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | DELETE,POST | `/api/v1/mobile/queue${operator_id ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/mobile/queue/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/queue/{var}/approve` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/queue/{var}/reject` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/queue/{var}/reject`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/queue/{var}`),
  mobileApprove: (ticket_id: string, operator_id: string, comment?: string) =>
    request<any>(`/api/v1/mobile/queue/{var}/approve`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/mobile/queue{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/model-budget/budgets` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/model-registry/capabilities` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/model-registry/models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/model-registry/models/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/model-registry/models/{var}`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/model-registry/models/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/model-registry/models{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/model-registry/models{var}`);
  },
  getModelRegistryStats: () => request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/anomalies` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/monitoring/anomalies/baselines/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/bloat/modules` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/monitoring/budget` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/budget/configure` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/budget/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/monitoring/budget/summary"),
  resetModelBudget: (modelId: string) =>
    request<{ reset: boolean }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/monitoring/budget/transactions${modelId ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/budget/transactions{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/monitoring/budget/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/budget/{var}/usage` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/budget/{var}/usage`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/cost/records` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/drift/reports` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/drift/snapshots/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/metrics/latest/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/metrics/{var}/buckets` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/performance/anomalies{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/performance/anomalies{var}`);
  },
  getModelTrend: (modelId: string, metricType?: string, hours?: number) => {
    const params = new URLSearchParams();
    if (metricType) params.set(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/monitoring/performance/leaderboard{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/performance/leaderboard{var}`);
  },
  compareModels: (data: { model_ids: string[]; metric_type: string; from_time?: number; to_time?: number }) =>
    request<{ comparison: any }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/performance/metrics{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/performance/metrics{var}`);
  },
  getModelSummary: (modelId: string) =>
    request<{ summary: any }>(`/api/v1/monitoring/performance/summary/{var}`),
  getAllModelSummaries: () =>
    request<{ summaries: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/monitoring/performance/record` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/performance/summary/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/performance/trend/{var}{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/performance/trend/{var}{var}`);
  },

  // Decision Audit
  getDecisionAuditLog: (params?: { decision_id?: string; event_type?: string; severity?: string; from_time?: number; to_time?: number; limit?: number }) => {
    const qs = params ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/preservation/health` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/monitoring/sla` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/monitoring/sla/policies/{var}/compliance` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/notifications/channels?type=${type ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/notifications/channels?type={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/notifications/{var}/read` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/notifications/{var}/read`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/notifications/{var}/unread` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/notifications/{var}/unread`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/notifications?status=${status ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/notifications?status={var}&limit={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/observability/logs{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/observability/metrics` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/observability/metrics"),
  listObservabilityTraces: (service?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (service) params.set("service", service);
    if (limit) params.set("limit", String(limit));
    return request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/observability/snapshot` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/observability/snapshot"),
  listObservabilityLogs: (service?: string, level?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (service) params.set("service", service);
    if (level) params.set("level", level);
    if (limit) params.set("limit", String(limit));
    return request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/observability/traces{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ontology/reload` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/ontology/types` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/ontology/types"),
  getOntologyType: (id: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/ontology/types/{var}/actions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/ontology/types/{var}/ddl` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/pipeline/ideas` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/pipeline/runs` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/pipeline/runs/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/pipeline/runs/{var}/cancel` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/pipeline/runs/{var}/cancel`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/pipeline/runs/{var}/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/pipeline/runs/{var}/execute`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/pipeline/runs/{var}/steps` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/pipeline/runs/{var}/steps`),

  // AI Workspace — Chat
  createChatSession: (title: string, modelIds: string[], systemPrompt?: string, teamId?: string, projectId?: string) =>
    request<{ session_id: string; title: string }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/pipeline/runs/{var}/steps`),

  // HumanGate
  createHumanGateSession: (title: string, description?: string) =>
    request<{ session_id: string; root_node_id: string }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/pipeline/runs/{var}`),
  listRuns: () =>
    request<{ runs: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase26/assign-models` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase27/synthesize-skills` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/planning/projects/{var}/phase27/synthesize-skills`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase28/generate-masterplan` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/planning/projects/{var}/phase28/generate-masterplan`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase29/generate-test-plan` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/planning/projects/{var}/phase29/generate-test-plan`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase30/preflight-cost` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/planning/projects/{var}/phase30/preflight-cost`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phase31/dry-run` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/planning/projects/{var}/phase31/dry-run`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/planning/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/planning/projects/{var}/phases/{var}/acceptance`),
  runPlanningAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/planning/projects/{var}/phases/{var}/acceptance-test`),
  getPlanningEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/planning/projects/{var}/edge-cases`),
  diagnosePlanningEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/{var}/edge-cases/diagnose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/planning/resource-profiles` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects/create` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects/preview` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/council/approve-readiness` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/project-start/projects/{var}/council/approve-readiness`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/council/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/project-start/projects/{var}/council/defaults`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/goals/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/phases/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/phases/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/project-start/projects/{var}/phases/{var}/acceptance`),
  runProjectStartAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/project-start/projects/{var}/phases/{var}/acceptance-test`),
  getProjectStartEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/project-start/projects/{var}/edge-cases`),
  diagnoseProjectStartEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/project-start/projects/{var}/edge-cases/diagnose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/project-start/projects/{var}/scope/defaults` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/project-start/projects/{var}/scope/defaults`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/project-start/templates` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects${status ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/projects/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/artifact/raw` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/artifact/raw`,

  // F-030: per-project meta-orchestration (rada, budzet, autonomia, modele)
  getProjectCouncil: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/council`),
  getProjectCouncilSuggest: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/council/suggest`),
  updateProjectCouncil: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/{var}/council`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/attachments` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/attachments`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/audit` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/autonomy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/budget` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/budget`),
  getProjectAutonomy: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/autonomy`),
  updateProjectAutonomy: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/{var}/autonomy`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/budget`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/build/authorize` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/build/authorize`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/canon` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/canon/freeze` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/canon`),
  getProjectMasterplan: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/masterplan`),
  // FE-2 (round_meta): freeze Canon (Source of Truth) — calls BE-1
  freezeProjectCanon: (
    projectId: string,
    body: { reason: string; evidence_pack_id?: string },
  ) =>
    request<any>(`/api/v1/projects/{var}/canon/freeze`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/cost` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/council` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/council/suggest` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/execution-models` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/execution-models`),
  updateProjectExecutionModels: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/{var}/execution-models`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/launch` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/masterplan` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/masterplan/freeze` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/masterplan/freeze`, {
        method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/masterplan/freeze`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/modules` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/modules`),
  getProjectAudit: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/audit`),
  getProjectCost: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/cost`),
  launchProject: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/{var}/launch`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/questions${status ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/questions/{var}/answer` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}/questions/{var}/answer`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/projects/{var}/timeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/projects/{var}`),
  getProjectTimeline: (projectId: string) =>
    request<any>(`/api/v1/projects/{var}/timeline`),
  listProjectQuestionsCanonical: (projectId: string, status?: string) =>
    request<any>(`/api/v1/projects/{var}/questions{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/provider-catalog/acceptance?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/provider-catalog/acceptance?goal={var}`),
  autoArrangeModelCouncil: (body?: { force?: boolean; max_members?: number }) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/provider-catalog/council/rebuild-hierarchy` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/provider-catalog/refresh-local` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/provider-catalog?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/provider-catalog?goal={var}`),
  getProviderCatalogTemplates: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
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
| no | GET | `/api/v1/roles'),
  getUserRoles: (userId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/analysis` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/captures` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/devices` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/sdr/rf/policies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/secrets/create` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/secrets/create', { method: 'POST', body: JSON.stringify(body) }),

  // Security Profiles
  listSecurityProfilesByLevel: (level?: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/secrets/list?scope=${scope ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/secrets/list?scope={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security-audit/findings/list?severity=${severity ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security-audit/findings/list?severity={var}&status={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security-audit/scans/list?status=${status ?? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security-audit/scans/list?status={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/audit` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/auth/users` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/security/hardened-profiles` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/security/hardened-profiles"),
  getActiveSecurityProfile: () => request<{ profile: any }>("/api/v1/security/hardened-profiles/active"),
  setActiveSecurityProfile: (name: string) => request<{ profile: any }>("/api/v1/security/hardened-profiles/active", { method: "POST", body: JSON.stringify({ name }) }),

  // Pipeline (Phase 6)
  submitPipelineIdea: (idea: string, context?: Record<string, unknown>) =>
    request<{ run_id: string; status: string }>("/api/v1/pipeline/ideas", {
      method: "POST",
      body: JSON.stringify({ idea, context }),
    }),
  executeRun: (runId: string) =>
    request<{ run_id: string; status: string; steps: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/security/hardened-profiles/active` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/session-manager/audit{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/session-manager/audit{var}`);
  },

  // Audit Trail
  listAuditEvents: (params?: { source?: string; module?: string; actor?: string; action?: string; event_type?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.source || params?.module) query.set(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/session-manager/sessions{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/session-manager/sessions{var}`);
  },
  listAuditTrail: (userId?: string, action?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (userId) params.set(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/session-manager/users{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/security/session-manager/users{var}`);
  },
  listSecuritySessions: (userId?: string) => {
    const params = new URLSearchParams();
    if (userId) params.set(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/security/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/self-healing/rules` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/self-healing/rules/{var}/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/self-healing/rules/{var}/trigger` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/self-healing/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/demand/signals` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/executions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/skills` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/{var}/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/skills/{var}/state` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/snapshots/latest/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/snapshots/latest/{var}`),

  // Cascade Analyzer
  listCascadeAnalyses: (sourceModule?: string, riskLevel?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (sourceModule) params.set(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/snapshots/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/snapshots/{var}/diff/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/snapshots/{var}/diff/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/snapshots{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/snapshots{var}`);
  },
  getSnapshot: (snapshotId: string) =>
    request<any>(`/api/v1/snapshots/{var}`),
  createSnapshot: (moduleId: string, version: string, filePath: string, content: string, metadata?: any) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/surface/console/endpoints` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/surface/ui/components` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/surface/ws/connections` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/acceptance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/acceptance-test` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}/acceptance`),
  runTemplatesSetupAcceptanceTest: (phaseId: string) =>
    request<any>(`/api/v1/templates-setup/{var}/acceptance-test`),

  // Phases 16-19 - Project Start
  getProjectStartOverview: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/custom-artifacts` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}/custom-artifacts`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/defaults/apply` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/edge-cases` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/edge-cases/diagnose` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}/edge-cases`),
  diagnoseTemplatesSetupEdgeCase: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/{var}/edge-cases/diagnose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/review` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}/review`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/templates-setup/{var}/simulate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}/simulate`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/templates-setup/{var}?goal={var}`),
  applyTemplatesSetupDefaults: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/{var}/defaults/apply`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/terminal/exec` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/terminal/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | DELETE,POST | `/api/v1/workers"),
  registerWorker: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workers", { method: "POST", body: JSON.stringify(body) }),
  heartbeatWorker: (workerId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/assignments/rebalance` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/evaluate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/execute` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workers/autoscaler/history${limit ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workers/autoscaler/policy` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workers/autoscaler/policy"),
  updateAutoscalerPolicy: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workers/autoscaler/policy", { method: "POST", body: JSON.stringify(body) }),
  evaluateAutoscaler: () =>
    request<any>("/api/v1/workers/autoscaler/evaluate", { method: "POST" }),
  executeAutoscaler: (decision?: string) =>
    request<any>("/api/v1/workers/autoscaler/execute", {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),

  // Build, deploy, event backbone, and observability surfaces
  getBuildState: () => request<any>("/api/v1/build-state"),
  listCandidateBuilds: () => request<any>("/api/v1/integration/builds"),
  createCandidateBuild: (body: Record<string, unknown>) =>
    request<any>("/api/v1/integration/builds", { method: "POST", body: JSON.stringify(body) }),
  validateCandidateBuild: (buildId: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/autoscaler/status` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/topology/all` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workers/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workers/{var}/heartbeat`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workers/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace-defaults/acceptance-test?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace-defaults/acceptance-test?goal={var}`),

  // Phase 5 - Autonomy Configuration
  getAutonomyConfiguration: (goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workspace-defaults/acceptance?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace-defaults/acceptance?goal={var}`),
  runWorkspaceDefaultsAcceptanceTest: (goal = ` | `src\sylion-frontend\src\lib\api\client.ts` |
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
| no | POST | `/api/v1/workspace-defaults?goal={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace-defaults?goal={var}`),
  getWorkspaceDefaultTemplates: () =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/books` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workspace/books${status ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/books/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/books/{var}/export?format={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/books/{var}/generate/chat` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/books/{var}/generate/chat`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/books/{var}/generate/council` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/books/{var}/generate/council`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/books/{var}`),
  exportBook: (id: string, format?: string) =>
    request<{ content: string }>(`/api/v1/workspace/books/{var}/export?format=${format || ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/books{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/council/sessions` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workspace/council/sessions", {
      method: "POST",
      body: JSON.stringify({ topic, description, model_ids: modelIds }),
    }),
  runParallelAnalysis: (sessionId: string) =>
    request<{ analyses?: any[]; created?: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workspace/council/sessions${phase ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/council/sessions/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/analyze`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/consensus` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/consolidate` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/consolidate-gated` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/consolidate`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/critic/sign` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/critic/signatures` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/critic/signatures`,
    ),
  evaluateSentinel: (
    sessionId: string,
    payload: {
      sentinel_role: string;
      model_id: string;
      verdict: string;
      score?: number;
      details?: string;
    },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/{var}/sentinels/evaluate`,
      { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/discuss` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/discuss`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/participants` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/participants`,
    ),
  signCriticDecision: (
    sessionId: string,
    payload: { model_id: string; signed_decision: string; rationale?: string },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/{var}/critic/sign`,
      { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/sentinels` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/sentinels/evaluate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/sentinels`,
    ),
  getCouncilConsensus: (sessionId: string) =>
    request<{
      verdict?: string;
      weights?: Record<string, number>;
      total_weight?: number;
      by_model?: Record<string, any>;
      critic_signed?: boolean;
      sentinel_blocks?: any[];
      [key: string]: any;
    }>(`/api/v1/workspace/council/sessions/{var}/consensus`),
  consolidateGated: (
    sessionId: string,
    payload: {
      consolidated_text: string;
      require_critic: boolean;
      require_sentinels_pass: boolean;
    },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/{var}/consolidate-gated`,
      { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/council/sessions/{var}/summary` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}/summary`),

  // AR-6.1 — canonical Council surface (9 roles / 5 ranks / critic / sentinels)
  getCouncilRoles: () =>
    request<{
      roles: string[];
      ranks: string[];
      default_role_weights: Record<string, number>;
      rank_multiplier: Record<string, number>;
      sentinel_roles: string[];
    }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions/{var}`),
  addCouncilParticipant: (
    sessionId: string,
    payload: { model_id: string; role: string; rank: string; weight?: number | null },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/{var}/participants`,
      { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/council/sessions{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/nodes/{var}/choose` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/humangate/nodes/{var}/choose`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/nodes/{var}/present` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/humangate/nodes/{var}/present`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/current` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/history` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/rollback` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/humangate/sessions/{var}/rollback`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/tree` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/humangate/sessions/{var}/tree`),
  getHumanGateHistory: (sessionId: string) =>
    request<{ history: any[] }>(`/api/v1/workspace/humangate/sessions/{var}/history`),
  getHumanGateCurrentDecision: (sessionId: string) =>
    request<any>(`/api/v1/workspace/humangate/sessions/{var}/current`),
  listHumanGateSessions: () =>
    request<{ sessions: any[] }>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/humangate/sessions/{var}/undo` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/humangate/sessions/{var}/undo`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/ideas` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | PUT | `/api/v1/workspace/ideas${status ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workspace/ideas/attachments/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/ideas/attachments/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | DELETE | `/api/v1/workspace/ideas/search?q={var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | DELETE,POST | `/api/v1/workspace/ideas/stats` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/ideas/upload` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workspace/ideas/upload`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | PUT | `/api/v1/workspace/ideas/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/attachments/analyze` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/ideas/{var}/attachments`),
  analyzeIdeaAttachments: (ideaId: string) =>
    request<{ idea_id: string; analyses: any[] }>(`/api/v1/workspace/ideas/{var}/attachments/analyze`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/ideas/{var}/submit-pipeline` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/ideas/{var}/submit-pipeline`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/ideas/{var}`),
  updateIdea: (ideaId: string, data: { content?: string; category?: string; priority?: string | number; tags?: string[] }) =>
    request<any>(`/api/v1/workspace/ideas/{var}`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/ideas/{var}`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/ideas{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/notifications/{var}/unread-count` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/notifications/{var}/unread-count`),

  // Idea attachments
  uploadIdeaFile: (file: File, ideaId?: string) => {
    const form = new FormData();
    form.append(` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST,PUT | `/api/v1/workspace/prompts` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST,PUT | `/api/v1/workspace/prompts", {
      method: "POST",
      body: JSON.stringify({ name, category, content }),
    }),
  updatePromptTemplate: (templateId: string, content: string) =>
    request<any>(` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST,PUT | `/api/v1/workspace/prompts${category ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/prompts/{var}/resolve` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/prompts/{var}/resolve`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/prompts/{var}`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/prompts{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | POST | `/api/v1/workspace/sessions${status ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/sessions/{var}` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/sessions/{var}/messages` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/sessions/{var}/messages${limit ? ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/sessions/{var}/messages{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/sessions/{var}`),
  sendChatMessage: (sessionId: string, content: string, modelId?: string) =>
    request<{ user_message: any; assistant_message: any }>(`/api/v1/workspace/sessions/{var}/messages`, {
      method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/sessions{var}` : ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/settings/council-members` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/settings/hierarchies` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | POST | `/api/v1/workspace/settings/keys` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/settings/keys/{var}/activate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/settings/keys/{var}/activate`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| yes | GET | `/api/v1/workspace/settings/keys/{var}/validate` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | GET | `/api/v1/workspace/settings/keys/{var}/validate`, { method: ` | `src\sylion-frontend\src\lib\api\client.ts` |
| no | PUT | `/api/v1/orchestration` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | PUT | `/api/v1/orchestration";

export const orchestrationApi = {
  // Health
  health: () => req<{ status: string }>(` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/auditor-cadence` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/auditor-cadence/trigger-now` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/council-rules` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/council-rules/simulate-vote` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | PUT | `{var}/dispatch-config` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/event-map${topicPrefix ? ` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/fixer-protocol` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/health` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | PUT | `{var}/inter-model-conversation` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/llm-judge-routing` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/llm-judge-routing/preset/{var}` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/llm-judge-routing/reset-cell` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/team-formation-rules` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST,PUT | `{var}/test-catalog/run-now` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST | `{var}/test-catalog/runs${limit ? ` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
| no | POST | `{var}/test-catalog{var}` | `src\sylion-frontend\src\lib\api\orchestration.ts` |
