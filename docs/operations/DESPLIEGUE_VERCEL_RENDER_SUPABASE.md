# Guía de despliegue · Vercel + Render + Supabase

Esta guía pone Aurora VIII en internet con tres servicios:

| Pieza | Dónde | Qué hace |
|---|---|---|
| Frontend React (`apps/web`) | **Vercel** | Interfaz, visualización de la red en vivo |
| API FastAPI (`services/api`) | **Render** (Web Service) | Autenticación, permisos, validación, cola, eventos SSE |
| Worker TensorFlow (`workers/training`) | **Render** (Background Worker) *o* tu PC / Google Colab | Entrena los modelos |
| PostgreSQL + Auth + Storage | **Supabase** | Datos, usuarios y archivos (datasets y modelos `.keras`) |

```
Navegador ──► Vercel (React) ──HTTPS + JWT──► Render: API ──► Supabase PostgreSQL ◄── Worker (TensorFlow)
     │                                           │  ▲ SSE                 ▲                     │
     └──── Supabase Auth (login) ────────────────┘  └── eventos ──────────┘   Supabase Storage ◄┘
```

La cola de entrenamientos vive en la propia base de datos (no hace falta Redis). Por eso el worker puede correr
en cualquier máquina que llegue a Supabase.

> **Antes de empezar, una decisión de costo.** TensorFlow ocupa ~650–750 MB de RAM en el worker (medido con
> TensorFlow 2.21). Las instancias de 512 MB de Render (Free y Starter) **no alcanzan para el worker**; la API
> sola usa ~100 MB y sí cabe. Elige una opción:
>
> | Opción | API | Worker | Costo aprox./mes |
> |---|---|---|---|
> | **A. Demo gratuita** | Render Free | Tu PC o Google Colab (abierto mientras entrenas) | US$ 0 |
> | **B. Producción ligera** | Render Free o Starter | Render Background Worker 2 GB (`1c-2g`) | US$ 25–32 |
> | **C. Todo en uno** | Render Web 2 GB con `RUN_WORKER_IN_PROCESS=true` | (embebido en la API) | US$ 25 |
>
> En Render Free la API se suspende tras 15 min sin tráfico y tarda ~1 min en despertar. Revisa los precios
> vigentes en render.com/pricing antes de decidir.

---

## 0. Requisitos

- Cuenta en GitHub, Supabase, Render y Vercel (las tres permiten ingresar con GitHub).
- El código de Aurora VIII subido a **un repositorio de GitHub** (puede ser privado):

```bash
cd aurora-viii
git init && git add . && git commit -m "Aurora VIII"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/aurora-viii.git
git push -u origin main
```

---

## 1. Supabase (base de datos, autenticación y almacenamiento)

### 1.1 Crear el proyecto
1. supabase.com → **New project**.
2. Nombre: `aurora-viii`. Contraseña de base de datos: genera una fuerte y **guárdala**.
3. Región: elige una y usa la **misma zona** en Render (p. ej. *East US* en Supabase ↔ *Virginia/Ohio* en Render;
   *West US* ↔ *Oregon*). La latencia API↔BD afecta cada evento en vivo.

### 1.2 Cadena de conexión (`DATABASE_URL`)
1. En el proyecto: botón **Connect** (arriba).
2. Elige **Session pooler** (puerto **5432**). Funciona por IPv4, que es lo que tiene Render.
   La “Direct connection” usa IPv6 y Render no la alcanza sin el complemento IPv4 de Supabase.
   No uses el *Transaction pooler* (6543): la API mantiene conexiones persistentes y el worker usa bloqueos de fila.
3. Copia la cadena. Tiene esta forma:
   ```
   postgresql://postgres.TU_REF:TU_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```
   Reemplaza `TU_PASSWORD`. Si la contraseña tiene `@ : / ? #`, codifícala (p. ej. `@` → `%40`).

No necesitas crear tablas a mano: **la API ejecuta las migraciones al arrancar** (`infra/migrations/*.sql`) y activa
RLS en todas las tablas para que nadie pueda leerlas con la clave pública; los datos solo se acceden vía API.
Si prefieres hacerlo tú, pega `infra/migrations/001_init.sql` en **SQL Editor → Run**.

### 1.3 Claves de API
**Project Settings → API Keys**. Anota:

| Valor | Variable | Dónde se usa |
|---|---|---|
| Project URL `https://TU_REF.supabase.co` | `SUPABASE_URL` / `VITE_SUPABASE_URL` | Render y Vercel |
| **Publishable key** (`sb_publishable_…`) o la *anon key* legada | `VITE_SUPABASE_ANON_KEY` | Solo Vercel (es pública) |
| **Secret key** (`sb_secret_…`) o la *service_role* legada | `SUPABASE_SECRET_KEY` | Solo Render (**secreta**) |

> Supabase anunció el retiro de las claves legadas `anon`/`service_role` para fines de 2026. Aurora VIII acepta
> las nuevas (`sb_publishable_`/`sb_secret_`) y las legadas. Nunca pongas la secret key en Vercel ni en el código.

### 1.4 Firma de tokens (JWT)
**Project Settings → JWT Keys**. Si tu proyecto usa claves asimétricas (ES256/RS256), no hay nada que copiar: la API
descarga las claves públicas desde `https://TU_REF.supabase.co/auth/v1/.well-known/jwks.json`.
Si aún usa el secreto compartido HS256 legado, migra a claves asimétricas (recomendado) o copia ese secreto en
`SUPABASE_JWT_SECRET` en Render.

### 1.5 Autenticación
1. **Authentication → Sign In / Providers → Email**: activado. Para clases o demos puedes desactivar
   *Confirm email*; en producción déjalo activo.
2. **Authentication → URL Configuration** (lo completarás en el paso 4, cuando tengas la URL de Vercel):
   - **Site URL**: `https://aurora-viii.vercel.app`
   - **Redirect URLs**: `https://aurora-viii.vercel.app/**` y, si usas previews, `https://aurora-viii-*.vercel.app/**`

### 1.6 Storage
La API crea el bucket **privado** `aurora-viii` al arrancar. Si quieres verlo o crearlo a mano:
**Storage → New bucket → `aurora-viii`**, *Public bucket* desactivado. No agregues políticas: solo la API (con la
secret key) lee y escribe.

---

## 2. Render (API y worker)

### 2.1 Opción rápida: Blueprint
El repositorio incluye `render.yaml` con la API y el worker.

1. render.com → **New → Blueprint** → conecta GitHub → elige `aurora-viii`.
2. Render muestra los dos servicios. Si vas por la **opción A** (worker en tu PC/Colab), elimina
   `aurora-viii-worker` del plan antes de aplicar, o edita `render.yaml` y bórralo.
3. Completa las variables marcadas como secretas (`sync: false`):

| Variable | Valor |
|---|---|
| `DATABASE_URL` | La cadena *Session pooler* del paso 1.2 |
| `SUPABASE_URL` | `https://TU_REF.supabase.co` |
| `SUPABASE_SECRET_KEY` | `sb_secret_…` |
| `CORS_ORIGINS` | De momento `http://localhost:5173`; en el paso 4 la cambias por tu URL de Vercel |
| `CORS_ORIGIN_REGEX` | Opcional, para previews: `https://aurora-viii-.*\.vercel\.app` (o déjala vacía) |
| `BOOTSTRAP_ADMIN_EMAILS` | Tu correo. Al ingresar por primera vez serás Administrador |

4. **Apply**. El primer build tarda varios minutos (la imagen del worker incluye TensorFlow).
5. Comprueba la API: `https://aurora-viii-api.onrender.com/healthz` → `{"status":"ok"}` y la documentación
   interactiva en `/api/docs`.

### 2.2 Opción manual (sin Blueprint)
**API** → New → **Web Service** → repo `aurora-viii`:
- Language: **Docker** · Dockerfile Path: `./infra/docker/api.Dockerfile` · Docker Build Context: `.`
- Instance type: Free (o Starter) · Health Check Path: `/healthz`
- Environment: las variables de la tabla anterior más
  `ENVIRONMENT=prod`, `AUTH_MODE=supabase`, `STORAGE_BACKEND=supabase`, `STORAGE_BUCKET=aurora-viii`,
  `RUN_WORKER_IN_PROCESS=false`.

**Worker (opción B)** → New → **Background Worker**:
- Docker · Dockerfile Path: `./infra/docker/worker.Dockerfile` · Context: `.`
- Instance type: **Standard (2 GB)** o superior.
- Environment: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `STORAGE_BACKEND=supabase`,
  `STORAGE_BUCKET=aurora-viii`, `ENVIRONMENT=prod`.

**Todo en uno (opción C)**: un solo Web Service con instancia de **2 GB** y las variables `WITH_TF=true`
(Render pasa las variables de entorno al build de Docker, así la imagen incluye TensorFlow) y
`RUN_WORKER_IN_PROCESS=true`.

### 2.3 Worker gratuito (opción A)
El worker solo necesita llegar a Supabase; no recibe tráfico.

**En tu computadora** (Linux/macOS/WSL, Python 3.12):
```bash
cp workers/training/.env.example workers/training/.env   # completa DATABASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY
./workers/training/run_worker.sh
```
Con Docker: `docker build -f infra/docker/worker.Dockerfile -t aurora-worker . && docker run --env-file workers/training/.env aurora-worker`

**En Google Colab**: abre `workers/training/aurora_worker_colab.ipynb` en Colab, pon la URL de tu repo y ejecuta las
celdas. Mientras la celda final corra, los entrenamientos se procesan.

Si el worker se apaga a mitad de un entrenamiento, la plataforma lo detecta por *heartbeat* y lo reencola (hasta 2
intentos). En **Administración → Salud del sistema** verás si hay un worker activo.

---

## 3. Vercel (frontend)

1. vercel.com → **Add New → Project** → importa `aurora-viii`.
2. **Root Directory**: `apps/web` (botón *Edit*). Framework: **Vite** (se detecta solo).
   Build: `npm run build` · Output: `dist` (ya definidos en `apps/web/vercel.json`).
3. **Environment Variables** (Production y Preview):

| Variable | Valor |
|---|---|
| `VITE_API_URL` | `https://aurora-viii-api.onrender.com` (sin barra final) |
| `VITE_SUPABASE_URL` | `https://TU_REF.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | La *publishable key* (`sb_publishable_…`) o la *anon key* |

4. **Deploy**. Obtendrás algo como `https://aurora-viii.vercel.app`.

> Vite incrusta las variables `VITE_*` **al compilar**. Si cambias una, ve a *Deployments → ⋯ → Redeploy*.
> `vercel.json` ya incluye la reescritura a `index.html`, así que recargar `/proyectos/...` no da 404.

---

## 4. Conectar las piezas

1. **Render → aurora-viii-api → Environment**: `CORS_ORIGINS=https://aurora-viii.vercel.app`
   (varias URL separadas por coma; sin barra final). Guarda: Render redepliega.
2. **Supabase → Authentication → URL Configuration**: Site URL y Redirect URLs con tu dominio de Vercel (paso 1.5).
3. Abre tu URL de Vercel → **Crear cuenta** con el correo de `BOOTSTRAP_ADMIN_EMAILS` → confirma el correo si
   corresponde → **Ingresar**. Verás *Administración* en el menú.

---

## 5. Verificación del MVP (criterio de finalización del documento maestro)

1. **Proyectos → Crear proyecto** («Espirales», describe el problema) → te lleva al diseñador.
2. Familia **Feedforward** (plantilla 16-12-8, ReLU, salida softmax 2) → **Guardar arquitectura**.
3. **Entrenar esta arquitectura** → dataset *Espirales entrelazadas* → 40 épocas → **Iniciar entrenamiento**.
4. En la página del entrenamiento deberías ver, **sin recargar**:
   - estado *En cola → Preparando → Ejecutando*, el indicador **En vivo**,
   - la **red neuronal animada**: neuronas que se iluminan con la activación de la muestra que pasa, conexiones
     turquesa/violeta según el signo del peso y pulsos de luz que viajan de la entrada a la salida,
   - la frontera de decisión curvándose época a época y las curvas de pérdida/exactitud.
5. Al terminar: *Completado*, evaluación con matriz de confusión y **Modelos → Versión 1** con su SHA-256.
6. Cierra sesión, vuelve a ingresar y abre el entrenamiento: todo sigue ahí (trazabilidad).
7. Con otra cuenta que no sea miembro, intenta abrir la URL del entrenamiento: debe responder *no encontrado*.

Si el paso 4 se queda en *En cola*, el worker no está corriendo (ver §7).

---

## 6. Seguridad en producción (lista de control)

- [ ] `ENVIRONMENT=prod` y `AUTH_MODE=supabase` en Render (el acceso local queda desactivado).
- [ ] La secret key de Supabase **solo** en Render/worker; en Vercel solo la publishable/anon key.
- [ ] `CORS_ORIGINS` con tus dominios exactos (nunca `*`).
- [ ] Bucket `aurora-viii` **privado**; RLS activo en las tablas (lo hace la migración).
- [ ] *Confirm email* activado en Supabase Auth.
- [ ] Límites revisados en **Administración → Límites de recursos** (épocas, tamaño de CSV, cuotas, duración).
- [ ] Copias de seguridad: Supabase hace respaldos diarios en planes pagos; en el plan gratuito exporta con
      `pg_dump "$DATABASE_URL" > respaldo.sql` periódicamente y prueba restaurarlo.

---

## 7. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| El login muestra «No se pudo conectar con la API» | API dormida (Render Free) o `VITE_API_URL` incorrecta | Espera ~1 min y recarga; revisa la variable y redepliega Vercel |
| Error de CORS en la consola del navegador | `CORS_ORIGINS` no incluye la URL exacta de Vercel | Corrige la variable en Render (sin `/` final) |
| «Token inválido» al ingresar | `SUPABASE_URL` distinta entre Vercel y Render, o proyecto con HS256 legado | Usa la misma URL; configura `SUPABASE_JWT_SECRET` o migra a claves asimétricas |
| Entrenamiento eternamente *En cola* | No hay worker activo | Revisa los logs del Background Worker, o arranca `run_worker.sh`/Colab |
| Worker reinicia con *Out of memory* | Instancia de 512 MB | Usa 2 GB (Standard) o la opción A |
| `could not translate host name` / timeout a la BD | Usaste la *Direct connection* (IPv6) | Cambia a **Session pooler** |
| `password authentication failed` | Contraseña sin codificar o usuario sin `.TU_REF` | Usa exactamente la cadena del botón *Connect* |
| «Supabase Storage rechazó la subida (401/403)» | Falta `SUPABASE_SECRET_KEY` o es la publishable | Pon la secret key en API **y** worker |
| La API no arranca: error en migración | Permisos o cadena equivocada | Ejecuta `001_init.sql` en el SQL Editor y revisa `DATABASE_URL` |
| Recargar una ruta en Vercel da 404 | Root Directory no es `apps/web` | Corrígelo: ahí está `vercel.json` |

Los logs de la API son JSON estructurado (Render → *Logs*); cada error devuelve una referencia (`X-Request-ID`) que
puedes buscar en ellos. Los fallos de entrenamiento muestran al usuario un mensaje controlado con una referencia; el
detalle técnico solo queda en los logs del worker.
