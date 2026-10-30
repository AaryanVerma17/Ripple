"use client";
import { useEffect, useState } from "react";
import { ClipboardCheck, Package, RotateCcw, Store } from "lucide-react";
import { api } from "../lib/api";
import { Skeleton, num, usd, useToast } from "../lib/ui";
import type { Any, Ctx } from "../lib/types";

export default function PartsView({ ctx }: { ctx: Ctx }) {
  const [tab, setTab] = useState<"bom" | "catalog" | "audit">("bom");
  const [audit, setAudit] = useState<Any | null>(null); const [vals, setVals] = useState<Record<string, string>>({}); const toast = useToast();
  const load = () => api.audit().then(setAudit).catch((e) => toast(e.message, "err"));
  useEffect(() => { load(); }, []); // eslint-disable-line
  const bom = ctx.bom; const lab = (k: string) => ctx.project.param_labels?.[k] || k;
  const supply = async (m: Any) => {
    const key = `${m.entity_id}.${m.parameter}`;
    try { await api.supply({ entity_id: m.entity_id, parameter: m.parameter, value: parseFloat(vals[key]), unit: m.unit, source_note: "Entered in Data audit", author: "engineer" }); toast("Saved as engineer-supplied evidence.", "ok"); await load(); await ctx.refresh(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div className="card pad">
      <div className="tabs" role="tablist">{([["bom", "Bill of materials", Package], ["catalog", "Catalogue", Store], ["audit", `Data audit${audit ? ` (${audit.missing.length} missing)` : ""}`, ClipboardCheck]] as const).map(([k, l, I]) =>
        <button key={k} role="tab" className="tab" aria-selected={tab === k} onClick={() => setTab(k)}><I size={14} style={{ verticalAlign: -2, marginRight: 6 }} />{l}</button>)}</div>
      {tab === "bom" && (bom ? <>
        <table className="t"><thead><tr><th>Part</th><th>Category</th><th className="num">Qty</th><th className="num">Unit</th><th className="num">Line</th><th className="num">Mass</th><th>Catalogue alternatives</th></tr></thead>
          <tbody>{bom.rows.map((r: Any) => <tr key={r.id}><td><b>{r.name}</b><div className="mono faint small">{r.id}</div></td><td className="muted">{r.category}</td><td className="num">{r.qty}</td><td className="num">{usd(r.unit_cost)}</td><td className="num"><b>{usd(r.line_cost)}</b></td><td className="num">{num(r.mass_kg, "kg")}</td>
            <td>{r.alternatives.length ? r.alternatives.map((a: Any) => <button key={a.id} className="btn sm ghost" style={{ margin: 2 }} onClick={() => { ctx.setPreset({ target: r.id, replacement: a.id }); ctx.go("analyze"); }}>{a.id} · {usd(a.unit_cost)}</button>) : <span className="faint">—</span>}</td></tr>)}</tbody>
          <tfoot><tr><td colSpan={4}><b>Total</b></td><td className="num"><b>{usd(bom.total_cost)}</b></td><td className="num"><b>{num(bom.metrics.total_mass_kg?.value, "kg")}</b></td><td className="muted small">Budget {usd(bom.budget)}</td></tr></tfoot></table></> : <Skeleton h={220} />)}
      {tab === "catalog" && <div className="grid g3">{ctx.catalog.map((c) => <div key={c.id} className="finding f-no_violation_found"><div className="row" style={{ justifyContent: "space-between" }}><b>{c.name}</b><span className="chip s-review_required">{c.category}</span></div><div className="mono faint small">{c.id} · {c.lead_time_days} d lead</div>
        <div className="small">{Object.entries(c.parameters).map(([k, v]: Any) => <div key={k} className="row" style={{ justifyContent: "space-between" }}><span className="muted">{lab(k)}</span><span className="tnum">{k === "unit_cost" ? usd(v.value) : num(v.value, v.unit)}</span></div>)}</div></div>)}</div>}
      {tab === "audit" && (audit ? <div className="col" style={{ gap: 16 }}>
        <div><div className="small muted" style={{ marginBottom: 8 }}>Values the checks need but the project doesn&apos;t record</div>
          {audit.missing.length === 0 ? <div className="callout"><ClipboardCheck size={15} />Nothing missing.</div> : audit.missing.map((m: Any) => { const key = `${m.entity_id}.${m.parameter}`; return (
            <div key={key} className="row wrap" style={{ marginBottom: 8 }}><span style={{ flex: 1, minWidth: 220 }}><b>{m.name}</b> · {m.label} <span className="faint small">needed for {m.needed_for.join(", ")}</span></span>
              <input className="input" style={{ width: 120 }} type="number" step="any" placeholder={m.unit} value={vals[key] || ""} onChange={(e) => setVals({ ...vals, [key]: e.target.value })} />
              <button className="btn sm primary" disabled={!vals[key]} onClick={() => supply(m)}>Save</button></div>); })}</div>
        <div><div className="row" style={{ justifyContent: "space-between" }}><span className="small muted">Engineer-supplied values</span>{audit.overrides.length > 0 && <button className="btn sm" onClick={async () => { await api.resetSupplied(); await load(); await ctx.refresh(); toast("Cleared.", "ok"); }}><RotateCcw size={13} />Clear all</button>}</div>
          {audit.overrides.length === 0 ? <div className="faint small">None yet.</div> : audit.overrides.map((o: Any) => <div key={o.id} className="small">{o.entity_id} · {lab(o.param)} = <b>{num(o.value, o.unit)}</b> <span className="faint">{o.source_note}</span></div>)}</div>
        <div><div className="small muted" style={{ marginBottom: 6 }}>Assumptions behind estimates (editable in the project data)</div>
          {Object.values(audit.assumptions).map((a: Any) => <div key={a.label} className="small row" style={{ justifyContent: "space-between" }}><span>{a.label}</span><b className="tnum">{a.value}</b></div>)}</div>
      </div> : <Skeleton h={160} />)}
    </div>
  );
}
