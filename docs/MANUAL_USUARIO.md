# Manual de usuario de Aurora VIII

## Roles
| Rol | Puede |
|---|---|
| Administrador | Todo, en todos los proyectos, más usuarios, límites, salud y auditoría global |
| Responsable de proyecto | Editar el proyecto, gestionar miembros, diseñar, entrenar, revisar/aprobar y retirar modelos |
| Ingeniero/analista de IA | Diseñar arquitecturas, subir datasets, entrenar, descargar modelos y exportar |
| Revisor | Consultar, comparar, registrar observaciones, marcar modelos como revisados o aprobados, exportar |
| Lector | Solo lectura |

## Inicio (M01)
Resumen de proyectos, entrenamientos activos, completados y modelos aprobados. Las alertas avisan de fallos o de
trabajos que esperan demasiado en cola. La tabla de entrenamientos recientes se actualiza sola.

## Proyectos (M02)
*Crear proyecto* pide nombre, etiquetas, descripción y el problema a resolver; al crearlo pasas al diseñador.
Dentro del proyecto, las pestañas son **Contexto** (documentación, miembros y archivado), **Arquitectura**,
**Dataset**, **Entrenamientos**, **Modelos** e **Historial**. Para añadir a alguien, esa persona debe haber ingresado
una vez; luego escribe su correo y elige su rol.

## Fundamentos (M03) y Catálogo de redes
Explica qué es una red neuronal y por qué importa, la neurona, capas, conexiones, activaciones, entrenamiento y el
código Keras. La **neurona interactiva** permite mover entradas, pesos y sesgo y ver la salida. El catálogo describe
Feedforward, CNN, RNN y GAN con casos de uso, restricciones y su grafo.

## Diseñador de arquitecturas (M04)
1. Elige la familia. Se carga una plantilla válida.
2. En **Capas ocultas** selecciona, sube, baja, elimina o añade capas (solo las permitidas por la familia).
3. En **Propiedades** ajusta neuronas, activación, filtros, kernel, *return sequences*, entrada y salida.
4. El servidor valida en vivo: verás el grafo, la forma de salida y los parámetros de cada capa, o la lista de
   problemas (p. ej. «Dense necesita entrada 1D: añade Flatten»).
5. Escribe por qué elegiste esa familia y **Guardar arquitectura**. Mismo nombre = nueva versión.

## Datasets (M05)
Seis datasets demo: Espirales, Anillos (3 clases) y XOR (Feedforward), Patrones 8×8 (CNN), Ondas temporales (RNN) y
Anillo 2D (GAN). Se dividen 70/15/15 en entrenamiento, validación y prueba. Puedes **subir un CSV** con cabecera y
columnas numéricas; la última columna es la clase salvo que indiques otra. Se estandariza automáticamente.

## Entrenamientos (M06) y la red en funcionamiento
Elige arquitectura y dataset (solo aparecen los compatibles), épocas, batch, optimizador, tasa de aprendizaje y
semilla, e **Iniciar entrenamiento**. En la página del entrenamiento:

- **Escenario de la red**: cada círculo es una neurona (cuadrados = mapas de una Conv2D; el lazo indica memoria
  recurrente). Brilla según su activación para la muestra que está pasando; turquesa = positiva, violeta = negativa.
  Las conexiones se engrosan con el peso; los pulsos de luz muestran por dónde fluye la señal. Pasa el cursor sobre
  una neurona para ver su valor. Si una capa tiene más de 14 neuronas, se muestra una selección («14 de 64»).
- **Muestra en tránsito**: el dato que atraviesa la red y la probabilidad que la red asigna a cada clase.
- **Frontera de decisión** (datasets 2D) o **Real frente a generado** (GAN).
- Barra de progreso, época, pérdida y exactitud en vivo, y eventos recientes.

**Cancelar** detiene el trabajo al terminar el lote en curso. Un trabajo fallido o cancelado puede **Reintentarse**.
Puedes cerrar la página: el entrenamiento sigue en el servidor y al volver verás el estado actual.

## Evaluación (M07)
Curvas de pérdida y exactitud (entrenamiento continuo, validación punteada), evaluación final en el conjunto de
prueba, matriz de confusión y observaciones automáticas (sobreajuste, exactitud cercana al azar). Registra tus
propias observaciones o limitaciones.

## Registro de modelos (M08)
Cada entrenamiento completado crea una versión inmutable con su SHA-256. Flujo: **Borrador → Revisado → Aprobado**;
cualquier versión puede **Retirarse**. Descarga el archivo `.keras` y cárgalo con `keras.models.load_model()`.

## Historial y reportes (M09)
Tabla de ejecuciones con fecha, versión, duración, estado y parámetros. Marca hasta cinco para **comparar** sus
curvas. Exporta el historial en **CSV** o la **ficha PDF** del proyecto. La auditoría del proyecto muestra quién hizo
qué y cuándo.

## Administración (M10)
Salud del sistema (base de datos y worker), límites de recursos (épocas, batch, capas, neuronas, parámetros, tamaño
de CSV, cuotas y duración), usuarios (administrador sí/no, suspender), auditoría global filtrable y la política de
retención de eventos.
