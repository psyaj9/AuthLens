import { expect, test } from "@playwright/test";

test.describe("PriorAuth Evidence Copilot", () => {
  test("renders account login as the first screen without static credentials", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "PriorAuth Evidence Copilot" })
    ).toBeVisible();
    await expect(
      page.getByText("Synthetic or de-identified documents only.").first()
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveValue("");
    await expect(page.getByLabel("Password")).toHaveValue("");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Forgot password" })).toBeVisible();
  });

  test("keeps account login usable on mobile", async ({ page }) => {
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
