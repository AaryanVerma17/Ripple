"use client";
import { useMemo } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import type { Any } from "../lib/types";

const TYPE_RING: Record<string, number> = { component: 0, subsystem: 0, requirement: 1, test: 2, document: 3 };
const TYPE_LABEL: Record<string, string> = { component: "Part", subsystem: "Subsystem", requirement: "Requirement", test: "Test", document: "Document" };

function RNode({ data }: NodeProps) {
  const d = data as Any;
  const cls = ["rnode", d.role === "changed" ? "changed" : "", d.status && d.role === "affected" ? `n-${d.status}` : "", d.dim ? "dim" : ""].join(" ");
  return (
    <div className={cls} title={d.why || d.name}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0, left: "50%", top: "50%" }} />
      <small>{d.id}{d.qty > 1 ? ` ×${d.qty}` : ""}</small>
      <b>{d.name}</b>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, left: "50%", top: "50%" }} />
    </div>
  );
}
const nodeTypes = { rnode: RNode };

export default function RippleMap({ graph, scenario, targetId, onSelect, height = 560 }: { graph: Any; scenario?: Any | null; targetId?: string; onSelect?: (id: string) => void; height?: number }) {
  const { nodes, edges } = useMemo(() => {
    const roles = new Map<string, Any>((scenario?.nodes || []).map((n: Any) => [n.entity_id, n]));
    const active = new Set<string>(scenario?.active_edges || []);
    const byRing = new Map<number, Any[]>();
    const place = (n: Any, ring: number) => { byRing.set(ring, [...(byRing.get(ring) || []), n]); };
    const maxHop = scenario ? Math.max(1, ...(scenario.nodes || []).map((n: Any) => n.hop)) : 0;
    for (const n of graph.nodes) {
      if (scenario) {
        const r = roles.get(n.id);
        place(n, r ? r.hop : maxHop + 1);
      } else place(n, TYPE_RING[n.type] ?? 3);
    }
    const radii = scenario ? [0, 190, 330, 450, 550, 640] : [130, 250, 350, 440];
    const out: Node[] = [];
    byRing.forEach((list, ring) => {
      const order = ["component", "subsystem", "requirement", "test", "document"];
      list.sort((a, b) => order.indexOf(a.type) - order.indexOf(b.type) || a.id.localeCompare(b.id));
      const r = radii[Math.min(ring, radii.length - 1)];
      list.forEach((n, i) => {
        const a = r === 0 ? 0 : (i / list.length) * Math.PI * 2 - Math.PI / 2 + ring * 0.35;
        const role = roles.get(n.id);
        out.push({
          id: n.id, type: "rnode", position: { x: Math.cos(a) * r * 1.45 - 60, y: Math.sin(a) * r * 0.9 - 20 },
          data: { id: n.id, name: n.name, qty: n.qty, role: role?.role, status: role?.status, dim: !!scenario && !role, why: role?.why?.join(" → ") || TYPE_LABEL[n.type] },
        });
      });
    });
    const eds: Edge[] = graph.edges.map((e: Any) => {
      const on = !scenario || active.has(e.id);
      return {
        id: e.id, source: e.source_id, target: e.target_id, type: "default",
        animated: false, className: scenario && on ? "pulse" : "",
        style: { stroke: scenario ? (on ? "#4fd1ff" : "var(--line)") : "var(--line-2)", strokeWidth: scenario && on ? 2.2 : 1.2, opacity: scenario && !on ? 0.35 : 0.9 },
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: scenario && on ? "#4fd1ff" : "#3a527d" },
      };
    });
    return { nodes: out, edges: eds };
  }, [graph, scenario]);

  return (
    <div className="mapbox" style={{ height }}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.04 }} minZoom={0.25} maxZoom={1.6}
        nodesDraggable proOptions={{ hideAttribution: true }} onNodeClick={(_, n) => onSelect?.(n.id)} key={scenario?.id ?? "base"}>
        <Background gap={26} size={1} color="var(--line)" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <div className="legend" style={{ position: "absolute", left: 12, bottom: 12, background: "var(--panel)", padding: "6px 10px", borderRadius: 10, border: "1px solid var(--line)" }}>
        {scenario ? (<>
          <span><i style={{ background: "var(--accent)" }} />Changed</span><span><i style={{ background: "var(--bad)" }} />Verified</span><span><i style={{ background: "var(--warn)" }} />Potential</span>
          <span><i style={{ background: "var(--unk)" }} />Unknown</span><span><i style={{ background: "var(--ok)" }} />Passes</span><span><i style={{ background: "var(--line-2)" }} />Not reached</span>
        </>) : (<span>Rings: parts · requirements · tests · documents. Click a part to start a change.</span>)}
      </div>
    </div>
  );
}
