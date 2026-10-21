import { afterEach, describe, expect, it, vi } from "vitest";

describe("frontend API helpers", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("normalizes and de-duplicates ticker symbols", async () => {
    const { normalizeTickers } = await import("@/lib/api");
    expect(normalizeTickers(" aapl, MSFT, AAPL ")).toEqual(["AAPL", "MSFT"]);
  });

  it("formats absent and numeric metrics safely", async () => {
    const { formatMetric } = await import("@/lib/api");
    expect(formatMetric(null)).toBe("—");
    expect(formatMetric(0.1234, "%")).toBe("0.12%");
  });

  it("uses the configured production URL as the API base", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://alphaforge-0rbn.onrender.com");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));

    const { api, getApiBaseUrl } = await import("@/lib/api");

    expect(getApiBaseUrl()).toBe("https://alphaforge-0rbn.onrender.com");
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledWith(
      "https://alphaforge-0rbn.onrender.com/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("falls back to the local development API URL when no production URL is configured", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));

    const { api, getApiBaseUrl } = await import("@/lib/api");

    expect(getApiBaseUrl()).toBe("http://127.0.0.1:8000");
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});
