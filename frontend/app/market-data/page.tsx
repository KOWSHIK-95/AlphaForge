"use client";

import { useState } from "react";
import { Chart } from "@/components/Chart";
import { Card, Field, inputClass, Notice, PageIntro } from "@/components/Ui";
import { api, ApiError, MarketBar } from "@/lib/api";
import { validateDateRange, validateTickerInput } from "@/lib/validation";

export default function MarketData() {
  const [tickerText, setTickerText] = useState("AAPL, MSFT");
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [rows, setRows] = useState<MarketBar[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setRows([]);
    try {
      const tickers = validateTickerInput(tickerText);
      validateDateRange(start, end);
      setState("loading"); setMessage("");
      setRows((await api.marketData(tickers, start, end)).data); setState("idle");
    } catch (error) { setState("error"); setMessage(error instanceof ApiError || error instanceof Error ? error.message : "Unable to load market data."); }
  }
  const traces = (() => { try { return validateTickerInput(tickerText).map((ticker) => { const data = rows.filter((row) => row.ticker === ticker); return { x: data.map((row) => row.date), y: data.map((row) => row.close), type: "scatter", mode: "lines", name: ticker, line: { width: 2 } } as const; }); } catch { return []; } })();
  return <><PageIntro eyebrow="Market data" title="Observe the tape." description="Fetch daily bars from the existing market-data endpoint. The start date is inclusive and the end date is exclusive." /><div className="grid gap-5 xl:grid-cols-[280px_1fr]"><Card className="h-fit p-5"><form onSubmit={submit} className="space-y-5"><Field label="Ticker symbols" hint="Comma-separated, for example AAPL, MSFT"><input className={inputClass} value={tickerText} onChange={(event) => setTickerText(event.target.value)} /></Field><Field label="Start date"><input className={inputClass} type="date" value={start} onChange={(event) => setStart(event.target.value)} /></Field><Field label="End date (exclusive)"><input className={inputClass} type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></Field><button className="w-full rounded-lg bg-signal px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-emerald-300 disabled:cursor-wait disabled:opacity-50" disabled={state === "loading"}>{state === "loading" ? "Loading…" : "Fetch market data"}</button></form>{state === "error" && <div className="mt-4"><Notice>{message}</Notice></div>}</Card><div className="space-y-5">{rows.length ? <><Card className="p-3"><Chart title="Close price" data={traces} height={390} /></Card><Card className="overflow-hidden"><div className="border-b border-line px-5 py-4"><h2 className="font-semibold">Returned observations <span className="ml-2 text-xs font-normal text-muted">{rows.length} rows</span></h2></div><div className="max-h-[420px] overflow-auto"><table className="w-full text-left text-sm"><thead className="sticky top-0 bg-panel text-xs uppercase tracking-wider text-muted"><tr><th className="px-5 py-3">Date</th><th>Ticker</th><th className="text-right">Close</th><th className="px-5 text-right">Return</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.ticker}-${row.date}-${index}`} className="border-t border-line/70"><td className="px-5 py-3 text-muted">{row.date}</td><td>{row.ticker}</td><td className="text-right tabular-nums">{row.close.toFixed(2)}</td><td className="px-5 text-right tabular-nums text-muted">{row.returns == null ? "—" : `${(row.returns * 100).toFixed(2)}%`}</td></tr>)}</tbody></table></div></Card></> : <Card className="grid min-h-[420px] place-items-center p-8 text-center"><div><LinePlaceholder /><h2 className="mt-4 font-semibold">No observations loaded</h2><p className="mt-2 text-sm text-muted">Set a universe and date range to begin.</p></div></Card>}</div></div></>;
}
function LinePlaceholder() { return <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-line text-signal">↗</div>; }
