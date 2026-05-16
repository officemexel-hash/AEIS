import { expect, test, type Page } from "@playwright/test";

const HEALTH_PAYLOAD = {
  status: "ok",
  version: "3.5.0",
  modules: 65,
  endpoints: 349,
  db_mode: "sqlite",
};

const TOPOLOGY_PAYLOAD = {
  variants: [
    {
      variant: "hybrid_stack",
      server_count: 3,
      servers: [
        { name: "edge-1", role: "edge", components: ["api", "ui"] },
        { name: "worker-1", role: "worker", components: ["builder"] },
        { name: "audit-1", role: "audit", components: ["validator"] },
      ],
    },
  ],
};

async function mockDeploySurface(page: Page, summaryPayload: unknown) {
  await page.route("**/health", async (route) => {
    await route.fulfill({ json: HEALTH_PAYLOAD });
  });

  await page.route("**/api/v1/deploy/summary", async (route) => {
    await route.fulfill({ json: summaryPayload });
  });

  await page.route("**/api/v1/deploy/topologies", async (route) => {
    await route.fulfill({ json: TOPOLOGY_PAYLOAD });
  });
}

test.describe("deploy surface", () => {
  test("shows an honest empty state when no deployable artifact is ready", async ({ page }) => {
    await mockDeploySurface(page, {
      surface_status: "live",
      stats: {
        tracked_projects: 0,
        ready_projects: 0,
        pending_projects: 0,
        active_deployments: 0,
      },
      ready_projects: [],
      pending_projects: [],
      active_deployments: [],
    });

    await page.goto("/deploy", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Deploy", exact: true })).toBeVisible();
    await expect(page.getByText("No deployable artifacts are ready yet.")).toBeVisible();
    await expect(page.getByText("Helper templates generated on demand.")).toBeVisible();
    await expect(page.getByText(/github\.com\/example|example\.com\/.+\.git/)).toHaveCount(0);
  });

  test("renders real ready deployments and rollout queue data", async ({ page }) => {
    await mockDeploySurface(page, {
      surface_status: "live",
      stats: {
        tracked_projects: 2,
        ready_projects: 1,
        pending_projects: 1,
        active_deployments: 1,
      },
      ready_projects: [
        {
          project_id: "proj_ready_001",
          title: "Operator Console",
          project_kind: "application",
          status: "completed",
          phase: "broadcast",
          launch_status: "completed",
          launched_at: 1767225600,
          artifact: {
            key: "artifact",
            label: "artifact",
            path: "/tmp/results/proj_ready_001/artifacts/app.py",
            exists: true,
            size_bytes: 4096,
            sha256: "1234567890abcdef1234567890abcdef",
            format: "py",
          },
          bundle: {
            status: "ready",
            files: [
              { key: "docker_compose", label: "docker-compose.yml", path: "/tmp/results/proj_ready_001/deploy/docker-compose.yml", exists: true, size_bytes: 512 },
              { key: "deploy_ps1", label: "deploy.local.ps1", path: "/tmp/results/proj_ready_001/deploy/deploy.local.ps1", exists: true, size_bytes: 128 },
              { key: "deploy_sh", label: "deploy.local.sh", path: "/tmp/results/proj_ready_001/deploy/deploy.local.sh", exists: true, size_bytes: 128 },
              { key: "terraform_tfvars", label: "terraform.tfvars.json", path: "/tmp/results/proj_ready_001/deploy/terraform.tfvars.json", exists: true, size_bytes: 128 },
              { key: "ansible_inventory", label: "ansible_inventory.ini", path: "/tmp/results/proj_ready_001/deploy/ansible_inventory.ini", exists: true, size_bytes: 128 },
              { key: "plan_md", label: "PLAN.md", path: "/tmp/results/proj_ready_001/deploy/PLAN.md", exists: true, size_bytes: 256 },
            ],
          },
          validation: { success: true, stages: { smoke: true } },
          audit: { result_count: 4 },
          module_output_count: 3,
          deployment_mode: "hybrid",
          provisioning_mode: "plan_and_generate",
          pending_question_count: 0,
          reason: "",
          recommended_action: "",
        },
      ],
      pending_projects: [
        {
          project_id: "proj_pending_001",
          title: "Pending Build",
          project_kind: "application",
          status: "running",
          phase: "build",
          launch_status: "running",
          launched_at: 1767225700,
          artifact: { key: "artifact", label: "artifact", path: "", exists: false, size_bytes: 0, sha256: "", format: "" },
          bundle: { status: "missing", files: [] },
          validation: { success: false, stages: {} },
          audit: { result_count: 0 },
          module_output_count: 0,
          deployment_mode: "local_docker",
          provisioning_mode: "plan_and_generate",
          pending_question_count: 0,
          reason: "Pipeline execution is still running and has not recorded an artifact yet.",
          recommended_action: "Wait for the pipeline run to finish before attempting deployment.",
        },
      ],
      active_deployments: [
        {
          deployment_id: "dep_001",
          module_id: "core.operator_panel",
          from_stage: "draft",
          to_stage: "build",
          strategy: "canary",
          status: "pending",
          started_at: 1767225800,
          step_summary: {
            total: 5,
            completed: 0,
            in_progress: 0,
            pending: 5,
            failed: 0,
            current_step: "prepare",
          },
        },
      ],
    });

    await page.goto("/deploy", { waitUntil: "networkidle" });

    await expect(page.getByText("Operator Console")).toBeVisible();
    await expect(page.getByText("/tmp/results/proj_ready_001/artifacts/app.py")).toBeVisible();
    await expect(page.getByText("deploy.local.ps1", { exact: true })).toBeVisible();
    await expect(page.getByText("Pending Build")).toBeVisible();
    await expect(page.getByText("core.operator_panel")).toBeVisible();
    await expect(page.getByText(/placeholder targets or fake repository URLs/i)).toBeVisible();
  });
});
