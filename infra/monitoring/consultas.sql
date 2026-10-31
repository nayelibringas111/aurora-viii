-- Aurora VIII · consultas de monitoreo (SQL Editor de Supabase o psql)

-- Trabajos por estado en las últimas 24 h
SELECT status, count(*) FROM training_jobs WHERE created_at > now() - interval '24 hours' GROUP BY status;

-- Cola: trabajos esperando más de 10 minutos (¿worker caído?)
SELECT id, created_at, now() - created_at AS espera FROM training_jobs
WHERE status = 'QUEUED' AND created_at < now() - interval '10 minutes' ORDER BY created_at;

-- Trabajos en ejecución sin heartbeat reciente
SELECT id, worker_id, heartbeat_at FROM training_jobs
WHERE status IN ('PREPARING','RUNNING') AND heartbeat_at < now() - interval '60 seconds';

-- Último latido del worker
SELECT value_json FROM system_settings WHERE key = 'worker_heartbeat';

-- Duración media y tasa de fallos por familia (7 días)
SELECT a.family, count(*) AS total,
       round(avg(extract(epoch FROM j.ended_at - j.started_at))::numeric, 1) AS seg_promedio,
       round(100.0 * avg((j.status = 'FAILED')::int), 1) AS pct_fallidos
FROM training_jobs j JOIN architectures a ON a.id = j.architecture_id
WHERE j.created_at > now() - interval '7 days' GROUP BY a.family;

-- Tamaño de la bitácora de eventos (candidata a retención)
SELECT event_type, count(*), pg_size_pretty(sum(pg_column_size(payload))) FROM job_events GROUP BY event_type;
