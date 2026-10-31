import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "@/components/Layout";
import { Loading } from "@/components/ui";
import { AdminPage } from "@/features/administration/AdminPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { FamiliesPage, FundamentalsPage } from "@/features/fundamentals/FundamentalsPage";
import { ProjectPage } from "@/features/projects/ProjectPage";
import { ProjectsPage } from "@/features/projects/ProjectsPage";
import { TrainingJobPage } from "@/features/training/TrainingJobPage";
import { AuthProvider, useAuth } from "./auth";

const qc = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 10_000, refetchOnWindowFocus: false, retry: (n, e: unknown) => n < 2 && (e as { status?: number })?.status !== 403 && (e as { status?: number })?.status !== 404 },
  },
});

function Gate() {
  const { me, loading, mode } = useAuth();
  if (loading) return <div style={{ display: "grid", placeItems: "center", height: "100%" }}><Loading label="Conectando con Aurora VIII…" /></div>;
  if (!me || !mode) return <LoginPage />;
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<DashboardPage />} />
        <Route path="proyectos" element={<ProjectsPage />} />
        <Route path="proyectos/:projectId" element={<ProjectPage />} />
        <Route path="proyectos/:projectId/arquitectura/nueva" element={<ProjectPage designer />} />
        <Route path="proyectos/:projectId/entrenamientos/:jobId" element={<TrainingJobPage />} />
        <Route path="proyectos/:projectId/:tab" element={<ProjectPage />} />
        <Route path="fundamentos" element={<FundamentalsPage />} />
        <Route path="familias" element={<FamiliesPage />} />
        <Route path="admin" element={me.is_admin ? <AdminPage /> : <Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider><Gate /></AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
