import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { IconDown, IconPlus, IconTrash, IconUp } from "@/components/Icons";
import { ErrorBox, Field } from "@/components/ui";
import { api } from "@/lib/api";
import { FAMILY_LABEL, LAYER_LABEL, fmtInt } from "@/lib/format";
import type { ArchConfig, ArchSummary, Architecture, ClassifierConfig, Family, FamilyInfo, GanConfig, Issue, LayerSpec } from "@/types";
import { NetworkCanvas, topologyFromSummary } from "@/features/training/NetworkCanvas";
import { kerasCode } from "./kerasCode";

const ALLOWED: Record<Family, string[]> = {
  feedforward: ["dense", "dropout", "batchnorm"],
  cnn: ["conv2d", "maxpool2d", "flatten", "globalavgpool", "dense", "dropout", "batchnorm"],
  rnn: ["lstm", "gru", "simplernn", "dense", "dropout"],
  gan: ["dense", "dropout", "batchnorm"],
};
const DEFAULTS: Record<string, LayerSpec> = {
  dense: { type: "dense", units: 16, activation: "relu" }, dropout: { type: "dropout", rate: 0.2 }, batchnorm: { type: "batchnorm" },
  conv2d: { type: "conv2d", filters: 8, kernel: 3, padding: "same", activation: "relu" }, maxpool2d: { type: "maxpool2d", pool: 2 },
  flatten: { type: "flatten" }, globalavgpool: { type: "globalavgpool" },
  lstm: { type: "lstm", units: 16, return_sequences: false }, gru: { type: "gru", units: 16, return_sequences: false },
  simplernn: { type: "simplernn", units: 16, return_sequences: false },
};
const ACTS = ["relu", "tanh", "sigmoid", "elu", "selu", "gelu", "leaky_relu", "swish", "linear"];

type Stack = "layers" | "generator" | "discriminator";

export function Designer() {
  const { projectId = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const families = useQuery({ queryKey: ["families"], queryFn: () => api.get<FamilyInfo[]>("/families") });
  const [family, setFamily] = useState<Family>("feedforward");
  const [cfg, setCfg] = useState<ArchConfig | null>(null);
  const [name, setName] = useState("Mi red");
  const [justification, setJustification] = useState("");
  const [stack, setStack] = useState<Stack>("layers");
  const [sel, setSel] = useState(0);
  const [summary, setSummary] = useState<ArchSummary | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [saveErr, setSaveErr] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const info = families.data?.find((f) => f.id === family);

  useEffect(() => {
    if (!families.data) return;
    const f = families.data.find((x) => x.id === family);
    if (f) { setCfg(JSON.parse(JSON.stringify(f.template))); setStack(family === "gan" ? "generator" : "layers"); setSel(0); setName(`${FAMILY_LABEL[family]} base`); }
  }, [family, families.data]);

  // Validación en vivo contra el backend (la autoridad final)
  useEffect(() => {
    if (!cfg) return;
    const t = setTimeout(async () => {
      try {
        const r = await api.post<{ valid: boolean; summary?: ArchSummary; issues: Issue[] }>("/architectures/validate", { family, config: cfg });
        setIssues(r.issues);
        if (r.valid && r.summary) setSummary(r.summary);
      } catch (e) { setIssues([{ path: "", message: e instanceof Error ? e.message : "Error" }]); }
    }, 300);
    return () => clearTimeout(t);
  }, [cfg, family]);

  const layers: LayerSpec[] = useMemo(() => (cfg ? ((cfg as unknown as Record<Stack, LayerSpec[]>)[stack] ?? []) : []), [cfg, stack]);
  const setLayers = (fn: (l: LayerSpec[]) => LayerSpec[]) => setCfg((c) => (c ? ({ ...c, [stack]: fn([...((c as unknown as Record<Stack, LayerSpec[]>)[stack] ?? [])]) } as ArchConfig) : c));
  const current = layers[sel];
  const update = (patch: Partial<LayerSpec>) => setLayers((l) => { l[sel] = { ...l[sel], ...patch }; return l; });
  const move = (d: number) => setLayers((l) => { const j = sel + d; if (j < 0 || j >= l.length) return l; [l[sel], l[j]] = [l[j], l[sel]]; setSel(j); return l; });
  const remove = () => setLayers((l) => { l.splice(sel, 1); setSel(Math.max(0, sel - 1)); return l; });
  const add = (t: string) => setLayers((l) => { l.splice(sel + 1, 0, { ...DEFAULTS[t] }); setSel(Math.min(l.length - 1, sel + 1)); return l; });

  const topology = useMemo(() => (summary ? topologyFromSummary(family, summary as never) : null), [summary, family]);

  const save = async () => {
    if (!cfg) return;
    setSaving(true); setSaveErr(null);
    try {
      await api.post<Architecture>(`/projects/${projectId}/architectures`, { name, family, justification, config: cfg });
      qc.invalidateQueries({ queryKey: ["architectures", projectId] });
      nav(`/proyectos/${projectId}/arquitectura`);
    } catch (e) { setSaveErr(e); } finally { setSaving(false); }
  };

  if (!cfg) return null;
  const c = cfg as ClassifierConfig, g = cfg as GanConfig;

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="family-pick" role="group" aria-label="Familia de red">
        {families.data?.map((f) => (
          <button key={f.id} aria-pressed={f.id === family} onClick={() => setFamily(f.id)}>
            <strong>{f.name}</strong>
            <span className="small muted">{f.summary}</span>
            {f.status !== "habilitada" && <div style={{ marginTop: 6 }}><span className="chip">{f.status}</span></div>}
          </button>
        ))}
      </div>

      <div className="designer">
        {/* Panel de capas */}
        <div className="panel panel-pad stack">
          {family === "gan" && (
            <div className="row" role="tablist">
              {(["generator", "discriminator"] as Stack[]).map((s) => (
                <button key={s} role="tab" aria-selected={stack === s} className={`btn btn-sm${stack === s ? " btn-primary" : ""}`} onClick={() => { setStack(s); setSel(0); }}>{s === "generator" ? "Generador" : "Discriminador"}</button>
              ))}
            </div>
          )}
          <h3>Capas ocultas</h3>
          <div className="stack" style={{ gap: 6 }}>
            <div className="layer-item" style={{ cursor: "default", background: "var(--surface-2)" }}>
              <span className="idx">in</span>
              <span>{family === "gan" ? (stack === "generator" ? `Ruido z (${g.latent_dim})` : `Muestra (${g.data_dim})`) : `Entrada [${c.input_shape.join("×")}]`}</span><span />
            </div>
            {layers.map((l, i) => (
              <button key={i} className={`layer-item${i === sel ? " sel" : ""}`} onClick={() => setSel(i)} aria-pressed={i === sel}>
                <span className="idx">{i + 1}</span>
                <span><strong>{LAYER_LABEL[l.type]}</strong> <span className="muted small">{l.units ?? l.filters ?? (l.rate != null ? `${l.rate}` : l.pool ?? "")}</span></span>
                <span className="small muted">{l.activation ?? ""}</span>
              </button>
            ))}
            <div className="layer-item" style={{ cursor: "default", background: "var(--surface-2)" }}>
              <span className="idx">out</span>
              <span>{family === "gan" ? (stack === "generator" ? `Dense ${g.data_dim} lineal` : "Dense 1 sigmoide") : `Dense ${c.output.units} ${c.output.activation}`}</span><span />
            </div>
          </div>
          <div className="row" style={{ gap: 6 }}>
            <button className="btn btn-sm" onClick={() => move(-1)} disabled={sel === 0} aria-label="Subir capa"><IconUp /></button>
            <button className="btn btn-sm" onClick={() => move(1)} disabled={sel >= layers.length - 1} aria-label="Bajar capa"><IconDown /></button>
            <button className="btn btn-sm btn-danger" onClick={remove} disabled={!current} aria-label="Eliminar capa"><IconTrash /></button>
          </div>
          <Field label="Añadir capa después de la seleccionada">
            <select value="" onChange={(e) => e.target.value && add(e.target.value)}>
              <option value="">Elegir tipo…</option>
              {ALLOWED[family].map((t) => <option key={t} value={t}>{LAYER_LABEL[t]}</option>)}
            </select>
          </Field>
        </div>

        {/* Lienzo central */}
        <div className="stack" style={{ minWidth: 0 }}>
          <div className="stage">
            <div className="stage-bar"><h2>Vista previa del grafo</h2><span className="small" style={{ color: "#aab5d9" }}>{summary ? `${fmtInt(summary.total_params)} parámetros entrenables` : "Validando…"}</span></div>
            {topology && <NetworkCanvas topology={topology} snapshot={null} running={false} compact />}
          </div>
          {issues.length > 0 ? (
            <div className="alert alert-error" role="alert">La configuración tiene problemas:<ul>{issues.map((i, k) => <li key={k}>{i.path && <code>{i.path}</code>} {i.message}</li>)}</ul></div>
          ) : <div className="alert alert-info">Configuración válida. Las formas de entrada y salida encajan en todas las capas.</div>}
          {summary && (
            <div className="panel table-wrap">
              <table className="tbl">
                <thead><tr><th>Capa</th><th>Forma de salida</th><th>Activación</th><th style={{ textAlign: "right" }}>Parámetros</th></tr></thead>
                <tbody>{summary.layers.map((l, i) => <tr key={i}><td>{l.name}</td><td className="num">[{l.output_shape.join(", ")}]</td><td>{l.activation ?? "—"}</td><td className="num" style={{ textAlign: "right" }}>{fmtInt(l.params)}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          <details className="panel panel-pad"><summary style={{ cursor: "pointer", fontWeight: 600 }}>Código Keras equivalente</summary><pre className="code" style={{ marginTop: 10 }}>{kerasCode(family, cfg)}</pre></details>
        </div>

        {/* Propiedades */}
        <div className="panel panel-pad stack">
          <h3>Propiedades</h3>
          {current ? <LayerProps layer={current} family={family} onChange={update} /> : <p className="muted small">Selecciona una capa para editarla.</p>}
          <hr style={{ border: 0, borderTop: "1px solid var(--line)", width: "100%" }} />
          {family === "gan" ? <>
            <Field label="Dimensión del ruido (latent_dim)"><input type="number" min={1} max={128} value={g.latent_dim} onChange={(e) => setCfg({ ...g, latent_dim: Number(e.target.value) })} /></Field>
            <Field label="Dimensión de los datos" hint="Debe coincidir con el dataset (Anillo 2D = 2)"><input type="number" min={1} max={64} value={g.data_dim} onChange={(e) => setCfg({ ...g, data_dim: Number(e.target.value) })} /></Field>
          </> : <>
            <Field label="Forma de entrada" hint={family === "cnn" ? "alto, ancho, canales" : family === "rnn" ? "pasos, rasgos" : "número de rasgos"}>
              <input value={c.input_shape.join(", ")} onChange={(e) => setCfg({ ...c, input_shape: e.target.value.split(",").map((v) => parseInt(v.trim(), 10)).filter((v) => !Number.isNaN(v)) })} />
            </Field>
            <div className="grid cols-2" style={{ gap: 10 }}>
              <Field label="Neuronas de salida"><input type="number" min={1} max={100} value={c.output.units} onChange={(e) => setCfg({ ...c, output: { ...c.output, units: Number(e.target.value) } })} /></Field>
              <Field label="Activación de salida"><select value={c.output.activation} onChange={(e) => setCfg({ ...c, output: { ...c.output, activation: e.target.value } })}>{["softmax", "sigmoid"].map((a) => <option key={a}>{a}</option>)}</select></Field>
            </div>
          </>}
          <hr style={{ border: 0, borderTop: "1px solid var(--line)", width: "100%" }} />
          <Field label="Nombre de la arquitectura" hint="Guardar con el mismo nombre crea una nueva versión"><input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} /></Field>
          <Field label="¿Por qué esta familia?" hint="Queda registrado como evidencia de la elección">
            <textarea value={justification} onChange={(e) => setJustification(e.target.value)} placeholder={info ? `Ej.: ${info.use_cases[0]}; ${info.summary.toLowerCase()}` : ""} />
          </Field>
          <ErrorBox error={saveErr} />
          <button className="btn btn-primary" onClick={save} disabled={saving || issues.length > 0 || name.trim().length < 2}><IconPlus />{saving ? "Guardando…" : "Guardar arquitectura"}</button>
        </div>
      </div>
    </div>
  );
}

function LayerProps({ layer, family, onChange }: { layer: LayerSpec; family: Family; onChange: (p: Partial<LayerSpec>) => void }) {
  const num = (k: keyof LayerSpec, label: string, min: number, max: number, step = 1, hint?: string) => (
    <Field label={label} hint={hint}><input type="number" min={min} max={max} step={step} value={(layer[k] as number) ?? ""} onChange={(e) => onChange({ [k]: step < 1 ? Number(e.target.value) : parseInt(e.target.value, 10) })} /></Field>
  );
  const actSel = (
    <Field label="Función de activación"><select value={layer.activation} onChange={(e) => onChange({ activation: e.target.value })}>{ACTS.map((a) => <option key={a}>{a}</option>)}</select></Field>
  );
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="small muted">{LAYER_LABEL[layer.type]} · familia {FAMILY_LABEL[family]}</div>
      {layer.type === "dense" && <>{num("units", "Neuronas", 1, 512)}{actSel}</>}
      {layer.type === "dropout" && num("rate", "Proporción apagada", 0, 0.85, 0.05, "Fracción de neuronas desactivadas al azar en cada lote")}
      {layer.type === "conv2d" && <>{num("filters", "Filtros", 1, 256)}{num("kernel", "Tamaño del kernel", 1, 7)}
        <Field label="Relleno"><select value={layer.padding} onChange={(e) => onChange({ padding: e.target.value as "same" | "valid" })}><option value="same">same (conserva tamaño)</option><option value="valid">valid (reduce tamaño)</option></select></Field>{actSel}</>}
      {layer.type === "maxpool2d" && num("pool", "Ventana de pooling", 2, 4)}
      {["lstm", "gru", "simplernn"].includes(layer.type) && <>{num("units", "Unidades", 1, 512)}
        <label className="row small"><input type="checkbox" checked={!!layer.return_sequences} onChange={(e) => onChange({ return_sequences: e.target.checked })} /> Devolver la secuencia completa (necesario si sigue otra capa recurrente)</label></>}
      {["flatten", "globalavgpool", "batchnorm"].includes(layer.type) && <p className="small muted">Esta capa no tiene parámetros configurables.</p>}
    </div>
  );
}
