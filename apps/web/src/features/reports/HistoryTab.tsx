import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { IconDownload } from "@/components/Icons";
import { Empty, ErrorBox, Loading, useToast } from "@/components/ui";
import { api, download, errorText } from "@/lib/api";
import { fmtDate, fmtNum, fmtPct } from "@/lib/format";
import type { AuditEvent, Project } from "@/types";

interface HistoryRow { job_id: string; fecha: string; arquitectura: string; familia: string; dataset: string; estado: string; epocas: number; epocas_totales: number; optimizador: string; learning_rate: number; batch_size: number; duracion_s: number | null; test_loss: number | null; test_accuracy: number | null; modelo_version: number | null }
interface CompareItem { job_id: string; label: string; family: string; evaluation: Record<string, number>; total_params: number; epochs: { epoch: number; [k: string]: number }[] }
const PALETTE = ["#0e8a8c", "#6d4fd6", "#d99a0b", "#c4384a", "#2e6fd8"];

export function HistoryTab({ project }: { project: Project }) {
  const toast = useToast();
  const report = useQuery({ queryKey: ["report", project.id], queryFn: () => api.get<{ history: HistoryRow[] }>(`/projects/${project.id}/report`) });
  const [picked, setPicked] = useState<string[]>([]);
  const [metric, setMetric] = useState("val_accuracy");
  const cmp = useQuery({
    queryKey: ["compare", project.id, picked], enabled: picked.length > 0,
    queryFn: () => api.get<CompareItem[]>(`/projects/${project.id}/compare?jobs=${picked.join(",")}`),
  });
  const canAudit = project.my_permissions.includes("view_audit");
  const audit = useQuery({ queryKey: ["audit", project.id], enabled: canAudit, queryFn: () => api.get<AuditEvent[]>(`/projects/${project.id}/audit-events?limit=60`) });
  const canExport = project.my_permissions.includes("export");

  const exp = async (kind: "csv" | "pdf") => {
    try { await download(kind === "csv" ? `/projects/${project.id}/export.csv` : `/projects/${project.id}/report.pdf`, `aurora-viii.${kind}`); }
    catch (e) { toast.show(errorText(e)); }
  };

  if (report.isLoading) return <Loading />;
  if (report.error) return <ErrorBox error={report.error} />;
  const rows = report.data!.history;
  const chartData = (() => {
    const m = new Map<number, Record<string, number>>();
    cmp.data?.forEach((c, i) => c.epochs.forEach((e) => { const r = m.get(e.epoch) ?? { epoch: e.epoch }; if (e[metric] != null) r[`s${i}`] = e[metric]; m.set(e.epoch, r); }));
    return [...m.values()].sort((a, b) => a.epoch - b.epoch);
  })();

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="panel">
        <div className="panel-head">
          <h2>Historial de entrenamiento</h2>
          {canExport && <div className="row"><button className="btn btn-sm" onClick={() => exp("csv")}><IconDownload />CSV</button><button className="btn btn-sm" onClick={() => exp("pdf")}><IconDownload />Ficha PDF</button></div>}
        </div>
        {!rows.length ? <Empty title="Sin ejecuciones todavía" /> : (
          <div className="table-wrap"><table className="tbl">
            <thead><tr><th><span className="sr-only">Comparar</span></th><th>Fecha</th><th>Versión</th><th>Dataset</th><th>Estado</th><th>Épocas</th><th>Parámetros principales</th><th>Duración</th><th>Exactitud test</th><th>Modelo</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.job_id}>
                <td><input type="checkbox" aria-label={`Comparar ${r.arquitectura} del ${fmtDate(r.fecha)}`} checked={picked.includes(r.job_id)} disabled={!picked.includes(r.job_id) && picked.length >= 5}
                  onChange={(e) => setPicked((p) => (e.target.checked ? [...p, r.job_id] : p.filter((x) => x !== r.job_id)))} /></td>
                <td className="small">{fmtDate(r.fecha)}</td>
                <td><Link to={`/proyectos/${project.id}/entrenamientos/${r.job_id}`}>{r.arquitectura}</Link></td>
                <td>{r.dataset}</td><td>{r.estado}</td><td className="num">{r.epocas}/{r.epocas_totales}</td>
                <td className="small">{r.optimizador}, lr {r.learning_rate}, batch {r.batch_size}</td>
                <td className="num">{r.duracion_s != null ? `${r.duracion_s} s` : "—"}</td>
                <td className="num">{fmtPct(r.test_accuracy)}</td>
                <td>{r.modelo_version ? `v${r.modelo_version}` : "—"}</td>
              </tr>))}
            </tbody>
          </table></div>
        )}
      </div>

      <div className="panel panel-pad stack">
        <div className="spread"><h2>Comparar ejecuciones</h2>
          <select value={metric} onChange={(e) => setMetric(e.target.value)} style={{ width: 240 }} aria-label="Métrica a comparar">
            <option value="val_accuracy">Exactitud (validación)</option><option value="val_loss">Pérdida (validación)</option>
            <option value="loss">Pérdida (entrenamiento)</option><option value="accuracy">Exactitud (entrenamiento)</option><option value="dist_gap">Brecha GAN</option>
          </select></div>
        {picked.length === 0 ? <p className="muted">Marca hasta cinco ejecuciones en el historial para superponer sus curvas.</p> : cmp.isLoading ? <Loading /> : cmp.data && <>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
              <CartesianGrid stroke="#e3e8ef" vertical={false} />
              <XAxis dataKey="epoch" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} width={48} />
              <Tooltip labelFormatter={(l) => `Época ${l}`} formatter={(v) => Number(v).toFixed(4)} />
              <Legend wrapperStyle={{ fontSize: 13 }} />
              {cmp.data.map((c, i) => <Line key={c.job_id} dataKey={`s${i}`} name={c.label} stroke={PALETTE[i]} dot={false} strokeWidth={2} isAnimationActive={false} />)}
            </LineChart>
          </ResponsiveContainer>
          <div className="table-wrap"><table className="tbl">
            <thead><tr><th>Ejecución</th><th>Parámetros de la red</th><th>Pérdida test</th><th>Exactitud test</th></tr></thead>
            <tbody>{cmp.data.map((c, i) => <tr key={c.job_id}><td><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: PALETTE[i], marginRight: 8 }} />{c.label}</td><td className="num">{c.total_params?.toLocaleString("es-PE")}</td><td className="num">{fmtNum(c.evaluation.loss)}</td><td className="num">{fmtPct(c.evaluation.accuracy)}</td></tr>)}</tbody>
          </table></div>
        </>}
      </div>

      {canAudit && (
        <div className="panel">
          <div className="panel-head"><h2>Auditoría del proyecto</h2></div>
          {audit.data?.length ? <div className="table-wrap"><table className="tbl">
            <thead><tr><th>Fecha</th><th>Persona</th><th>Acción</th><th>Detalle</th></tr></thead>
            <tbody>{audit.data.map((a) => <tr key={a.id}><td className="small">{fmtDate(a.created_at)}</td><td>{a.actor ?? "Sistema"}</td><td><code>{a.action}</code></td><td className="small muted" style={{ maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{JSON.stringify(a.metadata)}</td></tr>)}</tbody>
          </table></div> : <Empty title="Sin eventos" />}
        </div>
      )}
      {toast.node}
    </div>
  );
}
