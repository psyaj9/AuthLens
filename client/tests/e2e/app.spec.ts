import { expect, test } from "@playwright/test";

test.describe("PriorAuth Evidence Copilot", () => {
  test("renders demo login as the first screen", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "PriorAuth Evidence Copilot" })
    ).toBeVisible();
    await expect(
      page.getByText("Synthetic or de-identified documents only.").first()
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveValue("coordinator@demo.authlens.test");
    await expect(page.getByLabel("Password")).toHaveValue("demo-password");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("keeps demo login usable on mobile", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "PriorAuth Evidence Copilot" })
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Sign in" })
    ).toBeVisible();
  });
});
