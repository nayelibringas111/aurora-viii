import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorBox, Field, useToast } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Member, Project, Role } from "@/types";

const ROLES: { id: Role; label: string; desc: string }[] = [
  { id: "lead", label: "Responsable de proyecto", desc: "Todo, incluidos miembros y retiro de modelos" },
  { id: "engineer", label: "Ingeniero/analista de IA", desc: "Diseña, sube datasets, entrena y exporta" },
  { id: "reviewer", label: "Revisor", desc: "Compara, revisa y aprueba versiones" },
  { id: "reader", label: "Lector", desc: "Solo lectura" },
];

export function ContextTab({ project }: { project: Project }) {
  const qc = useQueryClient();
  const toast = useToast();
  const canEdit = project.my_permissions.includes("edit_project");
  const [f, setF] = useState({ name: project.name, description: project.description, problem: project.problem, tags: project.tags.join(", ") });
  const [err, setErr] = useState<unknown>(null);

  const save = async () => {
    setErr(null);
    try {
      await api.patch(`/projects/${project.id}`, { ...f, tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean) });
      qc.invalidateQueries({ queryKey: ["project", project.id] });
      toast.show("Cambios guardados");
    } catch (e) { setErr(e); }
  };
  const toggleArchive = async () => {
    await api.patch(`/projects/${project.id}`, { status: project.status === "active" ? "archived" : "active" });
    qc.invalidateQueries({ queryKey: ["project", project.id] });
  };

  return (
    <div className="grid cols-2" style={{ alignItems: "start" }}>
      <div className="panel panel-pad stack">
        <h2>Problema y documentación</h2>
        <Field label="Nombre"><input value={f.name} disabled={!canEdit} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Descripción"><input value={f.description} disabled={!canEdit} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <Field label="Problema que se desea resolver"><textarea rows={5} value={f.problem} disabled={!canEdit} onChange={(e) => setF({ ...f, problem: e.target.value })} /></Field>
        <Field label="Etiquetas" hint="Separadas por coma"><input value={f.tags} disabled={!canEdit} onChange={(e) => setF({ ...f, tags: e.target.value })} /></Field>
        <ErrorBox error={err} />
        {canEdit && <div className="row"><button className="btn btn-primary" onClick={save}>Guardar cambios</button><button className="btn" onClick={toggleArchive}>{project.status === "active" ? "Archivar proyecto" : "Reactivar proyecto"}</button></div>}
        <dl className="kv small" style={{ marginTop: 6 }}>
          <dt>Propietario</dt><dd>{project.owner.display_name}</dd>
          <dt>Creado</dt><dd>{fmtDate(project.created_at)}</dd>
          <dt>Actualizado</dt><dd>{fmtDate(project.updated_at)}</dd>
        </dl>
      </div>
      <Members project={project} onToast={toast.show} />
      {toast.node}
    </div>
  );
}

function Members({ project, onToast }: { project: Project; onToast: (s: string) => void }) {
  const qc = useQueryClient();
  const canManage = project.my_permissions.includes("manage_members");
  const q = useQuery({ queryKey: ["members", project.id], queryFn: () => api.get<Member[]>(`/projects/${project.id}/members`) });
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("engineer");
  const [err, setErr] = useState<unknown>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["members", project.id] });

  const add = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    try { await api.put(`/projects/${project.id}/members`, { email, role }); setEmail(""); refresh(); onToast("Miembro actualizado"); } catch (x) { setErr(x); }
  };
  const change = async (m: Member, r: Role) => {
    try { await api.put(`/projects/${project.id}/members`, { email: m.email, role: r }); refresh(); } catch (x) { onToast(errorText(x)); }
  };
  const remove = async (m: Member) => {
    try { await api.del(`/projects/${project.id}/members/${m.user_id}`); refresh(); } catch (x) { onToast(errorText(x)); }
  };

  return (
    <div className="panel">
      <div className="panel-head"><h2>Miembros y permisos</h2><span className="small muted">{q.data?.length ?? 0} personas</span></div>
      <div className="table-wrap">
        <table className="tbl">
          <tbody>
            {q.data?.map((m) => (
              <tr key={m.user_id}>
                <td><strong>{m.display_name}</strong><div className="small muted">{m.email}</div></td>
                <td style={{ width: 230 }}>
                  {canManage && !m.is_owner ? (
                    <select value={m.role} onChange={(e) => change(m, e.target.value as Role)} aria-label={`Rol de ${m.display_name}`}>
                      {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                    </select>
                  ) : <span>{m.role_label}{m.is_owner ? " (propietario)" : ""}</span>}
                </td>
                <td style={{ width: 80 }}>{canManage && !m.is_owner && <button className="btn btn-sm btn-ghost" onClick={() => remove(m)}>Quitar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canManage && (
        <form className="panel-pad stack" onSubmit={add} style={{ borderTop: "1px solid var(--line)" }}>
          <div className="grid cols-2" style={{ gap: 10 }}>
            <Field label="Correo" hint="La persona debe haber ingresado una vez a Aurora VIII"><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label="Rol"><select value={role} onChange={(e) => setRole(e.target.value as Role)}>{ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></Field>
          </div>
          <p className="small muted" style={{ margin: 0 }}>{ROLES.find((r) => r.id === role)?.desc}</p>
          <ErrorBox error={err} />
          <div><button className="btn">Añadir miembro</button></div>
        </form>
      )}
    </div>
  );
}
