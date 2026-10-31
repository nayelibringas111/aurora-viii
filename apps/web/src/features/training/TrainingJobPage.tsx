import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useCrumbs } from "@/components/Layout";
import { IconPlay, IconStop } from "@/components/Icons";
import { ErrorBox, Loading, StatusBadge, useToast } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { FAMILY_LABEL, METRIC_LABEL, fmtDate, fmtDuration, fmtNum, fmtPct } from "@/lib/format";
import type { Job, Project } from "@/types";
import { ConfusionMatrix, MetricsChart } from "@/features/evaluation/Charts";
import { NetworkCanvas } from "./NetworkCanvas";
import { BoundaryPanel, GanPanel, SamplePanel } from "./StagePanels";
import { useJobStream } from "./useJobStream";

export function TrainingJobPage() {
  const { projectId = "", jobId = "" } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { job, error, topology, snapshot, epochs, live, conn, log, resync } = useJobStream(jobId);
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api.get<Project>(`/projects/${projectId}`) });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  useCrumbs([{ label: "Proyectos", to: "/proyectos" }, { label: project.data?.name ?? "…", to: `/proyectos/${projectId}/entrenamientos` }, { label: "Entrenamiento" }]);

  if (error) return <ErrorBox error={error} />;
  if (!job) return <Loading label="Cargando entrenamiento…" />;

  const perms = project.data?.my_permissions ?? [];
  const running = job.status === "RUNNING";
  const active = ["QUEUED", "PREPARING", "RUNNING"].includes(job.status);
  const family = job.architecture.family;
  const classNames = topology?.class_names ?? job.dataset.class_names ?? [];
  const last = epochs[epochs.length - 1];
  const ev = job.result.evaluation;

  const cancel = async () => {
    setBusy(true);
    try { await api.post(`/training-jobs/${job.id}/cancel`, { reason: "Cancelado desde la interfaz" }); toast.show("Cancelación solicitada"); resync(); }
    catch (e) { toast.show(errorText(e)); } finally { setBusy(false); }
  };
  const retry = async () => {
    setBusy(true);
    try { const r = await api.post<Job & { job_id: string }>(`/training-jobs/${job.id}/retry`); nav(`/proyectos/${projectId}/entrenamientos/${r.job_id}`); }
    catch (e) { toast.show(errorText(e)); } finally { setBusy(false); }
  };
  const addNote = async () => {
    try { await api.post(`/training-jobs/${job.id}/notes`, { note }); setNote(""); toast.show("Observación registrada"); resync(); }
    catch (e) { toast.show(errorText(e)); }
  };

  const foot = family === "gan"
    ? [["Época", `${job.current_epoch} / ${job.total_epochs}`], ["Pérdida D", fmtNum(live?.d_loss ?? last?.d_loss, 3)], ["Pérdida G", fmtNum(live?.g_loss ?? last?.g_loss, 3)], ["Brecha", fmtNum(last?.dist_gap, 3)]]
    : [["Época", `${job.current_epoch} / ${job.total_epochs}`], ["Pérdida (lote)", fmtNum(live?.loss ?? last?.loss, 4)], ["Exactitud (val.)", fmtPct(last?.val_accuracy)], ["Pérdida (val.)", fmtNum(last?.val_loss, 4)]];

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <div className="row"><h1>{job.architecture.name} <span className="muted" style={{ fontWeight: 500 }}>v{job.architecture.version}</span></h1><StatusBadge status={job.status} /></div>
          <p>{FAMILY_LABEL[family]} con {job.dataset.name}. {job.params.optimizer.toUpperCase()}, tasa de aprendizaje {job.params.learning_rate}, batch {job.params.batch_size}{job.params.seed != null ? `, semilla ${job.params.seed}` : ""}.</p>
        </div>
        <div className="row">
          {active && perms.includes("train") && <button className="btn btn-danger" onClick={cancel} disabled={busy || job.cancel_requested}><IconStop />{job.cancel_requested ? "Cancelando…" : "Cancelar"}</button>}
          {["FAILED", "CANCELLED"].includes(job.status) && perms.includes("train") && <button className="btn btn-primary" onClick={retry} disabled={busy}><IconPlay />Reintentar</button>}
          {job.result.model_version && <Link className="btn" to={`/proyectos/${projectId}/modelos`}>Ver modelo v{job.result.model_version}</Link>}
        </div>
      </div>

      {job.status === "FAILED" && job.error_message && <div className="alert alert-error" role="alert">{job.error_message}</div>}
      {job.status === "QUEUED" && <div className="alert alert-info">En cola. El worker lo tomará en segundos; si el servicio de Render estaba dormido puede tardar alrededor de un minuto.</div>}

      {/* Escenario: la red neuronal en funcionamiento */}
      <section className="stage" aria-labelledby="stage-title">
        <div className="stage-bar">
          <div className="row" style={{ gap: 12 }}>
            <h2 id="stage-title">{running ? "La red está aprendiendo" : job.status === "COMPLETED" ? "Red entrenada" : job.status === "PREPARING" ? "Preparando datos y modelo" : "Red neuronal"}</h2>
            <StatusBadge status={job.status} />
          </div>
          <div className="stage-legend">
            <span><i style={{ background: "#2fd3c4" }} />Peso o activación positiva</span>
            <span><i style={{ background: "#8f7bff" }} />Negativa</span>
            <span className={`conn${conn === "live" ? " live" : ""}`}><i />{conn === "live" ? "En vivo" : conn === "reconnecting" ? "Reconectando…" : conn === "connecting" ? "Conectando…" : "Sin canal (resultado guardado)"}</span>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 270px", gap: 0 }} className="stage-body">
          <div style={{ padding: "6px 6px 0" }}>
            {topology ? <NetworkCanvas topology={topology} snapshot={snapshot} running={running} classNames={family === "gan" ? undefined : classNames} />
              : <div style={{ height: 320, display: "grid", placeItems: "center", color: "#aab5d9" }}>{active ? "Construyendo el modelo con TensorFlow/Keras…" : "Sin topología registrada"}</div>}
          </div>
          <div className="stack" style={{ padding: 12, gap: 12 }}>
            {family === "gan" ? <GanPanel snapshot={snapshot} real={topology?.real_points} /> : <SamplePanel snapshot={snapshot} classNames={classNames} />}
            {topology?.has_boundary && <BoundaryPanel snapshot={snapshot} points={topology.points} classNames={classNames} />}
          </div>
        </div>
        <div style={{ padding: "0 18px 12px" }}>
          <div className="spread small" style={{ color: "#aab5d9", marginBottom: 6 }}>
            <span>{live && running ? `Época ${live.epoch}, lote ${live.step} de ${live.steps}` : job.status_label}</span>
            <span className="num">{Math.round(job.progress * 100)} %</span>
          </div>
          <div className="progress" style={{ background: "rgba(255,255,255,.06)", borderColor: "rgba(255,255,255,.08)" }}><div style={{ width: `${job.progress * 100}%`, background: "linear-gradient(90deg,#0e8a8c,#2fd3c4)" }} /></div>
        </div>
        <div className="stage-foot">{foot.map(([k, v]) => <div key={k}><div className="k">{k}</div><div className="v num">{v}</div></div>)}</div>
      </section>
      <style>{`@media (max-width: 1000px){ .stage-body{ grid-template-columns: 1fr !important; } }`}</style>

      <div className="grid cols-2">
        {family === "gan" ? <>
          <MetricsChart data={epochs} keys={["d_loss", "g_loss"]} title="Pérdidas del duelo adversario" />
          <MetricsChart data={epochs} keys={["dist_gap"]} title="Brecha entre distribución real y generada" />
        </> : <>
          <MetricsChart data={epochs} keys={["loss", "val_loss"]} title="Pérdida por época" />
          <MetricsChart data={epochs} keys={["accuracy", "val_accuracy"]} title="Exactitud por época" percent />
        </>}
      </div>

      <div className="grid cols-2">
        <div className="panel">
          <div className="panel-head"><h3>Evaluación final</h3>{job.duration_seconds != null && <span className="small muted">Duración {fmtDuration(job.duration_seconds)}</span>}</div>
          <div className="panel-pad stack">
            {!ev ? <p className="muted">Disponible cuando el entrenamiento termine. Se evalúa con el 15 % de datos reservado para prueba.</p> : <>
              <dl className="kv">{Object.entries(ev).map(([k, v]) => <Fragment key={k}><dt>{METRIC_LABEL[k] ?? k}</dt><dd className="num">{k.includes("accuracy") ? fmtPct(v) : k === "test_samples" ? v : fmtNum(v)}</dd></Fragment>)}</dl>
              {job.result.confusion_matrix && <ConfusionMatrix matrix={job.result.confusion_matrix} classNames={job.result.class_names ?? classNames} />}
            </>}
            {job.result.observations?.map((o, i) => <div key={i} className="alert alert-warning">{o}</div>)}
          </div>
        </div>
        <div className="stack">
          <div className="panel">
            <div className="panel-head"><h3>Observaciones y limitaciones</h3></div>
            <div className="panel-pad stack">
              {(job.result.notes ?? []).length === 0 && <p className="muted small">Registra lo que el equipo debe saber sobre este resultado.</p>}
              {job.result.notes?.map((n, i) => <div key={i} className="small"><strong>{n.author}</strong> <span className="muted">{fmtDate(n.at)}</span><p>{n.text}</p></div>)}
              {perms.includes("export") && <div className="row" style={{ flexWrap: "nowrap" }}>
                <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ej.: el dataset tiene pocas muestras de la clase Marco" aria-label="Nueva observación" />
                <button className="btn" disabled={note.trim().length < 3} onClick={addNote}>Registrar</button>
              </div>}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head"><h3>Eventos recientes</h3><span className="small muted">Intento {job.attempt}</span></div>
            <ul className="small" style={{ listStyle: "none", margin: 0, padding: "10px 20px", maxHeight: 240, overflow: "auto" }} aria-live="polite">
              {log.length === 0 && <li className="muted">{active ? "Esperando eventos del worker…" : `Creado ${fmtDate(job.created_at)} · finalizado ${fmtDate(job.ended_at)}`}</li>}
              {log.map((l) => <li key={l.id} style={{ padding: "3px 0", color: l.tone === "error" ? "var(--red)" : l.tone === "ok" ? "var(--green)" : undefined }}><span className="muted num">{new Date(l.at).toLocaleTimeString("es-PE")}</span> {l.text}</li>)}
            </ul>
          </div>
        </div>
      </div>

      <details className="panel panel-pad">
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Trazabilidad de la ejecución</summary>
        <pre className="code" style={{ marginTop: 12 }}>{JSON.stringify(job.trace, null, 2)}</pre>
      </details>
      {toast.node}
    </div>
  );
}
