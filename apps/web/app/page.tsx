"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Camera, ClipboardList, Command, FlaskConical, History as HistoryIcon, LayoutDashboard, MessageSquareText, Moon, Network, Sun, Zap } from "lucide-react";
import RippleMap from "./components/RippleMap";
import AnalyzeView from "./components/AnalyzeView";
import CameraView from "./components/CameraView";
import ChatView, { ChatMsg } from "./components/ChatView";
import PartsView from "./components/PartsView";
import HistoryView from "./components/HistoryView";
import CommandPalette, { Cmd } from "./components/CommandPalette";
import { api } from "./lib/api";
import { Chip, Skeleton, ToastProvider, num, usd, useToast } from "./lib/ui";
import type { Any, Ctx, View } from "./lib/types";

const NAV: { id: View; label: string; icon: any; title: string; sub: string }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, title: "Rover Alpha", sub: "The product as recorded, and how its parts depend on each other." },
  { id: "analyze", label: "Analyse", icon: FlaskConical, title: "Change analysis", sub: "Describe a change and see what it touches, breaks and costs." },
  { id: "camera", label: "Camera", icon: Camera, title: "Identify a part from a photo", sub: "Photograph a component and see what swapping it in would mean." },
  { id: "chat", label: "What-if chat", icon: MessageSquareText, title: "What-if chat", sub: "Ask in plain language. Every answer runs the real analysis." },
  { id: "parts", label: "Parts & data", icon: ClipboardList, title: "Parts, cost and data", sub: "Bill of materials, catalogue, and the gaps in the recorded data." },
  { id: "history", label: "History", icon: HistoryIcon, title: "History", sub: "Every analysis, with its review decisions." },
];

function Shell() {
  const toast = useToast();
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<{ project?: Any; graph?: Any; bom?: Any; catalog?: Any[]; config?: Any; history?: Any[] }>({});
  const [report, setReport] = useState<Any | null>(null); const [lastRequest, setLastRequest] = useState<Any | null>(null);
  const [loadingReport, setLoadingReport] = useState(false); const [preset, setPreset] = useState<Any | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]); const [chatId, setChatId] = useState<string | null>(null); const [pendingChat, setPendingChat] = useState<string | null>(null);
  const [theme, setTheme] = useState("dark"); const [palette, setPalette] = useState(false); const [offline, setOffline] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [project, graph, bom, catalog, config, history] = await Promise.all([api.project(), api.graph(), api.bom(), api.catalog(), api.config(), api.history()]);
      setData({ project, graph, bom, catalog, config, history }); setOffline(null);
    } catch (e: any) { setOffline(e.message); }
  }, []);
  useEffect(() => { load(); setTheme(document.documentElement.dataset.theme || "dark"); }, [load]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); } };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, []);
  const toggleTheme = () => { const t = theme === "dark" ? "light" : "dark"; setTheme(t); document.documentElement.dataset.theme = t; try { localStorage.setItem("ripple-theme", t); } catch {} };

  const runChange = useCallback(async (body: Any) => {
    setLoadingReport(true); setView("analyze");
    try {
      const r = await api.change(body); setReport(r); setLastRequest(body); setChatId(r.analysis_id);
      api.history().then((h) => setData((d) => ({ ...d, history: h }))); api.bom().then((b) => setData((d) => ({ ...d, bom: b })));
      toast(`Analysis ${r.analysis_id} ready`, "ok"); return r;
    } catch (e: any) { toast(e.message, "err"); return null; } finally { setLoadingReport(false); }
  }, [toast]);

  const entities = data.graph?.nodes || [];
  const ctx: Ctx | null = data.project ? {
    project: data.project, graph: data.graph, bom: data.bom, catalog: data.catalog || [], config: data.config, report, setReport, go: setView, runChange,
    refresh: load, entities, lastRequest, preset, setPreset, sendChat: (t: string) => { setPendingChat(t); setView("chat"); },
  } : null;

  const cmds: Cmd[] = useMemo(() => {
    const c: Cmd[] = NAV.map((n) => ({ id: n.id, label: `Go to ${n.label}`, icon: <n.icon size={15} />, run: () => setView(n.id) }));
    c.push({ id: "theme", label: "Toggle light / dark theme", run: toggleTheme, icon: theme === "dark" ? <Sun size={15} /> : <Moon size={15} /> });
    entities.filter((e: Any) => e.type === "component").forEach((e: Any) => c.push({ id: "p" + e.id, label: `Change ${e.name}`, hint: e.id, icon: <Network size={15} />, run: () => { setPreset({ target: e.id }); setView("analyze"); } }));
    ["What if the motor is 24 V?", "What if the chassis is 0.5 kg lighter?", "What if battery capacity doubles?"].forEach((q, i) => c.push({ id: "q" + i, label: q, hint: "ask", icon: <MessageSquareText size={15} />, run: () => { setPendingChat(q); setView("chat"); } }));
    return c;
  }, [entities, theme]); // eslint-disable-line

  const meta = NAV.find((n) => n.id === view)!;
  const cfg = data.config;

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><div className="brand-mark"><Activity size={17} strokeWidth={2.6} /></div><div><b>Ripple</b><small>Change impact agent</small></div></div>
        {NAV.map((n) => <button key={n.id} className="nav" aria-current={view === n.id ? "page" : undefined} onClick={() => setView(n.id)}><n.icon size={17} /><span className="lbl">{n.label}</span>
          {n.id === "history" && !!data.history?.length && <span className="badge">{data.history.length}</span>}</button>)}
        <div className="side-foot">
          <button className="btn sm" onClick={() => setPalette(true)}><Command size={13} />Quick actions <span className="kbd" style={{ marginLeft: "auto" }}>Ctrl K</span></button>
          <div className="row wrap"><span className={`pill ${cfg?.text_ai ? "on" : ""}`}><span className="dot" />Text AI</span><span className={`pill ${cfg?.vision !== "off" && cfg ? "on" : ""}`}><span className="dot" />Vision</span></div>
          <button className="btn sm ghost" onClick={toggleTheme}>{theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}{theme === "dark" ? "Light" : "Dark"} theme</button>
          <div className="faint small">Fictional sample data. Ripple suggests; engineers decide.</div>
        </div>
      </aside>
      <main className="main">
        <div className="topbar"><div><h1>{meta.title}</h1><p>{meta.sub}</p></div><div className="spacer" />
          <button className="btn noprint" onClick={() => setPalette(true)}><Command size={14} />Search</button></div>
        {offline && <div className="callout bad" style={{ marginBottom: 16 }}><Zap size={16} /><div>{offline} <button className="btn sm" onClick={load}>Retry</button></div></div>}
        {!ctx ? (!offline && <div className="grid g4"><Skeleton h={90} /><Skeleton h={90} /><Skeleton h={90} /><Skeleton h={90} /></div>) : (
          <div key={view} className="fade-in">
            {view === "overview" && <Overview ctx={ctx} history={data.history || []} />}
            {view === "analyze" && <AnalyzeView ctx={ctx} loading={loadingReport} />}
            {view === "camera" && <CameraView ctx={ctx} />}
            {view === "chat" && <ChatView ctx={ctx} msgs={msgs} setMsgs={(f) => setMsgs(f)} lastId={chatId} setLastId={setChatId} pendingText={pendingChat} clearPending={() => setPendingChat(null)} />}
            {view === "parts" && <PartsView ctx={ctx} />}
            {view === "history" && <HistoryView items={data.history || null} ctx={ctx} />}
          </div>)}
      </main>
      <CommandPalette open={palette} onClose={() => setPalette(false)} cmds={cmds} />
    </div>
  );
}

function Overview({ ctx, history }: { ctx: Ctx; history: Any[] }) {
  const m = ctx.bom.metrics; const tiles = [
    { k: "top_speed_mps", u: "m/s", req: "REQ-SPD-01" }, { k: "runtime_h", u: "h", req: "REQ-RUN-01" }, { k: "total_mass_kg", u: "kg", req: "REQ-MASS-01" }, { k: "bom_cost_usd", u: "USD", req: "REQ-COST-01" },
  ];
  const reqs: Record<string, Any> = Object.fromEntries(ctx.entities.filter((e: Any) => e.type === "requirement").map((e: Any) => [e.id, e]));
  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="grid g4">
        {tiles.map((t) => { const x = m[t.k]; const r = reqs[t.req]; return (
          <div key={t.k} className="card pad"><div className="stat"><span>{x?.label}</span><b>{x?.value == null ? "—" : num(x.value, t.u === "USD" ? "USD" : "")}{t.u !== "USD" && x?.value != null && <small style={{ fontSize: 13, color: "var(--faint)" }}> {t.u}</small>}</b>
            <span className="small faint">{r ? `${r.operator} ${r.threshold} ${r.unit}` : ""}</span></div></div>); })}
      </div>
      <div className="split">
        <div className="card pad"><h3><Network size={14} />Dependency map</h3>
          <RippleMap graph={ctx.graph} height={520} onSelect={(id) => { const e = ctx.entities.find((x: Any) => x.id === id); if (e?.type === "component") { ctx.setPreset({ target: id }); ctx.go("analyze"); } }} /></div>
        <div className="col" style={{ gap: 16 }}>
          <div className="card pad"><h3>Start here</h3><div className="col">
            <button className="btn primary" onClick={() => ctx.go("analyze")}><FlaskConical size={15} />Analyse a change</button>
            <button className="btn" onClick={() => ctx.go("camera")}><Camera size={15} />Identify a part from a photo</button>
            <button className="btn" onClick={() => ctx.sendChat("What if the motor is 24 V?")}><MessageSquareText size={15} />Ask “what if the motor is 24 V?”</button></div></div>
          <div className="card pad"><h3>Requirements</h3>{Object.values(reqs).map((r: Any) => <div key={r.id} className="small" style={{ marginBottom: 8 }}><div className="row" style={{ justifyContent: "space-between" }}><b className="mono">{r.id}</b></div><div className="muted">{r.statement}</div></div>)}</div>
          <div className="card pad"><h3>Recent</h3>{history.length === 0 ? <div className="muted small">No analyses yet.</div> : history.slice(0, 4).map((h) => <button key={h.analysis_id} className="nav" onClick={async () => { ctx.setReport(await api.analysis(h.analysis_id)); ctx.go("analyze"); }}><span className="small" style={{ flex: 1 }}>{h.change_summary}</span></button>)}</div>
        </div>
      </div>
    </div>
  );
}

export default function Page() { return <ToastProvider><Shell /></ToastProvider>; }
