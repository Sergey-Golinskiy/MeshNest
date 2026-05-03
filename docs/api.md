# MeshNest REST API v1

Base: `https://meshnest.<your-domain>/api/v1`

Все endpoints (кроме отмеченных) требуют `Authorization: Bearer <access_token>`.

OpenAPI / Swagger: в dev — `GET /docs`. В prod — отключено.

## Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | — | `{email, password}` → `{access_token, refresh_token, access_expires_at, user}` |
| POST | `/auth/refresh` | — | `{refresh_token}` → `{access_token, access_expires_at}` |
| POST | `/auth/logout` | — | `{refresh_token}` — revoke |
| GET | `/auth/invite/{token}/info` | — | Проверка invite (valid + role + expires) |
| POST | `/auth/invite/{token}/redeem` | — | `{email, password, display_name?}` → `TokenPair` |
| GET | `/me` | yes | текущий user |

## Library (read)

| Method | Path | Description |
|---|---|---|
| GET | `/models?category=&tag=&has_stl=&has_3mf=&has_step=&is_flexi=&reviewed=&needs_review=&q=&page=&page_size=&sort=` | Listing с фильтрами |
| GET | `/models/{id_or_slug}` | ModelDetail |
| GET | `/models/{id_or_slug}/files` | список файлов с presigned URL |
| GET | `/models/{id_or_slug}/preview` | 302 → preview image |
| GET | `/models/{id_or_slug}/glb` | 302 → GLB |
| GET | `/models/{id_or_slug}/download` | 302 → per-model ZIP |
| GET | `/categories` | tree categories с model_count |
| GET | `/tags` | список tag'ов |

## Library (mutations)

| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/models/{id_or_slug}/mark-reviewed` | admin/contributor | Отметить как ready |

## Upload + import (контрибьютор/админ)

| Method | Path | Description |
|---|---|---|
| POST | `/uploads/init` | `{filename, total_size, expected_sha256?}` → `{upload_id, chunk_size, total_chunks}` |
| PUT | `/uploads/{upload_id}/chunk?n=N` | Тело: binary chunk (≤90 MB) |
| GET | `/uploads/{upload_id}` | Прогресс |
| POST | `/uploads/{upload_id}/complete` | Финализирует — собирает chunks, загружает в MinIO |
| POST | `/import-package` | `{upload_id}` → создаёт ImportJob, kicks Celery |
| GET | `/import-jobs?limit=50` | список последних jobs |
| GET | `/import-jobs/{id}` | детальный статус |

## Admin

| Method | Path | Description |
|---|---|---|
| GET | `/admin/invites?include_used=false` | список invites |
| POST | `/admin/invites` | `{role, expires_in_days, email_hint?}` → `InviteOut` (включая `invite_url`) |
| DELETE | `/admin/invites/{id}` | удалить неиспользованный invite |
| GET | `/admin/users` | список users |
| PATCH | `/admin/users/{id}` | `{role?, is_active?}` |

## Status / health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | — | Liveness |
| GET | `/readyz` | — | + DB ping |
