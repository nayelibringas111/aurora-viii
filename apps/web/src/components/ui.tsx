import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import type { Issue, JobStatus } from "@/types";

export function StatusBadge({ status, label }: { status: JobStatus | string; label?: string }) {
  const labels: Record<string, string> = {
    QUEUED: "En cola", PREPARING: "Preparando", RUNNING: "Ejecutando", COMPLETED: "Completado", FAILED: "Fallido", CANCELLED: "Cancelado",
    draft: "Borrador", reviewed: "Revisado", approved: "Aprobado", retired: "Retirado",
  };
  return <span className={`badge st-${status}`}>{label ?? labels[status] ?? status}</span>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  const issues = error instanceof ApiError ? error.issues : [];
  return (
    <div className="alert alert-error" role="alert">
      {msg}
      {issues.length > 0 && <ul>{issues.map((i, k) => <li key={k}>{typeof i === "string" ? i : `${(i as Issue).path ? (i as Issue).path + ": " : ""}${(i as Issue).message}`}</li>)}</ul>}
    </div>
  );
}

export function Loading({ label = "Cargando…" }: { label?: string }) {
  return <div className="row muted" style={{ padding: 20 }}><div className="spinner" /> {label}</div>;
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty"><h3>{title}</h3>{children && <p className="muted">{children}</p>}{action}</div>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

export function Progress({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${pct}%` }} /></div>;
}

export function Toast({ text, onDone }: { text: string | null; onDone: () => void }) {
  useEffect(() => { if (text) { const t = setTimeout(onDone, 3200); return () => clearTimeout(t); } }, [text, onDone]);
  return text ? <div className="toast" role="status">{text}</div> : null;
}

export function useToast() {
  const [text, setText] = useState<string | null>(null);
  return { text, show: setText, node: <Toast text={text} onDone={() => setText(null)} /> };
}

export function Stat({ k, v, sub }: { k: string; v: ReactNode; sub?: ReactNode }) {
  return <div className="panel stat"><div className="k">{k}</div><div className="v num">{v}</div>{sub && <div className="small muted">{sub}</div>}</div>;
}
