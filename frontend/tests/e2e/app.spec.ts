import { expect, test } from "@playwright/test";

test.describe("AuthLens workspace", () => {
  test("renders the app workspace as the first screen", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "AuthLens" })).toBeVisible();
    await expect(
      page.getByText("Synthetic or de-identified PDFs only.").first()
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Sources & status" })
    ).toBeVisible();
    await expect(page.getByLabel("Question")).toBeVisible();
  });

  test("keeps core panels available on mobile", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Sources & status" })
    ).toBeVisible();
  });
});
