import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useCrumbs } from "@/components/Layout";
import { IconPlus } from "@/components/Icons";
import { Empty, ErrorBox, Field, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Project } from "@/types";

export function ProjectsPage() {
  useCrumbs([{ label: "Proyectos" }]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("active");
  const [creating, setCreating] = useState(false);
  const list = useQuery({ queryKey: ["projects", q, status], queryFn: () => api.get<Project[]>(`/projects?q=${encodeURIComponent(q)}&status=${status}`) });

  return (
    <>
      <div className="page-head">
        <div><h1>Proyectos de IA</h1><p>Cada proyecto agrupa el problema, sus arquitecturas, datasets, entrenamientos y modelos.</p></div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}><IconPlus />Crear proyecto</button>
      </div>
      {creating && <CreateProject onClose={() => setCreating(false)} />}
      <div className="row" style={{ marginBottom: 14 }}>
        <input type="search" placeholder="Buscar por nombre o descripción" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 360 }} aria-label="Buscar proyectos" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 160 }} aria-label="Estado">
          <option value="active">Activos</option><option value="archived">Archivados</option><option value="all">Todos</option>
        </select>
      </div>
      <div className="panel">
        {list.isLoading ? <Loading /> : list.error ? <div className="panel-pad"><ErrorBox error={list.error} /></div> : list.data!.length === 0 ? (
          <Empty title="No hay proyectos todavía" action={<button className="btn btn-primary" onClick={() => setCreating(true)}>Crear el primero</button>}>
            Crea un proyecto para describir el problema y empezar a diseñar tu red.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Proyecto</th><th>Tu rol</th><th>Arquitecturas</th><th>Entrenamientos</th><th>Modelos</th><th>Etiquetas</th><th>Actualizado</th></tr></thead>
              <tbody>
                {list.data!.map((p) => (
                  <tr key={p.id}>
                    <td><Link to={`/proyectos/${p.id}`}>{p.name}</Link><div className="small muted" style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.description || "Sin descripción"}</div></td>
                    <td>{p.my_role_label}</td>
                    <td className="num">{p.counts.architectures}</td><td className="num">{p.counts.jobs}</td><td className="num">{p.counts.models}</td>
                    <td><div className="row" style={{ gap: 4 }}>{p.tags.map((t) => <span key={t} className="chip">{t}</span>)}</div></td>
                    <td className="small muted">{fmtDate(p.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function CreateProject({ onClose }: { onClose: () => void }) {
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", description: "", problem: "", tags: "" });
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const p = await api.post<Project>("/projects", { ...f, tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean) });
      nav(`/proyectos/${p.id}/arquitectura/nueva`);
    } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  return (
    <form className="panel panel-pad stack" style={{ marginBottom: 18 }} onSubmit={submit}>
      <h2>Nuevo proyecto</h2>
      <div className="grid cols-2">
        <Field label="Nombre"><input required minLength={3} maxLength={120} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Clasificador de patrones" autoFocus /></Field>
        <Field label="Etiquetas" hint="Separadas por coma"><input value={f.tags} onChange={(e) => setF({ ...f, tags: e.target.value })} placeholder="semana-11, visión" /></Field>
      </div>
      <Field label="Descripción breve"><input maxLength={2000} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
      <Field label="Problema que se desea resolver" hint="Qué entra, qué debe salir y por qué importa">
        <textarea maxLength={4000} value={f.problem} onChange={(e) => setF({ ...f, problem: e.target.value })} placeholder="Distinguir dos espirales entrelazadas, un caso que un modelo lineal no puede separar." />
      </Field>
      <ErrorBox error={err} />
      <div className="row"><button className="btn btn-primary" disabled={busy}>{busy ? "Creando…" : "Crear y diseñar la red"}</button><button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button></div>
    </form>
  );
}
