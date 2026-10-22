import { normalizeTickers } from "@/lib/api";

export const MAX_FRONTEND_TICKERS = 20;

export function parseFiniteNumber(value: string, label: string, minimum?: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || (minimum !== undefined && parsed < minimum)) {
    throw new Error(`${label} must be a valid number${minimum === undefined ? "" : ` at least ${minimum}`}.`);
  }
  return parsed;
}

export function validateDateRange(start: string, end: string): void {
  if (!start || !end || Number.isNaN(Date.parse(start)) || Number.isNaN(Date.parse(end)) || start >= end) {
    throw new Error("Enter a valid date range with an earlier start date.");
  }
  if ((Date.parse(end) - Date.parse(start)) / 86_400_000 > 3650) {
    throw new Error("The date range must not exceed 10 years.");
  }
}

export function validateTickerInput(value: string): string[] {
  const tickers = normalizeTickers(value);
  if (!tickers.length) throw new Error("Enter at least one ticker.");
  if (tickers.length > MAX_FRONTEND_TICKERS) {
    throw new Error(`Enter no more than ${MAX_FRONTEND_TICKERS} tickers.`);
  }
  return tickers;
}
