import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/app/auth";
import { useCrumbs } from "@/components/Layout";
import { Empty, ErrorBox, Loading, Progress, Stat, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { FAMILY_LABEL, fmtDate, fmtPct } from "@/lib/format";
import type { Job } from "@/types";

interface Dash { projects: number; jobs_by_status: Record<string, number>; active_jobs: number; models: number; approved_models: number; alerts: { level: string; text: string }[]; recent_jobs: (Job & { project_name: string })[] }

export function DashboardPage() {
  useCrumbs([{ label: "Inicio" }]);
  const { me } = useAuth();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<Dash>("/dashboard"), refetchInterval: (s) => (s.state.data?.active_jobs ? 3000 : 20000) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data!;
  const done = d.jobs_by_status.COMPLETED ?? 0, failed = d.jobs_by_status.FAILED ?? 0;
  return (
    <>
      <div className="page-head">
        <div><h1>Hola, {me?.display_name?.split(" ")[0]}</h1><p>Resumen de tus proyectos, entrenamientos y modelos.</p></div>
        <Link className="btn btn-primary" to="/proyectos">Ir a proyectos</Link>
      </div>
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Stat k="Proyectos activos" v={d.projects} />
        <Stat k="Entrenamientos activos" v={d.active_jobs} sub={`${d.jobs_by_status.QUEUED ?? 0} en cola`} />
        <Stat k="Completados" v={done} sub={failed ? `${failed} fallidos` : "Sin fallos"} />
        <Stat k="Modelos registrados" v={d.models} sub={`${d.approved_models} aprobados`} />
      </div>
      {d.alerts.length > 0 && <div className="stack" style={{ marginBottom: 18 }}>{d.alerts.map((a, i) => <div key={i} className={`alert alert-${a.level === "warning" ? "warning" : "info"}`}>{a.text}</div>)}</div>}
      <div className="panel">
        <div className="panel-head"><h2>Entrenamientos recientes</h2></div>
        {!d.recent_jobs.length ? (
          <Empty title="Todavía no has entrenado ninguna red" action={<Link className="btn btn-primary" to="/proyectos">Crear un proyecto</Link>}>
            Crea un proyecto, diseña una red Feedforward y observa cómo aprende a separar las espirales.
          </Empty>
        ) : (
          <div className="table-wrap"><table className="tbl">
            <thead><tr><th>Proyecto</th><th>Arquitectura</th><th>Estado</th><th style={{ width: 160 }}>Avance</th><th>Exactitud test</th><th>Creado</th></tr></thead>
            <tbody>{d.recent_jobs.map((j) => (
              <tr key={j.id}>
                <td>{j.project_name}</td>
                <td><Link to={`/proyectos/${j.project_id}/entrenamientos/${j.id}`}>{j.architecture_name}</Link> <span className="small muted">{FAMILY_LABEL[j.family ?? ""]}</span></td>
                <td><StatusBadge status={j.status} /></td>
                <td><Progress value={j.progress} /></td>
                <td className="num">{fmtPct(j.result.evaluation?.accuracy)}</td>
                <td className="small muted">{fmtDate(j.created_at)}</td>
              </tr>))}
            </tbody>
          </table></div>
        )}
      </div>
    </>
  );
}
