import { Fragment, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/app/auth";
import { useCrumbs } from "@/components/Layout";
import { ErrorBox, Loading, useToast } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { AuditEvent } from "@/types";

interface AdminUser { id: string; email: string; display_name: string; is_admin: boolean; status: string; created_at: string }
interface Health { database: { ok: boolean; latency_ms: number }; jobs_by_status: Record<string, number>; oldest_queued_at: string | null; worker_heartbeat: { worker_id: string; at: string; host: string } | null; config: Record<string, string | boolean> }

const LIMIT_LABELS: Record<string, string> = {
  max_epochs: "Épocas máximas por entrenamiento", max_batch_size: "Batch máximo", max_layers: "Capas ocultas máximas",
  max_units_per_layer: "Neuronas máximas por capa", max_parameters: "Parámetros máximos por red", max_upload_mb: "Tamaño máximo de CSV (MB)",
  max_concurrent_jobs_per_user: "Entrenamientos activos por usuario", max_queued_jobs_per_project: "Trabajos en cola por proyecto",
  job_timeout_seconds: "Duración máxima de un trabajo (s)", event_retention_days: "Retención de eventos en vivo (días)",
};

export function AdminPage() {
  useCrumbs([{ label: "Administración" }]);
  const { me } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => api.get<AdminUser[]>("/admin/users") });
  const health = useQuery({ queryKey: ["admin-health"], queryFn: () => api.get<Health>("/admin/health"), refetchInterval: 10000 });
  const limits = useQuery({ queryKey: ["admin-limits"], queryFn: () => api.get<{ values: Record<string, number>; bounds: Record<string, [number, number]> }>("/admin/limits") });
  const [action, setAction] = useState("");
  const audit = useQuery({ queryKey: ["admin-audit", action], queryFn: () => api.get<AuditEvent[]>(`/admin/audit-events?limit=150${action ? `&action=${encodeURIComponent(action)}` : ""}`) });
  const [vals, setVals] = useState<Record<string, number>>({});
  useEffect(() => { if (limits.data) setVals(limits.data.values); }, [limits.data]);

  const patchUser = async (u: AdminUser, body: Partial<AdminUser>) => {
    try { await api.patch(`/admin/users/${u.id}`, body); qc.invalidateQueries({ queryKey: ["admin-users"] }); } catch (e) { toast.show(errorText(e)); }
  };
  const saveLimits = async () => {
    try { await api.put("/admin/limits", { values: vals }); qc.invalidateQueries({ queryKey: ["admin-limits"] }); toast.show("Límites guardados"); } catch (e) { toast.show(errorText(e)); }
  };
  const retention = async () => {
    try { const r = await api.post<{ deleted_events: number; days: number }>("/admin/retention/run"); toast.show(`Retención aplicada: ${r.deleted_events} eventos de más de ${r.days} días eliminados`); } catch (e) { toast.show(errorText(e)); }
  };

  const beatAge = health.data?.worker_heartbeat ? (Date.now() - new Date(health.data.worker_heartbeat.at).getTime()) / 1000 : null;

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="page-head" style={{ marginBottom: 0 }}><div><h1>Administración y seguridad</h1><p>Usuarios, límites de recursos, salud del sistema, auditoría y retención.</p></div></div>

      <div className="grid cols-3">
        <div className="panel panel-pad stack">
          <h2>Salud del sistema</h2>
          {health.isLoading ? <Loading /> : health.error ? <ErrorBox error={health.error} /> : <dl className="kv small">
            <dt>Base de datos</dt><dd>{health.data!.database.ok ? `Operativa (${health.data!.database.latency_ms} ms)` : "Sin respuesta"}</dd>
            <dt>Worker</dt><dd>{beatAge == null ? "Nunca se ha reportado" : beatAge < 40 ? `Activo (${health.data!.worker_heartbeat!.worker_id})` : `Sin señal hace ${Math.round(beatAge)} s`}</dd>
            <dt>En cola</dt><dd>{health.data!.jobs_by_status.QUEUED ?? 0}{health.data!.oldest_queued_at ? `, el más antiguo desde ${fmtDate(health.data!.oldest_queued_at)}` : ""}</dd>
            <dt>Ejecutando</dt><dd>{(health.data!.jobs_by_status.RUNNING ?? 0) + (health.data!.jobs_by_status.PREPARING ?? 0)}</dd>
            {Object.entries(health.data!.config).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd><code>{String(v)}</code></dd></Fragment>)}
          </dl>}
          <div><button className="btn btn-sm" onClick={retention}>Aplicar política de retención</button></div>
        </div>
        <div className="panel panel-pad stack" style={{ gridColumn: "span 2" }}>
          <h2>Límites de recursos</h2>
          {limits.data && <div className="grid cols-2" style={{ gap: 10 }}>
            {Object.keys(LIMIT_LABELS).map((k) => (
              <label key={k} className="field"><span>{LIMIT_LABELS[k]}</span>
                <input type="number" min={limits.data.bounds[k]?.[0]} max={limits.data.bounds[k]?.[1]} value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: Number(e.target.value) })} />
              </label>
            ))}
          </div>}
          <div><button className="btn btn-primary" onClick={saveLimits}>Guardar límites</button></div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h2>Usuarios y roles globales</h2><span className="small muted">Los roles por proyecto se asignan en cada proyecto</span></div>
        {users.isLoading ? <Loading /> : <div className="table-wrap"><table className="tbl">
          <thead><tr><th>Persona</th><th>Alta</th><th>Administrador</th><th>Estado</th></tr></thead>
          <tbody>{users.data?.map((u) => (
            <tr key={u.id}>
              <td><strong>{u.display_name}</strong><div className="small muted">{u.email}</div></td>
              <td className="small">{fmtDate(u.created_at)}</td>
              <td><label className="row small"><input type="checkbox" checked={u.is_admin} disabled={u.id === me?.id} onChange={(e) => patchUser(u, { is_admin: e.target.checked })} />{u.is_admin ? "Sí" : "No"}</label></td>
              <td><select value={u.status} disabled={u.id === me?.id} onChange={(e) => patchUser(u, { status: e.target.value })} style={{ width: 140 }} aria-label={`Estado de ${u.display_name}`}><option value="active">Activo</option><option value="suspended">Suspendido</option></select></td>
            </tr>))}
          </tbody>
        </table></div>}
      </div>

      <div className="panel">
        <div className="panel-head"><h2>Auditoría global</h2>
          <select value={action} onChange={(e) => setAction(e.target.value)} style={{ width: 220 }} aria-label="Filtrar por acción">
            <option value="">Todas las acciones</option><option value="training">Entrenamientos</option><option value="member">Permisos</option>
            <option value="model">Modelos</option><option value="report">Exportaciones</option><option value="admin">Administración</option><option value="dataset">Datasets</option>
          </select></div>
        <div className="table-wrap"><table className="tbl">
          <thead><tr><th>Fecha</th><th>Persona</th><th>Proyecto</th><th>Acción</th><th>Detalle</th></tr></thead>
          <tbody>{audit.data?.map((a) => <tr key={a.id}><td className="small">{fmtDate(a.created_at)}</td><td>{a.actor ?? "Sistema"}</td><td>{a.project ?? "—"}</td><td><code>{a.action}</code></td><td className="small muted" style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{JSON.stringify(a.metadata)}</td></tr>)}</tbody>
        </table></div>
      </div>
      {toast.node}
    </div>
  );
}
