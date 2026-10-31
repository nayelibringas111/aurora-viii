"""Entrenamiento con TensorFlow/Keras: clasificadores (Feedforward, CNN, RNN) y GAN (bucle propio)."""
import numpy as np
import keras
import tensorflow as tf

from aurora_worker.builder import build_classifier, build_gan, optimizer
from aurora_worker.visual import NetworkProbe, decision_boundary, describe_sample

INPUT_LABELS = {"feedforward": "Entrada", "cnn": "Imagen (canales)", "rnn": "Secuencia (rasgos)"}


class _Bridge(keras.callbacks.Callback):
    def __init__(self, rep, snapshot_fn):
        super().__init__()
        self.rep, self.snapshot_fn = rep, snapshot_fn

    def on_train_batch_end(self, batch, logs=None):
        self.rep.batch(batch, logs or {}, self.snapshot_fn)

    def on_epoch_end(self, epoch, logs=None):
        self.rep.epoch_end(logs or {}, self.snapshot_fn)


def _family(cfg: dict) -> str:
    rank = len(cfg["input_shape"])
    return {1: "feedforward", 3: "cnn", 2: "rnn"}[rank]


def train_classifier(cfg, params, meta, train, val, test, rep):
    (Xtr, ytr), (Xva, yva), (Xte, yte) = train, val, test
    model = build_classifier(cfg)
    act = cfg["output"]["activation"]
    loss = "binary_crossentropy" if act == "sigmoid" else "sparse_categorical_crossentropy"
    model.compile(optimizer=optimizer(params["optimizer"], params["learning_rate"]), loss=loss, metrics=["accuracy"])

    family = _family(cfg)
    probe = NetworkProbe(model, "Red neuronal", INPUT_LABELS[family])
    class_names = meta.get("class_names") or [str(i) for i in range(meta.get("num_classes", 2))]
    two_d = cfg["input_shape"] == [2]
    rep.event("topology", {"family": family, "groups": [probe.topology()], "class_names": class_names,
                           "input_shape": cfg["input_shape"], "total_params": int(model.count_params()),
                           "has_boundary": two_d,
                           "points": np.round(np.c_[Xtr[:300], ytr[:300]], 3).tolist() if two_d else None})

    Xp, yp = Xva[:48], yva[:48]
    state = {"i": 0}

    def snapshot(phase: str) -> dict:
        idx = state["i"] % len(Xp)
        state["i"] += 1
        acts, out = probe.activations(Xp, idx)
        probs = out[idx]
        if probs.shape[0] == 1:
            probs = np.array([1 - probs[0], probs[0]])
        payload = {"phase": phase, "epoch": rep.epoch, "groups": [{"acts": acts, "weights": probe.weights()}],
                   "sample": {**describe_sample(Xp[idx]), "true": int(yp[idx]),
                              "probs": np.round(probs, 3).tolist(), "pred": int(np.argmax(probs))}}
        if two_d and phase == "epoch":
            payload["boundary"] = decision_boundary(model, Xtr)
        return payload

    rep.event("snapshot", snapshot("epoch"))
    model.fit(Xtr, ytr, epochs=rep.total, batch_size=params["batch_size"], validation_data=(Xva, yva),
              verbose=0, shuffle=True, callbacks=[_Bridge(rep, snapshot)])

    test_loss, test_acc = model.evaluate(Xte, yte, verbose=0)
    p = np.asarray(model.predict(Xte, verbose=0))
    pred = (p[:, 0] > 0.5).astype(int) if p.shape[1] == 1 else p.argmax(1)
    k = len(class_names)
    cm = np.zeros((k, k), dtype=int)
    for t, q in zip(yte, pred):
        cm[int(t), int(q)] += 1
    per_class = [round(float(cm[i, i] / cm[i].sum()), 4) if cm[i].sum() else None for i in range(k)]
    hist = model.history.history if model.history else {}
    evaluation = {"loss": round(float(test_loss), 5), "accuracy": round(float(test_acc), 5),
                  "best_val_accuracy": round(float(max(hist.get("val_accuracy", [0]))), 5),
                  "test_samples": int(len(Xte))}
    observations = []
    if hist.get("accuracy") and hist.get("val_accuracy") and hist["accuracy"][-1] - hist["val_accuracy"][-1] > 0.1:
        observations.append("Posible sobreajuste: la exactitud de entrenamiento supera en más de 10 puntos a la de validación.")
    if test_acc < 1.2 / k:
        observations.append("La exactitud está cerca del azar: prueba más épocas, otra tasa de aprendizaje o más capacidad.")
    return {"evaluation": evaluation, "confusion_matrix": cm.tolist(), "per_class_accuracy": per_class,
            "class_names": class_names, "observations": observations}, model


def train_gan(cfg, params, Xtr, rep):
    generator, discriminator = build_gan(cfg)
    g_opt = optimizer(params["optimizer"], params["learning_rate"], gan=True)
    d_opt = optimizer(params["optimizer"], params["learning_rate"], gan=True)
    bce = keras.losses.BinaryCrossentropy()
    latent, bs = cfg["latent_dim"], params["batch_size"]

    g_probe = NetworkProbe(generator, "Generador", "Ruido z")
    d_probe = NetworkProbe(discriminator, "Discriminador", "Muestra")
    rep.event("topology", {"family": "gan", "groups": [g_probe.topology(), d_probe.topology()],
                           "total_params": int(generator.count_params() + discriminator.count_params()),
                           "has_boundary": False, "real_points": np.round(Xtr[:300], 3).tolist()})

    @tf.function
    def step(real):
        n = tf.shape(real)[0]
        z = tf.random.normal((n, latent))
        with tf.GradientTape() as tape:
            fake = generator(z, training=True)
            d_real = discriminator(real, training=True)
            d_fake = discriminator(fake, training=True)
            d_loss = bce(tf.ones_like(d_real) * 0.9, d_real) + bce(tf.zeros_like(d_fake), d_fake)
        d_opt.apply_gradients(zip(tape.gradient(d_loss, discriminator.trainable_variables), discriminator.trainable_variables))
        z2 = tf.random.normal((n, latent))
        with tf.GradientTape() as tape:
            d_out = discriminator(generator(z2, training=True), training=True)
            g_loss = bce(tf.ones_like(d_out), d_out)
        g_opt.apply_gradients(zip(tape.gradient(g_loss, generator.trainable_variables), generator.trainable_variables))
        return d_loss, g_loss, tf.reduce_mean(d_real), tf.reduce_mean(d_fake)

    zp = np.random.default_rng(1).normal(size=(48, latent)).astype("float32")
    state = {"i": 0}

    def gap() -> float:
        g = np.asarray(generator(np.random.normal(size=(600, latent)).astype("float32"), training=False))
        r = Xtr[:600]
        return float(np.abs(g.mean(0) - r.mean(0)).mean() + np.abs(g.std(0) - r.std(0)).mean())

    def snapshot(phase: str) -> dict:
        idx = state["i"] % len(zp)
        state["i"] += 1
        g_acts, fake = g_probe.activations(zp, idx)
        d_acts, d_out = d_probe.activations(fake.astype("float32"), idx)
        payload = {"phase": phase, "epoch": rep.epoch,
                   "groups": [{"acts": g_acts, "weights": g_probe.weights()}, {"acts": d_acts, "weights": d_probe.weights()}],
                   "sample": {"kind": "gan", "generated": np.round(fake[idx], 3).tolist(),
                              "d_fake": round(float(d_out[idx][0]), 3)}}
        if phase == "epoch":
            g = np.asarray(generator(np.random.normal(size=(250, latent)).astype("float32"), training=False))
            payload["generated_points"] = np.round(g, 3).tolist()
        return payload

    rep.event("snapshot", snapshot("epoch"))
    data = tf.data.Dataset.from_tensor_slices(Xtr)
    history = {"d_loss": [], "g_loss": [], "dist_gap": []}
    for _ in range(rep.total):
        sums = np.zeros(4)
        n = 0
        for i, real in enumerate(data.shuffle(len(Xtr)).batch(bs)):
            vals = [float(v) for v in step(real)]
            sums += vals
            n += 1
            rep.batch(i, {"d_loss": vals[0], "g_loss": vals[1]}, snapshot)
        m = sums / max(n, 1)
        logs = {"d_loss": m[0], "g_loss": m[1], "d_real": m[2], "d_fake": m[3], "dist_gap": gap()}
        for k in history:
            history[k].append(logs[k])
        rep.epoch_end(logs, snapshot)

    evaluation = {"d_loss": round(float(history["d_loss"][-1]), 5), "g_loss": round(float(history["g_loss"][-1]), 5),
                  "dist_gap": round(float(history["dist_gap"][-1]), 5), "best_dist_gap": round(float(min(history["dist_gap"])), 5)}
    obs = ["En una GAN no hay exactitud: se evalúa la brecha entre la distribución generada y la real (menor es mejor)."]
    if history["dist_gap"][-1] > 0.3:
        obs.append("La brecha sigue alta: prueba más épocas o una tasa de aprendizaje menor (0.001).")
    return {"evaluation": evaluation, "observations": obs}, generator
