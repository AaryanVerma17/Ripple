export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const PID = "ROVER-ALPHA";
const P = `${API}/api/v1/projects/${PID}`;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(url, init); }
  catch { throw new ApiError("Can't reach the Ripple API. Is it running on port 8000?", 0); }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.json(); const d = j.detail; msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join("; ") : msg; } catch {}
    throw new ApiError(msg, res.status);
  }
  return res.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  config: () => req<any>(`${API}/api/v1/config`),
  project: () => req<any>(P),
  graph: () => req<any>(`${P}/graph`),
  bom: () => req<any>(`${P}/bom`),
  catalog: () => req<any[]>(`${P}/catalog`),
  audit: () => req<any>(`${P}/audit`),
  history: () => req<any[]>(`${P}/history`),
  analysis: (id: string) => req<any>(`${API}/api/v1/analyses/${id}`),
  change: (body: any) => req<any>(`${P}/changes`, json(body)),
  decide: (id: string, body: any) => req<any>(`${API}/api/v1/analyses/${id}/decision`, json(body)),
  supply: (body: any) => req<any>(`${P}/parameters`, json(body)),
  resetSupplied: () => req<any>(`${P}/parameters`, { method: "DELETE" }),
  chat: (body: any) => req<any>(`${P}/chat`, json(body)),
  identify: (file: Blob, hint: string) => { const f = new FormData(); f.append("image", file, "photo.jpg"); f.append("hint", hint); return req<any>(`${P}/vision/identify`, { method: "POST", body: f }); },
  exportUrl: (id: string) => `${API}/api/v1/analyses/${id}/export.md`,
};
