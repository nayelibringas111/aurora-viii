const dtf = new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" });
export const fmtDate = (s?: string | null) => (s ? dtf.format(new Date(s)) : "—");
export const fmtInt = (n?: number | null) => (n == null ? "—" : n.toLocaleString("es-PE"));
export const fmtNum = (n?: number | null, d = 4) => (n == null || Number.isNaN(n) ? "—" : Number(n).toFixed(d));
export const fmtPct = (n?: number | null) => (n == null ? "—" : `${(n * 100).toFixed(1)} %`);
export function fmtDuration(s?: number | null) {
  if (s == null) return "—";
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s % 60)} s`;
}
export const FAMILY_LABEL: Record<string, string> = { feedforward: "Feedforward", cnn: "CNN", rnn: "RNN", gan: "GAN" };
export const LAYER_LABEL: Record<string, string> = {
  dense: "Dense", dropout: "Dropout", batchnorm: "BatchNorm", conv2d: "Conv2D", maxpool2d: "MaxPool2D", flatten: "Flatten",
  globalavgpool: "GlobalAvgPool", simplernn: "SimpleRNN", lstm: "LSTM", gru: "GRU",
};
export const METRIC_LABEL: Record<string, string> = {
  loss: "Pérdida", accuracy: "Exactitud", val_loss: "Pérdida (validación)", val_accuracy: "Exactitud (validación)",
  d_loss: "Pérdida discriminador", g_loss: "Pérdida generador", dist_gap: "Brecha de distribución", d_real: "D(real)", d_fake: "D(falso)",
  best_val_accuracy: "Mejor exactitud (validación)", best_dist_gap: "Mejor brecha", test_samples: "Muestras de prueba",
};
