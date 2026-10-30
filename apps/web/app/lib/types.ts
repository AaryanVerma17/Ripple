// Deliberately loose: the API is the source of truth and the engine adds fields over time.
export type Any = any;
export type View = "overview" | "analyze" | "camera" | "chat" | "parts" | "history";
export interface Ctx {
  project: Any; graph: Any; bom: Any; catalog: Any[]; config: Any;
  report: Any | null; setReport: (r: Any | null) => void; go: (v: View) => void;
  runChange: (body: Any) => Promise<Any | null>; refresh: () => Promise<void>;
  entities: Any[]; lastRequest: Any | null; preset: Any | null; setPreset: (p: Any | null) => void; sendChat: (text: string) => void;
}
