import { describe, expect, it } from "vitest";
import { kerasCode } from "@/features/architectures/kerasCode";
import { topologyFromSummary } from "@/features/training/NetworkCanvas";
import type { ClassifierConfig } from "@/types";

const ff: ClassifierConfig = {
  input_shape: [2],
  layers: [{ type: "dense", units: 40, activation: "relu" }, { type: "dropout", rate: 0.2 }, { type: "dense", units: 8, activation: "tanh" }],
  output: { units: 2, activation: "softmax" },
};
const summary = {
  input_shape: [2],
  layers: [
    { type: "dense", units: 40, activation: "relu", output_shape: [40] },
    { type: "dropout", output_shape: [40] },
    { type: "dense", units: 8, activation: "tanh", output_shape: [8] },
    { type: "dense", units: 2, activation: "softmax", output_shape: [2] },
  ],
};

describe("kerasCode", () => {
  it("genera un Sequential con la entrada, las capas y la compilación", () => {
    const code = kerasCode("feedforward", ff);
    expect(code).toContain("keras.Input(shape=(2,))");
    expect(code).toContain("layers.Dense(40, activation='relu')");
    expect(code).toContain("layers.Dropout(0.2)");
    expect(code).toContain("loss='sparse_categorical_crossentropy'");
  });
  it("usa binary_crossentropy con salida sigmoide", () => {
    expect(kerasCode("feedforward", { ...ff, output: { units: 1, activation: "sigmoid" } })).toContain("binary_crossentropy");
  });
});

describe("topologyFromSummary", () => {
  const t = topologyFromSummary("feedforward", summary as never);
  const layers = t.groups[0].layers;
  it("convierte capas con neuronas en columnas visibles y las demás en operaciones", () => {
    expect(layers.map((l) => l.kind)).toEqual(["input", "dense", "dense", "output"]);
    expect(layers[2].ops_before).toEqual(["Dropout"]);
  });
  it("limita las neuronas dibujadas a 14 conservando los extremos", () => {
    expect(layers[1].size).toBe(40);
    expect(layers[1].shown.length).toBeLessThanOrEqual(14);
    expect(layers[1].shown[0]).toBe(0);
    expect(layers[1].shown.at(-1)).toBe(39);
  });
});
