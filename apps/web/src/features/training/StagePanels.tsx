import { useEffect, useRef } from "react";
import type { Snapshot } from "@/types";

export const CLASS_COLORS = ["#2fd3c4", "#8f7bff", "#f2b84b", "#ff7a93", "#5aa9ff", "#7fdc7a", "#e58cff", "#ffd27f"];

/** La muestra que atraviesa la red en este instante y lo que la red responde. */
export function SamplePanel({ snapshot, classNames }: { snapshot: Snapshot | null; classNames: string[] }) {
  const s = snapshot?.sample;
  if (!s) return <div className="stage-side"><h3>Muestra en tránsito</h3><p className="small" style={{ color: "#aab5d9" }}>Aparecerá cuando el worker empiece a entrenar.</p></div>;
  if (s.kind === "gan") {
    return (
      <div className="stage-side">
        <h3>Muestra generada</h3>
        <p className="small" style={{ color: "#aab5d9", margin: 0 }}>El generador produjo ({s.generated?.map((v) => v.toFixed(2)).join(", ")}).</p>
        <div className="probbar" style={{ marginTop: 10 }}><span className="lbl">D la cree real</span><div className="track"><div className="fill" style={{ width: `${(s.d_fake ?? 0) * 100}%` }} /></div><span className="num">{((s.d_fake ?? 0) * 100).toFixed(0)}%</span></div>
      </div>
    );
  }
  const correct = s.pred === s.true;
  return (
    <div className="stage-side">
      <h3>Muestra en tránsito</h3>
      {s.kind === "image" && s.pixels && <Pixels pixels={s.pixels} />}
      {s.kind === "series" && s.values && <Spark values={s.values} />}
      {s.kind === "vector" && s.values && <p className="small num" style={{ color: "#dfe6ff", margin: "0 0 8px" }}>({s.values.map((v) => v.toFixed(2)).join(", ")})</p>}
      <div style={{ marginTop: 10 }}>
        {s.probs?.map((p, i) => (
          <div key={i} className={`probbar${i === s.true ? " true" : ""}`}>
            <span className="lbl" title={classNames[i]}>{classNames[i] ?? `Clase ${i}`}{i === s.true ? " ✓" : ""}</span>
            <div className="track"><div className="fill" style={{ width: `${p * 100}%`, background: i === s.pred ? (correct ? "#2fd3c4" : "#ff7a93") : "rgba(223,230,255,.35)" }} /></div>
            <span className="num">{(p * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
      <p className="small" style={{ color: correct ? "#7fe6dc" : "#ff9fb0", margin: "8px 0 0" }}>
        {correct ? "La red acierta esta muestra." : `La red responde «${classNames[s.pred ?? 0] ?? s.pred}»; la etiqueta real es «${classNames[s.true ?? 0] ?? s.true}».`}
      </p>
    </div>
  );
}

function Pixels({ pixels }: { pixels: number[][] }) {
  const n = pixels.length, c = 12;
  return (
    <svg width={n * c} height={n * c} role="img" aria-label="Imagen de entrada" style={{ borderRadius: 4, display: "block" }}>
      {pixels.map((row, y) => row.map((v, x) => <rect key={`${x}-${y}`} x={x * c} y={y * c} width={c} height={c} fill={`rgba(223,240,255,${0.05 + v * 0.95})`} />))}
    </svg>
  );
}

function Spark({ values }: { values: number[] }) {
  const w = 220, h = 60, min = Math.min(...values), max = Math.max(...values);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 6) - 3}`).join(" ");
  return <svg width="100%" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Secuencia de entrada"><polyline points={pts} fill="none" stroke="#2fd3c4" strokeWidth="2" /></svg>;
}

/** Frontera de decisión (datasets 2D): cómo la red divide el plano época a época. */
export function BoundaryPanel({ snapshot, points, classNames }: { snapshot: Snapshot | null; points?: number[][] | null; classNames: string[] }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const b = snapshot?.boundary;
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !b) return;
    const S = 240, ctx = cv.getContext("2d")!;
    cv.width = S; cv.height = S;
    const cell = S / b.n;
    b.cls.forEach((c, i) => {
      const gx = i % b.n, gy = Math.floor(i / b.n);
      ctx.fillStyle = CLASS_COLORS[c % CLASS_COLORS.length];
      ctx.globalAlpha = 0.12 + 0.45 * Math.max(0, (b.conf[i] - 0.5) * 2);
      ctx.fillRect(gx * cell, S - (gy + 1) * cell, cell + 0.5, cell + 0.5);
    });
    ctx.globalAlpha = 1;
    (points ?? []).forEach(([x, y, c]) => {
      const px = ((x - b.x[0]) / (b.x[1] - b.x[0])) * S, py = S - ((y - b.y[0]) / (b.y[1] - b.y[0])) * S;
      ctx.fillStyle = CLASS_COLORS[c % CLASS_COLORS.length];
      ctx.strokeStyle = "rgba(10,14,32,.8)";
      ctx.beginPath(); ctx.arc(px, py, 2.6, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
  }, [b, points]);
  return (
    <div className="stage-side">
      <h3>Frontera de decisión</h3>
      {b ? <canvas ref={ref} style={{ width: "100%", maxWidth: 240, aspectRatio: "1", borderRadius: 6, display: "block" }} role="img" aria-label="Mapa de la frontera de decisión con los puntos de entrenamiento" />
        : <p className="small" style={{ color: "#aab5d9" }}>Se dibuja al terminar cada época.</p>}
      <div className="row small" style={{ marginTop: 8, gap: 12 }}>
        {classNames.map((c, i) => <span key={i} className="row" style={{ gap: 5, color: "#aab5d9" }}><i style={{ width: 9, height: 9, borderRadius: 2, background: CLASS_COLORS[i % CLASS_COLORS.length], display: "inline-block" }} />{c}</span>)}
      </div>
    </div>
  );
}

/** GAN: puntos reales vs generados. */
export function GanPanel({ snapshot, real }: { snapshot: Snapshot | null; real?: number[][] }) {
  const S = 240, lim = 1.4;
  const tx = (v: number) => ((v + lim) / (2 * lim)) * S;
  return (
    <div className="stage-side">
      <h3>Real frente a generado</h3>
      <svg viewBox={`0 0 ${S} ${S}`} width="100%" style={{ maxWidth: 240, display: "block", background: "rgba(255,255,255,.03)", borderRadius: 6 }} role="img" aria-label="Distribución real y generada">
        {(real ?? []).map(([x, y], i) => <circle key={`r${i}`} cx={tx(x)} cy={S - tx(y)} r={1.8} fill="#8f7bff" opacity={0.6} />)}
        {(snapshot?.generated_points ?? []).map(([x, y], i) => <circle key={`g${i}`} cx={tx(x)} cy={S - tx(y)} r={1.8} fill="#2fd3c4" />)}
      </svg>
      <div className="row small" style={{ marginTop: 8, color: "#aab5d9", gap: 12 }}>
        <span><i style={{ display: "inline-block", width: 9, height: 9, borderRadius: 9, background: "#8f7bff", marginRight: 5 }} />Real</span>
        <span><i style={{ display: "inline-block", width: 9, height: 9, borderRadius: 9, background: "#2fd3c4", marginRight: 5 }} />Generado</span>
      </div>
    </div>
  );
}
