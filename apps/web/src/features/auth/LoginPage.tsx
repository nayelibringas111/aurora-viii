import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/app/auth";
import { ErrorBox, Field } from "@/components/ui";

/** Fondo animado: una pequeña red que se ilumina como una aurora (decorativo, respeta movimiento reducido). */
function AuroraField() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const cols = [4, 7, 7, 5, 3];
    const draw = (t: number) => {
      const w = (cv.width = cv.clientWidth * 1.5), h = (cv.height = cv.clientHeight * 1.5);
      ctx.scale(1.5, 1.5);
      const W = w / 1.5, H = h / 1.5;
      const pts = cols.map((n, c) => Array.from({ length: n }, (_, i) => [W * (0.12 + c * 0.19), H * 0.12 + ((H * 0.55) / (n - 1 || 1)) * i]));
      for (let c = 1; c < pts.length; c++) for (const a of pts[c - 1]) for (const b of pts[c]) {
        const ph = Math.sin(t / 900 + a[1] * 0.02 + b[1] * 0.013 + c);
        ctx.strokeStyle = ph > 0 ? `rgba(47,211,196,${0.05 + ph * 0.22})` : `rgba(143,123,255,${0.05 - ph * 0.18})`;
        ctx.lineWidth = 0.6 + Math.abs(ph);
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo((a[0] + b[0]) / 2, a[1], (a[0] + b[0]) / 2, b[1], b[0], b[1]); ctx.stroke();
      }
      pts.flat().forEach(([x, y], i) => {
        const g = 0.5 + 0.5 * Math.sin(t / 700 + i);
        const grd = ctx.createRadialGradient(x, y, 1, x, y, 16 + g * 10);
        grd.addColorStop(0, `rgba(47,211,196,${0.35 * g + 0.1})`); grd.addColorStop(1, "rgba(47,211,196,0)");
        ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(x, y, 26, 0, 7); ctx.fill();
        ctx.fillStyle = "#18213f"; ctx.strokeStyle = "rgba(223,230,255,.6)"; ctx.beginPath(); ctx.arc(x, y, 5, 0, 7); ctx.fill(); ctx.stroke();
      });
      if (!reduced) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <canvas ref={ref} aria-hidden />;
}

export function LoginPage() {
  const { mode, signInLocal, signInPassword, signUp, configError } = useAuth();
  const [tab, setTab] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null); setInfo(null);
    try {
      if (mode === "local") await signInLocal(email, name || email.split("@")[0]);
      else if (tab === "in") await signInPassword(email, password);
      else setInfo(await signUp(email, password, name));
    } catch (x) { setErr(x); } finally { setBusy(false); }
  };

  return (
    <div className="login">
      <div className="login-art">
        <AuroraField />
        <div className="copy">
          <h1>Aurora<span> VIII</span></h1>
          <p style={{ fontSize: 17, color: "#c9d2f2" }}>Diseña redes neuronales, entrénalas con TensorFlow y Keras, y mira cómo aprenden neurona por neurona.</p>
        </div>
      </div>
      <div className="login-form">
        <form className="stack" onSubmit={submit} style={{ gap: 14 }}>
          <h2>{mode === "local" ? "Ingresar (modo local)" : tab === "in" ? "Ingresar" : "Crear cuenta"}</h2>
          {configError && <div className="alert alert-error">{configError}</div>}
          {mode === "supabase" && (
            <div className="row" role="tablist">
              <button type="button" role="tab" aria-selected={tab === "in"} className={`btn btn-sm${tab === "in" ? " btn-primary" : ""}`} onClick={() => setTab("in")}>Ingresar</button>
              <button type="button" role="tab" aria-selected={tab === "up"} className={`btn btn-sm${tab === "up" ? " btn-primary" : ""}`} onClick={() => setTab("up")}>Crear cuenta</button>
            </div>
          )}
          <Field label="Correo"><input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          {(mode === "local" || tab === "up") && <Field label="Nombre visible"><input required={tab === "up"} minLength={2} maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></Field>}
          {mode === "supabase" && <Field label="Contraseña" hint={tab === "up" ? "Mínimo 8 caracteres" : undefined}><input type="password" required minLength={tab === "up" ? 8 : 1} autoComplete={tab === "up" ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} /></Field>}
          {mode === "local" && <p className="small muted" style={{ margin: 0 }}>Modo de desarrollo: no requiere contraseña. En producción la API usa Supabase Auth.</p>}
          <ErrorBox error={err} />
          {info && <div className="alert alert-info">{info}</div>}
          <button className="btn btn-primary" disabled={busy}>{busy ? "Un momento…" : tab === "up" && mode === "supabase" ? "Crear cuenta" : "Ingresar"}</button>
        </form>
      </div>
    </div>
  );
}
