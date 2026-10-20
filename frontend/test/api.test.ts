import { describe, expect, it, vi } from "vitest";
import { normalizeTickers, formatMetric } from "@/lib/api";

describe("frontend API helpers", () => {
  it("normalizes and de-duplicates ticker symbols", () => {
    expect(normalizeTickers(" aapl, MSFT, AAPL ")).toEqual(["AAPL", "MSFT"]);
  });
  it("formats absent and numeric metrics safely", () => {
    expect(formatMetric(null)).toBe("—");
    expect(formatMetric(0.1234, "%")).toBe("0.12%");
  });
  it("uses the configured fetch boundary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    const { api } = await import("@/lib/api");
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/health"), expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });
});
