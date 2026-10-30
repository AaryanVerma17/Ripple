"use client";
import { useEffect, useRef, useState } from "react";
import { Bot, ExternalLink, Send, User } from "lucide-react";
import { Chip, Md, VERDICT, signed, usd } from "../lib/ui";
import type { Any, Ctx } from "../lib/types";

export interface ChatMsg { role: "user" | "assistant"; text: string; card?: Any; analysisId?: string; suggestions?: string[]; pending?: boolean }

export function ChatCard({ card, onOpen }: { card: Any; onOpen: () => void }) {
  const v = VERDICT[card.verdict] || VERDICT.incomplete;
  return (
    <div className="card tight" style={{ marginTop: 10, background: "var(--bg-2)" }}>
      <div className="row wrap" style={{ justifyContent: "space-between" }}><span className={`chip ${v.cls}`}><i />{v.label}</span><span className="small muted">Risk {card.risk.score}/100</span></div>
      <div className="row small tnum" style={{ gap: 14, margin: "8px 0" }}>
        <span style={{ color: "var(--bad)" }}>{card.counts.verified_issue} verified</span><span style={{ color: "var(--warn)" }}>{card.counts.potential_issue} potential</span><span style={{ color: "var(--unk)" }}>{card.counts.unknown} unknown</span></div>
      <div className="grid g2 small" style={{ gap: 8 }}>
        {card.metrics.map((m: Any) => <div key={m.label} className="row" style={{ justifyContent: "space-between" }}><span className="muted">{m.label}</span><span className="tnum">{m.proposed == null ? "n/a" : m.unit === "USD" ? `$${Number(m.proposed.toPrecision(4))}` : `${Number(m.proposed.toPrecision(3))} ${m.unit}`}{m.requirement_status && <> <Chip status={m.requirement_status} label="" /></>}</span></div>)}
      </div>
      <div className="row small" style={{ justifyContent: "space-between", marginTop: 8 }}><span>Parts <b>{signed(card.cost.parts_delta, "USD")}</b>/unit · effort ≈ {usd(card.cost.labour_total)}</span>
        <button className="btn sm" onClick={onOpen}><ExternalLink size={13} />Full report</button></div>
    </div>
  );
}

export default function ChatView({ ctx, msgs, setMsgs, lastId, setLastId, pendingText, clearPending }:
  { ctx: Ctx; msgs: ChatMsg[]; setMsgs: (f: (m: ChatMsg[]) => ChatMsg[]) => void; lastId: string | null; setLastId: (s: string) => void; pendingText: string | null; clearPending: () => void }) {
  const [text, setText] = useState(""); const [busy, setBusy] = useState(false); const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);

  const send = async (t: string) => {
    t = t.trim(); if (!t || busy) return;
    setText(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: t }, { role: "assistant", text: "", pending: true }]);
    const history = msgs.filter((m) => !m.pending).slice(-6).map((m) => ({ role: m.role, content: m.text.slice(0, 1500) }));
    try {
      const r = await (await import("../lib/api")).api.chat({ message: t, analysis_id: lastId, context_entity_id: ctx.report?.change?.target_entity_id, history });
      if (r.analysis_id) setLastId(r.analysis_id);
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "assistant", text: r.reply, card: r.card, analysisId: r.kind === "analysis" ? r.analysis_id : undefined, suggestions: r.suggestions }]);
    } catch (e: any) {
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "assistant", text: `**Something went wrong.** ${e.message}` }]);
    } finally { setBusy(false); }
  };
  useEffect(() => { if (pendingText) { send(pendingText); clearPending(); } }, [pendingText]); // eslint-disable-line
  const open = async (id: string) => { const a = await (await import("../lib/api")).api.analysis(id); ctx.setReport(a); ctx.go("analyze"); };
  const starters = ["What if the motor is 24 V?", "What if I swap the battery for BAT-ALT-24?", "What if the chassis is 0.5 kg lighter?", "What if the battery capacity doubles?"];
  const last = msgs[msgs.length - 1];

  return (
    <div className="card pad chat">
      <div className="msgs" aria-live="polite">
        {msgs.length === 0 && (<div className="col" style={{ margin: "auto", textAlign: "center", justifyItems: "center", padding: 24 }}>
          <Bot size={34} color="var(--accent)" /><h2 style={{ fontSize: 18 }}>Ask “what if…” about any part</h2>
          <div className="muted" style={{ maxWidth: 460 }}>Every answer runs the real analysis. The numbers come from the engine, and the wording is checked against them.</div>
          <div className="suggest" style={{ justifyContent: "center" }}>{starters.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}</div></div>)}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="row small faint" style={{ marginBottom: 4 }}>{m.role === "user" ? <User size={13} /> : <Bot size={13} />}{m.role === "user" ? "You" : "Ripple"}</div>
            {m.pending ? <div className="typing" aria-label="Thinking"><span /><span /><span /></div> : <Md text={m.text} />}
            {m.card && m.analysisId && <ChatCard card={m.card} onOpen={() => open(m.analysisId!)} />}
          </div>))}
        <div ref={end} />
      </div>
      <div className="col" style={{ gap: 8, paddingTop: 8, borderTop: "1px solid var(--line)" }}>
        {last && !last.pending && last.suggestions && <div className="suggest">{last.suggestions.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}</div>}
        <form className="row" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="What if the motor is 24 V?" maxLength={1000} aria-label="Ask a what-if question" />
          <button className="btn primary" disabled={busy || !text.trim()}><Send size={15} />Send</button>
        </form>
      </div>
    </div>
  );
}
