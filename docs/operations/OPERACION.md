# Guía operativa

## Monitoreo
- **Salud**: `GET /healthz` (Render lo usa como health check). En la app: *Administración → Salud del sistema*
  muestra latencia de BD, trabajos por estado, el trabajo en cola más antiguo y el último heartbeat del worker.
- **Logs**: JSON por línea (`ts`, `level`, `logger`, `msg`, `request_id`, `path`, `status`, `ms`, `job_id`). Los
  tokens se redactan automáticamente. Busca por `request_id` (cabecera `X-Request-ID`) o por la referencia que la
  interfaz muestra en los errores de entrenamiento.
- **Alertas sugeridas**: trabajos en cola > 10 min (el dashboard ya lo avisa), worker sin heartbeat > 60 s,
  tasa de `FAILED` creciente, respuestas 5xx.

## Respaldos y retención
- Supabase: activa respaldos diarios (plan Pro) o exporta con `pg_dump "$DATABASE_URL" -Fc > aurora-$(date +%F).dump`.
  Prueba la restauración en un proyecto aparte: `pg_restore -d "$OTRA_URL" aurora-AAAA-MM-DD.dump`.
- Storage: los modelos y CSV viven en el bucket `aurora-viii`; respáldalo con la CLI de Supabase o `rclone` (S3).
- Retención: *Administración → Aplicar política de retención* borra los eventos de alta frecuencia (`progress`,
  `snapshot`) de trabajos terminados hace más de `event_retention_days`. Métricas, resultados, modelos y auditoría
  se conservan. Puedes programarlo con un Cron Job de Render que haga `POST /api/v1/admin/retention/run`.

## Escalado
- **Más entrenamientos en paralelo**: añade workers (Render: sube *instances* del Background Worker, o arranca más
  procesos en otras máquinas). `SKIP LOCKED` reparte la cola sin duplicados.
- **GPU**: usa una imagen con CUDA y `tensorflow[and-cuda]` en lugar de `tensorflow-cpu`; ajusta los límites.
- **API**: es *stateless* (salvo el límite de tasa en memoria por instancia); puede escalar horizontalmente.

## Entornos
`ENVIRONMENT` = `dev` | `test` | `prod`. Usa un proyecto de Supabase y servicios de Render distintos por entorno.
Vercel crea *Preview Deployments* por rama; permítelos con `CORS_ORIGIN_REGEX` apuntando a una API de pruebas.

## Migraciones
Archivos `infra/migrations/NNN_nombre.sql`, idempotentes, aplicados en orden al arrancar la API o el worker
(protegidos con un *advisory lock*) y registrados en `schema_migrations`. Manual: `python -m app.core.migrate`.
