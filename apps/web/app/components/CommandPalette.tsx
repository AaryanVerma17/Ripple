"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
export interface Cmd { id: string; label: string; hint?: string; icon?: ReactNode; run: () => void }
export default function CommandPalette({ open, onClose, cmds }: { open: boolean; onClose: () => void; cmds: Cmd[] }) {
  const [q, setQ] = useState(""); const [i, setI] = useState(0); const ref = useRef<HTMLInputElement>(null);
  const list = useMemo(() => cmds.filter((c) => (c.label + " " + (c.hint || "")).toLowerCase().includes(q.toLowerCase())).slice(0, 30), [cmds, q]);
  useEffect(() => { if (open) { setQ(""); setI(0); setTimeout(() => ref.current?.focus(), 20); } }, [open]);
  useEffect(() => setI(0), [q]);
  if (!open) return null;
  const go = (c?: Cmd) => { if (c) { onClose(); c.run(); } };
  return (
    <div className="overlay" onMouseDown={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="card palette" onMouseDown={(e) => e.stopPropagation()}>
        <input ref={ref} className="input" placeholder="Jump to a view, a part, or run a what-if…" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(x + 1, list.length - 1)); } else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); } else if (e.key === "Enter") go(list[i]); else if (e.key === "Escape") onClose(); }} />
        <ul>{list.map((c, k) => <li key={c.id}><button data-active={k === i} onMouseEnter={() => setI(k)} onClick={() => go(c)}>{c.icon}<span>{c.label}</span><span className="faint small" style={{ marginLeft: "auto" }}>{c.hint}</span></button></li>)}
          {list.length === 0 && <li className="faint small" style={{ padding: 14 }}>No matches.</li>}</ul>
      </div>
    </div>
  );
}
