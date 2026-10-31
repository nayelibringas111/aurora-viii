/**
 * Lienzo de la red neuronal en vivo.
 * - Neuronas: brillan según su activación para la muestra que atraviesa la red (turquesa = positiva, violeta = negativa).
 * - Conexiones: grosor y opacidad según |peso|; color según el signo.
 * - Mientras el entrenamiento está en marcha, pulsos de luz viajan por las conexiones con más señal
 *   (activación de origen × peso), de la entrada a la salida.
 * Los valores se interpolan entre instantáneas para que los cambios se vean continuos.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { Snapshot, Topology, VisLayer } from "@/types";

interface Props {
  topology: Topology;
  snapshot: Snapshot | null;
  running: boolean;
  height?: number;
  classNames?: string[];
  compact?: boolean;
}

interface Node { x: number; y: number; g: number; l: number; n: number; idx: number; r: number }
interface Particle { g: number; c: number; a: number; b: number; t: number; speed: number; sign: number; s: number }

const POS = [47, 211, 196];
const NEG = [143, 123, 255];
const rgba = (c: number[], a: number) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

const OP_LABEL: Record<string, string> = { dropout: "Dropout", batchnorm: "BatchNorm", maxpool2d: "MaxPool", flatten: "Flatten", globalavgpool: "GlobalAvgPool" };
const KIND_LABEL: Record<VisLayer["kind"], string> = { input: "Entrada", dense: "Dense", conv: "Conv2D", recurrent: "Recurrente", output: "Salida" };

export function NetworkCanvas({ topology, snapshot, running, height, classNames, compact }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(900);
  const reduced = useMemo(() => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches, []);

  // Valores objetivo (última instantánea) y valores actuales (interpolados)
  const target = useRef<{ acts: number[][][]; weights: number[][][][] }>({ acts: [], weights: [] });
  const current = useRef<{ acts: number[][][]; weights: number[][][][] }>({ acts: [], weights: [] });
  const particles = useRef<Particle[]>([]);
  const hover = useRef<{ x: number; y: number } | null>(null);
  const runningRef = useRef(running);
  runningRef.current = running;
  const pulse = useRef(0); // destello breve cuando llega una nueva instantánea

  const maxShown = Math.max(...topology.groups.flatMap((g) => g.layers.map((l) => l.shown.length)));
  const H = height ?? Math.max(compact ? 240 : 320, Math.min(520, maxShown * (compact ? 22 : 30) + 110));

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(320, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Estructura vacía coherente con la topología
  useEffect(() => {
    const empty = {
      acts: topology.groups.map((g) => g.layers.map((l) => l.shown.map(() => 0))),
      weights: topology.groups.map((g) => g.layers.slice(1).map((l, i) => g.layers[i].shown.map(() => l.shown.map(() => 0.42)))),
    };
    target.current = JSON.parse(JSON.stringify(empty));
    current.current = JSON.parse(JSON.stringify(empty));
    particles.current = [];
    applySnapshot(snapRef.current, true);
  }, [topology]); // eslint-disable-line react-hooks/exhaustive-deps

  const snapRef = useRef(snapshot);
  snapRef.current = snapshot;
  // Si la topología se reconstruye (p. ej. al resincronizar), se reaplica la última instantánea sin animar desde cero
  function applySnapshot(s: Snapshot | null, instant = false) {
    if (!s) return;
    s.groups.forEach((sg, g) => {
      if (target.current.acts[g]?.length === sg.acts.length) target.current.acts[g] = sg.acts.map((a) => [...a]);
      if (target.current.weights[g]?.length === sg.weights.length) target.current.weights[g] = sg.weights.map((m) => m.map((r) => [...r]));
    });
    if (instant) current.current = JSON.parse(JSON.stringify(target.current));
    pulse.current = 1;
  }
  useEffect(() => { applySnapshot(snapshot); }, [snapshot]); // eslint-disable-line react-hooks/exhaustive-deps

  // Posiciones de neuronas
  const layout = useMemo(() => {
    const groups = topology.groups;
    const padX = compact ? 64 : 76, padTop = compact ? 34 : 48, padBottom = compact ? 52 : 70;
    const gap = groups.length > 1 ? (compact ? 120 : 150) : 0;
    const totalCols = groups.reduce((s, g) => s + g.layers.length, 0);
    const usable = width - padX * 2 - gap * (groups.length - 1) - (classNames?.length ? 90 : 0);
    const colW = usable / Math.max(1, totalCols - groups.length);
    const nodes: Node[][][] = [];
    let x = padX;
    groups.forEach((grp, g) => {
      const gNodes: Node[][] = [];
      const span = colW * (grp.layers.length - 1);
      const stepX = colW;
      grp.layers.forEach((layer, l) => {
        const n = layer.shown.length;
        const avail = H - padTop - padBottom;
        const sp = Math.min(compact ? 22 : 30, avail / Math.max(1, n));
        const y0 = padTop + (avail - sp * (n - 1)) / 2;
        const r = Math.max(3, Math.min(compact ? 6 : 8, sp * 0.36));
        gNodes.push(layer.shown.map((idx, i) => ({ x: x + stepX * l, y: y0 + sp * i, g, l, n: i, idx, r })));
      });
      nodes.push(gNodes);
      x += span + gap;
    });
    return { nodes, padTop, padBottom };
  }, [topology, width, H, compact, classNames]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = width * dpr;
    cv.height = H * dpr;
    const ctx = cv.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    let raf = 0;
    let last = performance.now();

    const bez = (a: Node, b: Node, t: number) => {
      const cx = (b.x - a.x) * 0.5;
      const mt = 1 - t;
      const x = mt ** 3 * a.x + 3 * mt * mt * t * (a.x + cx) + 3 * mt * t * t * (b.x - cx) + t ** 3 * b.x;
      const y = mt ** 3 * a.y + 3 * mt * mt * t * a.y + 3 * mt * t * t * b.y + t ** 3 * b.y;
      return [x, y];
    };

    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const cur = current.current, tgt = target.current;
      const k = reduced ? 1 : 1 - Math.pow(0.002, dt); // interpolación suave
      cur.acts.forEach((ga, g) => ga.forEach((la, l) => la.forEach((_, i) => {
        const t = tgt.acts[g]?.[l]?.[i] ?? 0;
        la[i] += (t - la[i]) * k;
      })));
      cur.weights.forEach((gw, g) => gw.forEach((m, c) => m.forEach((r, a) => r.forEach((_, b) => {
        const t = tgt.weights[g]?.[c]?.[a]?.[b] ?? 0;
        r[b] += (t - r[b]) * k;
      }))));
      pulse.current = Math.max(0, pulse.current - dt * 1.6);

      ctx.clearRect(0, 0, width, H);
      const { nodes } = layout;

      // Puente generador → discriminador (GAN)
      if (topology.groups.length > 1) {
        const gOut = nodes[0][nodes[0].length - 1];
        const dIn = nodes[1][0];
        const a = gOut[Math.floor(gOut.length / 2)], b = dIn[Math.floor(dIn.length / 2)];
        ctx.setLineDash([4, 6]);
        ctx.strokeStyle = "rgba(223,230,255,.35)";
        ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(a.x + 14, a.y); ctx.lineTo(b.x - 14, b.y); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(223,230,255,.55)";
        ctx.font = "12px 'IBM Plex Sans', sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("muestra generada", (a.x + b.x) / 2, a.y - 14);
      }

      // Conexiones
      nodes.forEach((gn, g) => {
        for (let c = 1; c < gn.length; c++) {
          const W = cur.weights[g]?.[c - 1];
          if (!W) continue;
          for (const a of gn[c - 1]) for (const b of gn[c]) {
            const w = W[a.n]?.[b.n] ?? 0;
            const m = Math.abs(w);
            if (m < 0.04) continue;
            ctx.strokeStyle = rgba(w >= 0 ? POS : NEG, 0.05 + 0.45 * m * m);
            ctx.lineWidth = 0.4 + 1.8 * m;
            const cx = (b.x - a.x) * 0.5;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.bezierCurveTo(a.x + cx, a.y, b.x - cx, b.y, b.x, b.y); ctx.stroke();
            // Generar pulsos donde hay señal
            if (runningRef.current && !reduced) {
              const src = Math.abs(cur.acts[g]?.[c - 1]?.[a.n] ?? 0);
              const strength = m * (0.25 + src);
              if (particles.current.length < 700 && Math.random() < strength * dt * 2.2) {
                particles.current.push({ g, c, a: a.n, b: b.n, t: 0, speed: 0.9 + Math.random() * 0.5, sign: w >= 0 ? 1 : -1, s: strength });
              }
            }
          }
        }
      });

      // Pulsos viajando
      if (!reduced) {
        ctx.globalCompositeOperation = "lighter";
        particles.current = particles.current.filter((p) => {
          p.t += dt * p.speed;
          if (p.t >= 1) return false;
          const a = nodes[p.g]?.[p.c - 1]?.[p.a], b = nodes[p.g]?.[p.c]?.[p.b];
          if (!a || !b) return false;
          const [x, y] = bez(a, b, p.t);
          const alpha = Math.sin(p.t * Math.PI) * Math.min(1, 0.35 + p.s);
          const col = p.sign > 0 ? POS : NEG;
          const r = 2 + 3 * Math.min(1, p.s);
          const grd = ctx.createRadialGradient(x, y, 0, x, y, r * 2.6);
          grd.addColorStop(0, rgba([235, 255, 252], alpha));
          grd.addColorStop(0.35, rgba(col, alpha * 0.8));
          grd.addColorStop(1, rgba(col, 0));
          ctx.fillStyle = grd;
          ctx.beginPath(); ctx.arc(x, y, r * 2.6, 0, Math.PI * 2); ctx.fill();
          return true;
        });
        ctx.globalCompositeOperation = "source-over";
      }

      // Neuronas
      let hovered: { node: Node; layer: VisLayer; act: number } | null = null;
      nodes.forEach((gn, g) => gn.forEach((ln, l) => {
        const layer = topology.groups[g].layers[l];
        ln.forEach((nd) => {
          const act = cur.acts[g]?.[l]?.[nd.n] ?? 0;
          const m = Math.min(1, Math.abs(act));
          const col = act >= 0 ? POS : NEG;
          const r = nd.r;
          const glow = r + 4 + 16 * m + 6 * pulse.current * m;
          const grd = ctx.createRadialGradient(nd.x, nd.y, r * 0.4, nd.x, nd.y, glow);
          grd.addColorStop(0, rgba(col, 0.55 * m + 0.05));
          grd.addColorStop(1, rgba(col, 0));
          ctx.fillStyle = grd;
          ctx.beginPath(); ctx.arc(nd.x, nd.y, glow, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = `rgba(${Math.round(24 + (col[0] - 24) * m)},${Math.round(33 + (col[1] - 33) * m)},${Math.round(63 + (col[2] - 63) * m)},1)`;
          ctx.strokeStyle = rgba([223, 230, 255], 0.35 + 0.5 * m);
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          if (layer.kind === "conv") ctx.roundRect(nd.x - r, nd.y - r, r * 2, r * 2, 3);
          else ctx.arc(nd.x, nd.y, r, 0, Math.PI * 2);
          ctx.fill(); ctx.stroke();
          if (layer.kind === "recurrent") { // lazo de memoria
            ctx.strokeStyle = rgba(POS, 0.25 + 0.5 * m);
            ctx.beginPath(); ctx.arc(nd.x + r + 3, nd.y - 2, 5, Math.PI * 0.9, Math.PI * 2.6); ctx.stroke();
          }
          const h = hover.current;
          if (h && Math.hypot(h.x - nd.x, h.y - nd.y) < r + 5) hovered = { node: nd, layer, act };
        });

        // Etiquetas de capa
        const first = ln[0];
        if (!first) return;
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(223,230,255,.92)";
        ctx.font = `600 ${compact ? 11.5 : 12.5}px 'IBM Plex Sans', sans-serif`;
        const yb = H - layout.padBottom + (compact ? 18 : 24);
        const title = layer.kind === "output" ? "Salida" : layer.kind === "input" ? layer.name : KIND_LABEL[layer.kind];
        ctx.fillText(title, first.x, yb);
        ctx.fillStyle = "rgba(170,181,217,.85)";
        ctx.font = `${compact ? 11 : 12}px 'IBM Plex Sans', sans-serif`;
        const sizeTxt = layer.size > layer.shown.length ? `${layer.shown.length} de ${layer.size}` : `${layer.size}`;
        ctx.fillText(sizeTxt, first.x, yb + 15);
        if (layer.activation && layer.kind !== "input") ctx.fillText(layer.activation, first.x, yb + 29);
        if (layer.ops_before?.length && l > 0) {
          const prev = gn[l - 1][0];
          ctx.fillStyle = "rgba(170,181,217,.7)";
          ctx.font = "11px 'IBM Plex Sans', sans-serif";
          ctx.fillText(layer.ops_before.join(" + "), (prev.x + first.x) / 2, layout.padTop - 18);
        }
        // Nombres de clase junto a la salida
        if (layer.kind === "output" && classNames?.length && g === nodes.length - 1) {
          ctx.textAlign = "left";
          ln.forEach((nd) => {
            const act = cur.acts[g]?.[l]?.[nd.n] ?? 0;
            ctx.fillStyle = rgba([223, 230, 255], 0.55 + 0.45 * Math.min(1, Math.abs(act)));
            ctx.font = "12px 'IBM Plex Sans', sans-serif";
            ctx.fillText(classNames[nd.idx] ?? `clase ${nd.idx}`, nd.x + 16, nd.y + 4);
          });
        }
      }));

      // Grupos (GAN)
      if (topology.groups.length > 1) {
        ctx.textAlign = "left";
        ctx.fillStyle = "rgba(255,255,255,.9)";
        ctx.font = "700 13px 'Bricolage Grotesque', sans-serif";
        nodes.forEach((gn, g) => ctx.fillText(topology.groups[g].name, gn[0][0].x - 10, 18));
      }

      // Tooltip
      const hv = hovered as { node: Node; layer: VisLayer; act: number } | null;
      if (hv) {
        const { node, layer, act } = hv;
        const lines = [`${layer.kind === "input" ? layer.name : layer.name} · neurona ${node.idx + 1}`, `activación ${act >= 0 ? "+" : ""}${act.toFixed(2)} (relativa)`];
        ctx.font = "12px 'IBM Plex Sans', sans-serif";
        const w = Math.max(...lines.map((s) => ctx.measureText(s).width)) + 18;
        let tx = node.x + 14, ty = node.y - 40;
        if (tx + w > width) tx = node.x - w - 14;
        if (ty < 4) ty = node.y + 12;
        ctx.fillStyle = "rgba(10,14,32,.94)";
        ctx.strokeStyle = "rgba(255,255,255,.15)";
        ctx.beginPath(); ctx.roundRect(tx, ty, w, 40, 6); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#fff"; ctx.textAlign = "left";
        lines.forEach((s, i) => ctx.fillText(s, tx + 9, ty + 16 + i * 15));
      }

      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [layout, width, H, topology, reduced, compact, classNames]);

  const describe = topology.groups.map((g) => `${g.name}: ` + g.layers.map((l) => `${KIND_LABEL[l.kind]} ${l.size}`).join(", ")).join(". ");

  return (
    <div ref={wrap} style={{ width: "100%" }}>
      <canvas
        ref={canvas}
        style={{ height: H }}
        role="img"
        aria-label={`Diagrama de la red neuronal${running ? " en entrenamiento" : ""}. ${describe}`}
        onMouseMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); hover.current = { x: e.clientX - r.left, y: e.clientY - r.top }; }}
        onMouseLeave={() => { hover.current = null; }}
      />
    </div>
  );
}

/** Topología de vista previa a partir del resumen validado (para el diseñador). */
export function topologyFromSummary(family: string, summary: { input_shape: number[]; layers: { type: string; units?: number; filters?: number; activation?: string; output_shape: number[] }[]; generator?: never[]; discriminator?: never[] }): Topology {
  const shown = (n: number) => (n <= 14 ? [...Array(n).keys()] : [...new Set(Array.from({ length: 14 }, (_, i) => Math.round((i * (n - 1)) / 13)))]);
  const toLayers = (inSize: number, inLabel: string, layers: { type: string; units?: number; filters?: number; activation?: string }[]) => {
    const out: VisLayer[] = [{ name: inLabel, kind: "input", size: inSize, shown: shown(inSize) }];
    let ops: string[] = [];
    layers.forEach((l, i) => {
      const kind: VisLayer["kind"] | null = l.type === "dense" ? (i === layers.length - 1 ? "output" : "dense") : l.type === "conv2d" ? "conv" : ["lstm", "gru", "simplernn"].includes(l.type) ? "recurrent" : null;
      if (!kind) { ops.push(OP_LABEL[l.type] ?? l.type); return; }
      const size = (l.units ?? l.filters ?? 1);
      out.push({ name: l.type, kind, size, shown: shown(size), activation: l.activation ?? (kind === "recurrent" ? "tanh" : null), ops_before: ops });
      ops = [];
    });
    return out;
  };
  if (family === "gan") {
    const s = summary as unknown as { input_shape: number[]; generator: { type: string }[]; discriminator: { type: string; output_shape: number[] }[] };
    const dataDim = (s.generator[s.generator.length - 1] as unknown as { units: number }).units;
    return { family: "gan", has_boundary: false, total_params: 0,
      groups: [{ name: "Generador", layers: toLayers(s.input_shape[0], "Ruido z", s.generator) },
               { name: "Discriminador", layers: toLayers(dataDim, "Muestra", s.discriminator) }] };
  }
  const inSize = summary.input_shape[summary.input_shape.length - 1];
  const label = family === "cnn" ? "Imagen (canales)" : family === "rnn" ? "Secuencia (rasgos)" : "Entrada";
  return { family: family as Topology["family"], has_boundary: false, total_params: 0, groups: [{ name: "Red neuronal", layers: toLayers(inSize, label, summary.layers) }] };
}
