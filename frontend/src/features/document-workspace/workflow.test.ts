import { describe, expect, it } from "vitest";
import { createDocumentItems, formatFileSize, isSupportedPdf } from "./workflow";

describe("document workspace workflow helpers", () => {
  it("keeps only supported PDF files", () => {
    const pdf = new File(["pdf"], "synthetic.pdf", { type: "application/pdf" });
    const namedPdf = new File(["pdf"], "deidentified.PDF", { type: "" });
    const text = new File(["text"], "notes.txt", { type: "text/plain" });

    expect(isSupportedPdf(pdf)).toBe(true);
    expect(isSupportedPdf(namedPdf)).toBe(true);
    expect(isSupportedPdf(text)).toBe(false);
  });

  it("creates stable document items for display", () => {
    const file = new File(["12345"], "synthetic.pdf", { type: "application/pdf" });

    expect(createDocumentItems([file], "queued")).toEqual([
      expect.objectContaining({
        name: "synthetic.pdf",
        size: 5,
        status: "queued"
      })
    ]);
  });

  it("formats file sizes for compact panel display", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1024)).toBe("1 KB");
    expect(formatFileSize(1_048_576)).toBe("1 MB");
  });
});
