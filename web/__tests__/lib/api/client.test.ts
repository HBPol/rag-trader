import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../../../src/lib/api/client";

describe("apiFetch", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("throws on non-ok responses by default", async () => {
    const mockResponse = new Response(
      JSON.stringify({ message: "Server exploded" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );

    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(apiFetch("/test")).rejects.toThrow(/status 500/);
  });

  it("rejects with an error when throwOnError is false", async () => {
    const mockResponse = new Response(
      JSON.stringify({ message: "Not Found" }),
      {
        status: 404,
        headers: { "Content-Type": "application/json" },
      },
    );

    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(apiFetch("/test", { throwOnError: false })).rejects.toThrow(
      /status 404/,
    );
  });
});
