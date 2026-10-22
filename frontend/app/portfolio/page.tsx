"use client";

import { useState } from "react";
import { Chart } from "@/components/Chart";
import { Card, Field, inputClass, Metric, Notice, PageIntro } from "@/components/Ui";
import { api, ApiError, formatMetric } from "@/lib/api";
import { alignReturns } from "@/lib/portfolio";
import { parseFiniteNumber, validateDateRange, validateTickerInput } from "@/lib/validation";

export default function Portfolio() {
  const [tickerText, setTickerText] = useState("AAPL, MSFT");
  const [weightsText, setWeightsText] = useState("0.5, 0.5");
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [optimization, setOptimization] = useState<"none" | "minimum_volatility" | "maximum_sharpe">("none");
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.portfolio>> | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setResult(null);
    setMessage("");
    try {
      const tickers = validateTickerInput(tickerText);
      validateDateRange(start, end);
      const weights = weightsText.split(",").map((value) => parseFiniteNumber(value.trim(), "Weights"));
      if (optimization === "none" && (weights.length !== tickers.length || Math.abs(weights.reduce((sum, value) => sum + value, 0) - 1) > 1e-8)) {
        throw new Error("Provide matching weights that sum to 1.0.");
      }
      setState("loading");
      const market = await api.marketData(tickers, start, end);
      const aligned = alignReturns(market.data, tickers);
      const allocation = Object.fromEntries(tickers.map((ticker, index) => [ticker, weights[index]]));
      const nextResult = await api.portfolio({
        asset_returns: aligned.values,
        weights: optimization === "none" ? allocation : undefined,
        risk_free_rate: 0,
        periods_per_year: 252,
        confidence_level: 0.95,
        optimization,
      });
      setResult(nextResult);
      setMessage(`${aligned.dropped ? `${aligned.dropped} non-consecutive intervals excluded; ` : ""}Using ${aligned.priceField === "adj_close" ? "adjusted close" : "close"} prices across ${aligned.dates.length} common observations.`);
      setState("idle");
    } catch (error) {
      setState("error");
      setMessage(error instanceof ApiError || error instanceof Error ? error.message : "Unable to calculate portfolio analytics.");
    }
  }

  const allocation = result?.optimization?.weights ?? Object.fromEntries(
    tickerText.split(",").map((ticker, index) => [ticker.trim().toUpperCase(), Number(weightsText.split(",")[index])]),
  );
  const lineData = result?.cumulative_returns
    ? [{ x: result.cumulative_returns.map((_, index) => index + 1), y: result.cumulative_returns, type: "scatter", mode: "lines", name: "Cumulative return", line: { color: "#76d6a1", width: 2 } } as const]
    : [];

  return <><PageIntro eyebrow="Portfolio analysis" title="Make risk visible." description="Prices are converted to consecutive per-asset returns, then aligned only where every asset shares the same observation interval. Adjusted close is preferred for total-return analytics." /><div className="grid gap-5 xl:grid-cols-[280px_1fr]"><Card className="h-fit p-5"><form onSubmit={submit} className="space-y-5"><Field label="Assets"><input className={inputClass} value={tickerText} onChange={(event) => setTickerText(event.target.value)} /></Field><Field label="Weights" hint="Same order as assets; must sum to 1.0"><input className={inputClass} inputMode="decimal" value={weightsText} onChange={(event) => setWeightsText(event.target.value)} /></Field><Field label="Start date"><input className={inputClass} type="date" value={start} onChange={(event) => setStart(event.target.value)} /></Field><Field label="End date (exclusive)"><input className={inputClass} type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></Field><Field label="Optimization"><select className={inputClass} value={optimization} onChange={(event) => setOptimization(event.target.value as typeof optimization)}><option value="none">Use supplied weights</option><option value="minimum_volatility">Minimum volatility</option><option value="maximum_sharpe">Maximum Sharpe</option></select></Field><button className="w-full rounded-lg bg-signal px-4 py-2.5 text-sm font-semibold text-ink disabled:opacity-50" disabled={state === "loading"}>{state === "loading" ? "Calculating…" : "Run analysis"}</button></form>{state === "error" && <div className="mt-4"><Notice>{message}</Notice></div>}{state === "idle" && message && <div className="mt-4"><Notice tone="info">{message}</Notice></div>}</Card><div className="space-y-5">{result ? <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Annualized volatility" value={formatMetric(result.annualized_volatility)} /><Metric label="Sharpe ratio" value={formatMetric(result.sharpe_ratio)} /><Metric label="Maximum drawdown" value={formatMetric(result.max_drawdown)} tone="negative" /><Metric label="Historical CVaR" value={formatMetric(result.cvar)} /></div><Card className="p-3"><Chart title="Cumulative return" data={lineData} /></Card><div className="grid gap-5 lg:grid-cols-2"><Card className="p-5"><h2 className="font-semibold">Allocation</h2><Chart height={280} data={[{ labels: Object.keys(allocation), values: Object.values(allocation), type: "pie", hole: 0.55 }]} />{result.optimization && <p className="mt-2 text-xs text-muted">Optimized weights shown from the backend response.</p>}</Card><Card className="p-5"><h2 className="font-semibold">Correlation</h2>{result.correlation && Object.keys(result.correlation).length > 1 ? <Chart height={280} data={[{ z: Object.values(result.correlation).map((row) => Object.values(row)), x: Object.keys(result.correlation), y: Object.keys(result.correlation), type: "heatmap", colorscale: "Greens" }]} /> : <p className="mt-8 text-sm text-muted">Correlation requires multiple assets.</p>}</Card></div></> : <Card className="grid min-h-[420px] place-items-center p-8 text-center"><div><h2 className="font-semibold">No portfolio run yet</h2><p className="mt-2 text-sm text-muted">Choose assets and allocations to calculate supported risk metrics.</p></div></Card>}</div></div></>;
}
