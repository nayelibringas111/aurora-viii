"""Datasets: demos integrados (generados de forma determinista, sin datos sensibles) y CSV subidos.

Cada dataset se describe con metadatos: tarea, forma de entrada, número de clases y separación
entrenamiento/validación/prueba. El worker usa load_arrays() para materializarlo.
"""
import csv
import io
import math

import numpy as np

SPLIT = {"train": 0.7, "validation": 0.15, "test": 0.15}

BUILTINS: dict[str, dict] = {
    "espirales": {
        "name": "Espirales entrelazadas", "family_hint": "feedforward", "task": "classification",
        "input_shape": [2], "num_classes": 2, "samples": 800,
        "description": "Dos espirales en el plano. No son separables linealmente: requieren capas ocultas.",
        "feature_names": ["x", "y"], "class_names": ["Espiral A", "Espiral B"],
    },
    "circulos": {
        "name": "Anillos concéntricos (3 clases)", "family_hint": "feedforward", "task": "classification",
        "input_shape": [2], "num_classes": 3, "samples": 900,
        "description": "Tres anillos con ruido. Ideal para ver cómo la red curva la frontera de decisión.",
        "feature_names": ["x", "y"], "class_names": ["Interior", "Medio", "Exterior"],
    },
    "xor": {
        "name": "XOR ruidoso", "family_hint": "feedforward", "task": "classification",
        "input_shape": [2], "num_classes": 2, "samples": 600,
        "description": "El clásico problema que un perceptrón simple no resuelve.",
        "feature_names": ["a", "b"], "class_names": ["0", "1"],
    },
    "patrones8x8": {
        "name": "Patrones 8×8 (líneas, cruces, marcos)", "family_hint": "cnn", "task": "classification",
        "input_shape": [8, 8, 1], "num_classes": 4, "samples": 1200,
        "description": "Imágenes pequeñas con ruido: línea horizontal, vertical, cruz o marco.",
        "class_names": ["Horizontal", "Vertical", "Cruz", "Marco"],
    },
    "ondas": {
        "name": "Ondas temporales", "family_hint": "rnn", "task": "classification",
        "input_shape": [24, 1], "num_classes": 3, "samples": 1200,
        "description": "Secuencias de 24 pasos: senoidal, cuadrada o diente de sierra, con fase y ruido aleatorios.",
        "class_names": ["Senoidal", "Cuadrada", "Sierra"],
    },
    "anillo2d": {
        "name": "Anillo 2D (para GAN)", "family_hint": "gan", "task": "generation",
        "input_shape": [2], "num_classes": 0, "samples": 2000,
        "description": "Puntos sobre un anillo. El generador debe aprender a producir puntos con esa forma.",
        "feature_names": ["x", "y"],
    },
}


def builtin_metadata(key: str) -> dict:
    b = BUILTINS[key]
    return {**{k: v for k, v in b.items() if k not in ("name", "family_hint")}, "builtin_key": key, "split": SPLIT}


def _generate(key: str, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = BUILTINS[key]["samples"]
    if key == "espirales":
        m = n // 2
        t = np.sqrt(rng.uniform(0, 1, m)) * 3 * math.pi
        a = np.stack([t * np.cos(t), t * np.sin(t)], 1) / (3 * math.pi)
        b = -a
        X = np.concatenate([a, b]) + rng.normal(0, 0.03, (2 * m, 2))
        y = np.concatenate([np.zeros(m), np.ones(m)])
    elif key == "circulos":
        m = n // 3
        X, y = [], []
        for c, r in enumerate([0.25, 0.6, 0.95]):
            ang = rng.uniform(0, 2 * math.pi, m)
            rad = r + rng.normal(0, 0.06, m)
            X.append(np.stack([rad * np.cos(ang), rad * np.sin(ang)], 1))
            y.append(np.full(m, c))
        X, y = np.concatenate(X), np.concatenate(y)
    elif key == "xor":
        X = rng.uniform(-1, 1, (n, 2))
        y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(float)
        X = X + rng.normal(0, 0.08, X.shape)
    elif key == "patrones8x8":
        X = np.zeros((n, 8, 8, 1))
        y = rng.integers(0, 4, n)
        for i, c in enumerate(y):
            r, col = rng.integers(1, 7), rng.integers(1, 7)
            if c == 0:
                X[i, r, 1:7, 0] = 1
            elif c == 1:
                X[i, 1:7, col, 0] = 1
            elif c == 2:
                X[i, r, 1:7, 0] = 1
                X[i, 1:7, col, 0] = 1
            else:
                s, e = rng.integers(0, 2), rng.integers(6, 8)
                X[i, s, s:e, 0] = X[i, e - 1, s:e, 0] = 1
                X[i, s:e, s, 0] = X[i, s:e, e - 1, 0] = 1
        X = np.clip(X + rng.normal(0, 0.18, X.shape), 0, 1)
    elif key == "ondas":
        T = 24
        y = rng.integers(0, 3, n)
        t = np.arange(T)[None, :]
        freq = rng.uniform(0.18, 0.35, (n, 1))
        phase = rng.uniform(0, 2 * math.pi, (n, 1))
        base = freq * t + phase
        sine = np.sin(base)
        square = np.sign(np.sin(base))
        saw = 2 * ((base / (2 * math.pi)) % 1) - 1
        X = np.where(y[:, None] == 0, sine, np.where(y[:, None] == 1, square, saw))
        X = (X + rng.normal(0, 0.15, X.shape))[..., None]
    elif key == "anillo2d":
        ang = rng.uniform(0, 2 * math.pi, n)
        rad = 0.8 + rng.normal(0, 0.05, n)
        X = np.stack([rad * np.cos(ang), rad * np.sin(ang)], 1)
        y = np.zeros(n)
    else:
        raise KeyError(key)
    perm = rng.permutation(len(X))
    return X[perm].astype("float32"), y[perm].astype("int32")


class DatasetError(ValueError):
    pass


def parse_csv(raw: bytes, target_column: str | None, max_rows: int = 50_000, max_features: int = 64) -> dict:
    """Valida un CSV numérico (no se ejecuta nada del archivo). Devuelve metadatos o lanza DatasetError."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DatasetError("El archivo debe estar codificado en UTF-8")
    if "\x00" in text:
        raise DatasetError("El archivo contiene bytes binarios: solo se aceptan CSV de texto")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 21:
        raise DatasetError("Se necesitan al menos 20 filas de datos más la cabecera")
    header = [h.strip() for h in rows[0]]
    if len(set(header)) != len(header) or any(not h for h in header):
        raise DatasetError("La cabecera debe tener nombres de columna únicos y no vacíos")
    target = target_column or header[-1]
    if target not in header:
        raise DatasetError(f"La columna objetivo «{target}» no existe")
    ti = header.index(target)
    feats = [h for i, h in enumerate(header) if i != ti]
    if not 1 <= len(feats) <= max_features:
        raise DatasetError(f"Se admiten entre 1 y {max_features} columnas de entrada")
    data = rows[1:]
    if len(data) > max_rows:
        raise DatasetError(f"Máximo {max_rows} filas")
    labels: list[str] = []
    for n, r in enumerate(data, start=2):
        if len(r) != len(header):
            raise DatasetError(f"La fila {n} tiene {len(r)} columnas; se esperaban {len(header)}")
        for i, v in enumerate(r):
            if i == ti:
                continue
            try:
                f = float(v)
            except ValueError:
                raise DatasetError(f"Valor no numérico en fila {n}, columna «{header[i]}»")
            if math.isnan(f) or math.isinf(f):
                raise DatasetError(f"Valor vacío o infinito en fila {n}, columna «{header[i]}»")
        labels.append(r[ti].strip())
    classes = sorted(set(labels), key=lambda s: (len(s), s))
    if not 2 <= len(classes) <= 50:
        raise DatasetError("La columna objetivo debe tener entre 2 y 50 clases")
    return {"task": "classification", "input_shape": [len(feats)], "num_classes": len(classes),
            "samples": len(data), "feature_names": feats, "class_names": classes, "target_column": target,
            "split": SPLIT, "description": "Dataset CSV subido por el usuario"}


def load_arrays(meta: dict, raw: bytes | None = None, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    if "builtin_key" in meta:
        return _generate(meta["builtin_key"], seed=7)  # el dataset demo es fijo; la semilla afecta al modelo
    if raw is None:
        raise DatasetError("Falta el contenido del dataset")
    text = raw.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    header = [h.strip() for h in rows[0]]
    ti = header.index(meta["target_column"])
    cls = {c: i for i, c in enumerate(meta["class_names"])}
    X = np.array([[float(v) for i, v in enumerate(r) if i != ti] for r in rows[1:]], dtype="float32")
    y = np.array([cls[r[ti].strip()] for r in rows[1:]], dtype="int32")
    # Estandarización por columna (los parámetros quedan implícitos en el modelo exportado como metadato)
    mu, sd = X.mean(0), X.std(0) + 1e-8
    X = (X - mu) / sd
    perm = np.random.default_rng(seed).permutation(len(X))
    return X[perm], y[perm]


def split_arrays(X: np.ndarray, y: np.ndarray):
    n = len(X)
    a = int(n * SPLIT["train"])
    b = a + int(n * SPLIT["validation"])
    return (X[:a], y[:a]), (X[a:b], y[a:b]), (X[b:], y[b:])


def preview(meta: dict, raw: bytes | None = None, limit: int = 300) -> dict:
    """Muestra pequeña para dibujar el dataset en la interfaz."""
    X, y = load_arrays(meta, raw)
    X, y = X[:limit], y[:limit]
    shape = meta["input_shape"]
    if len(shape) == 1 and shape[0] == 2:
        return {"kind": "scatter", "points": [[round(float(a), 3), round(float(b), 3), int(c)] for (a, b), c in zip(X, y)]}
    if len(shape) == 3:
        return {"kind": "images", "items": [{"pixels": np.round(X[i, :, :, 0], 2).tolist(), "label": int(y[i])} for i in range(12)]}
    if len(shape) == 2:
        return {"kind": "series", "items": [{"values": np.round(X[i, :, 0], 3).tolist(), "label": int(y[i])} for i in range(9)]}
    return {"kind": "table", "rows": [[round(float(v), 3) for v in X[i][:8]] + [int(y[i])] for i in range(15)]}
