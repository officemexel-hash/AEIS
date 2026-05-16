---
name: console-shell-builder
description: >
  Builds Next.js page shells for SYLION surface modules. Generates page.tsx,
  custom hooks, and mock fallback data following the patterns established in
  sylion-frontend.
---

# Console Shell Builder

## When to Use

- When onboarding a new SYLION module that needs a frontend page.
- When creating a new dashboard panel or admin view.
- When scaffolding a page that will later be wired to a live backend API.
- When adding a new surface module to the SYLION dashboard.

## Generated Artifacts

For a given `module_id` and `panel_name`, this skill generates:

1. **`page.tsx`** -- The Next.js page component with layout, data fetching, and mock fallback.
2. **`use{Panel}Data.ts`** -- A custom hook that fetches from the live API with automatic fallback to mock data.
3. **Mock data file** -- Static mock data matching the expected API response shape for development and demo mode.

## Inputs

| Name        | Type   | Required | Description                                                        |
|-------------|--------|----------|--------------------------------------------------------------------|
| module_id   | string | Yes      | The SYLION module identifier (e.g., `m1_roast`)                    |
| panel_name  | string | Yes      | The display name for the panel (e.g., `RoastEngine`)               |
| endpoints   | list   | Yes      | List of API endpoint objects the page will consume                  |

### Endpoint Object Structure

```json
{
  "name": "getRoastProfile",
  "method": "GET",
  "path": "/api/v1/roast/profiles/{id}",
  "response_shape": {
    "id": "string",
    "name": "string",
    "intensity": "number",
    "notes": "string[]"
  }
}
```

## Outputs

| Name      | Type   | Description                                                  |
|-----------|--------|--------------------------------------------------------------|
| files     | list   | List of created file paths with their purposes               |
| summary   | string | Human-readable summary of what was generated                  |

## Execution Steps

1. **Validate inputs** -- Confirm `module_id` exists in the module registry. Verify `panel_name` is non-empty. Validate each endpoint has `name`, `method`, `path`, and `response_shape`.
2. **Locate frontend root** -- Find the `sylion-frontend` directory. Confirm the app router structure (`app/` directory exists).
3. **Determine page path** -- Compute the page directory: `app/{module_id}/{panel_name_kebab}/page.tsx`. Convert `panel_name` to kebab-case for the URL segment.
4. **Generate page.tsx** -- Create the page component following the established pattern:
   - Import the custom hook.
   - Use `"use client"` directive where needed.
   - Render a loading skeleton while data is being fetched.
   - Render an error state if the API call fails and no mock data is available.
   - Render the main content with the fetched data.
   - Include the standard SYLION page layout wrapper.
5. **Generate hook** -- Create `use{Panel}Data.ts` in a `hooks/` subdirectory:
   - Accept endpoint parameters as hook arguments.
   - Use `fetch` or the project's API client to call the live endpoint.
   - If the API call fails (network error, 404, 5xx), fall back to mock data.
   - Return `{ data, isLoading, error, isUsingMock }`.
6. **Generate mock data** -- Create `mocks/{panel_name_kebab}.ts`:
   - Produce realistic mock data matching each endpoint's `response_shape`.
   - Export as typed constants.
   - Include a comment indicating this is auto-generated mock data.
7. **Verify build** -- Run TypeScript type-check on the generated files. Ensure no import errors.
8. **Return output** -- Emit the list of created files and a summary.

## Safety Rules

- Never overwrite an existing page.tsx without explicit confirmation. If a file exists, report the conflict and skip.
- Generated hooks must always include mock fallback so the page is functional even without a running backend.
- All generated files must pass TypeScript strict mode type-checking.
- The skill must not modify any existing files outside the newly created page directory.
- Follow the exact code style and patterns found in existing sylion-frontend pages (naming conventions, import ordering, component structure).
- Generated mock data must not contain real user data or credentials.

## Properties

- **parallel-safe**: true -- Multiple pages can be generated concurrently as long as they target different directories.
- **idempotent**: true -- Re-running with the same inputs produces identical output. Existing files are not overwritten.
