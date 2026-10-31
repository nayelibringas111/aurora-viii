import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { openJobStream, type ConnState } from "@/lib/sse";
import type { EpochMetrics, JobDetail, Snapshot, Topology } from "@/types";

export interface LogLine { id: number; at: string; text: string; tone?: "error" | "ok" | "info" }
export interface Live { epoch: number; step: number; steps: number; progress: number; loss?: number; accuracy?: number; d_loss?: number; g_loss?: number }

const TERMINAL = ["COMPLETED", "FAILED", "CANCELLED"];

/** Estado de un entrenamiento: REST como fuente de verdad + SSE para empujar cambios. */
export function useJobStream(jobId: string) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [epochs, setEpochs] = useState<EpochMetrics[]>([]);
  const [live, setLive] = useState<Live | null>(null);
  const [conn, setConn] = useState<ConnState>("connecting");
  const [log, setLog] = useState<LogLine[]>([]);
  const stopRef = useRef<() => void>(() => {});

  const addLog = (l: LogLine) => setLog((prev) => [l, ...prev].slice(0, 60));
  const mergeEpochs = (rows: EpochMetrics[]) =>
    setEpochs((prev) => {
      const m = new Map(prev.map((r) => [r.epoch, r]));
      rows.forEach((r) => m.set(r.epoch, { ...m.get(r.epoch), ...r }));
      return [...m.values()].sort((a, b) => a.epoch - b.epoch);
    });

  const resync = useCallback(async () => {
    try {
      const [j, m] = await Promise.all([api.get<JobDetail>(`/training-jobs/${jobId}`), api.get<{ epochs: EpochMetrics[] }>(`/training-jobs/${jobId}/metrics`)]);
      setJob(j);
      if (j.topology) setTopology((t) => t ?? j.topology);
      if (j.snapshot) setSnapshot((s) => s ?? j.snapshot);
      mergeEpochs(m.epochs);
      return j;
    } catch (e) {
      setError(e);
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    let alive = true;
    setJob(null); setTopology(null); setSnapshot(null); setEpochs([]); setLog([]); setLive(null);
    (async () => {
      const j = await resync();
      if (!alive || !j) return;
      if (j.snapshot) setSnapshot(j.snapshot);
      if (TERMINAL.includes(j.status)) { setConn("closed"); return; }
      stopRef.current = openJobStream(jobId, j.last_event_id, (ev) => {
        const d = ev.data as { payload: Record<string, unknown>; at: string };
        const p = d.payload ?? {};
        switch (ev.type) {
          case "status": {
            const to = p.to as JobDetail["status"];
            setJob((cur) => (cur ? { ...cur, status: to, status_label: String(p.label ?? to), error_message: (p.error as string) ?? cur.error_message,
              attempt: p.attempt != null ? Number(p.attempt) : cur.attempt } : cur));
            addLog({ id: ev.id, at: d.at, text: `Estado: ${p.label}${p.reason ? ` (${p.reason})` : ""}${p.error ? ` · ${p.error}` : ""}`, tone: to === "FAILED" ? "error" : to === "COMPLETED" ? "ok" : "info" });
            if (TERMINAL.includes(to)) setTimeout(resync, 300);
            break;
          }
          case "topology": setTopology(p as unknown as Topology); addLog({ id: ev.id, at: d.at, text: "Modelo Keras construido y compilado" }); break;
          case "snapshot": setSnapshot(p as unknown as Snapshot); break;
          case "progress":
            setLive(p as unknown as Live);
            setJob((cur) => (cur ? { ...cur, progress: Number(p.progress) } : cur));
            break;
          case "epoch": {
            const m = p.metrics as Record<string, number>;
            mergeEpochs([{ epoch: Number(p.epoch), ...m }]);
            setJob((cur) => (cur ? { ...cur, current_epoch: Number(p.epoch), progress: Number(p.progress) } : cur));
            const main = m.loss != null ? `pérdida ${m.loss.toFixed(4)}${m.val_accuracy != null ? ` · exactitud val. ${(m.val_accuracy * 100).toFixed(1)} %` : ""}` : `D ${m.d_loss?.toFixed(3)} · G ${m.g_loss?.toFixed(3)}`;
            addLog({ id: ev.id, at: d.at, text: `Época ${p.epoch}/${p.total}: ${main}` });
            break;
          }
          case "cancel_requested": addLog({ id: ev.id, at: d.at, text: "Cancelación solicitada; el worker la confirmará al terminar el lote" }); setJob((c) => (c ? { ...c, cancel_requested: true } : c)); break;
          case "end": setTimeout(resync, 200); break;
        }
      }, setConn, () => { resync(); });
    })();
    return () => { alive = false; stopRef.current(); };
  }, [jobId, resync]);

  return { job, error, topology, snapshot, epochs, live, conn, log, resync, setJob };
}
