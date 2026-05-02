# Задание для Claude Code: локальный organizer архива 3D-моделей под MeshNest

## 0. Контекст

У меня есть огромный локальный архив файлов для 3D-печати.

В архиве есть:

- `.stl`
- `.step`
- `.stp`
- `.3mf`
- картинки
- видео
- инструкции
- README
- license-файлы
- папки
- `.zip`
- `.rar`
- `.7z`
- другие архивы

Файлы лежат хаотично:

- часть файлов просто в папках;
- часть в архивах;
- часть архивов содержит одну модель;
- часть архивов содержит много моделей;
- иногда у модели несколько STL;
- иногда есть фото/видео, которые показывают, что печатается;
- иногда есть 3MF-проект;
- иногда есть STEP-файл;
- иногда есть дубли.

Нужно написать локальный инструмент, который пройдет по указанной папке, разберет весь архив, приведет его в красивую структуру и подготовит результат так, чтобы потом его можно было легко загрузить в веб-сервис `MeshNest`.

---

# 1. Главная задача

Создать локальный Python CLI tool:

```text
meshnest-local-organizer
```

Команда должна принимать input-папку с хаотичным архивом и output-папку для чистой библиотеки.

Пример запуска:

```bash
python -m meshnest_organizer scan "D:/My_3D_Archive" --output "D:/MeshNest_Ready_Library"
```

Или:

```bash
meshnest scan "D:/My_3D_Archive" --output "D:/MeshNest_Ready_Library"
```

---

# 2. Важнейшие правила безопасности

1. **Никогда не изменять оригинальные файлы.**
2. **Никогда не удалять оригинальные файлы.**
3. Все операции делать только через копирование в output/staging.
4. Перед распаковкой проверять размер архива и доступность.
5. Ошибки не должны останавливать весь процесс.
6. Если архив не удалось распаковать — записать в report и продолжить.
7. Если файл не удалось обработать — записать warning и продолжить.
8. Все действия писать в лог.

---

# 3. Что должен создать organizer

В output-папке должна быть структура:

```text
MeshNest_Ready_Library/
├── manifest.json
│
├── database/
│   ├── models.json
│   ├── models.csv
│   ├── files.csv
│   ├── tags.csv
│   ├── categories.csv
│   └── library.sqlite
│
├── models/
│   ├── animals/
│   ├── toys/
│   ├── functional/
│   ├── home_decor/
│   ├── cosplay/
│   ├── miniatures/
│   ├── engineering/
│   ├── electronics/
│   ├── seasonal/
│   ├── art/
│   └── uncategorized/
│
├── assets/
│   ├── previews/
│   ├── thumbnails/
│   └── viewer_models/
│
├── packages/
│   └── model_zip/
│
├── staging/
│   ├── extracted/
│   ├── temp/
│   ├── failed_extracts/
│   └── quarantine/
│
├── original_sources/
│   ├── archives/
│   ├── loose_files/
│   └── source_index.json
│
└── reports/
    ├── import_summary.md
    ├── duplicate_files.md
    ├── failed_extracts.md
    ├── failed_conversions.md
    ├── uncategorized_models.md
    └── warnings.jsonl
```

---

# 4. Финальная структура одной модели

Каждая найденная модель должна получить отдельную папку.

Пример:

```text
models/animals/cats/flexi_cat_v001/
├── model.yaml
├── README.md
│
├── source/
│   ├── source_info.json
│   └── original_archive_reference.txt
│
├── print_files/
│   ├── stl/
│   │   ├── body.stl
│   │   ├── head.stl
│   │   └── tail.stl
│   ├── step/
│   │   └── flexi_cat.step
│   ├── 3mf/
│   │   └── bambu_project.3mf
│   └── other/
│       └── notes.txt
│
├── media/
│   ├── images/
│   │   ├── preview_01.jpg
│   │   └── preview_02.png
│   └── videos/
│       └── demo.mp4
│
├── generated/
│   ├── preview.webp
│   ├── preview.png
│   ├── thumbnail.webp
│   ├── viewer_model.glb
│   └── mesh_info.json
│
└── package/
    └── flexi_cat_v001_all_files.zip
```

---

# 5. MeshNest import package

После завершения organizer должен создать готовый архив:

```text
meshnest_import_package.zip
```

Этот архив потом будет загружаться в веб-сервис MeshNest.

Внутри ZIP:

```text
manifest.json
database/
models/
assets/
packages/
reports/
```

`staging/` и `original_sources/` можно не включать в upload package, но оставить локально в output.

---

# 6. manifest.json

Создать в корне output:

```json
{
  "format": "meshnest-import",
  "format_version": "1.0",
  "created_by": "meshnest-local-organizer",
  "created_at": "2026-05-02T12:00:00+03:00",
  "source_root": "D:/My_3D_Archive",
  "output_root": "D:/MeshNest_Ready_Library",
  "models_count": 0,
  "files_count": 0,
  "categories_count": 0,
  "tags_count": 0,
  "archives_found": 0,
  "archives_extracted": 0,
  "archives_failed": 0,
  "duplicates_found": 0,
  "uncategorized_count": 0,
  "database": {
    "models_json": "database/models.json",
    "models_csv": "database/models.csv",
    "files_csv": "database/files.csv",
    "sqlite": "database/library.sqlite"
  },
  "package": {
    "path": "meshnest_import_package.zip",
    "sha256": ""
  }
}
```

Значения должны заполняться реальными данными после обработки.

---

# 7. Поддерживаемые форматы

## 7.1. 3D-файлы

```text
.stl
.step
.stp
.3mf
.obj optional
```

## 7.2. Изображения

```text
.jpg
.jpeg
.png
.webp
.bmp optional
```

## 7.3. Видео

```text
.mp4
.mov
.webm
.avi optional
```

## 7.4. Документы

```text
.txt
.md
.pdf
.docx optional
```

## 7.5. Архивы

```text
.zip
.7z
.rar
.tar
.gz
```

---

# 8. Алгоритм работы

## 8.1. Scan

1. Получить input path.
2. Проверить, что папка существует.
3. Создать output structure.
4. Рекурсивно просканировать все файлы.
5. Для каждого файла определить:
   - extension;
   - size;
   - full path;
   - relative path;
   - file type;
   - sha256;
   - probable role.

## 8.2. Archive detection

Найти архивы:

```text
.zip
.rar
.7z
.tar
.gz
```

Для каждого архива:

1. Записать в source index.
2. Скопировать в `original_sources/archives/`.
3. Попробовать распаковать в `staging/extracted/{archive_slug}/`.
4. Если ошибка — записать в `reports/failed_extracts.md`.
5. Если архив запаролен — записать как `password_protected`.
6. Если битый — записать как `broken_archive`.

## 8.3. Model detection

Правила:

### Правило 1

Один архив = одна модель, если внутри архива есть несколько 3D-файлов и они находятся в одной общей папке.

### Правило 2

Если архив содержит несколько явных подпапок, и каждая подпапка имеет свои STL/3MF/STEP, тогда каждая подпапка = отдельная модель.

### Правило 3

Если папка содержит:

```text
body.stl
head.stl
tail.stl
preview.jpg
readme.txt
```

это одна модель с несколькими print files.

### Правило 4

Если папка содержит:

```text
cat.stl
dog.stl
dragon.stl
```

и нет общего preview/readme, это могут быть 3 модели. Такие случаи лучше пометить `needs-review`.

### Правило 5

Если рядом с STL есть картинки/видео с похожими названиями, привязать их к этой модели.

### Правило 6

Если невозможно уверенно определить структуру, создать модель в `uncategorized` и добавить тег `needs-review`.

---

# 9. Нормализация имен

Нужно привести названия файлов и папок к safe format.

Правила:

1. lowercase;
2. spaces -> `_`;
3. remove special characters;
4. transliterate Cyrillic to Latin;
5. collapse duplicate underscores;
6. max slug length: 80 symbols;
7. if duplicate slug exists, add `_v002`, `_v003`.

Пример:

```text
Кот шарнирный финал (1).stl
```

можно превратить в:

```text
kot_sharnirnyy_final_v001.stl
```

Название карточки можно сделать более красивым:

```text
Kot Sharnirnyy Final
```

или если keyword rules определили cat/flexi:

```text
Flexi Cat
```

---

# 10. Категоризация

Категории определять по:

1. имени архива;
2. имени папки;
3. имени STL/STEP/3MF;
4. README;
5. названиям картинок;
6. вложенным папкам.

Если confidence низкий — отправлять в:

```text
models/uncategorized/
```

и добавлять:

```text
needs-review
```

---

# 11. Категории по умолчанию

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

# 12. Keyword rules

Создать файл:

```text
rules/categories.yaml
```

Пример:

```yaml
animals/cats:
  keywords:
    - cat
    - cats
    - kitty
    - kitten
    - feline
    - kot
    - koshka
    - kit
    - кот
    - кошка
    - кіт

animals/dogs:
  keywords:
    - dog
    - dogs
    - puppy
    - canine
    - sobaka
    - pes
    - собака
    - пес

animals/dragons:
  keywords:
    - dragon
    - dragons
    - drake
    - дракон

animals/dinosaurs:
  keywords:
    - dinosaur
    - dino
    - trex
    - t-rex
    - raptor

toys/flexi:
  keywords:
    - flexi
    - flexible
    - articulated
    - print in place
    - print-in-place
    - print_in_place
    - шарнир
    - шарнирный

functional/holders:
  keywords:
    - holder
    - stand
    - mount
    - bracket
    - держатель
    - подставка
    - кронштейн

functional/boxes:
  keywords:
    - box
    - case
    - container
    - storage
    - organizer
    - коробка
    - кейс
    - органайзер

home_decor/lamps:
  keywords:
    - lamp
    - lampshade
    - light
    - светильник
    - лампа

cosplay/masks:
  keywords:
    - mask
    - helmet
    - cosplay
    - шлем
    - маска

engineering/gears:
  keywords:
    - gear
    - pulley
    - sprocket
    - шестерня
    - зубчатое
```

---

# 13. Теги

Автоматически назначать теги.

## По формату

```text
has-stl
has-step
has-3mf
has-images
has-video
```

## По структуре

```text
multipart
single-part
assembly
source-archive
source-folder
needs-review
duplicate-detected
```

## По типу печати

```text
flexi
articulated
print-in-place
support-required
no-support
bambu-3mf
multicolor
ams
vase-mode
```

## По теме

```text
cat
dog
dragon
dinosaur
holder
box
lamp
mask
gear
miniature
terrain
cosplay
```

---

# 14. model.yaml

Для каждой модели создать `model.yaml`.

Пример:

```yaml
id: "mdl_000001"
slug: "flexi_cat_v001"
title: "Flexi Cat"
original_title: "Flexi_Cat_STL_Pack"
category: "animals/cats"
category_confidence: 0.91
status: "needs_review"
is_reviewed: false

tags:
  - cat
  - animal
  - flexi
  - articulated
  - print-in-place
  - has-stl
  - has-3mf

print_flags:
  is_flexi: true
  is_print_in_place: true
  is_multipart: true
  is_assembly: false
  supports_required: unknown

file_summary:
  stl_count: 3
  step_count: 1
  three_mf_count: 1
  image_count: 2
  video_count: 1
  document_count: 1

paths:
  model_folder: "models/animals/cats/flexi_cat_v001"
  preview_image: "models/animals/cats/flexi_cat_v001/generated/preview.webp"
  thumbnail: "models/animals/cats/flexi_cat_v001/generated/thumbnail.webp"
  viewer_model: "models/animals/cats/flexi_cat_v001/generated/viewer_model.glb"
  package_zip: "packages/model_zip/flexi_cat_v001_all_files.zip"

source:
  source_type: "archive"
  source_name: "Flexi_Cat_STL_Pack.zip"
  source_relative_path: "original_sources/archives/Flexi_Cat_STL_Pack.zip"
  source_hash_sha256: "..."

geometry:
  bbox_mm:
    x: null
    y: null
    z: null
  triangle_count: null
  mesh_count: null

conversion:
  preview_status: "pending"
  viewer_status: "pending"
  errors: []

license:
  detected: false
  license_file: null

created_at: "2026-05-02T12:00:00+03:00"
updated_at: "2026-05-02T12:00:00+03:00"
```

---

# 15. models.csv

Создать:

```text
database/models.csv
```

Колонки:

```csv
id,title,slug,category,category_confidence,tags,model_folder,preview_image,thumbnail,viewer_model,package_zip,stl_count,step_count,three_mf_count,image_count,video_count,document_count,is_flexi,is_print_in_place,is_multipart,has_stl,has_step,has_3mf,has_images,has_video,source_type,source_name,source_hash,status,is_reviewed,notes
```

---

# 16. files.csv

Создать:

```text
database/files.csv
```

Колонки:

```csv
file_id,model_id,file_name,original_file_name,extension,file_type,role,relative_path,size_bytes,sha256,is_primary,status,detected_tags
```

---

# 17. models.json

Создать:

```text
database/models.json
```

Структура:

```json
{
  "format": "meshnest-models",
  "format_version": "1.0",
  "models": [
    {
      "id": "mdl_000001",
      "slug": "flexi_cat_v001",
      "title": "Flexi Cat",
      "category": "animals/cats",
      "tags": ["cat", "flexi", "articulated"],
      "paths": {
        "model_folder": "models/animals/cats/flexi_cat_v001",
        "preview_image": "models/animals/cats/flexi_cat_v001/generated/preview.webp",
        "viewer_model": "models/animals/cats/flexi_cat_v001/generated/viewer_model.glb",
        "package_zip": "packages/model_zip/flexi_cat_v001_all_files.zip"
      }
    }
  ]
}
```

---

# 18. SQLite database

Создать:

```text
database/library.sqlite
```

Минимальные таблицы:

- models
- files
- tags
- model_tags
- categories
- import_logs
- duplicates

---

# 19. Preview generation

В MVP можно сделать так:

## Если есть картинки

1. Найти лучшую картинку:
   - в имени есть `preview`;
   - в имени есть `cover`;
   - в имени есть `render`;
   - самая большая картинка;
   - первое найденное изображение.

2. Скопировать ее в:

```text
generated/preview.webp
generated/thumbnail.webp
assets/previews/{model_id}.webp
assets/thumbnails/{model_id}.webp
```

## Если картинок нет

Создать placeholder:

```text
generated/preview.webp
```

и поставить:

```yaml
preview_status: "placeholder"
```

## Advanced later

Позже добавить render из STL/3MF/STEP.

---

# 20. GLB / viewer model

В MVP не обязательно делать полноценную конвертацию.

Но структура должна быть готова:

```text
generated/viewer_model.glb
assets/viewer_models/{model_id}.glb
```

Если GLB не создан:

```yaml
viewer_status: "pending"
```

или:

```yaml
viewer_status: "conversion_failed"
```

Важно: не ломать импорт, если GLB не сгенерировался.

---

# 21. ZIP package per model

Для каждой модели создать архив:

```text
packages/model_zip/{slug}_all_files.zip
```

Архив должен включать:

- STL;
- STEP/STP;
- 3MF;
- картинки;
- видео;
- README;
- license;
- model.yaml.

Это именно тот архив, который пользователь потом скачает на сайте.

---

# 22. Дубли

Считать SHA256 для каждого файла.

Создать:

```text
reports/duplicate_files.md
```

Если одинаковый SHA256:

```text
Exact duplicate
```

Если похожие имена/размеры:

```text
Possible duplicate
```

В MVP достаточно exact duplicates.

---

# 23. Reports

## import_summary.md

Должен содержать:

```markdown
# MeshNest Local Import Summary

Input folder:
Output folder:
Date:

## Result

- Total files scanned:
- Archives found:
- Archives extracted:
- Archives failed:
- Models detected:
- STL files:
- STEP/STP files:
- 3MF files:
- Images:
- Videos:
- Documents:
- Duplicates:
- Uncategorized:
- Needs review:

## Failed archives

| Archive | Reason |
|---|---|

## Categories

| Category | Count |
|---|---:|

## Warnings

| Type | Count |
|---|---:|
```

## warnings.jsonl

Каждая ошибка отдельной строкой:

```json
{"level":"warning","type":"failed_extract","path":"...","message":"CRC error"}
{"level":"warning","type":"uncategorized","model_id":"mdl_000123","message":"Low category confidence"}
```

---

# 24. CLI interface

Команды:

```bash
meshnest scan INPUT --output OUTPUT
meshnest scan INPUT --output OUTPUT --dry-run
meshnest scan INPUT --output OUTPUT --no-extract
meshnest scan INPUT --output OUTPUT --no-package
meshnest scan INPUT --output OUTPUT --copy-originals
meshnest scan INPUT --output OUTPUT --generate-preview-placeholders
meshnest scan INPUT --output OUTPUT --create-import-package
meshnest validate-package OUTPUT/meshnest_import_package.zip
```

Параметры:

```text
--dry-run
--verbose
--log-level
--max-archive-size
--skip-hidden
--include-original-sources
--create-import-package
--category-rules rules/categories.yaml
--tag-rules rules/tags.yaml
```

---

# 25. Рекомендуемый tech stack

```text
Python 3.11+
Typer
Pydantic
PyYAML
python-slugify
pathlib
hashlib
sqlite3
zipfile
py7zr
rarfile
Pillow
pandas optional
tqdm
```

---

# 26. Project structure

```text
meshnest-local-organizer/
├── pyproject.toml
├── README.md
├── rules/
│   ├── categories.yaml
│   └── tags.yaml
├── meshnest_organizer/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── schemas.py
│   ├── scanner.py
│   ├── archive_extractor.py
│   ├── file_hasher.py
│   ├── normalizer.py
│   ├── model_detector.py
│   ├── classifier.py
│   ├── tagger.py
│   ├── preview_selector.py
│   ├── package_builder.py
│   ├── library_writer.py
│   ├── database.py
│   ├── manifest.py
│   ├── reports.py
│   ├── import_package.py
│   └── logger.py
└── tests/
    ├── test_normalizer.py
    ├── test_classifier.py
    ├── test_model_detector.py
    └── test_manifest.py
```

---

# 27. Основные модули

## scanner.py

- рекурсивный обход;
- определение типа файла;
- первичная статистика.

## archive_extractor.py

- распаковка zip/rar/7z;
- обработка ошибок;
- staging structure.

## file_hasher.py

- SHA256;
- duplicate map.

## normalizer.py

- safe names;
- slug;
- transliteration.

## model_detector.py

- группировка файлов в модели;
- определение multi-model archive;
- определение multipart model.

## classifier.py

- category detection;
- confidence score;
- fallback to uncategorized.

## tagger.py

- auto tags by filename;
- auto tags by file composition.

## preview_selector.py

- выбрать лучшую картинку;
- создать thumbnail;
- создать placeholder.

## package_builder.py

- создать ZIP для каждой модели;
- создать общий `meshnest_import_package.zip`.

## library_writer.py

- создать папки модели;
- скопировать файлы;
- записать model.yaml.

## database.py

- записать SQLite;
- экспорт CSV/JSON.

## reports.py

- import summary;
- duplicate files;
- failed extracts;
- warnings.

## manifest.py

- создать manifest.json;
- посчитать package hash.

---

# 28. Definition of Done

Локальный organizer готов, если:

1. Команда `meshnest scan INPUT --output OUTPUT --create-import-package` работает.
2. Оригинальные файлы не меняются.
3. Архивы распаковываются в staging.
4. Найденные модели раскладываются в `models/category/subcategory/slug`.
5. Для каждой модели создан `model.yaml`.
6. Для каждой модели создан ZIP в `packages/model_zip`.
7. Созданы:
   - `database/models.csv`
   - `database/files.csv`
   - `database/models.json`
   - `database/library.sqlite`
8. Создан `manifest.json`.
9. Создан `meshnest_import_package.zip`.
10. Созданы отчеты.
11. Ошибки не останавливают весь импорт.
12. Непонятные модели попадают в `uncategorized` и получают `needs-review`.
13. Результат можно будет загрузить в MeshNest web service.

---

# 29. Первый MVP, который нужно реализовать

Реализуй сначала только это:

```text
1. scan folder
2. detect files
3. detect archives
4. extract archives
5. calculate SHA256
6. group by archive/folder
7. normalize names
8. categorize by keyword rules
9. copy files to clean model folders
10. create model.yaml
11. create models.csv
12. create files.csv
13. create models.json
14. create package ZIP for each model
15. create manifest.json
16. create import reports
17. create meshnest_import_package.zip
```

Не нужно в первом MVP:

```text
1. AI classification
2. full 3D rendering
3. STEP conversion
4. browser UI
5. server
6. cloud upload
```

---

# 30. Важная логика для будущей загрузки на сервер

Все пути в CSV/JSON/YAML должны быть относительными от корня MeshNest package.

Правильно:

```text
models/animals/cats/flexi_cat_v001/generated/preview.webp
packages/model_zip/flexi_cat_v001_all_files.zip
```

Неправильно:

```text
D:/MeshNest_Ready_Library/models/animals/cats/flexi_cat_v001/generated/preview.webp
```

Это нужно, чтобы пакет можно было загрузить на сервер независимо от локального пути на Windows.

---

# 31. Final command example

После реализации я хочу запускать так:

```bash
meshnest scan "D:/3D_ARCHIVE_RAW" ^
  --output "D:/MeshNest_Ready_Library" ^
  --create-import-package ^
  --generate-preview-placeholders ^
  --verbose
```

На выходе я должен получить:

```text
D:/MeshNest_Ready_Library/
├── manifest.json
├── database/
├── models/
├── assets/
├── packages/
├── reports/
└── meshnest_import_package.zip
```

Этот `meshnest_import_package.zip` потом загружается в веб-сервис MeshNest.

---
