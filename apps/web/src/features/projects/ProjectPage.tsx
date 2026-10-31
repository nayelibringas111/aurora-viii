import { NavLink, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useCrumbs } from "@/components/Layout";
import { ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import type { Project } from "@/types";
import { ArchitecturesTab } from "@/features/architectures/ArchitecturesTab";
import { Designer } from "@/features/architectures/Designer";
import { DatasetsTab } from "@/features/datasets/DatasetsTab";
import { TrainingTab } from "@/features/training/TrainingTab";
import { ModelsTab } from "@/features/model-registry/ModelsTab";
import { HistoryTab } from "@/features/reports/HistoryTab";
import { ContextTab } from "./ContextTab";

const TABS = [
  { id: "contexto", label: "Contexto" }, { id: "arquitectura", label: "Arquitectura" }, { id: "dataset", label: "Dataset" },
  { id: "entrenamientos", label: "Entrenamientos" }, { id: "modelos", label: "Modelos" }, { id: "historial", label: "Historial" },
];

export function ProjectPage({ designer }: { designer?: boolean }) {
  const { projectId = "", tab = "contexto" } = useParams();
  const q = useQuery({ queryKey: ["project", projectId], queryFn: () => api.get<Project>(`/projects/${projectId}`) });
  const active = designer ? "arquitectura" : tab;
  useCrumbs([{ label: "Proyectos", to: "/proyectos" }, { label: q.data?.name ?? "…", to: `/proyectos/${projectId}` }, { label: designer ? "Diseñar red" : TABS.find((t) => t.id === active)?.label ?? "" }]);

  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const p = q.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="row"><h1>{p.name}</h1>{p.status === "archived" && <span className="chip">Archivado</span>}</div>
          {p.description && <p>{p.description}</p>}
          <p className="small muted">Tu rol en este proyecto: {p.my_role_label}</p>
        </div>
      </div>
      <nav className="tabs" aria-label="Secciones del proyecto">
        {TABS.map((t) => <NavLink key={t.id} to={`/proyectos/${p.id}/${t.id}`} className={() => (t.id === active ? "active" : "")}>{t.label}</NavLink>)}
      </nav>
      {designer ? <Designer /> :
        active === "contexto" ? <ContextTab project={p} /> :
        active === "arquitectura" ? <ArchitecturesTab project={p} /> :
        active === "dataset" ? <DatasetsTab project={p} /> :
        active === "entrenamientos" ? <TrainingTab project={p} /> :
        active === "modelos" ? <ModelsTab project={p} /> :
        <HistoryTab project={p} />}
    </>
  );
}
