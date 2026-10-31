"""Construye modelos Keras a partir de configuraciones YA validadas por la API (nunca ejecuta código del usuario)."""
import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import keras  # noqa: E402
from keras import layers  # noqa: E402


def _act(name: str):
    return keras.activations.leaky_relu if name == "leaky_relu" else name


def _layer(spec: dict, name: str):
    t = spec["type"]
    if t == "dense":
        return layers.Dense(spec["units"], activation=_act(spec["activation"]), name=name)
    if t == "dropout":
        return layers.Dropout(spec["rate"], name=name)
    if t == "batchnorm":
        return layers.BatchNormalization(name=name)
    if t == "conv2d":
        return layers.Conv2D(spec["filters"], spec["kernel"], padding=spec["padding"], activation=_act(spec["activation"]), name=name)
    if t == "maxpool2d":
        return layers.MaxPooling2D(spec["pool"], name=name)
    if t == "flatten":
        return layers.Flatten(name=name)
    if t == "globalavgpool":
        return layers.GlobalAveragePooling2D(name=name)
    if t == "simplernn":
        return layers.SimpleRNN(spec["units"], return_sequences=spec["return_sequences"], activation=_act(spec["activation"]), name=name)
    if t == "lstm":
        return layers.LSTM(spec["units"], return_sequences=spec["return_sequences"], activation=_act(spec["activation"]), name=name)
    if t == "gru":
        return layers.GRU(spec["units"], return_sequences=spec["return_sequences"], activation=_act(spec["activation"]), name=name)
    raise ValueError(f"Capa no soportada: {t}")


def _stack(x, specs: list[dict], prefix: str):
    for i, s in enumerate(specs):
        x = _layer(s, f"{prefix}{i + 1}_{s['type']}")(x)
    return x


def build_classifier(cfg: dict) -> keras.Model:
    inp = keras.Input(shape=tuple(cfg["input_shape"]), name="entrada")
    x = _stack(inp, cfg["layers"], "oculta")
    out = layers.Dense(cfg["output"]["units"], activation=cfg["output"]["activation"], name="salida")(x)
    return keras.Model(inp, out, name="aurora_viii")


def build_gan(cfg: dict) -> tuple[keras.Model, keras.Model]:
    z = keras.Input(shape=(cfg["latent_dim"],), name="ruido")
    g = layers.Dense(cfg["data_dim"], activation="linear", name="gen_salida")(_stack(z, cfg["generator"], "gen"))
    generator = keras.Model(z, g, name="generador")
    xin = keras.Input(shape=(cfg["data_dim"],), name="muestra")
    d = layers.Dense(1, activation="sigmoid", name="disc_salida")(_stack(xin, cfg["discriminator"], "disc"))
    discriminator = keras.Model(xin, d, name="discriminador")
    return generator, discriminator


def optimizer(name: str, lr: float, gan: bool = False):
    if name == "adam" and gan:  # configuración estándar para GAN (Radford et al., DCGAN)
        return keras.optimizers.Adam(learning_rate=lr, beta_1=0.5)
    return {"adam": keras.optimizers.Adam, "sgd": keras.optimizers.SGD, "rmsprop": keras.optimizers.RMSprop}[name](learning_rate=lr)
