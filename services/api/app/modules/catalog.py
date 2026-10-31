"""Contenido del módulo de Fundamentos (M03) y del catálogo de familias (M04).

Cubre las operaciones de la Semana 11: definir la red neuronal y su importancia, describir su estructura,
identificar tipos de redes y crearlas con TensorFlow/Keras.
"""

FUNDAMENTALS = [
    {
        "id": "que-es",
        "title": "¿Qué es una red neuronal artificial?",
        "body": "Es un modelo matemático formado por unidades simples (neuronas) organizadas en capas y unidas por "
                "conexiones con peso. Cada neurona combina sus entradas, les suma un sesgo y aplica una función de "
                "activación. Al ajustar los pesos con datos de ejemplo, la red aprende a transformar entradas en "
                "salidas útiles: clasificar, predecir o generar.",
        "keypoints": ["Aprende de ejemplos en lugar de reglas escritas a mano",
                      "Aproxima funciones no lineales complejas",
                      "Es la base del aprendizaje profundo (Deep Learning)"],
    },
    {
        "id": "importancia",
        "title": "Importancia en la Inteligencia Artificial",
        "body": "Las redes neuronales impulsan la mayoría de los avances recientes de la IA: visión por computadora, "
                "reconocimiento de voz, traducción, recomendación y modelos generativos. Su ventaja es que extraen "
                "automáticamente las características relevantes de los datos, algo que antes requería ingeniería manual.",
        "keypoints": ["Visión: detectar objetos, diagnósticos por imagen",
                      "Secuencias: voz, texto, series de tiempo",
                      "Generación: imágenes, datos sintéticos"],
    },
    {
        "id": "neurona",
        "title": "La neurona artificial",
        "body": "Calcula z = w₁x₁ + w₂x₂ + … + wₙxₙ + b y luego a = f(z). Los pesos w indican cuánto influye cada "
                "entrada; el sesgo b desplaza el umbral; f es la función de activación que introduce no linealidad.",
        "formula": "a = f( Σ wᵢ·xᵢ + b )",
        "keypoints": ["Pesos: importancia de cada entrada", "Sesgo: desplazamiento del umbral",
                      "Activación: decide cuánto «se enciende» la neurona"],
    },
    {
        "id": "capas",
        "title": "Capas: entrada, ocultas y salida",
        "body": "La capa de entrada recibe los datos (una neurona por rasgo). Las capas ocultas transforman la "
                "representación paso a paso; más capas permiten patrones más abstractos. La capa de salida entrega "
                "el resultado: una neurona por clase con softmax, una sola con sigmoide para dos clases, o lineal "
                "para regresión.",
        "keypoints": ["Entrada = forma de los datos", "Ocultas = capacidad del modelo", "Salida = tipo de tarea"],
    },
    {
        "id": "conexiones",
        "title": "Conexiones y pesos",
        "body": "En una capa densa cada neurona se conecta con todas las de la capa anterior: n_entrada × n_salida "
                "pesos más un sesgo por neurona. Durante el entrenamiento el algoritmo de retropropagación calcula "
                "cómo cambia la pérdida respecto a cada peso y el optimizador los ajusta en la dirección que la reduce.",
        "formula": "parámetros(Dense) = entradas × unidades + unidades",
        "keypoints": ["Peso positivo: excita", "Peso negativo: inhibe", "Magnitud: fuerza de la conexión"],
    },
    {
        "id": "activaciones",
        "title": "Funciones de activación",
        "body": "Sin activaciones no lineales, apilar capas equivaldría a una sola transformación lineal. ReLU es la "
                "opción por defecto en capas ocultas; tanh y sigmoide comprimen valores; softmax convierte la salida "
                "en probabilidades que suman 1.",
        "activations": [
            {"name": "relu", "formula": "max(0, z)", "use": "Capas ocultas (por defecto)"},
            {"name": "tanh", "formula": "(eᶻ − e⁻ᶻ)/(eᶻ + e⁻ᶻ)", "use": "Ocultas y recurrentes, salida en [−1, 1]"},
            {"name": "sigmoid", "formula": "1/(1 + e⁻ᶻ)", "use": "Salida binaria"},
            {"name": "softmax", "formula": "eᶻⁱ / Σ eᶻʲ", "use": "Salida multiclase"},
            {"name": "elu / gelu / swish", "formula": "variantes suaves de ReLU", "use": "Redes más profundas"},
        ],
    },
    {
        "id": "entrenamiento",
        "title": "Cómo aprende: pérdida, épocas y optimizador",
        "body": "La función de pérdida mide el error. Una época es una pasada completa por el conjunto de "
                "entrenamiento, dividido en lotes (batch). El optimizador (Adam, SGD, RMSprop) actualiza los pesos "
                "tras cada lote según la tasa de aprendizaje. El conjunto de validación detecta sobreajuste; el de "
                "prueba da la evaluación final.",
        "keypoints": ["Pérdida baja en entrenamiento y alta en validación = sobreajuste",
                      "Tasa de aprendizaje alta = inestable; baja = lenta", "Dropout y BatchNorm ayudan a generalizar"],
    },
    {
        "id": "keras",
        "title": "Crear una red con TensorFlow y Keras",
        "body": "Keras define el modelo como una pila de capas. Aurora VIII traduce tu diseño visual a este código y lo "
                "ejecuta en el worker Python.",
        "code": "import tensorflow as tf\n\nmodel = tf.keras.Sequential([\n    tf.keras.Input(shape=(2,)),\n"
                "    tf.keras.layers.Dense(16, activation='relu'),\n    tf.keras.layers.Dense(16, activation='relu'),\n"
                "    tf.keras.layers.Dense(2, activation='softmax'),\n])\nmodel.compile(optimizer='adam',\n"
                "              loss='sparse_categorical_crossentropy',\n              metrics=['accuracy'])\n"
                "model.fit(X_train, y_train, epochs=40, batch_size=32,\n          validation_data=(X_val, y_val))",
    },
]

GLOSSARY = [
    ("Neurona", "Unidad que combina entradas ponderadas, suma un sesgo y aplica una activación."),
    ("Peso", "Parámetro que escala la señal de una conexión; se aprende durante el entrenamiento."),
    ("Sesgo (bias)", "Parámetro sumado antes de la activación que desplaza el umbral de la neurona."),
    ("Capa densa", "Capa en la que cada neurona se conecta con todas las de la capa anterior."),
    ("Función de activación", "Función no lineal aplicada a la salida de una neurona."),
    ("Época", "Pasada completa por todos los datos de entrenamiento."),
    ("Batch / lote", "Subconjunto de ejemplos procesados antes de actualizar los pesos."),
    ("Función de pérdida", "Mide el error entre la predicción y el valor real."),
    ("Retropropagación", "Algoritmo que calcula el gradiente de la pérdida respecto a cada peso."),
    ("Optimizador", "Regla que usa los gradientes para actualizar los pesos (Adam, SGD, RMSprop)."),
    ("Tasa de aprendizaje", "Tamaño del paso de cada actualización de pesos."),
    ("Sobreajuste", "El modelo memoriza el entrenamiento y generaliza mal a datos nuevos."),
    ("Dropout", "Apaga neuronas al azar durante el entrenamiento para reducir el sobreajuste."),
    ("Convolución", "Filtro que recorre la imagen detectando patrones locales con pesos compartidos."),
    ("Pooling", "Reduce el tamaño espacial conservando la información dominante."),
    ("Celda recurrente", "Unidad con memoria que procesa secuencias paso a paso (SimpleRNN, LSTM, GRU)."),
    ("Generador", "En una GAN, red que produce datos sintéticos a partir de ruido."),
    ("Discriminador", "En una GAN, red que distingue datos reales de generados."),
    ("Exactitud (accuracy)", "Proporción de predicciones correctas."),
    ("Validación", "Datos reservados para vigilar el entrenamiento sin usarlos para ajustar pesos."),
]

FAMILIES = [
    {
        "id": "feedforward", "name": "Feedforward (perceptrón multicapa)", "status": "habilitada",
        "summary": "La información fluye en una sola dirección, de la entrada a la salida, sin ciclos.",
        "use_cases": ["Datos tabulares", "Clasificación y regresión", "Línea base de cualquier problema"],
        "restrictions": ["Entrada 1D (vector de rasgos)", "Capas: Dense, Dropout, BatchNorm",
                         "Salida softmax = nº de clases; sigmoide = 1 neurona (2 clases)"],
        "template": {"input_shape": [2], "layers": [{"type": "dense", "units": 16, "activation": "relu"},
                                                    {"type": "dense", "units": 12, "activation": "relu"},
                                                    {"type": "dense", "units": 8, "activation": "relu"}],
                     "output": {"units": 2, "activation": "softmax"}},
        "suggested_dataset": "espirales",
    },
    {
        "id": "cnn", "name": "Convolucional (CNN)", "status": "habilitada",
        "summary": "Usa filtros que recorren la imagen y comparten pesos para detectar bordes, formas y texturas.",
        "use_cases": ["Clasificación de imágenes", "Detección de objetos", "Imágenes médicas"],
        "restrictions": ["Entrada 3D (alto, ancho, canales)", "Al menos una Conv2D",
                         "Flatten o GlobalAvgPool antes de las capas Dense"],
        "template": {"input_shape": [8, 8, 1], "layers": [{"type": "conv2d", "filters": 8, "kernel": 3, "activation": "relu"},
                                                          {"type": "maxpool2d", "pool": 2},
                                                          {"type": "conv2d", "filters": 12, "kernel": 3, "activation": "relu"},
                                                          {"type": "flatten"},
                                                          {"type": "dense", "units": 16, "activation": "relu"}],
                     "output": {"units": 4, "activation": "softmax"}},
        "suggested_dataset": "patrones8x8",
    },
    {
        "id": "rnn", "name": "Recurrente (RNN, LSTM, GRU)", "status": "habilitada",
        "summary": "Mantiene un estado interno que recuerda los pasos anteriores de una secuencia.",
        "use_cases": ["Series de tiempo", "Texto y voz", "Señales de sensores"],
        "restrictions": ["Entrada 2D (pasos, rasgos)", "Al menos una capa recurrente",
                         "Recurrentes encadenadas: return_sequences=true en todas menos la última"],
        "template": {"input_shape": [24, 1], "layers": [{"type": "lstm", "units": 16, "return_sequences": False},
                                                        {"type": "dense", "units": 12, "activation": "relu"}],
                     "output": {"units": 3, "activation": "softmax"}},
        "suggested_dataset": "ondas",
    },
    {
        "id": "gan", "name": "Generativa adversaria (GAN)", "status": "experimental",
        "summary": "Dos redes compiten: el generador crea datos falsos y el discriminador intenta detectarlos.",
        "use_cases": ["Datos sintéticos", "Aumento de datos", "Generación de imágenes"],
        "restrictions": ["Dataset de generación", "Entrenamiento inestable: tasas de aprendizaje bajas",
                         "Se evalúa por la calidad de las muestras, no por exactitud"],
        "template": {"data_dim": 2, "latent_dim": 8,
                     "generator": [{"type": "dense", "units": 32, "activation": "relu"},
                                   {"type": "dense", "units": 32, "activation": "relu"}],
                     "discriminator": [{"type": "dense", "units": 32, "activation": "leaky_relu"},
                                       {"type": "dense", "units": 16, "activation": "leaky_relu"}]},
        "suggested_dataset": "anillo2d",
    },
]
