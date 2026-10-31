import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { IconPlus } from "@/components/Icons";
import { Empty, ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { FAMILY_LABEL, fmtDate, fmtInt } from "@/lib/format";
import type { Architecture, Project } from "@/types";
import { NetworkCanvas, topologyFromSummary } from "@/features/training/NetworkCanvas";
import { kerasCode } from "./kerasCode";

export function ArchitecturesTab({ project }: { project: Project }) {
  const q = useQuery({ queryKey: ["architectures", project.id], queryFn: () => api.get<Architecture[]>(`/projects/${project.id}/architectures`) });
  const [selId, setSelId] = useState<string | null>(null);
  const sel = q.data?.find((a) => a.id === selId) ?? q.data?.[0];
  const topo = useMemo(() => (sel ? topologyFromSummary(sel.family, sel.summary as never) : null), [sel]);
  const canDesign = project.my_permissions.includes("design");

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data?.length) return (
    <div className="panel"><Empty title="Aún no hay arquitecturas" action={canDesign && <Link className="btn btn-primary" to={`/proyectos/${project.id}/arquitectura/nueva`}><IconPlus />Diseñar la red</Link>}>
      Elige una familia (Feedforward, CNN, RNN o GAN), define sus capas y guárdala validada.
    </Empty></div>
  );
  return (
    <div className="stack">
      <div className="spread"><p className="muted" style={{ margin: 0 }}>Cada guardado con el mismo nombre crea una versión nueva; las anteriores se conservan.</p>
        {canDesign && <Link className="btn btn-primary" to={`/proyectos/${project.id}/arquitectura/nueva`}><IconPlus />Diseñar nueva</Link>}</div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 340px) minmax(0, 1fr)", alignItems: "start" }}>
        <div className="panel table-wrap">
          <table className="tbl">
            <thead><tr><th>Arquitectura</th><th>Familia</th><th>Parámetros</th></tr></thead>
            <tbody>{q.data.map((a) => (
              <tr key={a.id} onClick={() => setSelId(a.id)} style={{ cursor: "pointer", background: a.id === sel?.id ? "var(--teal-soft)" : undefined }}>
                <td><button className="btn-ghost" style={{ border: 0, background: "none", padding: 0, font: "inherit", fontWeight: 600, cursor: "pointer", color: "var(--ink)" }} onClick={() => setSelId(a.id)}>{a.name}</button> <span className="muted small">v{a.version}</span></td>
                <td>{FAMILY_LABEL[a.family]}</td><td className="num">{fmtInt(a.summary.total_params)}</td>
              </tr>))}
            </tbody>
          </table>
        </div>
        {sel && topo && (
          <div className="stack" style={{ minWidth: 0 }}>
            <div className="stage">
              <div className="stage-bar"><h2>{sel.name} v{sel.version}</h2><span className="small" style={{ color: "#aab5d9" }}>{FAMILY_LABEL[sel.family]}, {fmtInt(sel.summary.total_params)} parámetros</span></div>
              <NetworkCanvas topology={topo} snapshot={null} running={false} compact />
            </div>
            <div className="panel panel-pad stack">
              <dl className="kv">
                <dt>Justificación</dt><dd>{sel.justification || <span className="muted">Sin justificación registrada</span>}</dd>
                <dt>Pérdida</dt><dd><code>{sel.summary.loss}</code></dd>
                <dt>Huella de configuración</dt><dd><code>{sel.config_hash}</code></dd>
                <dt>Creada</dt><dd>{fmtDate(sel.created_at)}</dd>
              </dl>
              <div className="row">
                {project.my_permissions.includes("train") && <Link className="btn btn-primary" to={`/proyectos/${project.id}/entrenamientos?arquitectura=${sel.id}`}>Entrenar esta arquitectura</Link>}
              </div>
              <details><summary style={{ cursor: "pointer", fontWeight: 600 }}>Código Keras</summary><pre className="code" style={{ marginTop: 10 }}>{kerasCode(sel.family, sel.config)}</pre></details>
            </div>
          </div>
        )}
      </div>
      <style>{`@media (max-width: 900px){ .grid[style*="340px"]{ grid-template-columns: 1fr !important; } }`}</style>
    </div>
  );
}
