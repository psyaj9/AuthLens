import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  approveDraft: vi.fn(),
  archiveCase: vi.fn(),
  createAppealDraft: vi.fn(),
  createCase: vi.fn(),
  createLetterExport: vi.fn(),
  createPacketExport: vi.fn(),
  createPriorAuthDraft: vi.fn(),
  createReadinessExport: vi.fn(),
  deleteDocument: vi.fn(),
  extractCriteria: vi.fn(),
  forgotPassword: vi.fn(),
  generateReadinessReport: vi.fn(),
  getCurrentUser: vi.fn(),
  getLatestReadinessReport: vi.fn(),
  listCaseAudit: vi.fn(),
  listCaseDocuments: vi.fn(),
  listCases: vi.fn(),
  listCriteria: vi.fn(),
  listDrafts: vi.fn(),
  listEvidence: vi.fn(),
  listOrganizationAudit: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  matchEvidence: vi.fn(),
  overrideEvidenceMatch: vi.fn(),
  registerUser: vi.fn(),
  resetPassword: vi.fn(),
  updateCriterion: vi.fn(),
  updateDraft: vi.fn(),
  uploadCaseDocument: vi.fn(),
  verifyDraftCitations: vi.fn()
}));

vi.mock("@/lib/api/client", () => apiMocks);

import { PriorAuthWorkspace } from "./PriorAuthWorkspace";

describe("PriorAuthWorkspace auth panel", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.getCurrentUser.mockResolvedValue(null);
    apiMocks.listCases.mockResolvedValue([]);
    apiMocks.registerUser.mockResolvedValue({
      user: {
        id: "user_123",
        email: "atihkash@example.test",
        name: "Athikash",
        organization: {
          id: "org_123",
          name: "psyaj9",
          plan: "demo"
        },
        role: "admin"
      }
    });
  });

  it("requires matching registration passwords and can reveal password fields", async () => {
    const user = userEvent.setup();

    render(<PriorAuthWorkspace />);

    await user.click(await screen.findByRole("button", { name: "Create account" }));

    const password = screen.getByLabelText("Password");
    const confirmPassword = screen.getByLabelText("Confirm password");

    expect(password).toHaveAttribute("type", "password");
    expect(confirmPassword).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Show password" }));

    expect(password).toHaveAttribute("type", "text");
    expect(confirmPassword).toHaveAttribute("type", "text");

    await user.type(screen.getByLabelText("Name"), "Athikash");
    await user.type(screen.getByLabelText("Organization"), "psyaj9");
    await user.type(screen.getByLabelText("Email"), "atihkash@example.test");
    await user.type(password, "strong-password");
    await user.type(confirmPassword, "different-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(apiMocks.registerUser).not.toHaveBeenCalled();

    await user.clear(confirmPassword);
    await user.type(confirmPassword, "strong-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(apiMocks.registerUser).toHaveBeenCalledWith({
      email: "atihkash@example.test",
      name: "Athikash",
      organization_name: "psyaj9",
      password: "strong-password"
    });
  });
});
