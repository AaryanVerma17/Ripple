"use client";
import { useState } from "react";
import { Download, History, Search } from "lucide-react";
import { api } from "../lib/api";
import { Chip, Empty, Skeleton, useToast } from "../lib/ui";
import type { Any, Ctx } from "../lib/types";

export default function HistoryView({ items, ctx }: { items: Any[] | null; ctx: Ctx }) {
  const [q, setQ] = useState(""); const [kind, setKind] = useState("all"); const toast = useToast();
  if (!items) return <Skeleton h={240} />;
  const list = items.filter((i) => (kind === "all" || i.kind === kind) && (i.change_summary || "").toLowerCase().includes(q.toLowerCase()));
  const open = async (id: string) => { try { ctx.setReport(await api.analysis(id)); ctx.go("analyze"); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div className="card pad">
      <div className="row wrap" style={{ marginBottom: 14 }}>
        <div style={{ position: "relative", flex: 1, minWidth: 220 }}><Search size={14} style={{ position: "absolute", left: 12, top: 12, color: "var(--faint)" }} /><input className="input" style={{ paddingLeft: 34 }} placeholder="Search changes" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="seg">{["all", "analysis", "whatif"].map((k) => <button key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>{k === "whatif" ? "what-if" : k}</button>)}</div>
      </div>
      {list.length === 0 ? <Empty icon={<History size={30} />} title="Nothing here yet">Run an analysis or a what-if and it will show up with its review status.</Empty> :
        <table className="t"><thead><tr><th>When</th><th>Change</th><th>Result</th><th>Risk</th><th>Review</th><th /></tr></thead>
          <tbody>{list.map((i) => <tr key={i.analysis_id}><td className="small muted">{new Date(i.created_at).toLocaleString()}<div className="mono faint">{i.analysis_id}</div></td>
            <td style={{ maxWidth: 380 }}>{i.change_summary} {i.kind === "whatif" && <span className="chip s-neutral">what-if</span>}</td>
            <td className="small tnum"><span style={{ color: "var(--bad)" }}>{i.counts?.verified_issue ?? 0}</span> · <span style={{ color: "var(--warn)" }}>{i.counts?.potential_issue ?? 0}</span> · <span style={{ color: "var(--unk)" }}>{i.counts?.unknown ?? 0}</span></td>
            <td className="tnum">{i.risk?.score ?? "—"}</td>
            <td>{i.review_decision ? <><Chip status={i.review_decision.decision === "approved" ? "no_violation_found" : i.review_decision.decision === "rejected" ? "verified_issue" : "potential_issue"} label={i.review_decision.decision.replace("_", " ")} /><div className="faint small">{i.review_decision.reviewer}{i.decision_count > 1 ? ` · ${i.decision_count} decisions` : ""}</div></> : <span className="faint small">Not recorded</span>}</td>
            <td className="num" style={{ whiteSpace: "nowrap" }}><button className="btn sm" onClick={() => open(i.analysis_id)}>Open</button> <a className="btn sm ghost" href={api.exportUrl(i.analysis_id)} download aria-label="Export Markdown"><Download size={13} /></a></td></tr>)}</tbody></table>}
    </div>
  );
}
