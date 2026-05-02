# MeshNest — ТЗ для веб-сервиса библиотеки 3D-моделей

## 0. Название сервиса

**Основное название:** `MeshNest`

Смысл: место, где “гнездятся” и аккуратно хранятся 3D-модели, наборы STL/STEP/3MF, фото, видео, превью и metadata.

### Альтернативные названия

- `PrintNest`
- `ModelNest`
- `MeshVault`
- `PrintVault`
- `STLarium`
- `Forge Library`
- `ForgeVault`
- `ModelHive`

Если сервис будет частью будущей экосистемы Forge, можно использовать:

**`Forge MeshNest`** или **`Forge Library`**.

---

# 1. Цель системы

Создать веб-сервис для хранения, просмотра, поиска, категоризации и скачивания 3D-моделей для 3D-печати.

Система должна позволять загружать один архив, несколько архивов или папку с файлами, автоматически анализировать содержимое, создавать карточки моделей, генерировать превью и давать возможность удобно просматривать модель в 3D.

---

# 2. Что является “моделью” в системе

Модель — это не обязательно один STL-файл.

Одна модель может включать:

- один STL;
- несколько STL для одной сборки;
- STEP/STP-файлы;
- 3MF-файлы;
- готовый Bambu/Prusa/Orca project file;
- картинки;
- видео;
- README;
- license-файл;
- PDF-инструкцию;
- дополнительные файлы.

Пример:

```text
Flexi Cat
├── body.stl
├── tail.stl
├── head.stl
├── flexi_cat.step
├── bambu_project.3mf
├── preview.jpg
├── demo.mp4
└── readme.txt
```

В системе это должна быть одна карточка модели.

---

# 3. Основная задача системы

Сервис должен решать 5 задач:

1. **Загрузка**  
   Принимать архивы, папки и наборы файлов.

2. **Обработка**  
   Распаковывать, анализировать, группировать, создавать metadata, генерировать превью.

3. **Каталогизация**  
   Назначать категории, теги, статусы, типы файлов, print-характеристики.

4. **Просмотр**  
   Показывать карточки моделей, фото, видео, список файлов, 3D-viewer.

5. **Скачивание**  
   Давать скачать весь набор модели одним архивом или отдельные типы файлов.

---

# 4. Роли пользователей

Для MVP можно сделать без сложной авторизации.

Но архитектурно заложить роли:

## Admin

- загружает файлы;
- запускает импорт;
- редактирует модели;
- меняет категории и теги;
- удаляет модели;
- объединяет дубли.

## User / Viewer

- смотрит библиотеку;
- фильтрует;
- открывает карточки;
- скачивает файлы.

---

# 5. Главные сущности системы

## 5.1. Model

Карточка модели.

Поля:

```yaml
id: string
slug: string
title: string
original_title: string
description: string
category_id: string
tags: string[]
status: draft | ready | needs_review | hidden | archived
is_reviewed: boolean

has_stl: boolean
has_step: boolean
has_3mf: boolean
has_images: boolean
has_video: boolean
has_readme: boolean
has_license: boolean

is_flexi: boolean
is_print_in_place: boolean
is_multipart: boolean
is_assembly: boolean
is_functional: boolean
is_decorative: boolean

preview_image_url: string
viewer_model_url: string
download_zip_url: string

source_type: upload | local_import | api
source_name: string
source_hash: string

created_at: datetime
updated_at: datetime
imported_at: datetime
```

## 5.2. File

Один физический файл внутри модели.

```yaml
id: string
model_id: string
file_name: string
original_file_name: string
extension: stl | step | stp | 3mf | jpg | png | webp | mp4 | mov | pdf | txt | other
file_type: mesh | cad | project | image | video | document | archive | other
role: print_file | preview_image | gallery_image | video | instruction | license | source
relative_path: string
size_bytes: integer
sha256: string
is_primary: boolean
status: ready | missing | failed | duplicate
created_at: datetime
```

## 5.3. Category

```yaml
id: string
parent_id: string | null
slug: string
name: string
path: string
sort_order: integer
```

Пример:

```text
animals/cats
toys/flexi
functional/holders
home_decor/lamps
engineering/brackets
```

## 5.4. Tag

```yaml
id: string
slug: string
name: string
type: topic | print | technical | source | status
```

Примеры тегов:

```text
cat
dog
dragon
flexi
articulated
print-in-place
multipart
no-support
supports-required
bambu-3mf
functional
decorative
mechanical
needs-review
```

## 5.5. Import Job

Задача импорта.

```yaml
id: string
status: queued | uploading | extracting | scanning | grouping | classifying | generating_previews | packaging | completed | failed | completed_with_warnings
source_type: archive | multiple_archives | folder | local_import_package
source_name: string
uploaded_path: string
models_created: integer
files_processed: integer
warnings_count: integer
errors_count: integer
log_path: string
started_at: datetime
finished_at: datetime
```

---

# 6. Поддерживаемые форматы

## 6.1. 3D / CAD / project

```text
.stl
.step
.stp
.3mf
.obj — optional
.glb — generated web preview
.gltf — optional
```

## 6.2. Images

```text
.jpg
.jpeg
.png
.webp
.bmp — optional
```

## 6.3. Videos

```text
.mp4
.mov
.webm
.avi — optional
```

## 6.4. Documents

```text
.txt
.md
.pdf
.docx — optional
```

## 6.5. Archives

```text
.zip
.7z
.rar
.tar
.gz
```

---

# 7. Категории по умолчанию

```yaml
animals:
  cats:
  dogs:
  dragons:
  dinosaurs:
  birds:
  fish:
  insects:
  other_animals:

toys:
  flexi:
  puzzles:
  figurines:
  mechanical_toys:
  educational:

functional:
  holders:
  boxes:
  organizers:
  hooks:
  tools:
  repair_parts:
  adapters:
  mounts:

home_decor:
  lamps:
  vases:
  wall_art:
  decor_figures:
  planters:

cosplay:
  masks:
  helmets:
  armor:
  props:
  accessories:

miniatures:
  tabletop:
  terrain:
  characters:
  vehicles:
  buildings:

engineering:
  brackets:
  gears:
  mounts:
  mechanisms:
  prototypes:
  fixtures:
  jigs:

electronics:
  enclosures:
  pcb_holders:
  cable_management:
  cases:

seasonal:
  christmas:
  halloween:
  easter:
  other_holidays:

art:
  sculptures:
  busts:
  reliefs:
  abstract:

uncategorized:
```

---

# 8. Карточка модели

Карточка модели в grid-view должна показывать:

- preview image;
- название;
- категорию;
- теги;
- бейджи форматов: STL, STEP, 3MF, IMG, VIDEO;
- количество файлов;
- статус: reviewed / needs review;
- кнопку “Open”;
- кнопку “Download”.

Пример:

```text
------------------------------------------------
| [Preview image]                              |
| Flexi Cat                                    |
| animals / cats                               |
| #cat #flexi #articulated #print-in-place     |
| [STL: 3] [STEP: 1] [3MF: 1] [IMG: 2]         |
| Status: Needs Review                         |
| [Open] [Download ZIP]                        |
------------------------------------------------
```

---

# 9. Страница модели

Страница `/models/{slug}` должна содержать:

## 9.1. Верхний блок

- название;
- категория;
- теги;
- статус;
- кнопка редактирования;
- кнопка скачивания.

## 9.2. Preview / Viewer

- большая картинка preview;
- 3D viewer;
- переключатель:
  - Preview image;
  - 3D model;
  - Gallery;
  - Video.

## 9.3. 3D Viewer

Функции:

- rotate;
- zoom;
- pan;
- reset camera;
- fullscreen;
- wireframe mode;
- bounding box;
- show axes;
- model info.

Предпочтительный формат для viewer:

```text
.glb
```

Система может хранить оригинальные STL/STEP/3MF, но для веба желательно заранее создавать `.glb`.

## 9.4. Files

Список всех файлов:

| File | Type | Size | Role | Action |
|---|---|---:|---|---|
| body.stl | STL | 4.2 MB | print file | Download |
| flexi_cat.step | STEP | 8.1 MB | CAD | Download |
| preview.jpg | Image | 0.8 MB | preview | Open |
| demo.mp4 | Video | 12 MB | demo | Open |

## 9.5. Metadata

Показывать:

- source;
- original name;
- hash;
- imported date;
- print flags;
- geometry info;
- conversion status.

---

# 10. Загрузка файлов

Система должна поддерживать:

1. Upload одного архива.
2. Upload нескольких архивов.
3. Upload папки через browser folder upload.
4. Drag & drop.
5. Импорт готового локального пакета, созданного локальным organizer-скриптом.

---

# 11. Важный режим: импорт локально подготовленной библиотеки

Локальный Claude Code organizer должен подготовить структуру, которую можно загрузить в MeshNest почти без дополнительной обработки.

Система должна уметь принимать:

```text
meshnest_import_package.zip
```

Внутри:

```text
manifest.json
models/
assets/
database/
packages/
reports/
```

При загрузке такого пакета система должна:

1. Прочитать `manifest.json`.
2. Проверить версию формата.
3. Импортировать модели в базу.
4. Скопировать файлы в storage.
5. Привязать preview, GLB, package ZIP.
6. Показать результат импорта.

---

# 12. Формат import package

```text
meshnest_import_package/
├── manifest.json
├── database/
│   ├── models.json
│   ├── models.csv
│   ├── files.csv
│   └── library.sqlite
├── models/
│   └── ...
├── assets/
│   ├── previews/
│   ├── glb/
│   └── thumbnails/
├── packages/
│   └── model_zip/
└── reports/
    ├── import_summary.md
    ├── failed_extracts.md
    └── duplicates.md
```

## 12.1. manifest.json

```json
{
  "format": "meshnest-import",
  "format_version": "1.0",
  "created_at": "2026-05-02T12:00:00+03:00",
  "created_by": "meshnest-local-organizer",
  "source_root": "D:/3D_ARCHIVE",
  "models_count": 3812,
  "files_count": 42381,
  "categories_count": 42,
  "tags_count": 118,
  "database": {
    "models_json": "database/models.json",
    "models_csv": "database/models.csv",
    "files_csv": "database/files.csv",
    "sqlite": "database/library.sqlite"
  },
  "checksums": {
    "models_json_sha256": "...",
    "files_csv_sha256": "..."
  }
}
```

---

# 13. Import pipeline на сервере

```text
1. Receive upload
2. Save to temporary upload storage
3. Create import job
4. Detect upload type
5. If MeshNest import package:
   - validate manifest
   - import metadata
   - copy files
   - create DB records
6. If raw archive/folder:
   - extract
   - scan
   - group
   - classify
   - generate previews
   - package
   - save DB records
7. Generate import report
8. Show result in UI
```

---

# 14. Preview generation

Система должна уметь хранить и показывать:

```text
preview.webp
preview.png
thumbnail.webp
viewer_model.glb
```

## Приоритет preview

1. Если есть реальное фото/рендер модели — использовать его.
2. Если фото нет — генерировать render из STL/3MF/STEP.
3. Если render не получился — показывать placeholder.

## Conversion status

```yaml
preview_status:
  - ready
  - generated
  - source_image_used
  - failed
  - pending

viewer_status:
  - glb_ready
  - stl_direct
  - conversion_failed
  - pending
```

---

# 15. Search & Filters

Фильтры:

- category;
- tags;
- file format;
- has STL;
- has STEP;
- has 3MF;
- has video;
- has image;
- flexi;
- print-in-place;
- multipart;
- reviewed / needs review;
- duplicates;
- import date.

Поиск:

- title;
- original title;
- file name;
- tag;
- category;
- notes.

---

# 16. Review Queue

В review queue попадают модели, если:

- категория не определена;
- нет preview;
- не создался GLB;
- есть конфликт названия;
- есть возможный дубль;
- очень много STL внутри одной модели;
- не удалось распаковать часть файлов;
- не удалось определить, одна это модель или набор;
- низкая уверенность классификации.

---

# 17. Duplicates

Система должна показывать:

## Exact duplicates

Одинаковый SHA256.

## Possible duplicates

Похожие:

- file name;
- file size;
- triangle count;
- bounding box;
- visual preview hash.

Действия:

- merge;
- keep both;
- delete duplicate;
- mark as variant.

---

# 18. API

## Models

```text
GET    /api/models
GET    /api/models/{id}
PATCH  /api/models/{id}
DELETE /api/models/{id}
GET    /api/models/{id}/files
GET    /api/models/{id}/download
GET    /api/models/{id}/download/stl
GET    /api/models/{id}/download/step
GET    /api/models/{id}/download/3mf
POST   /api/models/{id}/mark-reviewed
```

## Uploads / imports

```text
POST   /api/uploads
GET    /api/import-jobs
GET    /api/import-jobs/{id}
POST   /api/import-jobs/{id}/retry
POST   /api/import-package
```

## Categories / tags

```text
GET    /api/categories
POST   /api/categories
PATCH  /api/categories/{id}
DELETE /api/categories/{id}

GET    /api/tags
POST   /api/tags
PATCH  /api/tags/{id}
DELETE /api/tags/{id}
```

## Review / duplicates

```text
GET    /api/review-queue
GET    /api/duplicates
POST   /api/duplicates/merge
POST   /api/duplicates/ignore
```

---

# 19. Database schema для MVP

## models

```sql
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    original_title TEXT,
    description TEXT,
    category_id TEXT,
    status TEXT NOT NULL DEFAULT 'needs_review',
    is_reviewed BOOLEAN DEFAULT false,

    is_flexi BOOLEAN DEFAULT false,
    is_print_in_place BOOLEAN DEFAULT false,
    is_multipart BOOLEAN DEFAULT false,
    is_assembly BOOLEAN DEFAULT false,

    has_stl BOOLEAN DEFAULT false,
    has_step BOOLEAN DEFAULT false,
    has_3mf BOOLEAN DEFAULT false,
    has_images BOOLEAN DEFAULT false,
    has_video BOOLEAN DEFAULT false,

    preview_image_path TEXT,
    viewer_model_path TEXT,
    package_zip_path TEXT,

    source_type TEXT,
    source_name TEXT,
    source_hash TEXT,

    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    imported_at TIMESTAMP
);
```

## files

```sql
CREATE TABLE files (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    original_file_name TEXT,
    extension TEXT,
    file_type TEXT,
    role TEXT,
    relative_path TEXT NOT NULL,
    size_bytes INTEGER,
    sha256 TEXT,
    is_primary BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'ready',

    FOREIGN KEY (model_id) REFERENCES models(id)
);
```

## categories

```sql
CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);
```

## tags

```sql
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT
);
```

## model_tags

```sql
CREATE TABLE model_tags (
    model_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (model_id, tag_id)
);
```

## import_jobs

```sql
CREATE TABLE import_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    source_type TEXT,
    source_name TEXT,
    uploaded_path TEXT,
    log_path TEXT,
    models_created INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    warnings_count INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
```

---

# 20. Рекомендуемый стек

## MVP

```yaml
backend:
  language: Python 3.11+
  framework: FastAPI
  database: SQLite
  orm: SQLAlchemy
  files: local filesystem
  background_jobs: simple local worker

frontend:
  framework: React
  language: TypeScript
  build: Vite
  ui: TailwindCSS
  viewer:
    - Three.js
    - React Three Fiber
    - Drei
```

## Later

```yaml
backend:
  database: PostgreSQL
  jobs: Redis + RQ/Celery
  storage: S3-compatible MinIO
  auth: JWT
  deployment: Docker Compose
```

---

# 21. Storage structure на сервере

```text
storage/
├── uploads/
│   ├── raw/
│   └── processed/
├── models/
│   └── {model_id}/
│       ├── print_files/
│       ├── media/
│       ├── generated/
│       └── package/
├── previews/
├── viewer_models/
├── packages/
└── import_jobs/
    └── {job_id}/
        ├── logs/
        ├── staging/
        └── report.md
```

---

# 22. Frontend pages

```text
/
├── Dashboard
├── Models
├── Model detail
├── Upload
├── Import jobs
├── Review queue
├── Duplicates
├── Categories
├── Tags
└── Settings
```

---

# 23. MVP scope

## MVP 1

- Upload prepared MeshNest import package.
- Import metadata.
- Show model cards.
- Show model detail page.
- Show preview image.
- Show file list.
- Download full ZIP.
- Filter by category/tag.
- Mark model as reviewed.

## MVP 2

- Upload raw archive.
- Server-side extraction.
- Server-side scanning.
- Generate previews.
- Basic 3D viewer.

## MVP 3

- Advanced duplicate detection.
- STEP conversion.
- AI category/tag suggestions.
- Bulk editing.
- User accounts.
- Cloud/S3 storage.

---

# 24. Важное требование совместимости с локальным organizer

Локальный organizer должен создавать результат в формате, который сервер может принять без сложной повторной обработки.

Обязательные файлы для импорта:

```text
manifest.json
database/models.json
database/models.csv
database/files.csv
models/**
packages/**
assets/**
reports/**
```

Сервер должен проверять:

- наличие manifest;
- версию формата;
- целостность файлов;
- пути к preview;
- пути к ZIP;
- количество моделей;
- количество файлов;
- соответствие model_id в `models.json` и `files.csv`.

---

# 25. Definition of Done для системы

Система считается готовой на MVP-уровне, если:

1. Можно загрузить подготовленный MeshNest import package.
2. Система создает записи моделей в базе.
3. Все модели отображаются карточками.
4. У модели открывается детальная страница.
5. На странице видны preview, теги, категория, файлы.
6. Можно скачать полный ZIP модели.
7. Можно отфильтровать модели по категории и тегам.
8. Можно отметить модель как reviewed.
9. Есть страница import jobs.
10. Есть базовый report по импорту.

---
