# API v1 de Aurora VIII

Base: `https://<api>/api/v1` · OpenAPI interactivo en `/api/docs` · Autenticación: `Authorization: Bearer <JWT>`.
Errores: `{"detail": "mensaje"}` o `{"detail": {"message": "...", "issues": [{"path": "...", "message": "..."}]}}`.

| Método y ruta | Permiso | Uso |
|---|---|---|
| `GET /auth/config` | público | Modo de autenticación |
| `POST /auth/local-login` | público (solo modo local) | Token de desarrollo |
| `GET /me` | autenticado | Usuario actual |
| `GET /dashboard` | autenticado | Resumen M01 |
| `GET /fundamentals` · `GET /families` | autenticado | Contenido M03 y catálogo M04 |
| `GET/POST /projects` | autenticado | Listar (`q`, `status`, `tag`) / crear |
| `GET/PATCH /projects/{id}` | view / edit_project | Detalle / editar o archivar |
| `GET/PUT /projects/{id}/members` · `DELETE …/{user_id}` | view / manage_members | Miembros y roles |
| `POST /architectures/validate` | autenticado | Validación sin guardar (formas, parámetros) |
| `GET/POST /projects/{id}/architectures` | view / design | Listar / crear versión |
| `GET /projects/{id}/datasets` · `…/{ds}/preview` | view | Datasets y muestra visual |
| `POST /projects/{id}/datasets` (multipart) · `DELETE …/{ds}` | design / edit_project | Subir CSV / borrado seguro |
| `POST /projects/{id}/training-jobs` | train | Encolar → `202 {job_id}` |
| `GET /projects/{id}/training-jobs` | view | Historial del proyecto |
| `GET /training-jobs/{id}` | view | Estado persistido + topología + última instantánea |
| `GET /training-jobs/{id}/metrics` | view | Métricas por época |
| `POST /training-jobs/{id}/cancel` | train | Cancelación (inmediata si está en cola) |
| `POST /training-jobs/{id}/retry` | train | Nuevo trabajo con los mismos parámetros |
| `POST /training-jobs/{id}/notes` | export | Observaciones de evaluación |
| `GET /training-jobs/{id}/events` | view | **SSE** (ver abajo) |
| `GET /projects/{id}/models` | view | Registro de modelos |
| `PATCH /models/{id}/status` | review_model / retire_model | Flujo de revisión |
| `GET /models/{id}/download` | download_model | Archivo `.keras` (cabecera `X-Checksum-SHA256`) |
| `GET /projects/{id}/report` · `compare?jobs=a,b` | view | Ficha y comparación |
| `GET /projects/{id}/export.csv` · `report.pdf` | export | Exportaciones |
| `GET /projects/{id}/audit-events` | view_audit | Auditoría del proyecto |
| `GET/PATCH /admin/users…` · `GET/PUT /admin/limits` · `GET /admin/health` · `GET /admin/audit-events` · `POST /admin/retention/run` | admin | M10 |

## Canal de eventos (SSE)

`GET /training-jobs/{id}/events?after=<id>` con cabecera `Last-Event-ID` opcional. Formato:

```
id: 1532
event: epoch
data: {"type":"epoch","payload":{"epoch":12,"total":40,"progress":0.3,"metrics":{"loss":0.31,"accuracy":0.88,"val_loss":0.33,"val_accuracy":0.87},"elapsed_s":4.1},"at":"2026-10-31T20:37:21Z"}
```

| `event` | `payload` |
|---|---|
| `status` | `from`, `to`, `label`, y `reason` / `error` / `model_version` / `evaluation` según el caso |
| `topology` | `family`, `groups[{name, layers[{name, kind, size, shown[], activation, ops_before[], params}]}]`, `class_names`, `has_boundary`, `points` / `real_points` |
| `progress` | `epoch`, `step`, `steps`, `progress`, métricas del lote (≤ 3/s) |
| `epoch` | `epoch`, `total`, `progress`, `metrics`, `elapsed_s` |
| `snapshot` | `phase` (batch/epoch), `epoch`, `groups[{acts[capa][neurona], weights[conexión][origen][destino]}]`, `sample`, `boundary?`, `generated_points?` |
| `cancel_requested` | `reason` |
| `end` | `status` (cierra el flujo cuando el trabajo terminó y no hay más eventos) |

Comentarios `: keep-alive` cada 15 s sin eventos. El cliente web (`apps/web/src/lib/sse.ts`) usa `fetch` para poder
enviar `Authorization`; `EventSource` puede usarse con `?access_token=` solo en esta ruta.
