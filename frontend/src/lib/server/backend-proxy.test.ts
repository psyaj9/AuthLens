import { describe, expect, it } from "vitest";
import {
  buildBackendHeaders,
  buildBackendUrl,
  normalizeBackendError,
  parseQaResponse
} from "./backend-proxy";

describe("backend proxy helpers", () => {
  it("builds backend URLs from server-only configuration without double slashes", () => {
    expect(buildBackendUrl("https://api.example.test/", "/api/queries/")).toBe(
      "https://api.example.test/api/queries/"
    );
  });

  it("adds the internal token only when configured", () => {
    expect(buildBackendHeaders()).toEqual({});
    expect(buildBackendHeaders("internal-token")).toEqual({
      Authorization: "Bearer internal-token"
    });
  });

  it("normalizes backend JSON error payloads", async () => {
    const response = Response.json({ error: "Pinecone unavailable" }, { status: 502 });

    await expect(normalizeBackendError(response)).resolves.toEqual({
      error: "Pinecone unavailable",
      status: 502
    });
  });

  it("normalizes non-JSON backend error payloads", async () => {
    const response = new Response("gateway timeout", { status: 504 });

    await expect(normalizeBackendError(response)).resolves.toEqual({
      error: "gateway timeout",
      status: 504
    });
  });

  it("parses QA responses and defaults missing source documents to an empty list", () => {
    expect(parseQaResponse({ response: "Answer" })).toEqual({
      response: "Answer",
      source_documents: []
    });
  });
});
