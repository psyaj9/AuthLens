import { describe, expect, it } from "vitest";

import {
  formatCaseTypeLabel,
  formatDocumentTypeLabel,
  formatScoreLabel,
  formatStatusLabel,
  nextSyntheticCaseLabel
} from "./formatters";

describe("prior-auth workspace formatters", () => {
  it("renders machine status values as staff-readable labels", () => {
    expect(formatStatusLabel("not_found")).toBe("Not found");
    expect(formatStatusLabel("prior_auth")).toBe("Prior authorization");
    expect(formatStatusLabel("ready_for_review")).toBe("Ready for review");
    expect(formatStatusLabel("needs_more_documentation")).toBe("Needs more documentation");
    expect(formatStatusLabel("exported")).toBe("Exported");
  });

  it("renders document and case type labels consistently", () => {
    expect(formatDocumentTypeLabel("payer_policy")).toBe("Payer policy");
    expect(formatDocumentTypeLabel("patient_note")).toBe("Patient note");
    expect(formatCaseTypeLabel("appeal")).toBe("Appeal");
    expect(formatCaseTypeLabel("prior_auth")).toBe("Prior authorization");
  });

  it("renders readiness scores without the awkward raw score suffix", () => {
    expect(formatScoreLabel(12)).toBe("Readiness 12/100");
    expect(formatScoreLabel(null)).toBe("No readiness score");
  });

  it("generates the next synthetic case label without duplicating the default", () => {
    expect(nextSyntheticCaseLabel(["SYN-LMRI-001", "SYN-LMRI-002"], "SYN-LMRI")).toBe("SYN-LMRI-003");
    expect(nextSyntheticCaseLabel([], "SYN-LMRI-APPEAL")).toBe("SYN-LMRI-APPEAL-001");
  });
});
