import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { METRIC_LABEL } from "@/lib/format";
import type { EpochMetrics } from "@/types";

const COLORS: Record<string, string> = {
  loss: "#0e8a8c", val_loss: "#6d4fd6", accuracy: "#0e8a8c", val_accuracy: "#6d4fd6",
  d_loss: "#6d4fd6", g_loss: "#0e8a8c", dist_gap: "#d99a0b",
};

export function MetricsChart({ data, keys, title, percent, height = 240 }: { data: EpochMetrics[]; keys: string[]; title: string; percent?: boolean; height?: number }) {
  const present = keys.filter((k) => data.some((d) => d[k] != null));
  return (
    <div className="panel panel-pad">
      <h3 style={{ marginBottom: 10 }}>{title}</h3>
      {data.length === 0 ? <p className="muted small">Las curvas aparecen al terminar la primera época.</p> : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="#e3e8ef" vertical={false} />
            <XAxis dataKey="epoch" tick={{ fontSize: 12, fill: "#6f7891" }} tickLine={false} axisLine={{ stroke: "#d9e0ea" }} />
            <YAxis tick={{ fontSize: 12, fill: "#6f7891" }} tickLine={false} axisLine={false} width={48}
              domain={percent ? [0, 1] : ["auto", "auto"]} tickFormatter={(v: number) => (percent ? `${Math.round(v * 100)}%` : v.toFixed(2))} />
            <Tooltip formatter={(v, n) => [percent ? `${(Number(v) * 100).toFixed(1)} %` : Number(v).toFixed(4), METRIC_LABEL[String(n)] ?? String(n)]}
              labelFormatter={(l) => `Época ${l}`} contentStyle={{ borderRadius: 8, border: "1px solid #d9e0ea", fontSize: 13 }} />
            <Legend formatter={(v: string) => METRIC_LABEL[v] ?? v} wrapperStyle={{ fontSize: 13 }} />
            {present.map((k) => (
              <Line key={k} type="monotone" dataKey={k} stroke={COLORS[k] ?? "#48526e"} strokeWidth={2} dot={false} isAnimationActive={false}
                strokeDasharray={k.startsWith("val_") ? "5 4" : undefined} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export function ConfusionMatrix({ matrix, classNames }: { matrix: number[][]; classNames: string[] }) {
  const max = Math.max(1, ...matrix.flat());
  return (
    <div className="table-wrap">
      <table className="tbl" style={{ width: "auto" }}>
        <caption className="small muted" style={{ textAlign: "left", paddingBottom: 6 }}>Filas: clase real · Columnas: predicción (conjunto de prueba)</caption>
        <thead><tr><th />{classNames.map((c) => <th key={c} style={{ textAlign: "center" }}>{c}</th>)}</tr></thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <th scope="row">{classNames[i]}</th>
              {row.map((v, j) => (
                <td key={j} className="num" style={{ textAlign: "center", fontWeight: i === j ? 700 : 400,
                  background: i === j ? `rgba(14,138,140,${0.08 + 0.5 * (v / max)})` : v ? `rgba(196,56,74,${0.06 + 0.4 * (v / max)})` : undefined }}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
