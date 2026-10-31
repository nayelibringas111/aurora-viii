import type { ArchConfig, ClassifierConfig, Family, GanConfig, LayerSpec } from "@/types";

const act = (a?: string) => (a === "leaky_relu" ? "keras.activations.leaky_relu" : `'${a ?? "relu"}'`);

function layer(l: LayerSpec): string {
  switch (l.type) {
    case "dense": return `layers.Dense(${l.units}, activation=${act(l.activation)})`;
    case "dropout": return `layers.Dropout(${l.rate})`;
    case "batchnorm": return "layers.BatchNormalization()";
    case "conv2d": return `layers.Conv2D(${l.filters}, ${l.kernel}, padding='${l.padding ?? "same"}', activation=${act(l.activation)})`;
    case "maxpool2d": return `layers.MaxPooling2D(${l.pool})`;
    case "flatten": return "layers.Flatten()";
    case "globalavgpool": return "layers.GlobalAveragePooling2D()";
    case "simplernn": case "lstm": case "gru": {
      const n = { simplernn: "SimpleRNN", lstm: "LSTM", gru: "GRU" }[l.type];
      return `layers.${n}(${l.units}, return_sequences=${l.return_sequences ? "True" : "False"})`;
    }
    default: return `# ${l.type}`;
  }
}

/** Código Keras equivalente a lo que ejecuta el worker (con fines didácticos). */
export function kerasCode(family: Family, cfg: ArchConfig): string {
  if (family === "gan") {
    const g = cfg as GanConfig;
    return [
      "import keras", "from keras import layers", "",
      "generador = keras.Sequential([",
      `    keras.Input(shape=(${g.latent_dim},)),`,
      ...g.generator.map((l) => `    ${layer(l)},`),
      `    layers.Dense(${g.data_dim}, activation='linear'),`, "])", "",
      "discriminador = keras.Sequential([",
      `    keras.Input(shape=(${g.data_dim},)),`,
      ...g.discriminator.map((l) => `    ${layer(l)},`),
      "    layers.Dense(1, activation='sigmoid'),", "])",
      "# Entrenamiento adversario con tf.GradientTape (ver workers/training/aurora_worker/trainers.py)",
    ].join("\n");
  }
  const c = cfg as ClassifierConfig;
  const loss = c.output.activation === "sigmoid" ? "binary_crossentropy" : "sparse_categorical_crossentropy";
  return [
    "import keras", "from keras import layers", "",
    "model = keras.Sequential([",
    `    keras.Input(shape=(${c.input_shape.join(", ")}${c.input_shape.length === 1 ? "," : ""})),`,
    ...c.layers.map((l) => `    ${layer(l)},`),
    `    layers.Dense(${c.output.units}, activation='${c.output.activation}'),`, "])",
    `model.compile(optimizer='adam', loss='${loss}', metrics=['accuracy'])`,
    "model.summary()",
  ].join("\n");
}
