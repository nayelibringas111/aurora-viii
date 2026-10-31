"""Validación de arquitecturas por familia (en backend: el frontend NO es frontera de seguridad).

Propaga formas capa por capa, cuenta parámetros sin cargar TensorFlow y produce un resumen
que la interfaz usa para dibujar el grafo antes de entrenar.
"""
from dataclasses import dataclass, field
from math import prod

ACTIVATIONS = {"relu", "tanh", "sigmoid", "elu", "selu", "gelu", "leaky_relu", "swish", "linear"}
OUTPUT_ACTIVATIONS = {"softmax", "sigmoid", "linear", "tanh"}

FAMILY_LAYERS = {
    "feedforward": {"dense", "dropout", "batchnorm"},
    "cnn": {"conv2d", "maxpool2d", "flatten", "globalavgpool", "dense", "dropout", "batchnorm"},
    "rnn": {"simplernn", "lstm", "gru", "dense", "dropout"},
    "gan": {"dense", "dropout", "batchnorm"},
}
RECURRENT = {"simplernn", "lstm", "gru"}


class ArchitectureError(ValueError):
    def __init__(self, issues: list[dict]):
        super().__init__("; ".join(i["message"] for i in issues))
        self.issues = issues


@dataclass
class Limits:
    max_layers: int = 12
    max_units: int = 512
    max_params: int = 2_000_000


@dataclass
class _Ctx:
    issues: list[dict] = field(default_factory=list)

    def err(self, path: str, msg: str):
        self.issues.append({"path": path, "message": msg})


def _int(ctx: _Ctx, layer: dict, key: str, path: str, lo: int, hi: int, default=None) -> int:
    v = layer.get(key, default)
    if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
        ctx.err(f"{path}.{key}", f"«{key}» debe ser un entero entre {lo} y {hi}")
        return lo
    return v


def _act(ctx: _Ctx, layer: dict, path: str, default="relu") -> str:
    a = layer.get("activation", default)
    if a not in ACTIVATIONS:
        ctx.err(f"{path}.activation", f"Activación «{a}» no admitida en capas ocultas")
        return "relu"
    return a


def _stack(ctx: _Ctx, family: str, layers: list, in_shape: tuple, prefix: str, lim: Limits,
           allowed: set[str]) -> tuple[list[dict], list[dict], tuple]:
    """Devuelve (capas normalizadas, resumen por capa, forma final)."""
    norm, summary = [], []
    shape = tuple(in_shape)
    if not isinstance(layers, list):
        ctx.err(prefix, "Las capas deben ser una lista")
        return [], [], shape
    if len(layers) > lim.max_layers:
        ctx.err(prefix, f"Máximo {lim.max_layers} capas ocultas")
    for i, raw in enumerate(layers):
        path = f"{prefix}[{i}]"
        if not isinstance(raw, dict):
            ctx.err(path, "Cada capa debe ser un objeto")
            continue
        t = raw.get("type")
        if t not in allowed:
            ctx.err(f"{path}.type", f"La capa «{t}» no está permitida en la familia {family}")
            continue
        L: dict = {"type": t}
        params = 0
        if t == "dense":
            if len(shape) != 1:
                ctx.err(path, f"Dense necesita entrada 1D; recibe {list(shape)}. Añade Flatten/GlobalAvgPool o termina las capas recurrentes sin return_sequences")
                continue
            L["units"] = _int(ctx, raw, "units", path, 1, lim.max_units)
            L["activation"] = _act(ctx, raw, path)
            params = shape[0] * L["units"] + L["units"]
            shape = (L["units"],)
        elif t == "dropout":
            r = raw.get("rate", 0.2)
            if not isinstance(r, (int, float)) or not 0 <= r < 0.9:
                ctx.err(f"{path}.rate", "«rate» debe estar entre 0 y 0.9")
                r = 0.2
            L["rate"] = float(r)
        elif t == "batchnorm":
            params = 4 * shape[-1]
        elif t == "conv2d":
            if len(shape) != 3:
                ctx.err(path, "Conv2D necesita entrada (alto, ancho, canales)")
                continue
            L["filters"] = _int(ctx, raw, "filters", path, 1, min(lim.max_units, 256))
            L["kernel"] = _int(ctx, raw, "kernel", path, 1, 7, 3)
            L["padding"] = raw.get("padding", "same") if raw.get("padding", "same") in ("same", "valid") else "same"
            L["activation"] = _act(ctx, raw, path)
            h, w, c = shape
            if L["padding"] == "valid":
                h, w = h - L["kernel"] + 1, w - L["kernel"] + 1
            if h < 1 or w < 1:
                ctx.err(path, "El kernel es mayor que la imagen en este punto")
                continue
            params = L["kernel"] ** 2 * c * L["filters"] + L["filters"]
            shape = (h, w, L["filters"])
        elif t == "maxpool2d":
            if len(shape) != 3:
                ctx.err(path, "MaxPool2D necesita entrada 3D")
                continue
            L["pool"] = _int(ctx, raw, "pool", path, 2, 4, 2)
            h, w, c = shape
            if h // L["pool"] < 1 or w // L["pool"] < 1:
                ctx.err(path, "El pooling reduce la imagen a cero")
                continue
            shape = (h // L["pool"], w // L["pool"], c)
        elif t == "flatten":
            if len(shape) == 1:
                ctx.err(path, "Flatten innecesario: la entrada ya es 1D")
            shape = (prod(shape),)
        elif t == "globalavgpool":
            if len(shape) != 3:
                ctx.err(path, "GlobalAvgPool necesita entrada 3D")
                continue
            shape = (shape[2],)
        elif t in RECURRENT:
            if len(shape) != 2:
                ctx.err(path, f"{t.upper()} necesita una secuencia (pasos, rasgos); recibe {list(shape)}. Usa return_sequences=true en la capa recurrente anterior")
                continue
            L["units"] = _int(ctx, raw, "units", path, 1, lim.max_units)
            L["return_sequences"] = bool(raw.get("return_sequences", False))
            L["activation"] = raw.get("activation", "tanh") if raw.get("activation", "tanh") in ACTIVATIONS else "tanh"
            u, f = L["units"], shape[1]
            params = {"simplernn": u * (u + f + 1), "lstm": 4 * u * (u + f + 1), "gru": 3 * u * (u + f + 2)}[t]
            shape = (shape[0], u) if L["return_sequences"] else (u,)
        norm.append(L)
        summary.append({"name": f"{prefix.split('.')[-1]}_{i + 1}_{t}", "type": t, "output_shape": list(shape),
                        "params": params, **{k: v for k, v in L.items() if k != "type"}})
    return norm, summary, shape


def validate(family: str, cfg: dict, lim: Limits | None = None) -> tuple[dict, dict]:
    lim = lim or Limits()
    ctx = _Ctx()
    if family not in FAMILY_LAYERS:
        raise ArchitectureError([{"path": "family", "message": "Familia no válida"}])
    if not isinstance(cfg, dict):
        raise ArchitectureError([{"path": "config", "message": "La configuración debe ser un objeto"}])

    if family == "gan":
        data_dim = cfg.get("data_dim", 2)
        latent = cfg.get("latent_dim", 8)
        if not isinstance(data_dim, int) or not 1 <= data_dim <= 64:
            ctx.err("data_dim", "data_dim debe estar entre 1 y 64")
            data_dim = 2
        if not isinstance(latent, int) or not 1 <= latent <= 128:
            ctx.err("latent_dim", "latent_dim debe estar entre 1 y 128")
            latent = 8
        g, gs, gshape = _stack(ctx, family, cfg.get("generator", []), (latent,), "generator", lim, FAMILY_LAYERS["gan"])
        d, ds, dshape = _stack(ctx, family, cfg.get("discriminator", []), (data_dim,), "discriminator", lim, FAMILY_LAYERS["gan"])
        if not any(l["type"] == "dense" for l in g):
            ctx.err("generator", "El generador necesita al menos una capa Dense")
        if not any(l["type"] == "dense" for l in d):
            ctx.err("discriminator", "El discriminador necesita al menos una capa Dense")
        g_out = gshape[0] * data_dim + data_dim
        d_out = dshape[0] + 1
        gs.append({"name": "generator_out", "type": "dense", "units": data_dim, "activation": "linear",
                   "output_shape": [data_dim], "params": g_out})
        ds.append({"name": "discriminator_out", "type": "dense", "units": 1, "activation": "sigmoid",
                   "output_shape": [1], "params": d_out})
        total = sum(x["params"] for x in gs + ds)
        if total > lim.max_params:
            ctx.err("config", f"La red tiene {total:,} parámetros; el límite es {lim.max_params:,}")
        if ctx.issues:
            raise ArchitectureError(ctx.issues)
        normalized = {"data_dim": data_dim, "latent_dim": latent, "generator": g, "discriminator": d}
        return normalized, {"total_params": total, "input_shape": [latent], "generator": gs, "discriminator": ds,
                            "layers": gs + ds, "loss": "binary_crossentropy"}

    in_shape = cfg.get("input_shape")
    expected_rank = {"feedforward": 1, "cnn": 3, "rnn": 2}[family]
    if (not isinstance(in_shape, list) or len(in_shape) != expected_rank
            or not all(isinstance(v, int) and 1 <= v <= 512 for v in in_shape)):
        ctx.err("input_shape", f"La familia {family} requiere una entrada de {expected_rank} dimensión(es) con enteros 1–512")
        raise ArchitectureError(ctx.issues)
    layers, summary, shape = _stack(ctx, family, cfg.get("layers", []), tuple(in_shape), "layers", lim, FAMILY_LAYERS[family])

    if family == "cnn" and not any(l["type"] == "conv2d" for l in layers):
        ctx.err("layers", "Una CNN necesita al menos una capa Conv2D")
    if family == "rnn" and not any(l["type"] in RECURRENT for l in layers):
        ctx.err("layers", "Una RNN necesita al menos una capa recurrente (SimpleRNN, LSTM o GRU)")
    if family == "feedforward" and not any(l["type"] == "dense" for l in layers):
        ctx.err("layers", "Una red Feedforward necesita al menos una capa oculta Dense")

    out = cfg.get("output") or {}
    units = out.get("units")
    act = out.get("activation", "softmax")
    if not isinstance(units, int) or not 1 <= units <= 100:
        ctx.err("output.units", "La salida necesita entre 1 y 100 neuronas")
        units = 1
    if act not in OUTPUT_ACTIVATIONS:
        ctx.err("output.activation", "Activación de salida no válida")
    if act == "softmax" and units < 2:
        ctx.err("output", "Softmax necesita al menos 2 neuronas de salida")
    if act == "sigmoid" and units != 1:
        ctx.err("output", "Para clasificación binaria con sigmoide usa 1 neurona de salida")
    if len(shape) != 1:
        ctx.err("output", f"Antes de la salida la forma debe ser 1D; es {list(shape)}")
        shape = (1,)
    out_params = shape[0] * units + units
    summary.append({"name": "output", "type": "dense", "units": units, "activation": act,
                    "output_shape": [units], "params": out_params})
    total = sum(s["params"] for s in summary)
    if total > lim.max_params:
        ctx.err("config", f"La red tiene {total:,} parámetros; el límite es {lim.max_params:,}")
    if ctx.issues:
        raise ArchitectureError(ctx.issues)
    loss = {"softmax": "sparse_categorical_crossentropy", "sigmoid": "binary_crossentropy"}.get(act, "mse")
    normalized = {"input_shape": in_shape, "layers": layers, "output": {"units": units, "activation": act}}
    return normalized, {"total_params": total, "input_shape": in_shape, "layers": summary, "loss": loss}


def compatibility(family: str, cfg: dict, dataset_meta: dict) -> list[str]:
    """Errores de compatibilidad arquitectura ↔ dataset (se comprueba al enviar el entrenamiento)."""
    issues = []
    task = dataset_meta.get("task")
    if family == "gan":
        if task != "generation":
            issues.append("Una GAN necesita un dataset de generación (p. ej. «Anillo 2D»)")
        elif dataset_meta["input_shape"] != [cfg["data_dim"]]:
            issues.append(f"data_dim={cfg['data_dim']} no coincide con el dataset {dataset_meta['input_shape']}")
        return issues
    if task != "classification":
        issues.append("Esta familia se entrena con datasets de clasificación")
        return issues
    if list(cfg["input_shape"]) != list(dataset_meta["input_shape"]):
        issues.append(f"La entrada de la red {cfg['input_shape']} no coincide con el dataset {dataset_meta['input_shape']}")
    k = dataset_meta["num_classes"]
    u, a = cfg["output"]["units"], cfg["output"]["activation"]
    if a == "softmax" and u != k:
        issues.append(f"La salida softmax tiene {u} neuronas pero el dataset tiene {k} clases")
    if a == "sigmoid" and k != 2:
        issues.append("La salida sigmoide solo sirve para 2 clases")
    if a in ("linear", "tanh"):
        issues.append("Para clasificación usa salida softmax (o sigmoide si son 2 clases)")
    return issues
