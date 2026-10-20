import type { ReactNode } from "react";

export function PageIntro({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-intro"><div><p className="eyebrow">{eyebrow}</p><h1 className="page-title">{title}</h1><p className="page-description">{description}</p></div>{action}</div>;
}
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`surface-card ${className}`}>{children}</section>;
}
export function Metric({ label, value, note, tone = "default" }: { label: string; value: string; note?: string; tone?: "default" | "positive" | "negative" }) {
  return <Card className="metric-card"><p className="text-xs uppercase tracking-[0.12em] text-muted">{label}</p><p className={`mt-3 text-2xl font-semibold tracking-tight ${tone === "positive" ? "text-signal" : tone === "negative" ? "text-danger" : "text-white"}`}>{value}</p>{note && <p className="mt-1 text-xs text-muted">{note}</p>}</Card>;
}
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field-label"><span>{label}</span>{children}{hint && <small className="block text-muted">{hint}</small>}</label>;
}
export const inputClass = "field-control";
export function Notice({ children, tone = "error" }: { children: ReactNode; tone?: "error" | "info" | "success" }) {
  return <div role={tone === "error" ? "alert" : "status"} className={`notice ${tone === "error" ? "notice-error" : tone === "success" ? "notice-success" : "notice-info"}`}>{children}</div>;
}
