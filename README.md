# Aurora VIII :)

Plataforma enterprise para **diseñar, entrenar, evaluar, versionar y observar redes neuronales artificiales**.
Implementa el *Documento Maestro de Desarrollo* (NeuroLab Enterprise v1.0) sobre las operaciones de la
**Semana 11** de *Machine Learning y Deep Learning*: definir la red neuronal y su importancia, describir su
estructura, identificar sus tipos (Feedforward, RNN, CNN, GAN) y crearla con **TensorFlow y Keras**.

Mientras una red entrena, Aurora VIII la muestra **funcionando**: cada neurona se ilumina con su activación para
la muestra que la atraviesa, las conexiones cambian de grosor y color con sus pesos, y pulsos de luz recorren la
red de la entrada a la salida. Junto a ella se ven la predicción de esa muestra, la frontera de decisión
(datasets 2D) o la distribución generada (GAN), y las curvas de pérdida y exactitud, todo sin recargar la página.

```
React + Vite + TS (Vercel) ──► FastAPI (Render) ──► PostgreSQL (Supabase) ◄── Worker TensorFlow/Keras
            ▲   SSE con reanudación (Last-Event-ID)      cola SKIP LOCKED       ▲
            └──────────── Supabase Auth (JWT)        Supabase Storage ◄────────┘ modelos .keras
```

## Estructura

```
aurora-viii/
├── apps/web/                 Frontend React + TypeScript (Vite, TanStack Query, Recharts)
│   └── src/features/         dashboard · projects · fundamentals · architectures · datasets · training
│                             evaluation · model-registry · reports · administration · auth
├── services/api/             API FastAPI (/api/v1), RBAC, validación, auditoría, SSE, reportes
│   ├── app/{api/v1,core,modules,schemas,repositories}
│   └── tests/                unitarias · integración API/DB · e2e con TensorFlow · seguridad · recuperación
├── workers/training/         Worker TensorFlow/Keras aislado (cola en PostgreSQL) + cuaderno Colab
├── infra/{docker,migrations,monitoring}
├── docs/{architecture,api,operations}   + MANUAL_USUARIO.md
├── render.yaml · docker-compose.yml · .github/workflows/ci.yml
```

## Módulos (M01–M10)

| Módulo | Dónde |
|---|---|
| M01 Dashboard | Inicio: proyectos, trabajos activos y recientes, alertas |
| M02 Proyectos | Listado, búsqueda, filtros, contexto, miembros y roles, archivado |
| M03 Fundamentos | Conceptos, neurona interactiva, activaciones, código Keras, glosario |
| M04 Diseñador | Familia, editor de capas, validación de formas en backend, grafo, parámetros, código |
| M05 Datasets | 6 demos integrados + CSV propio validado, versionado y borrado seguro |
| M06 Entrenamientos | Cola con prioridad y cuotas, inicio, cancelación cooperativa, reintento, tiempo real |
| M07 Evaluación | Curvas por época, evaluación en test, matriz de confusión, observaciones |
| M08 Registro de modelos | Versiones inmutables con SHA-256, borrador → revisado → aprobado → retirado |
| M09 Reportes | Ficha PDF, historial CSV, comparación de hasta 5 ejecuciones |
| M10 Administración | Usuarios, límites de recursos, salud del sistema, auditoría global, retención |

## Ejecutar en local

**Con Docker** (requiere acceso a Docker Hub):
```bash
docker compose up --build        # http://localhost:5173  ·  API: http://localhost:8000/api/docs
```

**Sin Docker** (PostgreSQL 14+ local, Python 3.12, Node 22):
```bash
createdb aurora   # usuario/clave aurora:aurora o ajusta DATABASE_URL
pip install -r services/api/requirements.txt -r workers/training/requirements.txt

# API + worker embebido (modo local: ingreso sin contraseña)
cd services/api && PYTHONPATH=../../workers/training RUN_WORKER_IN_PROCESS=true \
  uvicorn app.main:app --reload --port 8000

# Frontend (otra terminal)
cd apps/web && npm install && npm run dev
```
El primer usuario que ingresa en modo desarrollo queda como Administrador.

## Pruebas
```bash
cd services/api && pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql://aurora:aurora@localhost:5432/aurora_test python -m pytest -q   # 32 pruebas
cd apps/web && npm test && npm run typecheck && npm run build
```

## Despliegue
Guía paso a paso: **[docs/operations/DESPLIEGUE_VERCEL_RENDER_SUPABASE.md](docs/operations/DESPLIEGUE_VERCEL_RENDER_SUPABASE.md)**.

## Documentación
- [Arquitectura, modelo de datos y decisiones](docs/architecture/ARQUITECTURA.md)
- [Contrato de la API y de los eventos en tiempo real](docs/api/API.md)
- [Operación: monitoreo, respaldos, retención, escalado](docs/operations/OPERACION.md)
- [Manual de usuario por módulo](docs/MANUAL_USUARIO.md)
