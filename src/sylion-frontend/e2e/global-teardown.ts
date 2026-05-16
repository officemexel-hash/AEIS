// F-013 follow-up (Kimi review): teardown for Playwright seeded data.
// Removes records tagged with the seed_run_id set by global-setup.ts so
// that CI runs do not leave accumulating test fixtures in the backend DB.

import { request } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const SEED_FILE = path.resolve(__dirname, "..", ".playwright-seed.json");

async function readSeedRunId(): Promise<string | null> {
  try {
    const raw = fs.readFileSync(SEED_FILE, "utf-8");
    const parsed = JSON.parse(raw) as { seed_run_id?: string };
    return parsed.seed_run_id ?? null;
  } catch {
    return null;
  }
}

async function deleteIfExists(url: string): Promise<boolean> {
  const ctx = await request.newContext();
  try {
    const r = await ctx.delete(url);
    return r.ok() || r.status() === 404;
  } catch {
    return false;
  } finally {
    await ctx.dispose();
  }
}

export default async function globalTeardown(): Promise<void> {
  const seedRunId = await readSeedRunId();
  if (!seedRunId) {
    return;
  }
  // Best-effort cleanup of seed records. Endpoints with /by-seed-run/{id}
  // are documented but optional; missing endpoint = silent skip (404 OK).
  await deleteIfExists(`${BACKEND_URL}/api/v1/governance/proposals/by-seed-run/${seedRunId}`);
  await deleteIfExists(`${BACKEND_URL}/api/v1/funding/applications/by-seed-run/${seedRunId}`);
  await deleteIfExists(`${BACKEND_URL}/api/v1/integration/builds/by-seed-run/${seedRunId}`);
  // Remove local seed marker file so next run starts fresh.
  try {
    fs.unlinkSync(SEED_FILE);
  } catch {
    // ignore
  }
}
