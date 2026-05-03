# MeshNest

Web-сервис для каталогизации, просмотра и хранения 3D-моделей для 3D-печати. Принимает чистые `meshnest_import_package.zip` пакеты от локального organizer'а, показывает галерею с фильтрами, отдаёт 3D-viewer (GLB через Three.js / React Three Fiber) и скачивание per-model или per-format ZIP'ов.

Разворачивается на домашнем mini-PC за NAT через Cloudflare Tunnel (без VPS, без port-forward'инга, без своих SSL-сертификатов).

## Структура

```
MeshNest/
├── backend/            # FastAPI + SQLAlchemy + Celery + Pydantic
├── frontend/           # React + Vite + R3F + Tailwind + shadcn/ui
├── deploy/             # docker-compose.yml + scripts + .env.example
├── nginx/              # reverse-proxy config (HTTP only, TLS на CF edge)
├── docs/               # architecture, api, deployment
├── organize-meshnest.ps1               # локальный organizer (готовит import-package)
├── MeshNest_TZ_Web_Service.md          # ТЗ веб-сервиса
└── MeshNest_Claude_Code_Local_Organizer_Task.md  # ТЗ organizer'а
```

## Стек

- **Backend:** FastAPI 0.115 + SQLAlchemy 2 + Pydantic 2 + Celery 5 + Alembic
- **DB:** PostgreSQL 16
- **Cache / Broker:** Redis 7
- **Object storage:** MinIO (S3-compatible)
- **Search:** Meilisearch v1.10
- **Frontend:** React 18 + Vite 5 + TypeScript + Tailwind + shadcn/ui + R3F + Drei + react-i18next + TanStack Query
- **Edge / TLS:** Cloudflare Tunnel (`cloudflared`) + Cloudflare WAF
- **Deploy:** Docker Compose (single host)

## Quick start (production, на mini-PC)

```bash
# 1. Подготовить env
cp deploy/.env.example deploy/.env
$EDITOR deploy/.env  # CLOUDFLARE_TUNNEL_TOKEN, JWT_SECRET, POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, SMTP_*

# 2. Поднять стек
cd deploy
docker compose pull
docker compose up -d

# 3. Накатить миграции
docker compose exec api alembic upgrade head

# 4. Создать первого админа
docker compose exec api python -m app.scripts.create_admin admin@example.com

# 5. Открыть meshnest.example.com (домен, привязанный к Cloudflare Tunnel)
```

## Local dev

```bash
# Backend
cd backend
uv sync         # или pip install -e .
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
pnpm install
pnpm dev

# Поддерживающие сервисы (postgres, redis, minio, meilisearch)
cd deploy
docker compose -f docker-compose.dev.yml up -d
```

## Документация

- [`docs/architecture.md`](docs/architecture.md) — общая архитектура
- [`docs/api.md`](docs/api.md) — REST API reference
- [`docs/deployment.md`](docs/deployment.md) — production deploy guide

## Лицензия

TBD.
