"""Instantáneas de la red para la visualización en vivo.

Por cada capa «visible» (entrada, Dense, Conv2D, recurrentes, salida) se elige un subconjunto de neuronas
(máx. MAX_SHOWN) y se envían:
  · la activación de cada neurona para una muestra concreta que «atraviesa» la red,
  · los pesos entre neuronas visibles de capas consecutivas (agregados para convoluciones y celdas),
  · la predicción de esa muestra y, para datos 2D, la frontera de decisión.
Los valores van normalizados a [-1, 1] para que la interfaz los dibuje sin conocer escalas.
"""
import numpy as np
import keras

MAX_SHOWN = 14
RECURRENT = ("SimpleRNN", "LSTM", "GRU")


def _shown(n: int) -> list[int]:
    if n <= MAX_SHOWN:
        return list(range(n))
    return sorted({int(round(i)) for i in np.linspace(0, n - 1, MAX_SHOWN)})


def _kind(layer) -> str | None:
    cls = layer.__class__.__name__
    if cls == "Dense":
        return "output" if layer.name.endswith("salida") else "dense"
    if cls == "Conv2D":
        return "conv"
    if cls in RECURRENT:
        return "recurrent"
    return None


def _size(layer) -> int:
    cls = layer.__class__.__name__
    if cls == "Conv2D":
        return layer.filters
    return layer.units


def _ops_between(model, a, b) -> list[str]:
    names, on = [], False
    for l in model.layers:
        if l is a:
            on = True
            continue
        if l is b:
            break
        if on and l.__class__.__name__ not in ("InputLayer",):
            names.append({"Dropout": "Dropout", "BatchNormalization": "BatchNorm", "MaxPooling2D": "MaxPool",
                          "Flatten": "Flatten", "GlobalAveragePooling2D": "GlobalAvgPool"}.get(l.__class__.__name__, l.__class__.__name__))
    return names


class NetworkProbe:
    """Envuelve un modelo Keras para extraer topología y activaciones por capa visible."""

    def __init__(self, model: keras.Model, group: str, input_label: str):
        self.model = model
        self.group = group
        self.visible = [l for l in model.layers if _kind(l)]
        self.extractor = keras.Model(model.inputs, [l.output for l in self.visible])
        in_shape = model.inputs[0].shape[1:]
        self.in_size = int(in_shape[-1])
        self.input_label = input_label
        self.sizes = [self.in_size] + [_size(l) for l in self.visible]
        self.shown = [_shown(n) for n in self.sizes]

    def topology(self) -> dict:
        layers = [{"name": self.input_label, "kind": "input", "size": self.in_size, "shown": self.shown[0]}]
        prev = None
        for l, sh in zip(self.visible, self.shown[1:]):
            layers.append({"name": l.name, "kind": _kind(l), "size": _size(l), "shown": sh,
                           "activation": getattr(l, "activation", None).__name__ if getattr(l, "activation", None) else None,
                           "ops_before": _ops_between(self.model, prev, l) if prev is not None else
                           [o for o in _ops_between(self.model, self.model.layers[0], l)],
                           "params": int(l.count_params())})
            prev = l
        return {"name": self.group, "layers": layers}

    def _kernel_matrix(self, idx: int) -> np.ndarray:
        """Matriz (n_prev, n_this) de pesos efectivos entre la capa visible idx-1 y la idx."""
        l = self.visible[idx - 1]
        cls = l.__class__.__name__
        prev_n = self.sizes[idx - 1]
        if cls in RECURRENT:
            k = np.asarray(l.cell.kernel)
            gates = k.shape[1] // l.units
            k = k.reshape(k.shape[0], gates, l.units).mean(1)
        elif cls == "Conv2D":
            k = np.asarray(l.kernel).mean((0, 1))
        else:
            k = np.asarray(l.kernel)
        if k.shape[0] != prev_n and k.shape[0] % prev_n == 0:  # Flatten: (H·W·C) → agrupar por canal
            k = k.reshape(-1, prev_n, k.shape[1]).mean(0)
        return k

    def weights(self) -> list[list[list[float]]]:
        out = []
        for i in range(1, len(self.sizes)):
            k = self._kernel_matrix(i)
            sub = k[np.ix_(self.shown[i - 1], self.shown[i])] if k.shape[0] == self.sizes[i - 1] else np.zeros((len(self.shown[i - 1]), len(self.shown[i])))
            m = np.abs(sub).max() or 1.0
            out.append(np.round(sub / m, 2).tolist())
        return out

    def activations(self, x_batch: np.ndarray, sample: int) -> tuple[list[list[float]], np.ndarray]:
        outs = self.extractor([x_batch], training=False)
        outs = outs if isinstance(outs, (list, tuple)) else [outs]
        acts = []
        xin = np.asarray(x_batch)
        xin_r = xin.reshape(xin.shape[0], -1, xin.shape[-1])
        layer_vals = [xin_r] + [np.asarray(o).reshape(o.shape[0], -1, o.shape[-1]) for o in outs]
        for vals, sh in zip(layer_vals, self.shown):
            per = vals.mean(1)                     # promedio espacial / temporal → (B, neuronas)
            scale = np.abs(per).max(0)
            scale[scale == 0] = 1
            a = per[sample][sh] / scale[sh]
            acts.append(np.round(a, 3).tolist())
        return acts, np.asarray(outs[-1])


def describe_sample(x: np.ndarray) -> dict:
    """Representación ligera de la muestra que atraviesa la red."""
    if x.ndim == 3:
        return {"kind": "image", "pixels": np.round(x[:, :, 0], 2).tolist()}
    if x.ndim == 2:
        return {"kind": "series", "values": np.round(x[:, 0], 3).tolist()}
    return {"kind": "vector", "values": np.round(x[:16], 3).tolist()}


def decision_boundary(model: keras.Model, X: np.ndarray, n: int = 28) -> dict:
    lo = (X.min(0) - 0.15).tolist()
    hi = (X.max(0) + 0.15).tolist()
    xs = np.linspace(lo[0], hi[0], n)
    ys = np.linspace(lo[1], hi[1], n)
    gx, gy = np.meshgrid(xs, ys)
    grid = np.stack([gx.ravel(), gy.ravel()], 1).astype("float32")
    p = np.asarray(model(grid, training=False))
    if p.shape[1] == 1:
        p = np.concatenate([1 - p, p], 1)
    return {"n": n, "x": [round(lo[0], 3), round(hi[0], 3)], "y": [round(lo[1], 3), round(hi[1], 3)],
            "cls": p.argmax(1).astype(int).tolist(), "conf": np.round(p.max(1), 2).tolist()}
