import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { IconDownload } from "@/components/Icons";
import { Empty, ErrorBox, Loading, StatusBadge, useToast } from "@/components/ui";
import { api, download, errorText } from "@/lib/api";
import { FAMILY_LABEL, METRIC_LABEL, fmtDate, fmtNum, fmtPct } from "@/lib/format";
import type { ModelVersion, Project } from "@/types";

const NEXT: Record<string, { to: "reviewed" | "approved" | "retired"; label: string; perm: "review_model" | "retire_model" }[]> = {
  draft: [{ to: "reviewed", label: "Marcar revisado", perm: "review_model" }, { to: "retired", label: "Retirar", perm: "retire_model" }],
  reviewed: [{ to: "approved", label: "Aprobar", perm: "review_model" }, { to: "retired", label: "Retirar", perm: "retire_model" }],
  approved: [{ to: "retired", label: "Retirar", perm: "retire_model" }],
  retired: [],
};

export function ModelsTab({ project }: { project: Project }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["models", project.id], queryFn: () => api.get<ModelVersion[]>(`/projects/${project.id}/models`) });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const perms = project.my_permissions;

  const move = async (m: ModelVersion, to: string) => {
    try {
      await api.patch(`/models/${m.id}/status`, { status: to, notes: notes[m.id] ?? "" });
      setNotes((n) => ({ ...n, [m.id]: "" }));
      qc.invalidateQueries({ queryKey: ["models", project.id] });
      toast.show(`Versión ${m.version}: ${{ reviewed: "revisada", approved: "aprobada", retired: "retirada" }[to]}`);
    } catch (e) { toast.show(errorText(e)); }
  };
  const dl = async (m: ModelVersion) => {
    try { await download(`/models/${m.id}/download`, `aurora-viii-modelo-v${m.version}.keras`); } catch (e) { toast.show(errorText(e)); }
  };

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data?.length) return <div className="panel"><Empty title="Aún no hay modelos registrados">Cada entrenamiento completado crea una versión inmutable con su checksum.</Empty></div>;
  return (
    <div className="stack">
      <p className="muted" style={{ margin: 0 }}>Las versiones no se sobrescriben. El flujo es borrador → revisado → aprobado, y cualquier versión puede retirarse.</p>
      {q.data.map((m) => (
        <div key={m.id} className="panel">
          <div className="panel-head">
            <div className="row"><h2>Versión {m.version}</h2><StatusBadge status={m.status} /></div>
            <span className="small muted">{fmtDate(m.created_at)}</span>
          </div>
          <div className="panel-pad grid cols-3">
            <dl className="kv small">
              <dt>Arquitectura</dt><dd>{m.architecture?.name} v{m.architecture?.version} · {FAMILY_LABEL[m.architecture?.family ?? ""]}</dd>
              <dt>Entrenamiento</dt><dd><Link to={`/proyectos/${project.id}/entrenamientos/${m.job_id}`}>Ver ejecución</Link></dd>
              <dt>Parámetros</dt><dd>{m.params?.optimizer}, lr {m.params?.learning_rate}, {m.params?.epochs} épocas</dd>
              <dt>SHA-256</dt><dd><code title={m.checksum}>{m.checksum.slice(0, 20)}…</code></dd>
              <dt>Tamaño</dt><dd>{(m.size_bytes / 1024).toFixed(1)} KB</dd>
            </dl>
            <dl className="kv small">{Object.entries(m.metrics).map(([k, v]) => <Fragment key={k}><dt>{METRIC_LABEL[k] ?? k}</dt><dd className="num">{k.includes("accuracy") ? fmtPct(v) : fmtNum(v)}</dd></Fragment>)}</dl>
            <div className="stack" style={{ gap: 8 }}>
              {m.notes && <pre className="small" style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit", color: "var(--ink-2)" }}>{m.notes}</pre>}
              {NEXT[m.status].some((n) => perms.includes(n.perm)) && (
                <input placeholder="Nota de revisión (opcional)" value={notes[m.id] ?? ""} onChange={(e) => setNotes({ ...notes, [m.id]: e.target.value })} aria-label="Nota de revisión" />
              )}
              <div className="row">
                {NEXT[m.status].filter((n) => perms.includes(n.perm)).map((n) => <button key={n.to} className={`btn btn-sm${n.to === "retired" ? " btn-danger" : ""}`} onClick={() => move(m, n.to)}>{n.label}</button>)}
                {perms.includes("download_model") && <button className="btn btn-sm" onClick={() => dl(m)}><IconDownload />Descargar .keras</button>}
              </div>
            </div>
          </div>
        </div>
      ))}
      {toast.node}
    </div>
  );
}
