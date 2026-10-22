import { describe, expect, it } from "vitest";
import { alignReturns } from "@/lib/portfolio";

describe("portfolio return alignment", () => {
  it("uses adjusted close for consecutive shared intervals", () => {
    const result = alignReturns(
      [
        { date: "2025-01-01", ticker: "A", close: 100, adj_close: 100 },
        { date: "2025-01-02", ticker: "A", close: 110, adj_close: 105 },
        { date: "2025-01-03", ticker: "A", close: 120, adj_close: 110 },
        { date: "2025-01-01", ticker: "B", close: 200, adj_close: 200 },
        { date: "2025-01-02", ticker: "B", close: 210, adj_close: 210 },
        { date: "2025-01-03", ticker: "B", close: 220, adj_close: 220 },
      ],
      ["A", "B"],
    );

    expect(result.priceField).toBe("adj_close");
    expect(result.dates).toEqual(["2025-01-02", "2025-01-03"]);
    expect(result.values.A[0]).toBeCloseTo(0.05);
    expect(result.values.B[0]).toBeCloseTo(0.05);
    expect(result.dropped).toBe(0);
  });

  it("falls back consistently to close when adjusted close is unavailable", () => {
    const result = alignReturns(
      [
        { date: "2025-01-01", ticker: "A", close: 100 },
        { date: "2025-01-02", ticker: "A", close: 110 },
        { date: "2025-01-01", ticker: "B", close: 200, adj_close: null },
        { date: "2025-01-02", ticker: "B", close: 220, adj_close: null },
      ],
      ["A", "B"],
    );
    expect(result.priceField).toBe("close");
    expect(result.values.A[0]).toBeCloseTo(0.1);
  });

  it("rejects insufficient complete observations", () => {
    expect(() => alignReturns([
      { date: "2025-01-01", ticker: "A", close: 100 },
      { date: "2025-01-01", ticker: "B", close: 200 },
    ], ["A", "B"])).toThrow("consecutive complete observations");
  });

  it("rejects a multi-session interval caused by differing trading calendars", () => {
    expect(() => alignReturns([
      { date: "2025-01-01", ticker: "A", close: 100 },
      { date: "2025-01-02", ticker: "A", close: 110 },
      { date: "2025-01-03", ticker: "A", close: 120 },
      { date: "2025-01-01", ticker: "B", close: 200 },
      { date: "2025-01-03", ticker: "B", close: 220 },
    ], ["A", "B"])).toThrow("consecutive complete observations");
  });
});
