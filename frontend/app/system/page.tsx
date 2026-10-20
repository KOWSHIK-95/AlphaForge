"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { Card, Notice, PageIntro } from "@/components/Ui";
import { api, ApiError } from "@/lib/api";

export default function System() {
  const [state, setState] = useState<"loading" | "ok" | "error">("loading"); const [message, setMessage] = useState(""); const [checkedAt, setCheckedAt] = useState("");
  const check = useCallback(() => { setState("loading"); api.health().then(() => { setState("ok"); setMessage(""); setCheckedAt(new Date().toLocaleTimeString()); }).catch((error: ApiError) => { setState("error"); setMessage(error.message); setCheckedAt(new Date().toLocaleTimeString()); }); }, []);
  useEffect(() => { check(); }, [check]);
  return <><PageIntro eyebrow="System status" title="Know what is alive." description="Application liveness is checked through the backend health endpoint. Dependency readiness is intentionally not inferred from it." action={<button onClick={check} className="flex items-center gap-2 rounded-lg border border-line bg-panel px-4 py-2 text-sm text-slate-200 hover:border-signal/50"><RefreshCw size={15} className={state === "loading" ? "animate-spin" : ""} /> Refresh</button>} /><div className="grid gap-5 md:grid-cols-2"><Card className="p-6"><div className="flex items-center gap-4">{state === "ok" ? <CheckCircle2 className="text-signal" size={30} /> : <XCircle className={state === "error" ? "text-danger" : "text-muted"} size={30} />}<div><h2 className="font-semibold">AlphaForge API</h2><p className="mt-1 text-sm text-muted">{state === "loading" ? "Checking liveness…" : state === "ok" ? "Reachable and responding." : "Unavailable"}</p></div></div>{state === "error" && <div className="mt-5"><Notice>{message}</Notice></div>}{checkedAt && <p className="mt-6 text-xs text-muted">Last checked at {checkedAt}</p>}</Card><Card className="p-6"><h2 className="font-semibold">What this check does not claim</h2><ul className="mt-4 space-y-3 text-sm leading-6 text-muted"><li>• PostgreSQL connectivity is not checked by GET /health.</li><li>• External market-provider availability is not checked.</li><li>• Market-data requests may still fail independently.</li></ul></Card></div></>;
}
