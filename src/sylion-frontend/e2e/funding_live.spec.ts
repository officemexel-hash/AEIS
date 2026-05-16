import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

test.describe("funding live flow", () => {
  test("runs the funding autopilot from company profile to submitted receipt", async ({ page, request }) => {
    test.setTimeout(120_000);

    const suffix = Date.now().toString().slice(-6);
    const programmeName = `FENG QA ${suffix}`;
    const callTitle = `AI Efficiency ${suffix}`;
    const callCode = `FENG-QA-${suffix}`;
    const portalUrl = `https://portal.example.test/${suffix}`;
    const submissionRef = `PORTAL-${suffix}`;
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];
    let createdCallId = "";
    let createdApplicationId = "";
    let createdSessionId = "";

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    page.on("response", (response) => {
      if (response.status() >= 400) {
        const url = response.url();
        if (url.startsWith(BASE_URL) || url.startsWith(API_BASE_URL)) {
          networkErrors.push(`${response.request().method()} ${response.status()} ${url}`);
        }
      }
    });

    await page.goto(`${BASE_URL}/funding`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Grant pipeline from company profile to approval-gated submission" })).toBeVisible();
    await expect(page.getByText("catalog_planned")).toHaveCount(0);

    await page.getByRole("textbox", { name: "Legal company name" }).fill("Razor Systems");
    await page.getByRole("textbox", { name: "Tax ID / NIP" }).fill("1234567890");
    await page.getByRole("textbox", { name: "KRS / CEIDG" }).fill("KRS0001");
    await page.getByRole("textbox", { name: "Legal form" }).fill("sp. z o.o.");
    await page.getByRole("textbox", { name: "Region" }).fill("Mazowieckie");
    await page.getByRole("textbox", { name: "City" }).fill("Warsaw");
    await page.getByRole("textbox", { name: "SME / large" }).fill("SME");
    await page.getByRole("spinbutton").nth(0).fill("24");
    await page.getByRole("spinbutton").nth(1).fill("4200000");
    await page.getByRole("spinbutton").nth(2).fill("650000");
    await page.getByRole("textbox", { name: "Export markets, comma-separated" }).fill("Germany, Poland");
    await page.getByRole("textbox", { name: "Technologies, comma-separated" }).fill("AI, Computer Vision, IoT");
    await page.getByRole("textbox", { name: "Products, comma-separated" }).fill("Industrial monitoring platform");
    await page.getByRole("textbox", { name: "Services, comma-separated" }).fill("Predictive maintenance");
    await page.getByRole("textbox", { name: "Team competencies, comma-separated" }).fill("ML engineering, Embedded systems");
    await page.getByRole("textbox", { name: "Strategic goals, comma-separated" }).fill("energy efficiency, automation, export");
    await page.getByRole("textbox", { name: "Representative name" }).fill("Jan Kowalski");
    await page.getByRole("textbox", { name: "Representative email" }).fill("jan@example.com");
    await page.getByRole("button", { name: "Save profile" }).click();

    for (const docType of [
      "financial_statement",
      "tax_clearance",
      "social_security_clearance",
      "incorporation_document",
    ]) {
      await page.getByRole("textbox", { name: "Document type" }).fill(docType);
      await page.getByRole("textbox", { name: "Filename" }).fill(`${docType}-${suffix}.pdf`);
      await page.getByRole("textbox", { name: "Storage path" }).fill(`C:/docs/${docType}-${suffix}.pdf`);
      await page.getByRole("button", { name: "Add document" }).click();
    }

    await page.getByRole("tab", { name: "Calls" }).click();
    await expect(page.getByText("Live manual intake")).toBeVisible();
    await page.getByRole("textbox", { name: "Programme name" }).fill(programmeName);
    await page.getByRole("textbox", { name: "Institution" }).fill("PARP");
    await page.getByRole("textbox", { name: "Programme summary" }).fill("Support for digital manufacturing and AI deployment.");
    await page.getByRole("button", { name: "Create programme" }).click();
    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/funding/programmes`);
        const payload = await response.json();
        return payload.programmes.some((item: Record<string, unknown>) => item.name === programmeName);
      })
      .toBeTruthy();

    await page.getByRole("combobox").first().selectOption({ label: programmeName });
    await page.getByRole("textbox", { name: "Call title" }).fill(callTitle);
    await page.getByRole("textbox", { name: "Call code" }).fill(callCode);
    await page.getByRole("textbox", { name: "Portal URL" }).fill(portalUrl);
    await page.getByRole("textbox", { name: "Closing date (YYYY-MM-DD)" }).fill("2027-06-30");
    await page.getByRole("button", { name: "Create call" }).click();
    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/funding/calls`);
        const payload = await response.json();
        const match = payload.calls.find((item: Record<string, unknown>) => item.code === callCode) as
          | Record<string, unknown>
          | undefined;
        return String(match?.call_id ?? "");
      })
      .not.toBe("");
    const callsResponse = await request.get(`${API_BASE_URL}/api/v1/funding/calls`);
    const callsPayload = await callsResponse.json();
    createdCallId = String(
      (callsPayload.calls.find((item: Record<string, unknown>) => item.code === callCode) as Record<string, unknown>)
        .call_id,
    );

    await page.getByRole("tab", { name: "Ideas" }).click();
    await page.getByRole("button", { name: "Generate ideas" }).click();
    await expect(page.getByRole("button", { name: "Convert to project" }).first()).toBeVisible();
    await page.getByRole("button", { name: "Convert to project" }).first().click();

    await page.getByRole("tab", { name: "Matching" }).click();
    await page.getByRole("button", { name: "Run matching" }).click();
    await expect(page.getByText("Grant Probability Score")).toBeVisible();

    await page.getByPlaceholder("Partner name").fill(`Warsaw Tech Lab ${suffix}`);
    await page.getByPlaceholder("Partner type").fill("research_institute");
    await page.getByPlaceholder("Country").fill("Poland");
    await page.getByPlaceholder("Expertise, comma-separated").fill("AI, energy efficiency, embedded systems");
    await page.getByPlaceholder("Grant track record").fill("6");
    await page.getByPlaceholder("Contact email").fill(`lab-${suffix}@example.com`);
    await page.getByRole("button", { name: "Add candidate" }).click();
    await page.getByRole("button", { name: "Shortlist" }).click();
    await page.getByRole("button", { name: "Generate outreach" }).click();
    await expect(page.getByText(/Score \d+%/).first()).toBeVisible();

    await page.getByRole("tab", { name: "Applications" }).click();
    await page.getByRole("button", { name: "Create application" }).click();
    await expect
      .poll(async () => {
        const applicationsResponse = await request.get(`${API_BASE_URL}/api/v1/funding/crm/applications?company_id=default`);
        const applicationsPayload = await applicationsResponse.json();
        const match = applicationsPayload.applications.find(
          (item: Record<string, unknown>) => item.call_id === createdCallId,
        ) as Record<string, unknown> | undefined;
        return String(match?.application_id ?? "");
      })
      .not.toBe("");
    const createdApplicationsResponse = await request.get(`${API_BASE_URL}/api/v1/funding/crm/applications?company_id=default`);
    const createdApplicationsPayload = await createdApplicationsResponse.json();
    createdApplicationId = String(
      (
        createdApplicationsPayload.applications.find(
          (item: Record<string, unknown>) => item.call_id === createdCallId,
        ) as Record<string, unknown>
      ).application_id,
    );
    await page.getByRole("button", { name: "Review" }).click();
    await page.getByRole("button", { name: "Export" }).click();
    await expect
      .poll(async () => {
        const applicationsResponse = await request.get(
          `${API_BASE_URL}/api/v1/funding/crm/applications?company_id=default`,
        );
        const applicationsPayload = await applicationsResponse.json();
        const targetApplication = applicationsPayload.applications.find(
          (item: Record<string, unknown>) => item.application_id === createdApplicationId,
        ) as Record<string, unknown> | undefined;
        if (!targetApplication) {
          return "missing";
        }
        const docsResponse = await request.get(
          `${API_BASE_URL}/api/v1/funding/application/${encodeURIComponent(createdApplicationId)}/documents`,
        );
        const docsPayload = await docsResponse.json();
        const exportEntries = Object.keys((targetApplication.export_json as Record<string, unknown> | undefined) ?? {});
        return JSON.stringify({
          status: targetApplication.status,
          missingDocuments: docsPayload.missing_documents,
          exportCount: exportEntries.length,
        });
      })
      .toContain("\"missingDocuments\":[]");

    await page.getByRole("tab", { name: "Submission & CRM" }).click();
    await page.getByPlaceholder("Portal URL").fill(portalUrl);
    await page.getByRole("button", { name: "Prepare submission" }).click();
    await expect
      .poll(async () => {
        const sessionsResponse = await request.get(
          `${API_BASE_URL}/api/v1/funding/submission/sessions?application_id=${encodeURIComponent(createdApplicationId)}`,
        );
        const sessionsPayload = await sessionsResponse.json();
        return String((sessionsPayload.sessions[0] as Record<string, unknown> | undefined)?.session_id ?? "");
      })
      .not.toBe("");
    const createdSessionsResponse = await request.get(
      `${API_BASE_URL}/api/v1/funding/submission/sessions?application_id=${encodeURIComponent(createdApplicationId)}`,
    );
    const createdSessionsPayload = await createdSessionsResponse.json();
    createdSessionId = String((createdSessionsPayload.sessions[0] as Record<string, unknown>).session_id);
    await page.getByRole("button", { name: "Fill mapping" }).click();
    await page.getByRole("button", { name: "Save draft" }).click();
    await page.getByRole("button", { name: "Request approval" }).click();
    await expect(page.getByText("Approval request is pending. Enter the portal reference to record the final submit.")).toBeVisible();
    await page.getByPlaceholder("Portal submission reference").fill(submissionRef);
    await page.getByRole("button", { name: "Finalize submit record" }).click();

    await expect
      .poll(async () => {
        const applicationsResponse = await request.get(`${API_BASE_URL}/api/v1/funding/crm/applications?company_id=default`);
        const applicationsPayload = await applicationsResponse.json();
        const targetApplication = applicationsPayload.applications.find(
          (item: Record<string, unknown>) => item.application_id === createdApplicationId,
        ) as Record<string, unknown> | undefined;
        return String(targetApplication?.status ?? "missing");
      })
      .toBe("submitted");

    await expect
      .poll(async () => {
        const sessionsResponse = await request.get(
          `${API_BASE_URL}/api/v1/funding/submission/sessions?application_id=${encodeURIComponent(createdApplicationId)}`,
        );
        const sessionsPayload = await sessionsResponse.json();
        const targetSession = sessionsPayload.sessions.find(
          (item: Record<string, unknown>) => item.session_id === createdSessionId,
        ) as Record<string, unknown> | undefined;
        return String(targetSession?.status ?? "missing");
      })
      .toBe("submitted");

    const receiptResponse = await request.get(
      `${API_BASE_URL}/api/v1/funding/submission/receipt?session_id=${encodeURIComponent(createdSessionId)}`,
    );
    const receiptPayload = await receiptResponse.json();
    expect(receiptPayload.receipt.portal_submission_reference).toBe(submissionRef);
    expect(networkErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
