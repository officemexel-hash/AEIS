# Playwright live-data fixtures

`src/sylion-frontend/e2e/global-setup.ts` seeds the backend before Playwright starts the e2e suite that expects real records instead of empty states.

## What it seeds

- 3 governance proposals through `/api/v1/governance/proposals` for `D0`, `D1`, and `D2` coverage
- 1 funding programme and call, then 2 funding projects and 2 CRM applications
- 1 candidate build through `/api/v1/integration/builds`
- Fallback: if build creation is unavailable, 1 deployment through `/api/v1/deployments`

## Environment

- `BACKEND_URL` is the backend origin used by global setup
- Default backend origin: `http://127.0.0.1:8000`
- Existing page/test-specific vars like `PLAYWRIGHT_TEST_API_BASE_URL` remain unchanged

## Seed marker

Every run gets a unique `seed_run_id` based on the current ISO timestamp.

The marker is propagated via:

- proposal titles and descriptions
- funding programme/call/project titles and summaries
- build `metadata.seed_run_id`
- deployment `module_id` fallback

Global setup stores a compact JSON summary in `process.env.PLAYWRIGHT_SEED_STATE` so optional fixtures can read the active seed context.

## Fixture

`e2e/fixtures/seeded-page.ts` exports a `test` fixture with `seededPage`.

Use it only for specs that need an explicit readiness check:

```ts
import { test, expect } from "./fixtures/seeded-page";

test("example", async ({ seededPage }) => {
  await seededPage.goto("/governance");
  await expect(seededPage.getByText(/proposal/i).first()).toBeVisible();
});
```

## Cleanup

No teardown is enabled by default.

Reason:

- the backend exposes create/list routes consistently for these domains
- delete routes are not consistently available across governance, funding, build, and deployment surfaces

If cleanup is added later, use `seed_run_id` as the selection marker and prefer domain-specific delete endpoints over direct database mutations.
