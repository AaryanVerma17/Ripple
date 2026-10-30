"use client";
import { useEffect, useRef, useState } from "react";
import { Camera, ImageUp, Loader2, ScanSearch, Video, X, TriangleAlert } from "lucide-react";
import { api } from "../lib/api";
import { Chip, num, signed, usd, useToast } from "../lib/ui";
import type { Any, Ctx } from "../lib/types";

async function downscale(src: Blob, max = 1280): Promise<Blob> {
  const bmp = await createImageBitmap(src);
  const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas"); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
  c.getContext("2d")!.drawImage(bmp, 0, 0, c.width, c.height);
  return new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("Couldn't prepare the image"))), "image/jpeg", 0.85));
}

export default function CameraView({ ctx }: { ctx: Ctx }) {
  const [file, setFile] = useState<Blob | null>(null); const [url, setUrl] = useState<string | null>(null);
  const [hint, setHint] = useState(""); const [busy, setBusy] = useState(false); const [res, setRes] = useState<Any | null>(null); const [err, setErr] = useState<string | null>(null);
  const [cam, setCam] = useState(false); const [over, setOver] = useState(false);
  const video = useRef<HTMLVideoElement>(null); const stream = useRef<MediaStream | null>(null); const toast = useToast();
  const stop = () => { stream.current?.getTracks().forEach((t) => t.stop()); stream.current = null; setCam(false); };
  useEffect(() => stop, []);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const take = (b: Blob) => { setFile(b); setUrl(URL.createObjectURL(b)); setRes(null); setErr(null); };
  const onFile = async (f?: File | null) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) { toast("Please choose an image file.", "err"); return; }
    try { take(await downscale(f)); } catch { toast("That image couldn't be read.", "err"); }
  };
  const startCam = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      stream.current = s; setCam(true); setTimeout(() => { if (video.current) { video.current.srcObject = s; video.current.play(); } }, 30);
    } catch { toast("Camera access was blocked. Upload a photo instead.", "err"); }
  };
  const snap = async () => {
    const v = video.current; if (!v) return;
    const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight; c.getContext("2d")!.drawImage(v, 0, 0);
    c.toBlob(async (b) => { if (b) take(await downscale(b)); stop(); }, "image/jpeg", 0.9);
  };
  const identify = async () => {
    if (!file) return; setBusy(true); setErr(null);
    try { setRes(await api.identify(file, hint)); } catch (e: any) { setErr(e.message); setRes(null); } finally { setBusy(false); }
  };
  const analyse = async (req: Any) => { const r = await ctx.runChange(req); if (r) ctx.go("analyze"); };
  const r = res?.read;
  const cur = res?.target?.current_unit_cost;

  return (
    <div className="split">
      <div className="col" style={{ gap: 16 }}>
        <div className="card pad">
          <h3><Camera size={14} />Photograph a part</h3>
          {cam ? (
            <div className="preview"><video ref={video} playsInline muted /><div className="row" style={{ position: "absolute", bottom: 10, left: 0, right: 0, justifyContent: "center" }}>
              <button className="btn primary" onClick={snap}><Camera size={15} />Capture</button><button className="btn" onClick={stop}><X size={15} />Cancel</button></div></div>
          ) : url ? (
            <div className="preview"><img src={url} alt="Part to identify" />{busy && <div className="scanline" />}
              <button className="btn icon sm" style={{ position: "absolute", top: 10, right: 10 }} aria-label="Remove photo" onClick={() => { setFile(null); setUrl(null); setRes(null); }}><X size={14} /></button></div>
          ) : (
            <label className={`drop ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]); }} style={{ cursor: "pointer" }}>
              <div><ImageUp size={34} color="var(--accent)" /><div style={{ fontWeight: 600, margin: "8px 0 4px" }}>Drop a photo here, or click to choose</div>
                <div className="muted small">JPEG, PNG or WebP · the part, ideally with its label visible</div></div>
              <input type="file" accept="image/*" capture="environment" hidden onChange={(e) => onFile(e.target.files?.[0])} />
            </label>)}
          <div className="row wrap" style={{ marginTop: 14 }}>
            {!cam && <button className="btn" onClick={startCam}><Video size={15} />Use webcam</button>}
            <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Optional hint, e.g. “this is the new motor”" value={hint} onChange={(e) => setHint(e.target.value)} maxLength={200} />
            <button className="btn primary" disabled={!file || busy} onClick={identify}>{busy ? <Loader2 size={15} className="spin" /> : <ScanSearch size={15} />}{busy ? "Reading…" : "Identify & analyse"}</button>
          </div>
          <div className="faint small" style={{ marginTop: 10 }}>Photos are resized in your browser, sent to the model once, and not stored.</div>
        </div>
        {err && <div className="callout bad"><TriangleAlert size={16} /><div>{err}{ctx.config?.vision === "off" && <div style={{ marginTop: 4 }}>Add <code>GEMINI_API_KEY</code> to <code>.env</code> and restart to turn photo reading on. Until then you can pick the part by hand in <b>Analyse</b>.</div>}</div></div>}
      </div>

      <div className="col" style={{ gap: 16 }}>
        {!res && !err && <div className="card pad muted">Upload or capture a photo of a part. Gemini reads what it is and any printed label. Ripple matches it to the project, then shows what swapping it in would break, cost and require.</div>}
        {res && (<>
          <div className="card pad fade-in">
            <h3><ScanSearch size={14} />What the model saw</h3>
            <div style={{ fontWeight: 600, fontSize: 16 }}>{r.component_type || "Unidentified part"}</div>
            <div className="muted" style={{ margin: "4px 0 10px" }}>{r.description}</div>
            <div className="row wrap" style={{ marginBottom: 10 }}>{r.category ? <span className="chip s-review_required"><i />{r.category}</span> : <span className="chip s-unknown"><i />Not in this project</span>}
              {r.confidence != null && <span className="pill">{Math.round(r.confidence * 100)}% confident</span>}<span className="pill mono">{res.provider}</span></div>
            {r.visible_text.length > 0 && <div className="small" style={{ marginBottom: 8 }}><span className="muted">Printed text: </span>{r.visible_text.map((t: string, i: number) => <span key={i} className="ev">{t}</span>)}</div>}
            {r.label_specs.length > 0 && <div className="small"><div className="muted">Values read from the label <Chip status="unknown" label="unverified" /></div>{r.label_specs.map((s: Any, i: number) => <div key={i}>{s.label}: <b>{num(s.value, s.unit)}</b></div>)}</div>}
            {r.condition_notes && <div className="small muted" style={{ marginTop: 8 }}>Condition: {r.condition_notes}</div>}
            {res.notes.map((n: string, i: number) => <div key={i} className="callout warn" style={{ marginTop: 10 }}><TriangleAlert size={15} />{n}</div>)}
          </div>

          {res.target && (<div className="card pad fade-in">
            <h3>Replacing the {res.target.name.toLowerCase()} <span className="mono faint">{res.target.entity_id}</span></h3>
            <div className="small muted" style={{ marginBottom: 10 }}>Currently {usd(cur)} each × {res.target.qty}</div>
            <div className="col">
              {res.changes.map((c: Any, i: number) => (<div key={i} className="finding f-no_violation_found"><div>{c.label}</div>
                {c.unit_cost != null && <div className="small muted">{usd(c.unit_cost)} each · {signed((c.unit_cost - cur) * res.target.qty, "USD")} for {res.target.qty}</div>}
                <button className="btn primary sm" style={{ justifySelf: "start" }} onClick={() => analyse(c.request)}>Analyse this change</button></div>))}
              {res.changes.length === 0 && <div className="muted small">Nothing in the photo maps to a catalogue part or a recorded value. Pick one of the options below.</div>}
            </div>
            {res.candidates.length > 0 && (<><div className="small muted" style={{ margin: "14px 0 6px" }}>Other catalogue options for this slot</div>
              <table className="t"><tbody>{res.candidates.map((c: Any) => <tr key={c.id}><td><b>{c.name}</b><div className="mono faint small">{c.id}</div></td><td className="num">{usd(c.unit_cost)}</td><td className="num"><button className="btn sm" onClick={() => analyse(c.request)}>Analyse</button></td></tr>)}</tbody></table></>)}
          </div>)}
        </>)}
      </div>
    </div>
  );
}
