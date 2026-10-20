export type MarketBar = {
  date: string;
  ticker: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  adj_close?: number | null;
  volume?: number | null;
  returns?: number | null;
};

export type MarketDataResponse = { data: MarketBar[]; count: number };
export type PortfolioResponse = {
  returns?: (number | null)[];
  cumulative_returns?: (number | null)[];
  volatility?: number | null;
  annualized_volatility?: number | null;
  sharpe_ratio?: number | null;
  max_drawdown?: number | null;
  var?: number | null;
  cvar?: number | null;
  correlation?: Record<string, Record<string, number>>;
  optimization?: {
    weights: Record<string, number>;
    expected_annual_return: number;
    annualized_volatility: number;
    sharpe_ratio: number;
  };
};
export type BacktestResponse = {
  metrics: Record<string, number | null>;
  equity: { date: string; value: number }[];
  cash: { date: string; value: number }[];
  positions: Record<string, string | number | null>[];
  returns: { date: string; value: number }[];
  cumulative_returns: { date: string; value: number }[];
  trades: Record<string, string | number | null>[];
  benchmark_equity?: { date: string; value: number }[];
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public readonly status: number | null, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal });
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      throw new ApiError(response.status, "The API returned an invalid response.");
    }
    if (!response.ok) {
      const detail = typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail?: { message?: string } }).detail?.message
        : undefined;
      throw new ApiError(response.status, detail ?? `The API returned HTTP ${response.status}.`);
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(null, error instanceof DOMException && error.name === "AbortError"
      ? "The request timed out."
      : "Unable to reach the AlphaForge API.");
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  marketData: (tickers: string[], start: string, end: string) =>
    request<MarketDataResponse>("/market-data/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers, start, end, include_returns: true }),
    }),
  portfolio: (payload: {
    asset_returns: Record<string, number[]>;
    weights?: Record<string, number>;
    risk_free_rate: number;
    periods_per_year: number;
    confidence_level: number;
    optimization: "none" | "minimum_volatility" | "maximum_sharpe";
  }) => request<PortfolioResponse>("/portfolio/analytics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  backtest: (payload: Record<string, unknown>) => request<BacktestResponse>("/backtests/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
};

export function normalizeTickers(value: string): string[] {
  return [...new Set(value.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean))];
}

export function formatMetric(value: number | null | undefined, suffix = ""): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : `${value.toFixed(2)}${suffix}`;
}
