/**
 * Cliente SSE sobre fetch: permite enviar Authorization (EventSource no admite cabeceras) y
 * reanudar con Last-Event-ID tras una desconexión, sin perder eventos.
 */
import { API_URL, getToken } from "./api";

export interface StreamEvent { id: number; type: string; data: { type: string; payload: Record<string, unknown>; at: string } | { status: string } }
export type ConnState = "connecting" | "live" | "reconnecting" | "closed";

export function openJobStream(
  jobId: string,
  startAfter: number,
  onEvent: (e: StreamEvent) => void,
  onState: (s: ConnState) => void,
  onResync: () => void,
): () => void {
  let lastId = startAfter;
  let stopped = false;
  let ctrl: AbortController | null = null;
  let attempt = 0;

  const run = async () => {
    while (!stopped) {
      ctrl = new AbortController();
      onState(attempt === 0 ? "connecting" : "reconnecting");
      try {
        const token = await getToken();
        const res = await fetch(`${API_URL}/api/v1/training-jobs/${jobId}/events?after=${lastId}`, {
          headers: { Accept: "text/event-stream", ...(token ? { Authorization: `Bearer ${token}` } : {}), "Last-Event-ID": String(lastId) },
          signal: ctrl.signal,
          cache: "no-store",
        });
        if (!res.ok || !res.body) throw new Error(`SSE ${res.status}`);
        if (attempt > 0) onResync(); // REST es la fuente de verdad: refrescar estado al reconectar
        attempt = 0;
        onState("live");
        const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
        let buf = "";
        let ended = false;
        while (!stopped) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += value;
          let sep: number;
          while ((sep = buf.indexOf("\n\n")) >= 0) {
            const chunk = buf.slice(0, sep);
            buf = buf.slice(sep + 2);
            let id: number | null = null, type = "message", data = "";
            for (const line of chunk.split("\n")) {
              if (line.startsWith("id: ")) id = Number(line.slice(4));
              else if (line.startsWith("event: ")) type = line.slice(7);
              else if (line.startsWith("data: ")) data += line.slice(6);
            }
            if (!data) continue;
            if (id !== null) lastId = id;
            if (type === "end") ended = true;
            try { onEvent({ id: id ?? lastId, type, data: JSON.parse(data) }); } catch { /* evento malformado */ }
          }
        }
        if (ended) { onState("closed"); return; }
      } catch (err) {
        if (stopped) return;
      }
      attempt += 1;
      await new Promise((r) => setTimeout(r, Math.min(10000, 800 * 2 ** Math.min(attempt, 4))));
    }
  };
  run();
  return () => { stopped = true; ctrl?.abort(); onState("closed"); };
}
