"use client";
import { useEffect, useMemo, useState } from "react";
import { FlaskConical, Play, Repeat, SlidersHorizontal } from "lucide-react";
import ReportView from "./ReportView";
import { Empty, Skeleton, num, usd, useToast } from "../lib/ui";
import type { Any, Ctx } from "../lib/types";

export default function AnalyzeView({ ctx, loading }: { ctx: Ctx; loading: boolean }) {
  const parts = ctx.entities.filter((e) => e.type === "component");
  const [target, setTarget] = useState<string>("MTR-01");
  const [mode, setMode] = useState<"swap" | "param">("swap");
  const [repl, setRepl] = useState(""); const [param, setParam] = useState(""); const [value, setValue] = useState(""); const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false); const toast = useToast();
  const ent = parts.find((p) => p.id === target);
  const alts = useMemo(() => ctx.catalog.filter((c) => c.category === ent?.category), [ctx.catalog, ent]);
  const params = useMemo(() => Object.entries(ent?.parameters || {}).filter(([k]) => k !== "unit_cost" || true), [ent]);

  useEffect(() => { if (ctx.preset) { setTarget(ctx.preset.target); if (ctx.preset.replacement) { setMode("swap"); setRepl(ctx.preset.replacement); } ctx.setPreset(null); } }, [ctx.preset]);
  useEffect(() => { setRepl(alts[0]?.id || ""); setParam(params[0]?.[0] || ""); setValue(""); }, [target]); // eslint-disable-line
  const unit = (ent?.parameters?.[param] as Any)?.unit || "";
  const label = (k: string) => ctx.project.param_labels?.[k] || k;

  const run = async () => {
    setBusy(true);
    const body = mode === "swap" ? { target_entity_id: target, replacement_id: repl, reason: reason || undefined }
      : { target_entity_id: target, parameter: param, proposed_value: parseFloat(value), unit, reason: reason || undefined };
    try { await ctx.runChange(body); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const examples = [
    { t: "MTR-01", label: "Motor → 24 V compact", r: "MTR-ALT-24A" }, { t: "MTR-01", label: "Motor → 12 V low-power", r: "MTR-ALT-12L" },
    { t: "CHS-01", label: "Lighter chassis", r: "CHS-ALT-LITE" }, { t: "BAT-01", label: "Bigger battery", r: "BAT-ALT-12XL" },
  ];
  const item = alts.find((a) => a.id === repl);

  return (
    <div className="col" style={{ gap: 18 }}>
      <div className="card pad">
        <h3><SlidersHorizontal size={14} />Describe the change</h3>
        <div className="grid g3" style={{ alignItems: "end" }}>
          <label className="f">Part to change
            <select value={target} onChange={(e) => setTarget(e.target.value)}>{parts.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.id}</option>)}</select></label>
          <div className="f"><span className="muted" style={{ fontSize: 12, fontWeight: 500 }}>Type of change</span>
            <div className="seg" role="group"><button aria-pressed={mode === "swap"} onClick={() => setMode("swap")}><Repeat size={13} style={{ verticalAlign: -2 }} /> Swap part</button><button aria-pressed={mode === "param"} onClick={() => setMode("param")}>Change a value</button></div></div>
          <label className="f">Reason (optional)<input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why this change?" maxLength={300} /></label>
        </div>
        {mode === "swap" ? (
          <div className="grid g2" style={{ marginTop: 14, alignItems: "end" }}>
            <label className="f">New part from the catalogue
              {alts.length ? <select value={repl} onChange={(e) => setRepl(e.target.value)}>{alts.map((a) => <option key={a.id} value={a.id}>{a.name} · {usd(a.parameters.unit_cost.value)}</option>)}</select> : <span className="muted">No catalogue part exists for this category.</span>}</label>
            {item && <div className="small muted">{usd(ent?.parameters?.unit_cost?.value)} now → <b style={{ color: "var(--text)" }}>{usd(item.parameters.unit_cost.value)}</b> each · lead time {item.lead_time_days} d · {Object.entries(item.parameters).filter(([k]) => k !== "unit_cost").slice(0, 3).map(([k, v]: Any) => `${label(k)} ${num(v.value, v.unit)}`).join(" · ")}</div>}
          </div>) : (
          <div className="grid g3" style={{ marginTop: 14, alignItems: "end" }}>
            <label className="f">Value<select value={param} onChange={(e) => setParam(e.target.value)}>{params.map(([k, v]: Any) => <option key={k} value={k}>{label(k)} (now {num(v.value, v.unit)})</option>)}</select></label>
            <label className="f">New value ({unit})<input className="input" type="number" step="any" value={value} onChange={(e) => setValue(e.target.value)} placeholder={`e.g. ${num((ent?.parameters?.[param] as Any)?.value * 2 || 24)}`} /></label>
          </div>)}
        <div className="row wrap" style={{ marginTop: 16 }}>
          <button className="btn primary" disabled={busy || (mode === "swap" ? !repl : !value)} onClick={run}><Play size={15} />{busy ? "Analysing…" : "Analyse impact"}</button>
          <span className="faint small">Try:</span>
          {examples.map((x) => <button key={x.label} className="btn sm ghost" onClick={() => { setTarget(x.t); setMode("swap"); setTimeout(() => setRepl(x.r), 0); }}>{x.label}</button>)}
        </div>
      </div>
      {loading ? <div className="col"><Skeleton h={140} /><Skeleton h={260} /></div>
        : ctx.report ? <ReportView report={ctx.report} ctx={ctx} />
        : <div className="card pad"><Empty icon={<FlaskConical size={32} />} title="No analysis yet">Pick a part and a change above. Ripple will trace what it touches, check the numbers and price the fix.</Empty></div>}
    </div>
  );
}
