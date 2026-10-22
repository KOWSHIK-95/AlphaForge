import type { MarketBar } from "@/lib/api";

export type AlignedReturns = {
  values: Record<string, number[]>;
  dates: string[];
  dropped: number;
  priceField: "adj_close" | "close";
};

export function alignReturns(rows: MarketBar[], tickers: string[]): AlignedReturns {
  const byTicker = new Map<string, Map<string, number>>();
  const requestedRows = rows.filter((row) => tickers.includes(row.ticker));
  const usedAdjustedClose = requestedRows.length > 0
    && requestedRows.every((row) => row.adj_close != null && Number.isFinite(row.adj_close));

  for (const ticker of tickers) {
    byTicker.set(ticker, new Map());
  }
  for (const row of rows) {
    if (!byTicker.has(row.ticker)) continue;
    const price = usedAdjustedClose ? row.adj_close : row.close;
    if (price == null || !Number.isFinite(price) || price <= 0) continue;
    byTicker.get(row.ticker)?.set(row.date, price);
  }

  const commonDates = [...new Set(
    tickers.flatMap((ticker) => [...(byTicker.get(ticker)?.keys() ?? [])]),
  )].filter((date) => tickers.every((ticker) => byTicker.get(ticker)?.has(date))).sort();
  const values: Record<string, number[]> = Object.fromEntries(
    tickers.map((ticker) => [ticker, []]),
  );
  const dates: string[] = [];
  let dropped = 0;

  for (let index = 1; index < commonDates.length; index += 1) {
    const previousDate = commonDates[index - 1];
    const currentDate = commonDates[index];
    const intervalIsConsecutiveForEveryAsset = tickers.every((ticker) => {
      const points = [...(byTicker.get(ticker)?.entries() ?? [])]
        .map(([date, price]) => ({ date, price }))
        .sort((left, right) => left.date.localeCompare(right.date));
      const currentIndex = points.findIndex((point) => point.date === currentDate);
      return currentIndex > 0 && points[currentIndex - 1]?.date === previousDate;
    });

    if (!intervalIsConsecutiveForEveryAsset) {
      dropped += 1;
      continue;
    }
    tickers.forEach((ticker) => {
      const prices = byTicker.get(ticker);
      values[ticker].push(prices!.get(currentDate)! / prices!.get(previousDate)! - 1);
    });
    dates.push(currentDate);
  }

  if (!dates.length) {
    throw new Error("There are not enough consecutive complete observations.");
  }
  return {
    values,
    dates,
    dropped,
    priceField: usedAdjustedClose ? "adj_close" : "close",
  };
}
