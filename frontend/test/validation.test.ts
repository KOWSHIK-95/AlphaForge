import { describe, expect, it } from "vitest";
import { parseFiniteNumber, validateDateRange, validateTickerInput } from "@/lib/validation";

describe("frontend request validation", () => {
  it("rejects non-finite numeric input and oversized universes", () => {
    expect(() => parseFiniteNumber("not-a-number", "Capital")).toThrow("Capital");
    expect(() => validateTickerInput(Array.from({ length: 21 }, (_, index) => `T${index}`).join(","))).toThrow("no more than");
  });

  it("rejects invalid and excessively long date ranges", () => {
    expect(() => validateDateRange("2025-02-01", "2025-01-01")).toThrow("valid date range");
    expect(() => validateDateRange("2000-01-01", "2025-01-01")).toThrow("10 years");
  });
});
