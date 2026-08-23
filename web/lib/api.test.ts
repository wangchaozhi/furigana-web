import { afterEach, describe, expect, it, vi } from "vitest";

import { annotate, getCurrentUser, setAccessToken } from "./api";

afterEach(() => {
  setAccessToken(null);
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("API client", () => {
  it("adds the access token and parses JSON responses", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "user-1", email: "user@example.com" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    setAccessToken("secret-token");

    await expect(getCurrentUser()).resolves.toEqual({ id: "user-1", email: "user@example.com" });
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer secret-token");
  });

  it("surfaces structured API errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "文本过长" }), { status: 422 }),
    );

    await expect(annotate("明日")).rejects.toThrow("文本过长");
  });

  it("aborts requests after the timeout", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));

    const rejection = expect(annotate("明日")).rejects.toThrow("请求超时");
    await vi.advanceTimersByTimeAsync(30_000);
    await rejection;
  });
});
