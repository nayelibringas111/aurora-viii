import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Empty, ErrorBox, Field, Loading, useToast } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { FAMILY_LABEL, fmtInt } from "@/lib/format";
import type { Dataset, Project } from "@/types";
import { CLASS_COLORS } from "@/features/training/StagePanels";

interface Preview { kind: "scatter" | "images" | "series" | "table"; points?: number[][]; items?: { pixels?: number[][]; values?: number[]; label: number }[]; rows?: number[][]; dataset: Dataset }

export function DatasetsTab({ project }: { project: Project }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["datasets", project.id], queryFn: () => api.get<Dataset[]>(`/projects/${project.id}/datasets`) });
  const [selId, setSelId] = useState<string | null>(null);
  const sel = q.data?.find((d) => d.id === selId) ?? q.data?.[0];
  const pv = useQuery({ queryKey: ["preview", sel?.id], enabled: !!sel, queryFn: () => api.get<Preview>(`/projects/${project.id}/datasets/${sel!.id}/preview`) });

  const del = async (d: Dataset) => {
    if (!confirm(`¿Eliminar «${d.name}» v${d.version}? El archivo se borra; el registro se conserva para la trazabilidad.`)) return;
    try { await api.del(`/projects/${project.id}/datasets/${d.id}`); qc.invalidateQueries({ queryKey: ["datasets", project.id] }); setSelId(null); toast.show("Dataset eliminado"); }
    catch (e) { toast.show(errorText(e)); }
  };

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  return (
    <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)", alignItems: "start" }}>
      <div className="stack">
        <div className="panel table-wrap">
          <table className="tbl">
            <thead><tr><th>Dataset</th><th>Uso sugerido</th><th>Muestras</th><th>Entrada</th></tr></thead>
            <tbody>{q.data!.map((d) => (
              <tr key={d.id} onClick={() => setSelId(d.id)} style={{ cursor: "pointer", background: d.id === sel?.id ? "var(--teal-soft)" : undefined }}>
                <td><strong>{d.name}</strong> <span className="muted small">v{d.version}</span><div className="small muted">{d.kind === "builtin" ? "Demo integrado" : "Subido al proyecto"}</div></td>
                <td>{FAMILY_LABEL[d.family_hint]}</td><td className="num">{fmtInt(d.samples)}</td><td className="num">[{d.input_shape.join("×")}]</td>
              </tr>))}
            </tbody>
          </table>
        </div>
        {project.my_permissions.includes("design") && <Upload project={project} onDone={() => { qc.invalidateQueries({ queryKey: ["datasets", project.id] }); toast.show("Dataset validado y guardado"); }} />}
      </div>
      {sel && (
        <div className="panel panel-pad stack">
          <div className="spread"><h2>{sel.name}</h2>{sel.kind === "upload" && project.my_permissions.includes("edit_project") && <button className="btn btn-sm btn-danger" onClick={() => del(sel)}>Eliminar</button>}</div>
          <p className="muted" style={{ margin: 0 }}>{sel.description}</p>
          <dl className="kv">
            <dt>Tarea</dt><dd>{sel.task === "classification" ? `Clasificación en ${sel.num_classes} clases` : "Generación"}</dd>
            {sel.class_names && <><dt>Clases</dt><dd>{sel.class_names.join(", ")}</dd></>}
            <dt>Separación</dt><dd>{Object.entries(sel.split).map(([k, v]) => `${{ train: "entrenamiento", validation: "validación", test: "prueba" }[k]} ${Math.round(v * 100)} %`).join(", ")}</dd>
            {sel.sha256 && <><dt>SHA-256</dt><dd><code>{sel.sha256.slice(0, 16)}…</code></dd></>}
          </dl>
          {pv.isLoading ? <Loading label="Generando vista previa…" /> : pv.data && <PreviewView p={pv.data} classNames={sel.class_names ?? []} />}
        </div>
      )}
      {!q.data!.length && <Empty title="Sin datasets" />}
      {toast.node}
      <style>{`@media (max-width: 1000px){ .grid[style*="minmax(0,1fr) minmax(0,1fr)"]{ grid-template-columns: 1fr !important; } }`}</style>
    </div>
  );
}

function PreviewView({ p, classNames }: { p: Preview; classNames: string[] }) {
  if (p.kind === "scatter" && p.points) {
    const xs = p.points.map((q) => q[0]), ys = p.points.map((q) => q[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const S = 300, m = 10;
    return (
      <svg viewBox={`0 0 ${S} ${S}`} style={{ width: "100%", maxWidth: 320, background: "var(--surface-2)", borderRadius: 8 }} role="img" aria-label="Distribución de puntos del dataset">
        {p.points.map(([x, y, c], i) => <circle key={i} cx={m + ((x - x0) / (x1 - x0 || 1)) * (S - 2 * m)} cy={S - m - ((y - y0) / (y1 - y0 || 1)) * (S - 2 * m)} r={2.6} fill={["#0e8a8c", "#6d4fd6", "#d99a0b", "#c4384a"][c % 4]} />)}
      </svg>
    );
  }
  if (p.kind === "images" && p.items) return (
    <div className="row" style={{ gap: 10 }}>{p.items.map((it, i) => (
      <figure key={i} style={{ margin: 0, textAlign: "center" }}>
        <svg width={56} height={56} style={{ background: "var(--night)", borderRadius: 4 }}>{it.pixels!.map((r, y) => r.map((v, x) => <rect key={`${x}${y}`} x={x * 7} y={y * 7} width={7} height={7} fill={`rgba(223,240,255,${v})`} />))}</svg>
        <figcaption className="small muted">{classNames[it.label]}</figcaption>
      </figure>))}
    </div>
  );
  if (p.kind === "series" && p.items) return (
    <div className="grid cols-3" style={{ gap: 8 }}>{p.items.map((it, i) => {
      const v = it.values!, mn = Math.min(...v), mx = Math.max(...v);
      return <figure key={i} style={{ margin: 0 }}><svg viewBox="0 0 120 44" width="100%"><polyline fill="none" stroke={CLASS_COLORS[it.label]} strokeWidth="2" points={v.map((y, k) => `${(k / (v.length - 1)) * 120},${42 - ((y - mn) / (mx - mn || 1)) * 40}`).join(" ")} /></svg><figcaption className="small muted">{classNames[it.label]}</figcaption></figure>;
    })}</div>
  );
  return <pre className="code">{p.rows?.map((r) => r.join("  ")).join("\n")}</pre>;
}

function Upload({ project, onDone }: { project: Project; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setErr(null);
    const fd = new FormData();
    fd.append("name", name || file.name.replace(/\.csv$/i, ""));
    if (target) fd.append("target_column", target);
    fd.append("file", file);
    try { await api.post(`/projects/${project.id}/datasets`, fd); setFile(null); setName(""); setTarget(""); onDone(); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  return (
    <form className="panel panel-pad stack" onSubmit={submit}>
      <h3>Subir dataset CSV</h3>
      <p className="small muted" style={{ margin: 0 }}>Columnas numéricas con cabecera; la columna objetivo es la última salvo que indiques otra. Se valida tipo, tamaño y contenido; el archivo nunca se ejecuta.</p>
      <Field label="Archivo"><input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required /></Field>
      <div className="grid cols-2" style={{ gap: 10 }}>
        <Field label="Nombre"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="iris-medidas" /></Field>
        <Field label="Columna objetivo"><input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="(última)" /></Field>
      </div>
      <ErrorBox error={err} />
      <div><button className="btn" disabled={!file || busy}>{busy ? "Validando…" : "Subir y validar"}</button></div>
    </form>
  );
}
