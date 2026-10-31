/** Cliente API tipado. La API en Render es la única puerta a los datos; el token viaja en Authorization. */
import type { Issue } from "@/types";

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

let tokenProvider: () => Promise<string | null> = async () => null;
let onUnauthorized: () => void = () => {};

export function configureAuth(provider: () => Promise<string | null>, unauthorized: () => void) {
  tokenProvider = provider;
  onUnauthorized = unauthorized;
}
export const getToken = () => tokenProvider();

export class ApiError extends Error {
  status: number;
  issues: Issue[] | string[];
  constructor(status: number, message: string, issues: Issue[] | string[] = []) {
    super(message);
    this.status = status;
    this.issues = issues;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try { body = await res.json(); } catch { /* sin cuerpo JSON */ }
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return new ApiError(res.status, detail);
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; issues?: Issue[] | string[] };
    return new ApiError(res.status, d.message ?? "Solicitud rechazada", d.issues ?? []);
  }
  const fallback: Record<number, string> = {
    401: "Tu sesión terminó. Vuelve a ingresar.", 403: "No tienes permiso para esta acción.",
    404: "No se encontró el recurso.", 429: "Demasiadas solicitudes. Espera un momento.",
  };
  return new ApiError(res.status, fallback[res.status] ?? `Error del servidor (${res.status})`);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await tokenProvider();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "No se pudo conectar con la API. Si está en Render gratuito, puede tardar ~1 min en despertar.");
  }
  if (res.status === 401) onUnauthorized();
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) => request<T>(p, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) }),
  put: <T>(p: string, body: unknown) => request<T>(p, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(p: string, body: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};

/** Descarga autenticada (CSV, PDF, modelos .keras). */
export async function download(path: string, fallbackName: string) {
  const token = await tokenProvider();
  const res = await fetch(`${API_URL}/api/v1${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : "Ocurrió un error inesperado";
}
