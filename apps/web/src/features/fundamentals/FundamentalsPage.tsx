import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useCrumbs } from "@/components/Layout";
import { ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import type { FamilyInfo } from "@/types";
import { NetworkCanvas, topologyFromSummary } from "@/features/training/NetworkCanvas";

interface Section { id: string; title: string; body: string; keypoints?: string[]; formula?: string; code?: string; activations?: { name: string; formula: string; use: string }[] }

const ACT: Record<string, (z: number) => number> = {
  relu: (z) => Math.max(0, z), sigmoid: (z) => 1 / (1 + Math.exp(-z)), tanh: Math.tanh, linear: (z) => z,
};

/** Neurona interactiva: mueve entradas, pesos y sesgo y mira cómo cambia la salida. */
function NeuronLab() {
  const [x, setX] = useState([0.8, -0.4]);
  const [w, setW] = useState([1.2, 0.7]);
  const [b, setB] = useState(0.1);
  const [f, setF] = useState("relu");
  const z = x[0] * w[0] + x[1] * w[1] + b;
  const a = ACT[f](z);
  const slider = (label: string, v: number, set: (n: number) => void, min = -2, max = 2) => (
    <label className="field"><span>{label}: <span className="num">{v.toFixed(2)}</span></span><input type="range" min={min} max={max} step={0.05} value={v} onChange={(e) => set(Number(e.target.value))} /></label>
  );
  const curve = useMemo(() => Array.from({ length: 81 }, (_, i) => { const zz = -4 + i * 0.1; return `${i * 3},${70 - Math.max(-1.2, Math.min(1.6, ACT[f](zz))) * 30}`; }).join(" "), [f]);
  return (
    <div className="panel panel-pad">
      <h2 style={{ marginBottom: 4 }}>Prueba una neurona</h2>
      <p className="muted">Calcula z = x₁·w₁ + x₂·w₂ + b y aplica la activación.</p>
      <div className="grid cols-3" style={{ alignItems: "center" }}>
        <div className="stack" style={{ gap: 6 }}>
          {slider("Entrada x₁", x[0], (v) => setX([v, x[1]]))}{slider("Entrada x₂", x[1], (v) => setX([x[0], v]))}
          {slider("Peso w₁", w[0], (v) => setW([v, w[1]]))}{slider("Peso w₂", w[1], (v) => setW([w[0], v]))}
          {slider("Sesgo b", b, setB)}
        </div>
        <svg viewBox="0 0 260 160" style={{ width: "100%", background: "var(--night)", borderRadius: 10 }} role="img" aria-label={`Neurona con salida ${a.toFixed(2)}`}>
          {[0, 1].map((i) => <g key={i}>
            <line x1={40} y1={45 + i * 70} x2={150} y2={80} stroke={w[i] >= 0 ? "#2fd3c4" : "#8f7bff"} strokeWidth={1 + Math.abs(w[i]) * 2.5} opacity={0.4 + Math.min(0.6, Math.abs(x[i] * w[i]) / 2)} />
            <circle cx={40} cy={45 + i * 70} r={14} fill="#18213f" stroke="#dfe6ff" strokeOpacity={0.5} />
            <text x={40} y={49 + i * 70} textAnchor="middle" fill="#fff" fontSize={11}>{x[i].toFixed(1)}</text>
          </g>)}
          <circle cx={150} cy={80} r={22 + Math.min(14, Math.abs(a) * 6)} fill={a >= 0 ? "#2fd3c4" : "#8f7bff"} opacity={0.18} />
          <circle cx={150} cy={80} r={20} fill="#18213f" stroke="#2fd3c4" />
          <text x={150} y={84} textAnchor="middle" fill="#fff" fontSize={11}>Σ, {f}</text>
          <line x1={172} y1={80} x2={232} y2={80} stroke="#dfe6ff" strokeOpacity={0.6} />
          <text x={238} y={84} fill="#fff" fontSize={13} fontWeight={700}>{a.toFixed(2)}</text>
        </svg>
        <div className="stack" style={{ gap: 8 }}>
          <label className="field"><span>Activación</span><select value={f} onChange={(e) => setF(e.target.value)}>{Object.keys(ACT).map((k) => <option key={k}>{k}</option>)}</select></label>
          <svg viewBox="0 0 240 110" style={{ width: "100%", background: "var(--surface-2)", borderRadius: 8 }} aria-hidden>
            <line x1={0} y1={70} x2={240} y2={70} stroke="#c3ccd9" /><line x1={120} y1={0} x2={120} y2={110} stroke="#c3ccd9" />
            <polyline points={curve} fill="none" stroke="#0e8a8c" strokeWidth={2} />
            <circle cx={120 + Math.max(-4, Math.min(4, z)) * 30} cy={70 - Math.max(-1.2, Math.min(1.6, a)) * 30} r={5} fill="#6d4fd6" />
          </svg>
          <div className="formula num">z = {z.toFixed(2)} → a = {a.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}

export function FundamentalsPage() {
  useCrumbs([{ label: "Fundamentos" }]);
  const q = useQuery({ queryKey: ["fundamentals"], queryFn: () => api.get<{ sections: Section[]; glossary: { term: string; definition: string }[] }>("/fundamentals") });
  const [filter, setFilter] = useState("");
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const { sections, glossary } = q.data!;
  return (
    <>
      <div className="page-head"><div><h1>Fundamentos de redes neuronales</h1><p>Qué es una red neuronal, cómo está construida y cómo se crea con TensorFlow y Keras.</p></div></div>
      <div className="grid" style={{ gridTemplateColumns: "220px minmax(0,1fr)", alignItems: "start" }}>
        <nav className="panel panel-pad stack" style={{ position: "sticky", top: 80, gap: 6 }} aria-label="Índice">
          {sections.map((s, i) => <a key={s.id} href={`#${s.id}`} className="small" style={{ textDecoration: "none" }}>{i + 1}. {s.title}</a>)}
          <a href="#glosario" className="small" style={{ textDecoration: "none" }}>Glosario</a>
        </nav>
        <div className="stack" style={{ gap: 18 }}>
          {sections.map((s) => (
            <section key={s.id} id={s.id} className="panel panel-pad prose" style={{ maxWidth: "none" }}>
              <h2>{s.title}</h2>
              <p style={{ maxWidth: "72ch" }}>{s.body}</p>
              {s.formula && <div className="formula">{s.formula}</div>}
              {s.keypoints && <ul style={{ margin: "6px 0 0", paddingLeft: 20 }}>{s.keypoints.map((k) => <li key={k}>{k}</li>)}</ul>}
              {s.activations && <table className="tbl" style={{ marginTop: 8 }}><thead><tr><th>Función</th><th>Fórmula</th><th>Uso típico</th></tr></thead><tbody>{s.activations.map((a) => <tr key={a.name}><td><strong>{a.name}</strong></td><td>{a.formula}</td><td>{a.use}</td></tr>)}</tbody></table>}
              {s.code && <pre className="code">{s.code}</pre>}
              {s.id === "neurona" && <div style={{ marginTop: 14 }}><NeuronLab /></div>}
            </section>
          ))}
          <section id="glosario" className="panel">
            <div className="panel-head"><h2>Glosario</h2><input type="search" placeholder="Filtrar términos" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ maxWidth: 240 }} aria-label="Filtrar glosario" /></div>
            <dl className="panel-pad kv">{glossary.filter((g) => (g.term + g.definition).toLowerCase().includes(filter.toLowerCase())).map((g) => <Fragment key={g.term}><dt style={{ color: "var(--ink)", fontWeight: 600 }}>{g.term}</dt><dd>{g.definition}</dd></Fragment>)}</dl>
          </section>
        </div>
      </div>
      <style>{`@media (max-width: 900px){ .grid[style*="220px"]{ grid-template-columns: 1fr !important; } .grid[style*="220px"] > nav{ position: static !important; } }`}</style>
    </>
  );
}

export function FamiliesPage() {
  useCrumbs([{ label: "Catálogo de redes" }]);
  const q = useQuery({ queryKey: ["families"], queryFn: () => api.get<FamilyInfo[]>("/families") });
  const previews = useQuery({
    queryKey: ["family-previews"], enabled: !!q.data,
    queryFn: async () => Object.fromEntries(await Promise.all(q.data!.map(async (f) => [f.id, (await api.post<{ summary: never }>("/architectures/validate", { family: f.id, config: f.template })).summary]))),
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  return (
    <>
      <div className="page-head"><div><h1>Catálogo de arquitecturas</h1><p>Las cuatro familias de la Semana 11: cuándo usar cada una y qué restricciones valida Aurora VIII.</p></div></div>
      <div className="grid cols-2">
        {q.data!.map((f) => (
          <article key={f.id} className="panel">
            <div className="stage" style={{ borderRadius: "10px 10px 0 0", border: 0 }}>
              {previews.data?.[f.id] ? <NetworkCanvas topology={topologyFromSummary(f.id, previews.data[f.id])} snapshot={null} running={false} compact height={300} /> : <div style={{ height: 300 }} />}
            </div>
            <div className="panel-pad stack">
              <div className="spread"><h2>{f.name}</h2>{f.status !== "habilitada" && <span className="chip">{f.status}</span>}</div>
              <p style={{ margin: 0 }}>{f.summary}</p>
              <div className="grid cols-2" style={{ gap: 10 }}>
                <div><h3 style={{ fontSize: 14, marginBottom: 4 }}>Casos de uso</h3><ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{f.use_cases.map((u) => <li key={u}>{u}</li>)}</ul></div>
                <div><h3 style={{ fontSize: 14, marginBottom: 4 }}>Restricciones</h3><ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{f.restrictions.map((u) => <li key={u}>{u}</li>)}</ul></div>
              </div>
              <div><Link className="btn btn-sm" to="/proyectos">Usar en un proyecto</Link></div>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
