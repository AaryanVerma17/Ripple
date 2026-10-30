"use client";
import { createContext, useCallback, useContext, useState, ReactNode } from "react";
import { CheckCircle2, AlertTriangle } from "lucide-react";

export const STATUS: Record<string, string> = {
  verified_issue: "Verified issue", potential_issue: "Potential issue", unknown: "Unknown",
  no_violation_found: "No violation found", review_required: "Review required",
};
export const VERDICT: Record<string, { label: string; cls: string }> = {
  blocked: { label: "Blocked", cls: "s-verified_issue" }, at_risk: { label: "At risk", cls: "s-potential_issue" },
  incomplete: { label: "Incomplete", cls: "s-unknown" }, clear: { label: "No violations found", cls: "s-no_violation_found" },
};

export function Chip({ status, label }: { status: string; label?: string }) {
  return <span className={`chip s-${status}`}><i />{label ?? STATUS[status] ?? status}</span>;
}

export function num(v: number | null | undefined, unit = "", digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  const s = a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : Number(v.toPrecision(digits)).toString();
  if (unit === "USD") return `$${Number(v.toFixed(2)).toLocaleString()}`;
  return unit ? `${s} ${unit}` : s;
}
export const usd = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v < 0 ? "−" : ""}$${Math.abs(Number(v.toFixed(2))).toLocaleString()}`);
export const signed = (v: number | null | undefined, unit = "") => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${unit === "USD" ? "$" : ""}${Math.abs(Number(v.toPrecision(3)))}${unit && unit !== "USD" ? " " + unit : ""}`);

/** Tiny, safe Markdown: **bold**, `code`, "- " bullets and paragraphs. No HTML is ever injected. */
export function Md({ text }: { text: string }) {
  const inline = (s: string, k: number) => {
    const parts = s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return parts.map((p, i) => p.startsWith("**") ? <strong key={`${k}-${i}`}>{p.slice(2, -2)}</strong> : p.startsWith("`") ? <code key={`${k}-${i}`}>{p.slice(1, -1)}</code> : <span key={`${k}-${i}`}>{p}</span>);
  };
  const out: ReactNode[] = []; let list: string[] = [];
  const flush = (k: number) => { if (list.length) { out.push(<ul key={`u${k}`}>{list.map((l, i) => <li key={i}>{inline(l, i)}</li>)}</ul>); list = []; } };
  text.split("\n").forEach((line, i) => {
    const m = line.match(/^\s*[-•]\s+(.*)/);
    if (m) list.push(m[1]); else { flush(i); if (line.trim()) out.push(<p key={i}>{inline(line, i)}</p>); }
  });
  flush(999);
  return <div className="md">{out}</div>;
}

export function Skeleton({ h = 16, w = "100%" }: { h?: number; w?: string | number }) { return <div className="skel" style={{ height: h, width: w }} />; }

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return <div style={{ textAlign: "center", padding: "40px 16px" }}><div style={{ color: "var(--accent)", marginBottom: 10 }}>{icon}</div><h3 style={{ fontSize: 16, textTransform: "none", letterSpacing: 0, color: "var(--text)", justifyContent: "center", margin: "0 0 6px" }}>{title}</h3><div className="muted" style={{ maxWidth: 420, margin: "0 auto" }}>{children}</div></div>;
}

type Toast = { id: number; msg: string; kind: "ok" | "err" | "info" };
const ToastCtx = createContext<(msg: string, kind?: Toast["kind"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((msg: string, kind: Toast["kind"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, msg, kind }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === "err" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind === "err" ? "err" : t.kind === "ok" ? "ok" : ""}`}>
          {t.kind === "err" ? <AlertTriangle size={16} color="var(--bad)" /> : <CheckCircle2 size={16} color="var(--ok)" />}<span>{t.msg}</span></div>)}
      </div>
    </ToastCtx.Provider>
  );
}
