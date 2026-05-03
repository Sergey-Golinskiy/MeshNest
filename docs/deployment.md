# MeshNest deployment — Firebat mini-PC + Cloudflare Tunnel

Целевая среда: домашний mini-PC за NAT, доступ из интернета через Cloudflare Tunnel.

## 1. Подготовка mini-PC

```bash
# 1. ОС: Debian 12 / Ubuntu Server 24.04 LTS (минимальная)
# 2. Включить swap 8-16 GB (для 16 GB RAM это обязательно)
sudo fallocate -l 12G /swapfile
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 3. Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# logout/login
docker compose version  # должно быть ≥ 2.20

# 4. SSH открыт ТОЛЬКО из LAN (на роутере не пробрасывать)
sudo ufw allow from 192.168.0.0/16 to any port 22
sudo ufw enable
```

## 2. Cloudflare Tunnel

1. Cloudflare → Zero Trust → **Networks → Tunnels → Create tunnel**.
2. Имя: `meshnest-home`.
3. Скопировать **Tunnel token** (длинная строка).
4. Добавить **Public hostname**:
   - `meshnest.<your-domain>` → Service: `http://web:80`
   - (опционально) `minio.meshnest.<your-domain>` → Service: `http://minio:9001` (для админки MinIO)
5. Добавить **Cloudflare Access policy** для `minio.*` host (one-time-pin на email админа) — защита админки.

## 3. Деплой

```bash
git clone <repo> meshnest && cd meshnest/deploy
cp .env.example .env

# заполнить:
# - CLOUDFLARE_TUNNEL_TOKEN
# - JWT_SECRET (openssl rand -hex 32)
# - POSTGRES_PASSWORD
# - MINIO_ROOT_PASSWORD
# - MEILI_MASTER_KEY
# - SMTP_* (если invite emails — опц.)
# - PUBLIC_URL / FRONTEND_URL = https://meshnest.your-domain

vim .env

# Build + up
docker compose pull
docker compose build
docker compose up -d

# Подождать пока postgres станет healthy:
docker compose ps

# Создать первого админа
docker compose exec api python -m app.scripts.create_admin you@example.com

# Открыть https://meshnest.your-domain → залогиниться → /admin/invites → создать invite для контрибьютора
```

## 4. Первый импорт (79 GB package)

⚠️ **Через CF Tunnel это будет очень долго** (Free план = 100 MB chunks, домашний upstream обычно 10-50 Mbps → 8-16 часов).

**Рекомендуется:** залить ZIP **локально** через LAN/SCP на mini-PC и запустить импорт минуя CF.

```bash
# на mini-PC через SSH из LAN:
scp meshnest_import_package.zip user@mini-pc-ip:/tmp/
ssh user@mini-pc-ip
cd ~/meshnest
bash deploy/scripts/local-import.sh /tmp/meshnest_import_package.zip

# Логи Celery worker
docker compose -f deploy/docker-compose.yml logs -f worker
```

Импорт ~1k моделей с STL→GLB конверсией займёт ~30-90 мин (зависит от размера STL).

## 5. Backups

```bash
# Daily Postgres dump (cron)
crontab -e
# 0 4 * * *  bash /home/user/meshnest/deploy/scripts/backup-db.sh >> /var/log/meshnest-backup.log 2>&1

# Off-site sync через rclone в Cloudflare R2 (10 GB free)
# 1. rclone config — настроить remote `r2`
# 2. в backup-db.sh указать: export RCLONE_REMOTE=r2:meshnest-backups
```

## 6. Мониторинг

- `docker stats` — RAM/CPU per service
- `docker compose logs -f --tail=100`
- `htop` на хосте — общий load
- (опц.) UptimeRobot ping `https://meshnest.your-domain/healthz` каждые 5 мин

## 7. Обновления

```bash
cd ~/meshnest
git pull
cd deploy
docker compose build api worker web
docker compose up -d
docker compose exec api alembic upgrade head
```

## 8. Известные ограничения

- **CF Free 100 MB request body** — все upload'ы через chunked (90 MB chunks), enforced на стороне `nginx`/`api`/`frontend`.
- **N100 + 16 GB RAM** — впритык. Concurrent тяжёлые задачи (одновременно import + 3-4 STL→GLB) могут swap'ить. Если регулярно — апгрейд RAM до 32 GB или вынос Meilisearch отдельно.
- **500 GB NVMe** — хватит на 2-3k моделей. На 5k+ нужен внешний HDD под MinIO `meshnest-files`.
- **Meilisearch индекс не реализован в MVP1** — поиск пока через DB `LIKE` (slow на 100k+). Добавить во вторую итерацию.
- **Long paths** в organizer-output (>260 символов) дают редкие копи-ошибки → 3 модели потеряли STL во время теста. На самом миграции не критично, но важно знать.
