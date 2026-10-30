"use client";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Calculator, ChevronDown, Clock, Download, FileText, Gavel, PackageCheck, Printer, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import RippleMap from "./RippleMap";
import { api } from "../lib/api";
import { Chip, Md, VERDICT, num, signed, usd, useToast } from "../lib/ui";
import type { Any, Ctx } from "../lib/types";

const ORDER = ["verified_issue", "potential_issue", "unknown", "review_required", "no_violation_found"];

function Calc({ calc }: { calc: Any }) {
  return (
    <div className="small" style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginTop: 6 }}>
      <div className="row" style={{ gap: 6 }}><Calculator size={13} /><b>{calc.name}</b><span className="faint mono">{calc.calculation_id}</span></div>
      <div className="muted mono" style={{ margin: "4px 0" }}>{calc.formula}</div>
      {calc.inputs.map((i: Any, k: number) => (
        <div key={k} className="row" style={{ justifyContent: "space-between", gap: 8 }}>
          <span>{i.label}</span><span className="tnum mono">{num(i.value, i.unit)} <span className="ev">{i.evidence_id}</span></span>
        </div>))}
      {calc.result && <div className="row" style={{ justifyContent: "space-between", borderTop: "1px solid var(--line)", marginTop: 6, paddingTop: 6 }}>
        <b>Result</b><b className="tnum mono">{num(calc.result.value, calc.result.unit)} <span className="muted">{calc.result.text}</span></b></div>}
      {calc.assumptions?.map((a: string, k: number) => <div key={k} className="faint">Assumption: {a}</div>)}
    </div>
  );
}

function Finding({ f, calcs, evidence }: { f: Any; calcs: Any[]; evidence: Any }) {
  const [open, setOpen] = useState(false);
  const calc = calcs.find((c) => c.calculation_id === f.calc_id);
  return (
    <div className={`finding f-${f.status}`}>
      <div className="row wrap" style={{ justifyContent: "space-between" }}>
        <span className="title">{f.title}</span><Chip status={f.status} />
      </div>
      <div>{f.summary}</div>
      {f.impact_path?.length > 1 && <div className="row wrap small faint mono">{f.impact_path.map((p: string, i: number) => <span key={i} className="row" style={{ gap: 4 }}>{p}{i < f.impact_path.length - 1 && <ArrowRight size={11} />}</span>)}</div>}
      <div className="next"><b>Next:</b> {f.recommended_action}</div>
      {(calc || f.evidence_ids?.length > 0) && (
        <button className="btn ghost sm" style={{ justifySelf: "start" }} onClick={() => setOpen(!open)} aria-expanded={open}>
          <ChevronDown size={14} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }} />{open ? "Hide" : "Show"} calculation and evidence
        </button>)}
      {open && (<div className="fade-in">
        {calc && <Calc calc={calc} />}
        <div style={{ marginTop: 6 }}>{f.evidence_ids?.map((e: string) => <span key={e} className="ev" title={evidence[e]?.source_location}>{e}{evidence[e] ? ` · ${evidence[e].status.replace("_", " ")}` : ""}</span>)}</div>
      </div>)}
    </div>
  );
}

function SupplyForm({ q, onDone }: { q: Any; onDone: () => void }) {
  const [v, setV] = useState(""); const [note, setNote] = useState(""); const [busy, setBusy] = useState(false); const toast = useToast();
  const submit = async () => {
    setBusy(true);
    try { await api.supply({ entity_id: q.entity_id, parameter: q.param, value: parseFloat(v), unit: q.unit, source_note: note, author: "engineer" }); toast("Saved. Re-running the checks…", "ok"); onDone(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <div className="row wrap" style={{ marginTop: 6 }}>
      <input className="input" style={{ width: 110 }} type="number" step="any" placeholder={q.unit} value={v} onChange={(e) => setV(e.target.value)} aria-label={`Value in ${q.unit}`} />
      <input className="input" style={{ flex: 1, minWidth: 140 }} placeholder="Source (e.g. datasheet p.4)" value={note} onChange={(e) => setNote(e.target.value)} />
      <button className="btn primary sm" disabled={busy || !v} onClick={submit}>Supply &amp; re-run</button>
    </div>
  );
}

export default function ReportView({ report, ctx }: { report: Any; ctx: Ctx }) {
  const [sid, setSid] = useState<string>(report.primary_scenario);
  const [filter, setFilter] = useState<string>("all");
  const [tab, setTab] = useState<"findings" | "map" | "cost" | "fix" | "scope">("findings");
  const [dec, setDec] = useState({ decision: "needs_revision", reviewer: "", comments: "" });
  const [busy, setBusy] = useState(false); const toast = useToast();
  const sc = useMemo(() => report.scenarios.find((s: Any) => s.id === sid) || report.scenarios[0], [report, sid]);
  const v = VERDICT[sc.verdict] || VERDICT.incomplete;
  const findings = ORDER.flatMap((st) => sc.findings.filter((f: Any) => f.status === st)).filter((f: Any) => filter === "all" ? f.status !== "no_violation_found" || true : f.status === filter);
  const co = sc.cost; const syn = report.ai_synthesis;
  const rerun = async () => { if (ctx.lastRequest) await ctx.runChange(ctx.lastRequest); };

  const decide = async () => {
    setBusy(true);
    try { await api.decide(report.analysis_id, dec); ctx.setReport(await api.analysis(report.analysis_id)); toast("Decision recorded. Earlier decisions are kept.", "ok"); setDec({ ...dec, comments: "" }); await ctx.refresh(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const riskColor = sc.risk.score >= 60 ? "var(--bad)" : sc.risk.score >= 30 ? "var(--warn)" : "var(--ok)";

  return (
    <div className="col fade-in" style={{ gap: 16 }}>
      <div className="hero">
        <div className="row wrap" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ maxWidth: 780 }}>
            <div className="row wrap" style={{ marginBottom: 8 }}><span className={`chip ${v.cls}`}><i />{v.label}</span><span className="chip s-neutral">{report.kind === "whatif" ? "What-if" : "Analysis"}</span><span className="faint mono small">{report.analysis_id}</span></div>
            <h2 style={{ fontSize: 21, lineHeight: 1.3 }}>{report.headline}</h2>
          </div>
          <div className="row noprint">
            <a className="btn sm" href={api.exportUrl(report.analysis_id)} download><Download size={14} />Markdown</a>
            <button className="btn sm" onClick={() => window.print()}><Printer size={14} />Print</button>
          </div>
        </div>
        <div className="grid g4" style={{ marginTop: 18 }}>
          <div className="stat"><b style={{ color: "var(--bad)" }}>{sc.counts.verified_issue}</b><span>Verified issues</span></div>
          <div className="stat"><b style={{ color: "var(--warn)" }}>{sc.counts.potential_issue}</b><span>Potential issues</span></div>
          <div className="stat"><b style={{ color: "var(--unk)" }}>{sc.counts.unknown}</b><span>Unknowns</span></div>
          <div className="stat"><b style={{ color: riskColor }}>{sc.risk.score}<small style={{ fontSize: 13, color: "var(--faint)" }}>/100</small></b><span title={sc.risk.formula}>Risk score · {sc.risk.band}</span>
            <div className="meter"><div style={{ width: `${sc.risk.score}%`, background: riskColor }} /></div></div>
        </div>
        <div className="titleblock" style={{ marginTop: 18 }}>
          <div><small>Target</small>{report.change.target_name} <span className="mono faint">{report.change.target_entity_id}</span></div>
          <div><small>Change</small>{report.change.mode === "swap" ? `Swap to ${report.change.replacement?.name}` : "Parameter change"}</div>
          <div><small>Review</small>{report.review_decision ? report.review_decision.decision.replace("_", " ") : "Awaiting engineer"}</div>
          <div><small>Created</small>{new Date(report.created_at).toLocaleString()}</div>
        </div>
      </div>

      {report.scenarios.length > 1 && (
        <div className="grid g3">
          {report.scenarios.map((s: Any) => (
            <button key={s.id} className="scen" aria-pressed={s.id === sid} onClick={() => setSid(s.id)}>
              <div className="row" style={{ justifyContent: "space-between" }}><b>Plan {s.id}{s.id === report.primary_scenario && <span className="faint small"> · fullest</span>}</b><span className={`chip ${(VERDICT[s.verdict] || VERDICT.incomplete).cls}`}><i />{(VERDICT[s.verdict] || VERDICT.incomplete).label}</span></div>
              <div style={{ fontWeight: 600 }}>{s.title}</div><div className="muted small">{s.summary}</div>
              <div className="row small tnum" style={{ gap: 12 }}><span style={{ color: "var(--bad)" }}>{s.counts.verified_issue} verified</span><span style={{ color: "var(--warn)" }}>{s.counts.potential_issue} potential</span><span style={{ color: "var(--unk)" }}>{s.counts.unknown} unknown</span><span className="spacer" /><b>{signed(s.cost.parts_delta, "USD")}</b></div>
            </button>))}
        </div>)}

      <div className="split">
        <div className="col" style={{ gap: 16 }}>
          <div className="card pad">
            <h3><Sparkles size={14} />What the change does to the product</h3>
            <table className="t"><thead><tr><th>Measure</th><th className="num">Before</th><th className="num">After</th><th className="num">Δ</th><th>Requirement</th></tr></thead>
              <tbody>{sc.metrics.map((m: Any) => (
                <tr key={m.name}><td><b>{m.label}</b>{m.model_assumption && <div className="faint small">estimate</div>}</td>
                  <td className="num">{num(m.baseline, m.unit)}</td>
                  <td className="num">{m.proposed === null ? <span className="muted small" title={m.reason}>unavailable</span> : num(m.proposed, m.unit)}</td>
                  <td className={`num ${m.delta > 0 ? (m.name.includes("cost") || m.name.includes("mass") || m.name.includes("peak") || m.name.includes("average") ? "delta-up" : "delta-down") : m.delta < 0 ? (m.name.includes("cost") || m.name.includes("mass") || m.name.includes("peak") || m.name.includes("average") ? "delta-down" : "delta-up") : ""}`}>{m.delta === null || m.delta === undefined ? "—" : signed(m.delta, m.unit === "USD" ? "USD" : "")}</td>
                  <td>{m.requirement ? <span className="row" style={{ gap: 6 }}><span className="mono small">{m.requirement.id}</span><Chip status={m.requirement.status} /></span> : <span className="faint">—</span>}</td></tr>))}
              </tbody></table>
            {sc.metrics.some((m: Any) => m.proposed === null) && <div className="callout" style={{ marginTop: 10 }}><AlertTriangle size={15} />Some measures can&apos;t be computed because a recorded value is missing. Hover “unavailable” for the reason, or supply the value below.</div>}
          </div>

          <div className="card pad">
            <div className="tabs" role="tablist" style={{ margin: "-6px 0 14px" }}>
              {([["findings", `Findings (${sc.findings.filter((f: Any) => f.status !== "no_violation_found").length})`], ["map", "Ripple map"], ["cost", "Cost"], ["fix", `Fix options (${sc.fix_options.length})`], ["scope", "Scope"]] as const).map(([k, l]) => (
                <button key={k} role="tab" aria-selected={tab === k} className="tab" onClick={() => setTab(k)}>{l}</button>))}
            </div>

            {tab === "findings" && (<div className="col">
              <div className="row wrap">{["all", ...ORDER].map((o) => <button key={o} className={`btn sm ${filter === o ? "primary" : ""}`} onClick={() => setFilter(o)}>{o === "all" ? "All" : o.replace(/_/g, " ")}</button>)}</div>
              {findings.length === 0 ? <div className="muted">Nothing in this category.</div> : findings.map((f: Any) => <Finding key={f.id} f={f} calcs={sc.calculations} evidence={report.evidence} />)}
            </div>)}

            {tab === "map" && <RippleMap graph={ctx.graph} scenario={sc} height={540} />}

            {tab === "cost" && (<div className="col fade-in">
              <div className="grid g3">
                <div className="stat"><b>{signed(co.parts_delta, "USD")}</b><span>Parts per unit</span></div>
                <div className="stat"><b>{usd(co.labour.total)}</b><span>One-off effort (estimate)</span></div>
                <div className="stat"><b>{usd(co.first_build_total)}</b><span>First-unit total</span></div>
              </div>
              {co.budget != null && <div><div className="row small" style={{ justifyContent: "space-between" }}><span>BOM {usd(co.bom_after)} of {usd(co.budget)} budget</span><span style={{ color: co.budget_margin_after < 0 ? "var(--bad)" : "var(--ok)" }}>{co.budget_margin_after < 0 ? `over by ${usd(-co.budget_margin_after)}` : `${usd(co.budget_margin_after)} left`}</span></div>
                <div className="meter" style={{ marginTop: 6 }}><div style={{ width: `${Math.min(100, (co.bom_after / co.budget) * 100)}%`, background: co.bom_after > co.budget ? "var(--bad)" : "var(--accent)" }} /></div></div>}
              <table className="t"><thead><tr><th>Part</th><th>From → to</th><th className="num">Unit</th><th className="num">Qty</th><th className="num">Δ</th></tr></thead>
                <tbody>{co.lines.filter((l: Any) => l.swapped).map((l: Any) => <tr key={l.entity_id}><td className="mono">{l.entity_id}</td><td>{l.from_part} → <b>{l.to_part}</b></td><td className="num">{usd(l.unit_cost_from)} → {usd(l.unit_cost_to)}</td><td className="num">{l.qty}</td><td className="num">{signed(l.line_delta, "USD")}</td></tr>)}</tbody></table>
              <div className="callout"><Clock size={15} /><div><b>How the effort estimate works.</b> {co.labour.swapped_parts} replaced part(s) and {co.labour.tests} test(s) to re-run, {co.labour.hours} h at ${co.labour.rate}/h. These are editable assumptions, not quotes. {co.note}</div></div>
            </div>)}

            {tab === "fix" && (<div className="col fade-in">
              {sc.fix_options.length === 0 ? <div className="muted">No failing check has a catalogue fix in this plan.</div> : sc.fix_options.map((o: Any) => (
                <div key={o.entity_id} className="finding f-no_violation_found"><div className="title">{o.name} <span className="mono faint">{o.entity_id}</span></div>
                  <div className="small muted">Fixes: {o.issues.map((i: Any) => i.title).join("; ")}</div>
                  {o.options.length === 0 ? <div className="small">No catalogue part fixes this. The change or a requirement has to move.</div> :
                    o.options.map((x: Any) => (<div key={x.catalog_id} className="row wrap" style={{ justifyContent: "space-between" }}>
                      <span><PackageCheck size={14} style={{ verticalAlign: -2 }} /> <b>{x.name}</b> <span className="mono faint">{x.catalog_id}</span>{o.chosen === x.catalog_id && <span className="chip s-review_required" style={{ marginLeft: 8 }}>used in plan</span>}</span>
                      <span className="tnum small">{usd(x.unit_cost)} · {signed(x.cost_delta, "USD")} · {x.lead_time_days} d lead</span></div>))}
                </div>))}
            </div>)}

            {tab === "scope" && (<div className="col fade-in">
              <div><div className="small muted" style={{ marginBottom: 6 }}>Not affected</div>{sc.unaffected.length === 0 ? <span className="faint">Everything is touched.</span> : sc.unaffected.map((u: Any) => <div key={u.entity_id} className="small" style={{ marginBottom: 6 }}><ShieldCheck size={13} color="var(--ok)" style={{ verticalAlign: -2 }} /> <b>{u.name}</b> <span className="mono faint">{u.entity_id}</span> — {u.reason}</div>)}</div>
              <div><div className="small muted" style={{ marginBottom: 6 }}>Tests to reconsider</div>{sc.tests.length === 0 ? <span className="faint">None connected.</span> : sc.tests.map((t: Any) => <div key={t.id} className="small"><b>{t.name}</b> <span className="mono faint">{t.id}</span></div>)}</div>
              <div><div className="small muted" style={{ marginBottom: 6 }}>Documents to update</div>{sc.docs.length === 0 ? <span className="faint">None.</span> : sc.docs.map((t: Any) => <div key={t.id} className="small"><FileText size={13} style={{ verticalAlign: -2 }} /> {t.name} <span className="mono faint">{t.id}</span></div>)}</div>
            </div>)}
          </div>
        </div>

        <div className="col" style={{ gap: 16 }}>
          <div className="card pad">
            <h3><Sparkles size={14} />AI summary</h3>
            {syn?.status === "completed" ? (<div className="col"><Md text={syn.summary} />{syn.review_actions.length > 0 && <Md text={syn.review_actions.map((a: string) => `- ${a}`).join("\n")} />}
              <div className="faint small">Written by {syn.model}; every number and ID was checked against the analysis.</div></div>)
              : <div className="muted small">{syn?.message || "No AI summary."}{syn?.status === "rejected" && " The deterministic analysis above is unaffected."}</div>}
          </div>

          {sc.unresolved.length > 0 && (
            <div className="card pad"><h3><AlertTriangle size={14} />Missing data ({sc.unresolved.length})</h3>
              <div className="col">{sc.unresolved.map((q: Any, i: number) => (<div key={i}><div className="small">{q.text}</div><SupplyForm q={q} onDone={rerun} /></div>))}</div>
              <div className="faint small" style={{ marginTop: 8 }}>Supplied values are stored with your note as evidence and used in every later analysis.</div></div>)}

          {report.suggestions?.length > 0 && (
            <div className="card pad"><h3><Wrench size={14} />Catalogue parts that match</h3>
              {report.suggestions.map((s: Any) => <div key={s.catalog_id} className="small" style={{ marginBottom: 8 }}><b>{s.name}</b> <span className="mono faint">{s.catalog_id}</span> · {usd(s.unit_cost)}<div className="muted">{s.why}</div>
                <button className="btn sm" style={{ marginTop: 4 }} onClick={() => ctx.runChange({ target_entity_id: report.change.target_entity_id, replacement_id: s.catalog_id })}>Analyse this swap</button></div>)}</div>)}

          <div className="card pad">
            <h3><Gavel size={14} />Engineer review</h3>
            <div className="callout warn" style={{ marginBottom: 12 }}><AlertTriangle size={15} />Ripple never approves a change. This records your decision.</div>
            <div className="col">
              <div className="seg" role="group" aria-label="Decision">{(["approved", "needs_revision", "rejected"] as const).map((d) => <button key={d} aria-pressed={dec.decision === d} onClick={() => setDec({ ...dec, decision: d })}>{d.replace("_", " ")}</button>)}</div>
              <input className="input" placeholder="Your name" value={dec.reviewer} onChange={(e) => setDec({ ...dec, reviewer: e.target.value })} />
              <textarea className="input" rows={3} placeholder="Comments" value={dec.comments} onChange={(e) => setDec({ ...dec, comments: e.target.value })} />
              <button className="btn primary" disabled={busy || !dec.reviewer.trim()} onClick={decide}>Record decision</button>
            </div>
            {report.decisions?.length > 0 && <div className="col" style={{ marginTop: 14 }}>
              <div className="small muted">History (newest first)</div>
              {[...report.decisions].reverse().map((d: Any, i: number) => <div key={i} className="small" style={{ borderLeft: "2px solid var(--line-2)", paddingLeft: 10 }}><b>{d.decision.replace("_", " ")}</b> · {d.reviewer} <span className="faint">{new Date(d.recorded_at).toLocaleString()}</span>{d.comments && <div className="muted">{d.comments}</div>}</div>)}</div>}
          </div>

          {report.validation && <div className="card tight"><div className="row small"><ShieldCheck size={15} color={report.validation.ok ? "var(--ok)" : "var(--bad)"} /><b>{report.validation.ok ? "Report self-check passed" : "Report self-check failed"}</b></div>
            <div className="faint small" style={{ marginTop: 4 }}>{report.validation.checks.map((c: Any) => c.name).join(" · ")}</div></div>}
        </div>
      </div>
    </div>
  );
}
