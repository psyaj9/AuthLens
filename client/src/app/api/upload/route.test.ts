import { describe, expect, it, vi } from "vitest";

describe("POST /api/upload", () => {
  it("uses the Node.js runtime for multipart uploads", async () => {
    const route = await import("./route");

    expect(route.runtime).toBe("nodejs");
  });

  it("proxies uploaded files to the FastAPI uploaded_files field", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test/";
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ accepted: true }));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["pdf"], "synthetic.pdf", { type: "application/pdf" });
    const formData = new FormData();
    formData.append("uploaded_files", file);

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/upload", {
        method: "POST",
        body: formData
      })
    );

    await expect(response.json()).resolves.toEqual({ accepted: true });
    expect(response.status).toBe(200);
    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example.test/api/upload_pdf/",
      expect.objectContaining({ method: "POST" })
    );
    expect(init.body.getAll("uploaded_files")).toHaveLength(1);
  });

  it("rejects requests without files", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/upload", {
        method: "POST",
        body: new FormData()
      })
    );

    await expect(response.json()).resolves.toEqual({
      error: "Select at least one PDF before uploading."
    });
    expect(response.status).toBe(400);
  });

  it("returns a generic error when the backend upload fetch fails", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("connect ECONNREFUSED backend.example.test"))
    );

    const file = new File(["pdf"], "synthetic.pdf", { type: "application/pdf" });
    const formData = new FormData();
    formData.append("uploaded_files", file);

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/upload", {
        method: "POST",
        body: formData
      })
    );

    await expect(response.json()).resolves.toEqual({
      error: "AuthLens could not upload documents."
    });
    expect(response.status).toBe(502);
  });
});
