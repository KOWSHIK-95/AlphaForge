"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export function Chart({ data, title, height = 330 }: { data: Partial<Data>[]; title?: string; height?: number }) {
  const layout: Partial<Layout> = { title: title ? { text: title, font: { color: "#d9e1ea", size: 13 }, x: 0.03, xanchor: "left" } : undefined, height, autosize: true, paper_bgcolor: "transparent", plot_bgcolor: "transparent", font: { color: "#82909f", size: 11 }, margin: { l: 52, r: 20, t: title ? 42 : 18, b: 48 }, hoverlabel: { bgcolor: "#151b22", bordercolor: "#303b47", font: { color: "#f1f5f9" } }, xaxis: { gridcolor: "#202731", zerolinecolor: "#202731", automargin: true, showline: false }, yaxis: { gridcolor: "#202731", zerolinecolor: "#202731", automargin: true, showline: false }, legend: { orientation: "h", y: -0.22, font: { size: 10 } }};
  return <div className="chart-frame"><Plot data={data} layout={layout} config={{ responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] }} style={{ width: "100%" }} useResizeHandler /></div>;
}
