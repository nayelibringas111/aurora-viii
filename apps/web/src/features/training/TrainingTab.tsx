import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { IconPlay } from "@/components/Icons";
import { Empty, ErrorBox, Field, Loading, Progress, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { FAMILY_LABEL, fmtDate, fmtDuration, fmtPct } from "@/lib/format";
import type { Architecture, Dataset, Job, Project, TrainingParams } from "@/types";

export function TrainingTab({ project }: { project: Project }) {
  const jobs = useQuery({
    queryKey: ["jobs", project.id], queryFn: () => api.get<Job[]>(`/projects/${project.id}/training-jobs`),
    refetchInterval: (q) => (q.state.data?.some((j) => ["QUEUED", "PREPARING", "RUNNING"].includes(j.status)) ? 2500 : false),
  });
  return (
    <div className="stack" style={{ gap: 18 }}>
      {project.my_permissions.includes("train") && project.status === "active" && <Launcher project={project} />}
      <div className="panel">
        <div className="panel-head"><h2>Ejecuciones</h2><span className="small muted">Se actualiza sola mientras haya trabajos activos</span></div>
        {jobs.isLoading ? <Loading /> : jobs.error ? <div className="panel-pad"><ErrorBox error={jobs.error} /></div> : !jobs.data?.length ? <Empty title="Sin entrenamientos">Configura uno arriba y observa la red mientras aprende.</Empty> : (
          <div className="table-wrap"><table className="tbl">
            <thead><tr><th>Arquitectura</th><th>Dataset</th><th>Estado</th><th style={{ width: 160 }}>Avance</th><th>Exactitud test</th><th>Duración</th><th>Creado</th></tr></thead>
            <tbody>{jobs.data.map((j) => (
              <tr key={j.id}>
                <td><Link to={`/proyectos/${project.id}/entrenamientos/${j.id}`}>{j.architecture_name} v{j.architecture_version}</Link><div className="small muted">{FAMILY_LABEL[j.family ?? ""]} · {j.params.optimizer}, lr {j.params.learning_rate}</div></td>
                <td>{j.dataset_name}</td>
                <td><StatusBadge status={j.status} /></td>
                <td><div className="stack" style={{ gap: 3 }}><Progress value={j.progress} /><span className="small muted num">Época {j.current_epoch}/{j.total_epochs}</span></div></td>
                <td className="num">{fmtPct(j.result.evaluation?.accuracy)}</td>
                <td className="num">{fmtDuration(j.duration_seconds)}</td>
                <td className="small muted">{fmtDate(j.created_at)}</td>
              </tr>))}
            </tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

function Launcher({ project }: { project: Project }) {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const archs = useQuery({ queryKey: ["architectures", project.id], queryFn: () => api.get<Architecture[]>(`/projects/${project.id}/architectures`) });
  const dss = useQuery({ queryKey: ["datasets", project.id], queryFn: () => api.get<Dataset[]>(`/projects/${project.id}/datasets`) });
  const [archId, setArchId] = useState(sp.get("arquitectura") ?? "");
  const [dsId, setDsId] = useState("");
  const [p, setP] = useState<TrainingParams>({ epochs: 40, batch_size: 32, optimizer: "adam", learning_rate: 0.01, seed: 42, observe: true });
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const arch = archs.data?.find((a) => a.id === archId) ?? archs.data?.[0];

  // Dataset compatible por defecto (misma familia y forma de entrada)
  const compatible = useMemo(() => {
    if (!arch || !dss.data) return [];
    const out = arch.family === "gan" ? null : (arch.config as { output: { units: number; activation: string } }).output;
    return dss.data.filter((d) => {
      if (arch.family === "gan") return d.task === "generation";
      if (d.task !== "classification" || JSON.stringify(d.input_shape) !== JSON.stringify(arch.summary.input_shape)) return false;
      return out!.activation === "sigmoid" ? d.num_classes === 2 : d.num_classes === out!.units;
    });
  }, [arch, dss.data]);
  useEffect(() => { if (arch) { setDsId(compatible[0]?.id ?? ""); setP((x) => ({ ...x, learning_rate: arch.family === "gan" ? 0.002 : arch.family === "rnn" ? 0.005 : 0.01, epochs: arch.family === "gan" ? 80 : 40, batch_size: arch.family === "gan" ? 64 : 32 })); } }, [arch, compatible]);

  if (archs.isLoading || dss.isLoading) return <Loading />;
  if (!archs.data?.length) return <div className="alert alert-info">Primero guarda una arquitectura en la pestaña Arquitectura.</div>;

  const start = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.post<{ job_id: string }>(`/projects/${project.id}/training-jobs`, { architecture_id: arch!.id, dataset_id: dsId, params: p });
      nav(`/proyectos/${project.id}/entrenamientos/${r.job_id}`);
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="panel panel-pad stack">
      <h2>Nuevo entrenamiento</h2>
      <div className="grid cols-2">
        <Field label="Arquitectura"><select value={arch?.id} onChange={(e) => setArchId(e.target.value)}>{archs.data.map((a) => <option key={a.id} value={a.id}>{a.name} v{a.version} · {FAMILY_LABEL[a.family]}</option>)}</select></Field>
        <Field label="Dataset" hint={arch?.family === "gan" ? "Solo se listan datasets de generación" : compatible.length ? `Solo se listan datasets con entrada [${arch?.summary.input_shape.join("×")}] y el mismo número de clases que la salida` : "Ningún dataset encaja con esta arquitectura: ajusta la entrada o las neuronas de salida"}>
          <select value={dsId} onChange={(e) => setDsId(e.target.value)}>
            {compatible.map((d) => <option key={d.id} value={d.id}>{d.name} v{d.version}</option>)}
            {!compatible.length && <option value="">—</option>}
          </select>
        </Field>
      </div>
      <div className="grid cols-4">
        <Field label="Épocas"><input type="number" min={1} max={5000} value={p.epochs} onChange={(e) => setP({ ...p, epochs: Number(e.target.value) })} /></Field>
        <Field label="Tamaño de batch"><input type="number" min={1} max={4096} value={p.batch_size} onChange={(e) => setP({ ...p, batch_size: Number(e.target.value) })} /></Field>
        <Field label="Optimizador"><select value={p.optimizer} onChange={(e) => setP({ ...p, optimizer: e.target.value as TrainingParams["optimizer"] })}><option value="adam">Adam</option><option value="sgd">SGD</option><option value="rmsprop">RMSprop</option></select></Field>
        <Field label="Tasa de aprendizaje"><input type="number" step="0.001" min={0.0001} max={1} value={p.learning_rate} onChange={(e) => setP({ ...p, learning_rate: Number(e.target.value) })} /></Field>
      </div>
      <div className="row" style={{ gap: 18, alignItems: "flex-start" }}>
        <Field label="Semilla"><input type="number" min={0} value={p.seed ?? ""} onChange={(e) => setP({ ...p, seed: e.target.value === "" ? null : Number(e.target.value) })} style={{ width: 120 }} /></Field>
        <label className="small" style={{ maxWidth: 560, display: "flex", gap: 10, alignItems: "flex-start", marginTop: 22 }}><input type="checkbox" checked={p.observe} onChange={(e) => setP({ ...p, observe: e.target.checked })} />
          Modo observación: cada época dura al menos 0,15 s para que puedas ver a la red aprender. Desactívalo para entrenar a máxima velocidad.</label>
      </div>
      <ErrorBox error={err} />
      <div><button className="btn btn-primary" onClick={start} disabled={busy || !dsId}><IconPlay />{busy ? "Enviando a la cola…" : "Iniciar entrenamiento"}</button></div>
    </div>
  );
}
