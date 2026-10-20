"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, CandlestickChart, FlaskConical, LayoutDashboard, Menu, Server, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/market-data", label: "Market data", icon: CandlestickChart },
  { href: "/portfolio", label: "Portfolio analysis", icon: BarChart3 },
  { href: "/backtesting", label: "Backtesting studio", icon: FlaskConical },
  { href: "/system", label: "System status", icon: Server },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-ink text-slate-100">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-sidebar px-5 py-6 lg:block">
        <Link href="/" className="mb-12 flex items-center gap-3" aria-label="AlphaForge home">
          <span className="brand-mark"><TrendingUp size={19} /></span>
          <span><b className="block tracking-tight text-white">AlphaForge</b><small className="text-[10px] uppercase tracking-[0.22em] text-muted">Research terminal</small></span>
        </Link>
        <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted/70">Workspace</p>
        <nav className="space-y-1" aria-label="Primary navigation">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${pathname === href ? "bg-signal/10 text-signal" : "text-muted hover:bg-white/[.03] hover:text-slate-100"}`}>
              <Icon size={17} strokeWidth={1.8} />{label}
            </Link>
          ))}
        </nav>
        <div className="absolute bottom-6 left-5 right-5 rounded-lg border border-line bg-panel/80 p-3 text-xs text-muted shadow-panel">
          <div className="mb-2 flex items-center gap-2 text-slate-300"><Activity size={14} className="text-signal" /> API on demand</div>
          <span>Calculations remain in the Python engine.</span>
        </div>
      </aside>
      <main className="lg:pl-64">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-line bg-ink/90 px-5 backdrop-blur lg:px-10">
          <div className="flex items-center gap-3 lg:hidden"><span className="brand-mark h-8 w-8"><TrendingUp size={16} /></span><b>AlphaForge</b></div>
          <div className="hidden items-center gap-3 lg:flex"><Menu size={16} className="text-muted" /><span className="text-xs uppercase tracking-[0.2em] text-muted">Quantitative research workspace</span></div>
          <Link href="/system" className="status-link" aria-label="View API system status"><span className="status-dot" /> API status</Link>
        </header>
        <div className="mx-auto max-w-[1500px] px-5 py-8 lg:px-10">{children}</div>
      </main>
    </div>
  );
}
