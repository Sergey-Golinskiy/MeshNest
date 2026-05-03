# MeshNest architecture

## Контейнеры (`deploy/docker-compose.yml`)

```
┌─────────────────────────────────────────────────────────────┐
│  Internet                                                   │
│   └── Cloudflare edge (TLS, WAF, optional Access)          │
│        └── outbound tunnel ↓                                │
│                                                             │
│  Mini-PC (Firebat AK2 plus, N100, 16GB, 500GB NVMe):        │
│   ┌────────────────────────────────────────────────────┐   │
│   │  cloudflared (256 MB)                              │   │
│   │     └── HTTP → web:80                              │   │
│   │  web = nginx + react/dist + reverse-proxy (256 MB) │   │
│   │     ├── /  → static SPA                            │   │
│   │     └── /api/  → api:8000                          │   │
│   │  api = FastAPI uvicorn x2 workers (1.5 GB)         │   │
│   │     ├── REST /api/v1/*                             │   │
│   │     ├── postgres (SQLAlchemy async)                │   │
│   │     ├── redis (cache)                              │   │
│   │     ├── minio (S3 presigned URLs)                  │   │
│   │     └── celery enqueue                             │   │
│   │  worker x2 (3 GB)                                  │   │
│   │     ├── process_import_package                     │   │
│   │     ├── stl_to_glb (trimesh)                       │   │
│   │     └── extract_3mf_thumbnail                      │   │
│   │  worker-beat (256 MB)                              │   │
│   │     └── periodic: cleanup, reindex                 │   │
│   │  postgres:16 (2.5 GB) — pg_data volume             │   │
│   │  redis:7 (512 MB) — broker + cache                 │   │
│   │  minio (1 GB) — meshnest-files / -derived /        │   │
│   │                 -imports buckets                   │   │
│   │  meilisearch:1.10 (2 GB) — full-text (Phase 2)     │   │
│   └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Поток данных при импорте

```
User → frontend → POST /api/v1/uploads/init
                    ← {upload_id, chunk_size: 90MB, total_chunks: N}
User → frontend → 3 параллельных PUT /api/v1/uploads/{id}/chunk?n=…
                    (каждый ≤90 MB чтобы пройти CF Free)
                    api → /var/lib/meshnest/uploads/{id}/chunk-NNNN.bin
User → frontend → POST /api/v1/uploads/{id}/complete
                    api: склеивает chunks → upload в minio
                    bucket=meshnest-imports key=uploads/{id}/{filename}
User → frontend → POST /api/v1/import-package {upload_id}
                    api: создаёт ImportJob (status=queued)
                    api: kick celery process_import_package
                    ← {import_job_id}

Worker → celery process_import_package(job_id, key):
  1. download zip из minio:meshnest-imports
  2. unzip в /tmp/meshnest-import-{job_id}/
  3. read manifest.json + database/models.json + database/files.csv
  4. for each model:
       - upsert Category, Tag's
       - INSERT Model
       - upload файлы в minio:meshnest-files под models/{model_id}/...
       - upload preview/thumbnail/package zip в minio:meshnest-derived
       - INSERT File rows + ModelTag links
  5. update ImportJob (status=completed, counts)
  6. for each model with STL: kick stl_to_glb
  7. for each model с 3MF без preview: kick extract_3mf_thumbnail

Worker → stl_to_glb(model_id):
  download STL → trimesh.load → export glb → upload в minio:meshnest-derived/glb/{id}.glb
  set viewer_status=glb_ready
```

## Поток данных при просмотре

```
User → /models/flexi-cat
  → frontend GET /api/v1/models/flexi-cat → ModelDetail JSON (с preview_url presigned)
  → frontend GET /api/v1/models/flexi-cat/files → FileItem[] (download_url presigned)
  → user click "3D viewer"
  → frontend GET /api/v1/models/flexi-cat/glb → 302 → presigned MinIO URL
  → @react-three/drei useGLTF(presigned_url) — загружает GLB напрямую с MinIO
  → user click "Download ZIP"
  → 302 → presigned URL на packages/{model_id}.zip в meshnest-derived
```

## Auth flow

1. Admin создаёт invite через `/admin/invites` → копирует ссылку `https://meshnest.tld/invite/{token}`.
2. Получатель открывает ссылку → form (email/password/display_name) → POST `/auth/invite/{token}/redeem`.
3. Backend: валидирует invite, создаёт User, помечает invite как used, выдаёт JWT pair.
4. Frontend: сохраняет access (15 min) и refresh (7 days) в zustand → localStorage.
5. axios interceptor: при 401 → refresh → retry. Если refresh тоже падает → clear → redirect /login.

## Storage layout (MinIO)

```
meshnest-files/
  models/{model_uuid}/print_files/stl/body.stl
                     /print_files/3mf/project.3mf
                     /media/images/preview.jpg
                     /...

meshnest-derived/
  previews/{model_uuid}.{ext}
  thumbnails/{model_uuid}.{ext}
  glb/{model_uuid}.glb
  packages/{model_uuid}.zip

meshnest-imports/
  uploads/{upload_id}/meshnest_import_package.zip
```

Все объекты приватные. Frontend получает presigned URL'ы (TTL 5 мин) от backend через 302 redirect.

## Cloudflare Free лимиты (важно)

- **100 MB на request body** → chunked upload обязателен (90 MB/chunk).
- **Bandwidth не лимитирован** — download'ы пролетают.
- **Free WAF rules** — включить Bot Fight Mode.
- **R2 free tier** — 10 GB storage + 10M reads/мес → отлично для backup'ов.
- **Cloudflare Access free** — до 50 users → можно поверх admin.
