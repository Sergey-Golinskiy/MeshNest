<#
.SYNOPSIS
    MeshNest local organizer — однократный прогон каталогизации 3D-архива.

.DESCRIPTION
    Принимает на вход хаотичную папку с 3D-моделями, архивами, фото/видео и
    производит чистый MeshNest import package v1.0 на выходе.

    Pipeline (10 фаз):
      0. Pre-flight (валидация, скелет директорий)
      1. Scan input + junk filter
      2. SHA256 + dedup index
      3. Архивы: копия в original_sources + распаковка в staging
      4. Re-scan staging + final FileEntry pool
      5. Группировка файлов в model units
      6. Normalize + categorize + tag + preview selection
      7. Materialize models on disk + per-model ZIP
      8. Aggregates (CSV/JSON)
      9. Reports + manifest
     10. Build top-level meshnest_import_package.zip

.PARAMETER InputPath
    Путь к хаотичной входной папке.

.PARAMETER OutputPath
    Путь к выходной чистой библиотеке (будет создана).

.PARAMETER SevenZipPath
    Путь к 7z.exe.

.PARAMETER Resume
    Если установлен — пропускает Phase 1-2 (если есть .scan_index.jsonl)
    и Phase 3 (если есть .extract_log.jsonl).

.EXAMPLE
    .\organize-meshnest.ps1
    .\organize-meshnest.ps1 -Resume
#>
[CmdletBinding()]
param(
    [string]$InputPath = "C:\Users\sngol\Downloads\MODELS",
    [string]$OutputPath = "D:\MeshNest_Ready_Library",
    [string]$SevenZipPath = "C:\Program Files\7-Zip\7z.exe",
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

#region Console encoding
chcp 65001 > $null 2>&1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
#endregion

#region Constants
$Script:VERSION    = "1.0.0"
$Script:RUN_ID     = (Get-Date -Format "yyyyMMdd_HHmmss")
$Script:STARTED_AT = (Get-Date)
$Script:SevenZipPath = $SevenZipPath

# Расширения
$Script:EXT_3D_PRINTABLE = @('.stl', '.3mf', '.step', '.stp', '.obj')
$Script:EXT_IMAGE        = @('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
$Script:EXT_VIDEO        = @('.mp4', '.mov', '.webm', '.avi', '.mkv')
$Script:EXT_DOC          = @('.txt', '.md', '.pdf', '.docx', '.rtf')
$Script:EXT_OTHER_3D     = @('.fbx', '.max', '.gcode', '.bgcode', '.gltf', '.glb', '.mtl')
$Script:EXT_ARCHIVE      = @('.zip', '.rar', '.7z', '.tar', '.gz', '.tgz')
# 3MF/docx/glb — это zip-контейнеры, но НЕ архивы в нашем смысле. Whitelist by extension.
$Script:EXT_ZIPLIKE_NONARCHIVE = @('.3mf', '.docx', '.glb', '.xlsx', '.pptx', '.epub', '.jar')

# Пороги
$Script:HASH_LARGE_THRESHOLD       = 100MB
$Script:CATEGORY_CONFIDENCE_MIN    = 0.30
$Script:MULTI_MODEL_SUSPECT_THRESH = 20
$Script:READ_BUFFER_SIZE           = 1MB
$Script:SLUG_MAX_LEN               = 80
$Script:IMPORT_PKG_WARN_SIZE       = 4GB
#endregion

#region Cyrillic transliteration map
$Script:CyrMap = @{
    'а'='a'; 'б'='b'; 'в'='v'; 'г'='g'; 'д'='d'; 'е'='e'; 'ё'='yo'
    'ж'='zh'; 'з'='z'; 'и'='i'; 'й'='y'; 'к'='k'; 'л'='l'; 'м'='m'
    'н'='n'; 'о'='o'; 'п'='p'; 'р'='r'; 'с'='s'; 'т'='t'; 'у'='u'
    'ф'='f'; 'х'='kh'; 'ц'='ts'; 'ч'='ch'; 'ш'='sh'; 'щ'='shch'
    'ъ'=''; 'ы'='y'; 'ь'=''; 'э'='e'; 'ю'='yu'; 'я'='ya'
    # Украинские
    'і'='i'; 'ї'='yi'; 'є'='ye'; 'ґ'='g'
}
#endregion

#region Category keyword rules (вес: folder=3, filename=2, readme=1)
$Script:CategoryKeywords = [ordered]@{
    'animals/cats' = @('cat','cats','kitty','kitten','feline','kot','koshka','kotenok')
    'animals/dogs' = @('dog','dogs','puppy','doggy','canine','dachshund','sobaka','pyos','pes')
    'animals/dragons' = @('dragon','dragons','drake','wyvern','drakon','toothless','night-fury','nightfury')
    'animals/dinosaurs' = @('dinosaur','dino','trex','t-rex','raptor','ankylosaurus','spinosaurus','velociraptor','brontosaurus','dodo')
    'animals/birds' = @('bird','birds','eagle','owl','parrot','penguin','duck','crow','raven','hawk','falcon','flamingo','swan','pigeon','sparrow','robin','chicken')
    'animals/fish' = @('fish','shark','whale','dolphin','octopus','squid','beluga','turtle','sea-turtle','seaturtle')
    'animals/insects' = @('insect','bug','ant','bee','spider','scorpion','beetle','butterfly','mantis','wasp')
    'animals/other_animals' = @('animal','fox','bear','rabbit','frog','lizard','snake','cobra','monkey','deer','horse','lion','tiger','wolf','pig','cow','sheep','mouse','rat','crab','lobster','armadillo','hedgehog','panda','koala','kangaroo','pangolin','platypus','sloth','capybara','beaver','octo','minion','wiggly','seal','otter')

    'toys/flexi' = @('flexi','flexible','articulated','print-in-place','print_in_place','printinplace','sharnir','sharnirnyy','wiggly','articulado')
    'toys/puzzles' = @('puzzle','puzzles')
    'toys/figurines' = @('figurine','figure','figurines','figures','statuette')
    'toys/mechanical_toys' = @('fidget','spinner','mechanical-toy','wind-up','wind_up')
    'toys/educational' = @('educational','learning')

    'functional/holders' = @('holder','stand','phone-holder','tablet-stand','derzhatel','podstavka')
    'functional/boxes' = @('box','case','container','storage','koroba','keys-box','keys_box')
    'functional/organizers' = @('organizer','tray','divider')
    'functional/hooks' = @('hook','hooks','hanger')
    'functional/tools' = @('tool','wrench','spanner','screwdriver')
    'functional/repair_parts' = @('repair','spare-part','replacement')
    'functional/adapters' = @('adapter','adaptor')
    'functional/mounts' = @('mount','wall-mount','wall_mount','bracket','kronshteyn')

    'home_decor/lamps' = @('lamp','lampshade','svetilnik','lampa')
    'home_decor/vases' = @('vase','vases','vaza')
    'home_decor/wall_art' = @('wall-art','wall_art','plaque')
    'home_decor/decor_figures' = @('decor','decoration','sculpture-decor')
    'home_decor/planters' = @('planter','planters','flowerpot','pot-plant')

    'cosplay/masks' = @('mask','maska','cosplay-mask')
    'cosplay/helmets' = @('helmet','shlem')
    'cosplay/armor' = @('armor','armour','pauldron','gauntlet')
    'cosplay/props' = @('prop','cosplay-prop','sword','shield')
    'cosplay/accessories' = @('cosplay','accessory')

    'miniatures/tabletop' = @('miniature','tabletop','dnd','d-and-d','28mm','32mm')
    'miniatures/terrain' = @('terrain','scenery','dungeon-tile','dungeon_tile')
    'miniatures/characters' = @('character','pokemon','pikachu','dratini','weedle','groot','leon','minion','unicorn-bee','unicorn','dukes-of-hazzard')
    'miniatures/vehicles' = @('vehicle','car','truck','tank','plane','helicopter','ship','shuttle','space-shuttle','dodge','charger','mystery-machine','scooby')
    'miniatures/buildings' = @('building','house','castle','tower')

    'engineering/brackets' = @('bracket','brackets','l-bracket')
    'engineering/gears' = @('gear','gears','pulley','sprocket','shesternya','zubchatoe')
    'engineering/mechanisms' = @('mechanism','mechanical','linkage','cam','excavator')
    'engineering/prototypes' = @('prototype','proto')
    'engineering/fixtures' = @('fixture','fixtures')
    'engineering/jigs' = @('jig','jigs')

    'electronics/enclosures' = @('enclosure','project-box','project_box')
    'electronics/pcb_holders' = @('pcb','pcb-holder')
    'electronics/cable_management' = @('cable','cable-management','cable_management','cable-clip')
    'electronics/cases' = @('arduino-case','raspberry-case','rpi-case','electronics-case')

    'seasonal/christmas' = @('christmas','xmas','santa','snowman','snowflake','reindeer','rozhdestvo','candy-cane','candy_cane')
    'seasonal/halloween' = @('halloween','pumpkin','jack-o-lantern','ghost','witch')
    'seasonal/easter' = @('easter','pasha')
    'seasonal/other_holidays' = @('valentine','birthday','holiday','egypt','anubis','pharaoh')

    'art/sculptures' = @('sculpture','sculpting','statue')
    'art/busts' = @('bust','busts')
    'art/reliefs' = @('relief','bas-relief')
    'art/abstract' = @('abstract','abstract-art')
}

# Print/style auto-tags (по keyword)
$Script:PrintFlagKeywords = [ordered]@{
    'flexi'           = @('flexi','flexible')
    'articulated'     = @('articulated','sharnir','sharnirnyy','articulado')
    'print-in-place'  = @('print-in-place','print_in_place','printinplace')
    'bambu-3mf'       = @('bambu')
    'multicolor'      = @('multicolor','multi-color','multi_color','ams')
    'no-support'      = @('no-support','no_support','support-free','support_free')
}

# Theme tags (берутся из category-match, плюс прямой keyword scan)
$Script:ThemeKeywords = [ordered]@{
    'cat'      = @('cat','cats','kitty','kot')
    'dog'      = @('dog','dogs','puppy','dachshund','sobaka')
    'dragon'   = @('dragon','wyvern','drake','toothless')
    'dinosaur' = @('dinosaur','dino','trex','raptor')
    'bird'     = @('bird','eagle','owl','raven','penguin','flamingo')
    'fish'     = @('fish','shark','whale','dolphin','turtle','beluga')
    'mask'     = @('mask','maska')
    'gear'     = @('gear','shesternya')
    'lamp'     = @('lamp','svetilnik')
    'box'      = @('box','case','container')
    'holder'   = @('holder','stand')
    'pokemon'  = @('pokemon','pikachu','dratini','weedle')
    'unicorn'  = @('unicorn')
}

# Топ-уровневые категории (создаются как пустые папки заранее)
$Script:TopCategories = @(
    'animals','toys','functional','home_decor','cosplay',
    'miniatures','engineering','electronics','seasonal','art','uncategorized'
)
#endregion

#region Logging
$Script:LogPath      = $null
$Script:WarningsPath = $null

function Write-Log {
    param([string]$Level, [string]$Message)
    $ts = (Get-Date -Format "HH:mm:ss")
    $line = "[$ts][$Level] $Message"
    Write-Host $line
    if ($Script:LogPath) {
        $enc = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::AppendAllText($Script:LogPath, $line + "`r`n", $enc)
    }
}
function Write-Info { param([string]$Msg) Write-Log -Level "INFO" -Message $Msg }
function Write-Warn { param([string]$Msg) Write-Log -Level "WARN" -Message $Msg }
function Write-Err  { param([string]$Msg) Write-Log -Level "ERROR" -Message $Msg }
function Write-Step { param([string]$Msg) Write-Host ""; Write-Log -Level "STEP" -Message ("=== " + $Msg + " ===") }

function Add-Warning {
    param([hashtable]$Entry)
    if (-not $Script:WarningsPath) { return }
    if (-not $Entry.ContainsKey('timestamp')) { $Entry['timestamp'] = (Get-Date -Format "o") }
    $json = ($Entry | ConvertTo-Json -Compress -Depth 5)
    $enc = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::AppendAllText($Script:WarningsPath, $json + "`n", $enc)
}
#endregion

#region Filesystem helpers (long-path safe)
function New-DirIfNeeded {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        [System.IO.Directory]::CreateDirectory($Path) | Out-Null
    }
}

function Copy-FileSafe {
    param([string]$Source, [string]$Destination, [switch]$Overwrite)
    $destDir = [System.IO.Path]::GetDirectoryName($Destination)
    if ($destDir) { New-DirIfNeeded $destDir }
    [System.IO.File]::Copy($Source, $Destination, [bool]$Overwrite)
}

function Get-RelativePath {
    param([string]$BasePath, [string]$TargetPath)
    $base = ([string]$BasePath).TrimEnd('\','/') + '\'
    $baseUri = New-Object System.Uri($base)
    $targetUri = New-Object System.Uri($TargetPath)
    $rel = [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString())
    return $rel.Replace('\','/').TrimEnd('/')
}

function Write-Utf8Json {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Object, [int]$Depth = 10, [switch]$Bom)
    $json = $Object | ConvertTo-Json -Depth $Depth
    if ($Bom) { $enc = [System.Text.Encoding]::UTF8 } else { $enc = New-Object System.Text.UTF8Encoding $false }
    [System.IO.File]::WriteAllText($Path, $json, $enc)
}

function Write-Utf8Text {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Content, [switch]$Bom)
    if ($Bom) { $enc = [System.Text.Encoding]::UTF8 } else { $enc = New-Object System.Text.UTF8Encoding $false }
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function Add-Utf8Line {
    param([string]$Path, [string]$Line, [switch]$Bom)
    if ($Bom) { $enc = [System.Text.Encoding]::UTF8 } else { $enc = New-Object System.Text.UTF8Encoding $false }
    [System.IO.File]::AppendAllText($Path, $Line + "`n", $enc)
}

function Get-DirSizeBytes {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    return (Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
}
#endregion

#region SHA256 (fast streaming)
function Get-FileSha256Fast {
    param([string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
            $hash = $sha.ComputeHash($stream)
            return ([System.BitConverter]::ToString($hash) -replace '-','').ToLowerInvariant()
        } finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}
#endregion

#region Slug / normalization / title
function Convert-Cyrillic {
    param([string]$Text)
    if (-not $Text) { return '' }
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $Text.ToCharArray()) {
        $key = ([string]$ch).ToLowerInvariant()
        if ($Script:CyrMap.ContainsKey($key)) {
            [void]$sb.Append($Script:CyrMap[$key])
        } else {
            [void]$sb.Append($ch)
        }
    }
    return $sb.ToString()
}

function Get-Slug {
    param([string]$Text)
    if (-not $Text) { return 'untitled' }
    $s = Convert-Cyrillic $Text
    $s = $s.ToLowerInvariant()
    # Удалить технические суффиксы вида YYYYMMDD-NN-hashish
    $s = [regex]::Replace($s, '\d{8,}[-_][a-z0-9]{2,}([-_][a-z0-9]+)*', '')
    # Убрать (1), (2)
    $s = [regex]::Replace($s, '\s*\(\d+\)\s*', ' ')
    # Всё кроме a-z 0-9 → _
    $s = [regex]::Replace($s, '[^a-z0-9]+', '_')
    $s = [regex]::Replace($s, '_+', '_').Trim('_')
    if ($s.Length -gt $Script:SLUG_MAX_LEN) {
        $s = $s.Substring(0, $Script:SLUG_MAX_LEN).TrimEnd('_')
    }
    if (-not $s) { return 'untitled' }
    return $s
}

function Get-CleanTitle {
    param([string]$Text)
    if (-not $Text) { return 'Untitled' }
    $t = $Text
    # Удалить расширение если сохранилось
    $t = [regex]::Replace($t, '\.(stl|3mf|step|stp|obj|zip|rar|7z)$', '', 'IgnoreCase')
    # Технические суффиксы
    $t = [regex]::Replace($t, '\d{8,}[-_][a-z0-9]{2,}([-_][a-z0-9]+)*', '')
    # (1), (2), _stls, _files
    $t = [regex]::Replace($t, '\s*\(\d+\)\s*', ' ')
    $t = [regex]::Replace($t, '_(stls|files|stl|pack)$', '', 'IgnoreCase')
    # Подчёркивания и + на пробелы
    $t = [regex]::Replace($t, '[_\+]+', ' ')
    $t = [regex]::Replace($t, '\s+', ' ').Trim()
    if (-not $t) { return 'Untitled' }
    $ti = (Get-Culture).TextInfo
    return $ti.ToTitleCase($t.ToLowerInvariant())
}

function Get-UniqueSlug {
    param([string]$BaseSlug, [hashtable]$UsedSet)
    if (-not $UsedSet.ContainsKey($BaseSlug)) {
        $UsedSet[$BaseSlug] = $true
        return $BaseSlug
    }
    for ($i = 2; $i -lt 1000; $i++) {
        $candidate = "{0}_v{1:D3}" -f $BaseSlug, $i
        if (-not $UsedSet.ContainsKey($candidate)) {
            $UsedSet[$candidate] = $true
            return $candidate
        }
    }
    throw "Cannot resolve slug collision for '$BaseSlug' (>999 versions)"
}
#endregion

#region 7-Zip wrappers (через call operator — корректно квотит пробелы)
function Invoke-SevenZipExtract {
    param([string]$ArchivePath, [string]$DestPath)
    New-DirIfNeeded $DestPath
    $output = & $Script:SevenZipPath x -bb0 -bd -y "-o$DestPath" "$ArchivePath" 2>&1
    $exit = $LASTEXITCODE
    $combined = ($output | Out-String)
    return [pscustomobject]@{ ExitCode = $exit; Stdout = $combined; Stderr = '' }
}

function Invoke-SevenZipAdd {
    param([string]$ZipPath, [string]$SourceDir, [string[]]$ExcludePatterns)
    $glob = (Join-Path $SourceDir '*')
    $extraArgs = @()
    if ($ExcludePatterns) {
        foreach ($p in $ExcludePatterns) { $extraArgs += "-xr!$p" }
    }
    $output = & $Script:SevenZipPath a -tzip -mcu=on -bb0 -bd -y "$ZipPath" "$glob" @extraArgs 2>&1
    $exit = $LASTEXITCODE
    return [pscustomobject]@{ ExitCode = $exit; Stdout = ($output | Out-String) }
}
#endregion

#region Junk detection
function Test-IsJunkPath {
    param([string]$Path)
    $name = [System.IO.Path]::GetFileName($Path).ToLowerInvariant()
    if ($name -in @('.ds_store','thumbs.db','desktop.ini')) { return $true }
    if ($name.StartsWith('._')) { return $true }
    if ($name.EndsWith('.tmp')) { return $true }
    if ($Path -match '[\\/]__MACOSX[\\/]') { return $true }
    return $false
}
#endregion

#region File classification (extension → bucket)
function Get-FileBucket {
    param([string]$Path)
    $ext = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
    $name = [System.IO.Path]::GetFileNameWithoutExtension($Path).ToLowerInvariant()
    if ($ext -eq '.stl') { return 'stl' }
    if ($ext -in @('.step','.stp')) { return 'step' }
    if ($ext -eq '.3mf') { return '3mf' }
    if ($ext -in $Script:EXT_OTHER_3D) { return 'other_3d' }
    if ($ext -in $Script:EXT_IMAGE) { return 'image' }
    if ($ext -in $Script:EXT_VIDEO) { return 'video' }
    if ($ext -in $Script:EXT_DOC) { return 'doc' }
    if ($ext -in $Script:EXT_ARCHIVE -and $ext -notin $Script:EXT_ZIPLIKE_NONARCHIVE) { return 'archive' }
    if ($name -match '^(readme|license|licence|notice|copyright)$') { return 'doc' }
    return 'other'
}
#endregion

#region Phase 0 — Pre-flight
function Invoke-Phase0PreFlight {
    Write-Step "Phase 0: Pre-flight"

    if (-not (Test-Path -LiteralPath $InputPath)) {
        throw "Input path not found: $InputPath"
    }
    if (-not (Test-Path -LiteralPath $Script:SevenZipPath)) {
        throw "7-Zip not found at: $Script:SevenZipPath"
    }

    # Свободное место на output drive
    $outDrive = [System.IO.Path]::GetPathRoot($OutputPath).TrimEnd('\') -replace ':',''
    $drvInfo = Get-PSDrive -Name $outDrive -ErrorAction SilentlyContinue
    if (-not $drvInfo) { throw "Cannot inspect drive '$outDrive':" }
    $freeGB = [math]::Round($drvInfo.Free / 1GB, 1)
    $inputSizeGB = [math]::Round((Get-DirSizeBytes $InputPath) / 1GB, 1)
    Write-Info "Input size: $inputSizeGB GB. Free on $($outDrive):: $freeGB GB."
    if ($drvInfo.Free -lt ($inputSizeGB * 1GB * 2)) {
        Write-Warn "Free space is less than 2x input. May fail mid-run."
    }

    # Скелет директорий
    Write-Info "Creating output skeleton at $OutputPath"
    New-DirIfNeeded $OutputPath
    foreach ($sub in @(
        'database', 'staging', 'staging\extracted', 'staging\temp', 'staging\failed_extracts', 'staging\quarantine',
        'original_sources', 'original_sources\archives', 'original_sources\loose_files',
        'reports', 'assets', 'assets\previews', 'assets\thumbnails', 'assets\viewer_models',
        'packages', 'packages\model_zip', 'logs'
    )) {
        New-DirIfNeeded (Join-Path $OutputPath $sub)
    }
    # Топ-уровневые категории как пустые папки
    foreach ($cat in $Script:TopCategories) {
        New-DirIfNeeded (Join-Path $OutputPath "models\$cat")
    }

    # Логи
    $Script:LogPath      = Join-Path $OutputPath "logs\organizer_$($Script:RUN_ID).log"
    $Script:WarningsPath = Join-Path $OutputPath "reports\warnings.jsonl"
    Write-Utf8Text -Path (Join-Path $OutputPath "staging\.run_id.txt") -Content "run_id=$($Script:RUN_ID)`nstarted_at=$($Script:STARTED_AT.ToString('o'))`ninput=$InputPath`noutput=$OutputPath"
    Write-Info "Run ID: $($Script:RUN_ID)"
    Write-Info "Log: $($Script:LogPath)"
}
#endregion

#region Phase 1 — Scan input + junk filter
function Invoke-Phase1Scan {
    Write-Step "Phase 1: Scan input + junk filter"

    $scanIndexPath = Join-Path $OutputPath "staging\.scan_index.jsonl"

    if ($Resume -and (Test-Path -LiteralPath $scanIndexPath)) {
        Write-Info "Resume: loading scan index from staging\.scan_index.jsonl"
        $list = New-Object System.Collections.ArrayList
        $reader = [System.IO.File]::OpenText($scanIndexPath)
        try {
            while ($null -ne ($line = $reader.ReadLine())) {
                if (-not $line.Trim()) { continue }
                [void]$list.Add(($line | ConvertFrom-Json))
            }
        } finally { $reader.Dispose() }
        $Script:Files = $list
        Write-Info "Loaded $($Script:Files.Count) cached entries."
        return
    }

    Write-Info "Scanning $InputPath ..."
    $allItems = Get-ChildItem -LiteralPath $InputPath -Recurse -File -Force -ErrorAction SilentlyContinue
    Write-Info "Found $($allItems.Count) raw files. Filtering junk..."

    $entries = New-Object System.Collections.ArrayList
    $junkCount = 0
    $inputPathTrim = $InputPath.TrimEnd('\','/')
    foreach ($f in $allItems) {
        if (Test-IsJunkPath $f.FullName) { $junkCount++; continue }
        $rel = $f.FullName.Substring($inputPathTrim.Length).TrimStart('\','/').Replace('\','/')
        $bucket = Get-FileBucket $f.FullName
        [void]$entries.Add([pscustomobject]@{
            abs_path   = $f.FullName
            rel_path   = $rel
            file_name  = $f.Name
            size       = [int64]$f.Length
            ext        = $f.Extension.ToLowerInvariant()
            bucket     = $bucket
            mtime      = $f.LastWriteTime.ToString('o')
            sha256     = $null
            provenance = 'input'
        })
    }
    $Script:Files = $entries
    Write-Info "Kept $($Script:Files.Count) files. Skipped $junkCount junk items."

    $Script:Files | Group-Object bucket | Sort-Object Count -Descending | ForEach-Object {
        $sumMB = [math]::Round((($_.Group | Measure-Object size -Sum).Sum) / 1MB, 1)
        Write-Info ("  {0,-10} count={1,5}  size={2,9} MB" -f $_.Name, $_.Count, $sumMB)
    }
}
#endregion

#region Phase 2 — SHA256 + dedup index
function Invoke-Phase2Hash {
    Write-Step "Phase 2: SHA256 + dedup index"

    $scanIndexPath = Join-Path $OutputPath "staging\.scan_index.jsonl"

    if ($Resume -and $Script:Files.Count -gt 0 -and $Script:Files[0].sha256) {
        Write-Info "Resume: scan index already has hashes."
        # Все равно построим dedup map
        $Script:DedupMap = @{}
        foreach ($f in $Script:Files) {
            if (-not $f.sha256) { continue }
            if (-not $Script:DedupMap.ContainsKey($f.sha256)) {
                $Script:DedupMap[$f.sha256] = New-Object System.Collections.ArrayList
            }
            [void]$Script:DedupMap[$f.sha256].Add($f.abs_path)
        }
        return
    }

    $total = $Script:Files.Count
    $hashedSmall   = 0
    $hashedArchive = 0
    $deferred      = 0
    $failed        = 0
    $hashedBytes   = [int64]0
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    for ($i = 0; $i -lt $total; $i++) {
        $f = $Script:Files[$i]
        $isArchive = ($f.bucket -eq 'archive')
        $isLarge   = ($f.size -ge $Script:HASH_LARGE_THRESHOLD)

        if ($isArchive -or -not $isLarge) {
            try {
                $f.sha256 = Get-FileSha256Fast -Path $f.abs_path
                if ($isArchive) { $hashedArchive++ } else { $hashedSmall++ }
                $hashedBytes += $f.size
            } catch {
                $failed++
                Write-Warn "Hash failed: $($f.abs_path) — $_"
                Add-Warning @{ level='warning'; type='hash_failed'; path=$f.abs_path; message=$_.ToString() }
            }
        } else {
            $deferred++
        }

        if ($i -gt 0 -and ($i % 200 -eq 0)) {
            $pct = [math]::Round(($i / $total) * 100, 1)
            $mbps = if ($sw.Elapsed.TotalSeconds -gt 0.5) {
                [math]::Round(($hashedBytes / 1MB) / $sw.Elapsed.TotalSeconds, 1)
            } else { 0 }
            Write-Info ("  progress {0}/{1} ({2}%) — {3} MB/s" -f $i, $total, $pct, $mbps)
        }
    }
    $sw.Stop()
    Write-Info ("Hashed: {0} small + {1} archives. Deferred large: {2}. Failed: {3}. Time: {4}" -f `
        $hashedSmall, $hashedArchive, $deferred, $failed, $sw.Elapsed.ToString('mm\:ss'))

    # Запись scan_index.jsonl
    Write-Info "Writing scan index → staging\.scan_index.jsonl"
    $enc = New-Object System.Text.UTF8Encoding $false
    $writer = New-Object System.IO.StreamWriter($scanIndexPath, $false, $enc)
    try {
        foreach ($f in $Script:Files) {
            $writer.WriteLine(($f | ConvertTo-Json -Compress -Depth 5))
        }
    } finally { $writer.Dispose() }

    # Dedup map
    $Script:DedupMap = @{}
    foreach ($f in $Script:Files) {
        if (-not $f.sha256) { continue }
        if (-not $Script:DedupMap.ContainsKey($f.sha256)) {
            $Script:DedupMap[$f.sha256] = New-Object System.Collections.ArrayList
        }
        [void]$Script:DedupMap[$f.sha256].Add($f.abs_path)
    }
    $dupGroups = @($Script:DedupMap.Values | Where-Object { $_.Count -gt 1 }).Count
    Write-Info "Exact duplicate groups (by SHA): $dupGroups"
}
#endregion

#region Phase 3 — Archives: copy + extract
function Invoke-Phase3Extract {
    Write-Step "Phase 3: Archives — copy + extract"

    $extractLogPath = Join-Path $OutputPath "staging\.extract_log.jsonl"
    $sourceIndexPath = Join-Path $OutputPath "original_sources\source_index.json"
    $archivesDir   = Join-Path $OutputPath "original_sources\archives"
    $extractedRoot = Join-Path $OutputPath "staging\extracted"

    # Resume: если log уже есть — читаем и проверяем валидность
    if ($Resume -and (Test-Path -LiteralPath $extractLogPath)) {
        Write-Info "Resume: loading extract log from staging\.extract_log.jsonl"
        $list = New-Object System.Collections.ArrayList
        $reader = [System.IO.File]::OpenText($extractLogPath)
        try {
            while ($null -ne ($line = $reader.ReadLine())) {
                if (-not $line.Trim()) { continue }
                [void]$list.Add(($line | ConvertFrom-Json))
            }
        } finally { $reader.Dispose() }

        $totalCached = $list.Count
        $extractedOk = @($list | Where-Object { $_.status -eq 'extracted' }).Count
        $failedCount = @($list | Where-Object { $_.status -in @('extract_failed','broken_archive') }).Count
        $okRatio = if ($totalCached -gt 0) { $extractedOk / $totalCached } else { 0 }
        # Также проверим что физически extracted_path существует
        $physExists = 0
        foreach ($e in $list) {
            if ($e.status -eq 'extracted' -and $e.extract_path -and (Test-Path -LiteralPath $e.extract_path)) {
                $physExists++
            }
        }
        if ($okRatio -lt 0.5 -or $physExists -lt $extractedOk * 0.8) {
            Write-Warn "Cached extract log looks stale or invalid (ok=$extractedOk, failed=$failedCount, physExists=$physExists). Re-running Phase 3."
        } else {
            $Script:Archives = $list
            Write-Info "Loaded $($Script:Archives.Count) cached archive entries (extracted=$extractedOk, failed=$failedCount)."
            return
        }
    }

    # Очистка предыдущих неудачных результатов
    if (Test-Path -LiteralPath $extractedRoot) {
        $existing = Get-ChildItem -LiteralPath $extractedRoot -Directory -ErrorAction SilentlyContinue
        if ($existing.Count -gt 0) {
            Write-Info "Cleaning $($existing.Count) previous extraction dirs from staging/extracted/ ..."
            foreach ($d in $existing) {
                try { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction Stop } catch { Write-Warn "Could not remove $($d.FullName): $_" }
            }
        }
    }
    foreach ($cleanupFile in @($extractLogPath, $sourceIndexPath, (Join-Path $OutputPath "reports\failed_extracts.md"))) {
        if (Test-Path -LiteralPath $cleanupFile) {
            try { Remove-Item -LiteralPath $cleanupFile -Force -ErrorAction Stop; Write-Info "Removed stale: $(Split-Path $cleanupFile -Leaf)" } catch { Write-Warn "Could not remove ${cleanupFile}: $_" }
        }
    }
    # Сбрасываем warnings.jsonl от предыдущих неудачных запусков
    if (Test-Path -LiteralPath $Script:WarningsPath) {
        try { Remove-Item -LiteralPath $Script:WarningsPath -Force -ErrorAction Stop } catch {}
    }

    # Архивы из scan-pool с валидным SHA
    $archiveFiles = @($Script:Files | Where-Object { $_.bucket -eq 'archive' -and $_.sha256 })
    Write-Info "Archives to process: $($archiveFiles.Count)"

    # Группируем по SHA → canonical = lex-min abs_path
    $bySha = $archiveFiles | Group-Object sha256
    $canonicalMap = @{}
    foreach ($g in $bySha) {
        $canon = $g.Group | Sort-Object abs_path | Select-Object -First 1
        $canonicalMap[$g.Name] = $canon.abs_path
    }
    $canonCount = $canonicalMap.Count
    $dupArchiveCount = $archiveFiles.Count - $canonCount
    Write-Info "Canonical: $canonCount. Duplicate archives (will skip): $dupArchiveCount"

    $Script:Archives = New-Object System.Collections.ArrayList
    $failedExtractsMd = New-Object System.Collections.ArrayList
    [void]$failedExtractsMd.Add("# Failed Archive Extractions`n")
    [void]$failedExtractsMd.Add("`n| Archive | Reason | Detail |")
    [void]$failedExtractsMd.Add("|---|---|---|")

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $idx = 0
    foreach ($a in $archiveFiles) {
        $idx++
        $isCanonical = ($canonicalMap[$a.sha256] -eq $a.abs_path)
        $sha8 = $a.sha256.Substring(0, 8)
        $baseSlug = Get-Slug ([System.IO.Path]::GetFileNameWithoutExtension($a.file_name))
        if (-not $baseSlug) { $baseSlug = 'archive' }
        $copyName = "{0}__{1}{2}" -f $baseSlug, $sha8, $a.ext
        $copyPath = Join-Path $archivesDir $copyName
        $extractDir = Join-Path $extractedRoot ("{0}__{1}" -f $baseSlug, $sha8)

        $info = [pscustomobject]@{
            source_abs_path  = $a.abs_path
            source_rel_path  = $a.rel_path
            source_name      = $a.file_name
            sha256           = $a.sha256
            size             = $a.size
            ext              = $a.ext
            canonical        = $isCanonical
            archive_slug     = "{0}__{1}" -f $baseSlug, $sha8
            copy_path        = $null
            extract_path     = $null
            status           = $null     # extracted | exact_dup_archive | password_protected | broken_archive | extract_failed | empty | no_3d_content
            error_message    = $null
            extracted_files  = 0
            duration_ms      = 0
        }

        if (-not $isCanonical) {
            $info.status = 'exact_dup_archive'
            $info.error_message = "Duplicate of canonical $($canonicalMap[$a.sha256])"
            [void]$Script:Archives.Add($info)
            continue
        }

        # Копируем canonical в original_sources/archives/
        try {
            if (-not (Test-Path -LiteralPath $copyPath)) {
                Copy-FileSafe -Source $a.abs_path -Destination $copyPath
            }
            $info.copy_path = $copyPath
        } catch {
            Write-Warn "Failed to copy archive: $($a.abs_path) — $_"
            Add-Warning @{ level='warning'; type='archive_copy_failed'; path=$a.abs_path; message=$_.ToString() }
        }

        # Распаковка
        $tStart = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $res = Invoke-SevenZipExtract -ArchivePath $a.abs_path -DestPath $extractDir
            $tStart.Stop()
            $info.duration_ms = [int]$tStart.ElapsedMilliseconds

            if ($res.ExitCode -eq 0) {
                $info.status = 'extracted'
                $info.extract_path = $extractDir
                $info.extracted_files = @(Get-ChildItem -LiteralPath $extractDir -Recurse -File -ErrorAction SilentlyContinue).Count
            } else {
                # Анализ stderr для классификации
                $combined = "$($res.Stdout)`n$($res.Stderr)"
                if ($combined -match 'Wrong password|Cannot open encrypted') {
                    $info.status = 'password_protected'
                } elseif ($combined -match 'CRC failed|Headers Error|Data Error|Unexpected end') {
                    $info.status = 'broken_archive'
                } else {
                    $info.status = 'extract_failed'
                }
                $info.error_message = ($combined -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 3) -join ' | '
                Write-Warn "Archive failed [$($info.status)]: $($a.file_name) — $($info.error_message)"
                [void]$failedExtractsMd.Add(("| {0} | {1} | {2} |" -f $a.rel_path, $info.status, ($info.error_message -replace '\|', '/')))
                Add-Warning @{ level='warning'; type=$info.status; path=$a.abs_path; message=$info.error_message }
            }
        } catch {
            $tStart.Stop()
            $info.duration_ms = [int]$tStart.ElapsedMilliseconds
            $info.status = 'extract_failed'
            $info.error_message = $_.ToString()
            Write-Warn "Extract exception on $($a.file_name): $_"
            [void]$failedExtractsMd.Add(("| {0} | exception | {1} |" -f $a.rel_path, ($_.ToString() -replace '\|', '/')))
        }
        [void]$Script:Archives.Add($info)

        if ($idx % 10 -eq 0 -or $idx -eq $archiveFiles.Count) {
            $pct = [math]::Round(($idx / $archiveFiles.Count) * 100, 1)
            Write-Info ("  archives {0}/{1} ({2}%) elapsed={3}" -f $idx, $archiveFiles.Count, $pct, $sw.Elapsed.ToString('mm\:ss'))
        }
    }
    $sw.Stop()

    # Запись extract log
    Write-Info "Writing extract log → staging\.extract_log.jsonl"
    $enc = New-Object System.Text.UTF8Encoding $false
    $writer = New-Object System.IO.StreamWriter($extractLogPath, $false, $enc)
    try {
        foreach ($a in $Script:Archives) {
            $writer.WriteLine(($a | ConvertTo-Json -Compress -Depth 5))
        }
    } finally { $writer.Dispose() }

    # source_index.json
    $sourceIndex = [pscustomobject]@{
        format         = 'meshnest-source-index'
        format_version = '1.0'
        created_at     = (Get-Date -Format 'o')
        archives_count = $Script:Archives.Count
        canonical_count = ($Script:Archives | Where-Object { $_.canonical }).Count
        archives = $Script:Archives
    }
    Write-Utf8Json -Path $sourceIndexPath -Object $sourceIndex -Depth 8

    # failed_extracts.md
    $failedCount = @($Script:Archives | Where-Object { $_.status -in @('password_protected','broken_archive','extract_failed') }).Count
    if ($failedCount -gt 0) {
        $failedExtractsMd[0] = "# Failed Archive Extractions ($failedCount)`n"
    }
    Write-Utf8Text -Path (Join-Path $OutputPath "reports\failed_extracts.md") -Content (($failedExtractsMd) -join "`n")

    $byStatus = $Script:Archives | Group-Object status | Sort-Object Count -Descending
    foreach ($g in $byStatus) {
        Write-Info ("  {0,-22} {1,5}" -f $g.Name, $g.Count)
    }
    Write-Info ("Phase 3 done in {0}" -f $sw.Elapsed.ToString('mm\:ss'))
}
#endregion

#region Phase 4 — Re-scan staging + finish hashing
function Invoke-Phase4ReScan {
    Write-Step "Phase 4: Re-scan staging + final FileEntry pool"

    $extractedRoot = Join-Path $OutputPath "staging\extracted"

    # 1. Дохешируем отложенные большие файлы
    $deferred = @($Script:Files | Where-Object { -not $_.sha256 })
    if ($deferred.Count -gt 0) {
        Write-Info "Hashing $($deferred.Count) deferred large files..."
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $bytes = [int64]0
        foreach ($f in $deferred) {
            try {
                $f.sha256 = Get-FileSha256Fast -Path $f.abs_path
                $bytes += $f.size
                if (-not $Script:DedupMap.ContainsKey($f.sha256)) {
                    $Script:DedupMap[$f.sha256] = New-Object System.Collections.ArrayList
                }
                [void]$Script:DedupMap[$f.sha256].Add($f.abs_path)
            } catch {
                Write-Warn "Hash failed (deferred): $($f.abs_path) — $_"
                Add-Warning @{ level='warning'; type='hash_failed'; path=$f.abs_path; message=$_.ToString() }
            }
        }
        $sw.Stop()
        $mbps = if ($sw.Elapsed.TotalSeconds -gt 0.5) { [math]::Round(($bytes/1MB)/$sw.Elapsed.TotalSeconds,1) } else { 0 }
        Write-Info ("Deferred hashing done: {0} files, {1} MB/s, {2}" -f $deferred.Count, $mbps, $sw.Elapsed.ToString('mm\:ss'))
    }

    # 2. Сканируем staging/extracted/
    if (-not (Test-Path -LiteralPath $extractedRoot)) {
        Write-Info "No staging/extracted directory — skipping rescan."
        return
    }
    Write-Info "Re-scanning $extractedRoot ..."
    $extractedItems = Get-ChildItem -LiteralPath $extractedRoot -Recurse -File -Force -ErrorAction SilentlyContinue
    Write-Info "Found $($extractedItems.Count) extracted files."

    $junkCount = 0
    $newFiles = 0
    $hashedNew = 0
    $extRootTrim = $extractedRoot.TrimEnd('\','/')

    foreach ($f in $extractedItems) {
        if (Test-IsJunkPath $f.FullName) { $junkCount++; continue }
        $relFromExt = $f.FullName.Substring($extRootTrim.Length).TrimStart('\','/').Replace('\','/')
        $archiveSlug = ($relFromExt -split '/')[0]
        $bucket = Get-FileBucket $f.FullName
        $sha = $null
        $isLarge = ($f.Length -ge $Script:HASH_LARGE_THRESHOLD)
        if (-not $isLarge -or $bucket -eq 'archive') {
            try {
                $sha = Get-FileSha256Fast -Path $f.FullName
                $hashedNew++
            } catch {}
        }
        $entry = [pscustomobject]@{
            abs_path   = $f.FullName
            rel_path   = "staging/extracted/$relFromExt"
            file_name  = $f.Name
            size       = [int64]$f.Length
            ext        = $f.Extension.ToLowerInvariant()
            bucket     = $bucket
            mtime      = $f.LastWriteTime.ToString('o')
            sha256     = $sha
            provenance = "archive:$archiveSlug"
        }
        [void]$Script:Files.Add($entry)
        $newFiles++
        if ($sha) {
            if (-not $Script:DedupMap.ContainsKey($sha)) {
                $Script:DedupMap[$sha] = New-Object System.Collections.ArrayList
            }
            [void]$Script:DedupMap[$sha].Add($f.FullName)
        }
    }
    Write-Info "Added $newFiles extracted files (hashed $hashedNew). Skipped $junkCount junk."
    Write-Info "Total FileEntries now: $($Script:Files.Count)"
}
#endregion

#region Phase 5 — Group files into model units
function Invoke-Phase5GroupModels {
    Write-Step "Phase 5: Group files into model units"

    $extractedRoot = (Join-Path $OutputPath "staging\extracted").TrimEnd('\','/')
    $inputRoot = $InputPath.TrimEnd('\','/')

    # Helper: scope-root для файла
    $resolveScopeRoot = {
        param($absPath)
        if ($absPath.StartsWith($extractedRoot + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
            $absPath.StartsWith($extractedRoot + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
            $rel = $absPath.Substring($extractedRoot.Length).TrimStart('\','/')
            $first = ($rel -split '[\\/]')[0]
            return (Join-Path $extractedRoot $first)
        }
        return $inputRoot
    }

    # 1. Все 3D-primary файлы
    $threeDFiles = @($Script:Files | Where-Object { $_.bucket -in @('stl','step','3mf') })
    Write-Info "3D primary files (stl/step/3mf): $($threeDFiles.Count)"

    # 2. Группировка по host-dir
    $hostMap = @{}      # абс host-dir → ArrayList of FileEntry
    $looseFiles = New-Object System.Collections.ArrayList
    foreach ($f in $threeDFiles) {
        $dir = [System.IO.Path]::GetDirectoryName($f.abs_path).TrimEnd('\','/')
        $scopeRoot = (& $resolveScopeRoot $f.abs_path).TrimEnd('\','/')
        if ($dir -ieq $scopeRoot) {
            [void]$looseFiles.Add($f)
        } else {
            if (-not $hostMap.ContainsKey($dir)) {
                $hostMap[$dir] = New-Object System.Collections.ArrayList
            }
            [void]$hostMap[$dir].Add($f)
        }
    }
    Write-Info "Host directories (potential models): $($hostMap.Count). Loose 3D at scope-root: $($looseFiles.Count)"

    # 3. Set всех hosts (для фильтрации поддеревьев)
    $hostSet = @{}
    foreach ($k in $hostMap.Keys) { $hostSet[$k.ToLowerInvariant()] = $true }

    $Script:Models = New-Object System.Collections.ArrayList

    # Helper: проверить лежит ли файл внутри другого host-dir (не текущего)
    $isInOtherHost = {
        param($filePath, $thisHost)
        $thisHostLower = $thisHost.ToLowerInvariant()
        $entryDir = [System.IO.Path]::GetDirectoryName($filePath).TrimEnd('\','/')
        $checkDir = $entryDir
        while ($checkDir) {
            $cl = $checkDir.ToLowerInvariant()
            if ($cl -eq $thisHostLower) { return $false }
            if ($hostSet.ContainsKey($cl)) { return $true }
            $parent = [System.IO.Path]::GetDirectoryName($checkDir)
            if ($parent -eq $checkDir -or -not $parent) { break }
            $checkDir = $parent.TrimEnd('\','/')
        }
        return $false
    }

    # 4. Каждая host-dir → модель
    foreach ($hostDir in $hostMap.Keys) {
        $hostPrefix = $hostDir.TrimEnd('\','/') + '\'
        $modelFiles = New-Object System.Collections.ArrayList
        foreach ($entry in $Script:Files) {
            if (-not $entry.abs_path.StartsWith($hostPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            if ((& $isInOtherHost $entry.abs_path $hostDir)) { continue }
            [void]$modelFiles.Add($entry)
        }

        $titleSrc = [System.IO.Path]::GetFileName($hostDir)
        $isInExtracted = $hostDir.StartsWith($extractedRoot, [System.StringComparison]::OrdinalIgnoreCase)
        $sourceLabel = if ($isInExtracted) { 'archive' } else { 'folder' }

        $archiveSlug = $null
        if ($isInExtracted) {
            $relFromExt = $hostDir.Substring($extractedRoot.Length).TrimStart('\','/')
            $archiveSlug = ($relFromExt -split '[\\/]')[0]
        }

        # Эдж-кейс: много STL без readme/preview
        $stlCount = @($modelFiles | Where-Object { $_.bucket -eq 'stl' }).Count
        $hasReadmeOrImg = @($modelFiles | Where-Object {
            $_.bucket -eq 'image' -or $_.file_name -match '^readme|\.md$|\.txt$'
        }).Count -gt 0

        $extraTags = @()
        if ($stlCount -gt $Script:MULTI_MODEL_SUSPECT_THRESH -and -not $hasReadmeOrImg) {
            $extraTags += 'multi-model-suspect'
            $extraTags += 'needs-review'
        }
        # Nested archive flag
        if (@($modelFiles | Where-Object { $_.bucket -eq 'archive' }).Count -gt 0) {
            $extraTags += 'nested-archive'
            $extraTags += 'needs-review'
        }

        [void]$Script:Models.Add([pscustomobject]@{
            host_dir    = $hostDir
            title_src   = $titleSrc
            files       = $modelFiles
            source_type = $sourceLabel
            archive_ref = $archiveSlug
            tags_extra  = $extraTags
            is_loose    = $false
        })
    }

    # 5. Loose models (Rule D)
    foreach ($f in $looseFiles) {
        $titleSrc = [System.IO.Path]::GetFileNameWithoutExtension($f.file_name)
        $isInExtracted = $f.abs_path.StartsWith($extractedRoot, [System.StringComparison]::OrdinalIgnoreCase)
        $sourceLabel = if ($isInExtracted) { 'archive' } else { 'folder' }
        $archiveSlug = $null
        if ($isInExtracted) {
            $relFromExt = $f.abs_path.Substring($extractedRoot.Length).TrimStart('\','/')
            $archiveSlug = ($relFromExt -split '[\\/]')[0]
        }
        $loose = New-Object System.Collections.ArrayList
        [void]$loose.Add($f)
        [void]$Script:Models.Add([pscustomobject]@{
            host_dir    = [System.IO.Path]::GetDirectoryName($f.abs_path)
            title_src   = $titleSrc
            files       = $loose
            source_type = $sourceLabel
            archive_ref = $archiveSlug
            tags_extra  = @('loose-file','needs-review')
            is_loose    = $true
        })
    }

    Write-Info "Total model units: $($Script:Models.Count)"
    $bySrc = $Script:Models | Group-Object source_type
    foreach ($g in $bySrc) {
        Write-Info ("  source={0,-7} {1,5}" -f $g.Name, $g.Count)
    }
    $needsReview = @($Script:Models | Where-Object { 'needs-review' -in $_.tags_extra }).Count
    Write-Info "  needs-review flagged: $needsReview"
}
#endregion

#region Phase 6 — Normalize + categorize + tag + preview
function Get-CategoryScore {
    param([string]$FolderText, [string]$FileText)
    $scores = @{}
    foreach ($cat in $Script:CategoryKeywords.Keys) {
        $score = 0
        foreach ($kw in $Script:CategoryKeywords[$cat]) {
            $kwL = $kw.ToLowerInvariant()
            $kwEsc = [regex]::Escape($kwL)
            # Folder hits — weight 3
            $score += ([regex]::Matches($FolderText, $kwEsc)).Count * 3
            # Filename hits — weight 2
            $score += ([regex]::Matches($FileText, $kwEsc)).Count * 2
        }
        if ($score -gt 0) { $scores[$cat] = $score }
    }
    return $scores
}

function Resolve-ModelCategory {
    param([pscustomobject]$Model)
    $folderText = ($Model.title_src + ' ').ToLowerInvariant()
    $folderText += ' ' + (Convert-Cyrillic $Model.title_src).ToLowerInvariant()
    if ($Model.archive_ref) { $folderText += ' ' + $Model.archive_ref.ToLowerInvariant() }
    # Также добавим путь host_dir (имена родительских папок дают подсказку категории)
    $folderText += ' ' + ($Model.host_dir.Replace('\',' ').Replace('/',' ')).ToLowerInvariant()
    $folderText += ' ' + (Convert-Cyrillic $Model.host_dir.Replace('\',' ').Replace('/',' ')).ToLowerInvariant()

    $fileText = (($Model.files | ForEach-Object { $_.file_name }) -join ' ').ToLowerInvariant()
    $fileText += ' ' + (Convert-Cyrillic $fileText).ToLowerInvariant()

    $scores = Get-CategoryScore -FolderText $folderText -FileText $fileText
    if ($scores.Count -eq 0) {
        return [pscustomobject]@{ Category='uncategorized'; Confidence=0.0 }
    }
    $sorted = $scores.GetEnumerator() | Sort-Object Value -Descending
    $best = $sorted | Select-Object -First 1
    $total = ($scores.Values | Measure-Object -Sum).Sum
    $conf = if ($total -gt 0) { [math]::Round($best.Value / $total, 3) } else { 0.0 }
    if ($conf -lt $Script:CATEGORY_CONFIDENCE_MIN) {
        return [pscustomobject]@{ Category='uncategorized'; Confidence=$conf }
    }
    return [pscustomobject]@{ Category=$best.Key; Confidence=$conf }
}

function Resolve-ModelTags {
    param([pscustomobject]$Model, [string]$Category, [string[]]$ExtraTags)
    $tags = New-Object System.Collections.ArrayList
    $files = $Model.files

    # Format
    if (@($files | Where-Object { $_.bucket -eq 'stl' }).Count -gt 0) { [void]$tags.Add('has-stl') }
    if (@($files | Where-Object { $_.bucket -eq '3mf' }).Count -gt 0) { [void]$tags.Add('has-3mf') }
    if (@($files | Where-Object { $_.bucket -eq 'step' }).Count -gt 0) { [void]$tags.Add('has-step') }
    if (@($files | Where-Object { $_.bucket -eq 'image' }).Count -gt 0) { [void]$tags.Add('has-images') }
    if (@($files | Where-Object { $_.bucket -eq 'video' }).Count -gt 0) { [void]$tags.Add('has-video') }

    # Structure
    $printCount = @($files | Where-Object { $_.bucket -in @('stl','step','3mf') }).Count
    if ($printCount -ge 2) { [void]$tags.Add('multipart') } else { [void]$tags.Add('single-part') }
    if (@($files | Where-Object { $_.bucket -eq 'step' }).Count -gt 0) { [void]$tags.Add('assembly') }

    # Source provenance
    if ($Model.source_type -eq 'archive') { [void]$tags.Add('source-archive') } else { [void]$tags.Add('source-folder') }

    # Duplicate detection (по SHA с другими моделями)
    $isDup = $false
    foreach ($f in $files) {
        if (-not $f.sha256) { continue }
        if ($Script:DedupMap.ContainsKey($f.sha256) -and $Script:DedupMap[$f.sha256].Count -gt 1) {
            $isDup = $true; break
        }
    }
    if ($isDup) { [void]$tags.Add('duplicate-detected') }

    # Theme + print-style теги по тексту
    $textBlob = ($Model.title_src + ' ' + (($files | ForEach-Object { $_.file_name }) -join ' ')).ToLowerInvariant()
    $textBlob += ' ' + (Convert-Cyrillic $textBlob).ToLowerInvariant()
    if ($Model.host_dir) { $textBlob += ' ' + $Model.host_dir.ToLowerInvariant() }

    foreach ($pf in $Script:PrintFlagKeywords.Keys) {
        foreach ($kw in $Script:PrintFlagKeywords[$pf]) {
            if ($textBlob -match [regex]::Escape($kw.ToLowerInvariant())) {
                [void]$tags.Add($pf); break
            }
        }
    }
    foreach ($th in $Script:ThemeKeywords.Keys) {
        foreach ($kw in $Script:ThemeKeywords[$th]) {
            if ($textBlob -match [regex]::Escape($kw.ToLowerInvariant())) {
                [void]$tags.Add($th); break
            }
        }
    }

    # Category-derived primary tag (cat/dog/dragon ...)
    if ($Category -ne 'uncategorized') {
        $leaf = ($Category -split '/')[-1]
        if ($leaf) { [void]$tags.Add($leaf.Replace('_','-')) }
    }

    # Дополнительные tag'и из Phase 5 (loose-file, multi-model-suspect, nested-archive, needs-review)
    if ($ExtraTags) { foreach ($t in $ExtraTags) { [void]$tags.Add($t) } }

    # Если uncategorized — needs-review
    if ($Category -eq 'uncategorized' -and 'needs-review' -notin $tags) {
        [void]$tags.Add('needs-review')
    }

    return ($tags | Select-Object -Unique)
}

function Resolve-ModelPreview {
    param([pscustomobject]$Model)
    $images = @($Model.files | Where-Object { $_.bucket -eq 'image' })
    if ($images.Count -gt 0) {
        foreach ($keyword in @('preview','cover','render','thumb')) {
            $match = $images | Where-Object { $_.file_name -match $keyword } | Select-Object -First 1
            if ($match) { return [pscustomobject]@{ File=$match; Status='source_image_used' } }
        }
        $largest = $images | Sort-Object size -Descending | Select-Object -First 1
        return [pscustomobject]@{ File=$largest; Status='source_image_used' }
    }
    # Fallback: 3MF embedded thumbnail (реальная экстракция в Phase 7)
    $threemf = @($Model.files | Where-Object { $_.bucket -eq '3mf' }) | Select-Object -First 1
    if ($threemf) {
        return [pscustomobject]@{ File=$threemf; Status='extracted_from_3mf' }
    }
    return [pscustomobject]@{ File=$null; Status='placeholder' }
}

function Invoke-Phase6Categorize {
    Write-Step "Phase 6: Normalize + categorize + tag + preview"

    if (-not $Script:Models -or $Script:Models.Count -eq 0) {
        Write-Warn "No models from Phase 5 — nothing to categorize."
        return
    }

    Write-Info "Processing $($Script:Models.Count) models..."

    # 1. Title + slug + uniqueness
    $usedSlugs = @{}
    foreach ($m in $Script:Models) {
        $titleClean = Get-CleanTitle $m.title_src
        $baseSlug = Get-Slug $titleClean
        if (-not $baseSlug -or $baseSlug -eq 'untitled') {
            $baseSlug = Get-Slug $m.title_src
        }
        $finalSlug = Get-UniqueSlug -BaseSlug $baseSlug -UsedSet $usedSlugs

        $cat = Resolve-ModelCategory -Model $m
        $tags = Resolve-ModelTags -Model $m -Category $cat.Category -ExtraTags $m.tags_extra
        $prev = Resolve-ModelPreview -Model $m

        # Структурные флаги
        $isFlexi = ('flexi' -in $tags)
        $isPip   = ('print-in-place' -in $tags)
        $isMulti = ('multipart' -in $tags)
        $isAsm   = ('assembly' -in $tags)

        $m | Add-Member -NotePropertyName title_clean       -NotePropertyValue $titleClean -Force
        $m | Add-Member -NotePropertyName slug              -NotePropertyValue $finalSlug -Force
        $m | Add-Member -NotePropertyName category          -NotePropertyValue $cat.Category -Force
        $m | Add-Member -NotePropertyName category_confidence -NotePropertyValue $cat.Confidence -Force
        $m | Add-Member -NotePropertyName tags              -NotePropertyValue ([string[]]$tags) -Force
        $m | Add-Member -NotePropertyName preview_file      -NotePropertyValue $prev.File -Force
        $m | Add-Member -NotePropertyName preview_status    -NotePropertyValue $prev.Status -Force
        $m | Add-Member -NotePropertyName is_flexi          -NotePropertyValue $isFlexi -Force
        $m | Add-Member -NotePropertyName is_print_in_place -NotePropertyValue $isPip -Force
        $m | Add-Member -NotePropertyName is_multipart      -NotePropertyValue $isMulti -Force
        $m | Add-Member -NotePropertyName is_assembly       -NotePropertyValue $isAsm -Force
    }

    # 2. Детерминированная нумерация model_id (sort by slug)
    $sorted = $Script:Models | Sort-Object slug
    $i = 1
    foreach ($m in $sorted) {
        $m | Add-Member -NotePropertyName model_id -NotePropertyValue ("mdl_{0:D6}" -f $i) -Force
        $i++
    }
    $Script:Models = $sorted

    # Сводка
    Write-Info "Model IDs assigned: mdl_000001 .. mdl_$($i-1)"
    $catSummary = $Script:Models | Group-Object category | Sort-Object Count -Descending
    foreach ($g in $catSummary) {
        Write-Info ("  {0,-30} {1,5}" -f $g.Name, $g.Count)
    }
    $unc = @($Script:Models | Where-Object { $_.category -eq 'uncategorized' }).Count
    $pct = [math]::Round(($unc / $Script:Models.Count) * 100, 1)
    Write-Info "Uncategorized: $unc / $($Script:Models.Count) ($pct%)"
    if ($pct -gt 30) { Write-Warn "More than 30% uncategorized — keyword rules may need tuning." }

    $previewSummary = $Script:Models | Group-Object preview_status
    foreach ($g in $previewSummary) {
        Write-Info ("  preview {0,-25} {1,5}" -f $g.Name, $g.Count)
    }
}
#endregion

#region Phase 7 — Materialize models on disk
function Get-3MFThumbnail {
    param([string]$ZipPath, [string]$OutPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        try {
            foreach ($e in $zip.Entries) {
                $n = $e.FullName.Replace('\','/').ToLowerInvariant()
                if ($n -match 'thumbnail.*\.png$' -or $n -match 'metadata/thumbnail\.png$' -or $n -match 'thumbnails?/.*\.png$') {
                    New-DirIfNeeded ([System.IO.Path]::GetDirectoryName($OutPath))
                    $stream = $e.Open()
                    try {
                        $fs = [System.IO.File]::Create($OutPath)
                        try { $stream.CopyTo($fs) } finally { $fs.Dispose() }
                    } finally { $stream.Dispose() }
                    return $true
                }
            }
            return $false
        } finally { $zip.Dispose() }
    } catch {
        return $false
    }
}

function Get-FileRole {
    param([pscustomobject]$FileEntry, [bool]$IsPreview)
    if ($IsPreview) { return 'preview_image' }
    switch ($FileEntry.bucket) {
        'stl'      { return 'print_file' }
        'step'     { return 'print_file' }
        '3mf'      { return 'print_file' }
        'other_3d' { return 'source' }
        'image'    { return 'gallery_image' }
        'video'    { return 'video' }
        'doc'      {
            if ($FileEntry.file_name -match '(?i)license|licence|copyright|notice') { return 'license' }
            return 'instruction'
        }
        'archive'  { return 'nested_archive' }
        default    { return 'other' }
    }
}

function Get-FileTypeFromBucket {
    param([string]$Bucket)
    switch ($Bucket) {
        'stl'      { 'mesh' }
        'step'     { 'cad' }
        '3mf'      { 'project' }
        'other_3d' { 'mesh' }
        'image'    { 'image' }
        'video'    { 'video' }
        'doc'      { 'document' }
        'archive'  { 'archive' }
        default    { 'other' }
    }
}

function Get-DestSubdir {
    param([pscustomobject]$FileEntry)
    switch ($FileEntry.bucket) {
        'stl'      { 'print_files\stl' }
        'step'     { 'print_files\step' }
        '3mf'      { 'print_files\3mf' }
        'other_3d' { 'print_files\other' }
        'image'    { 'media\images' }
        'video'    { 'media\videos' }
        'doc'      { 'print_files\other' }
        'archive'  { 'source' }    # nested archives → source/
        default    { 'print_files\other' }
    }
}

function Resolve-UniqueFileName {
    param([string]$Dir, [string]$Name)
    $candidate = Join-Path $Dir $Name
    if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($Name)
    $ext = [System.IO.Path]::GetExtension($Name)
    for ($i = 2; $i -lt 1000; $i++) {
        $candidate = Join-Path $Dir ("{0}__{1}{2}" -f $stem, $i, $ext)
        if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw "Cannot resolve filename collision in $Dir for $Name"
}

function New-ModelYaml {
    param([pscustomobject]$Model)
    $tagsLines = ''
    foreach ($t in $Model.tags) { $tagsLines += "  - " + $t + "`n" }

    $previewRel = if ($Model.preview_dest_rel) { '"' + $Model.preview_dest_rel + '"' } else { 'null' }
    $thumbnailRel = if ($Model.thumbnail_dest_rel) { '"' + $Model.thumbnail_dest_rel + '"' } else { 'null' }
    $packageRel = if ($Model.package_zip_rel) { '"' + $Model.package_zip_rel + '"' } else { 'null' }

    $stlCount = @($Model.materialized_files | Where-Object { $_.bucket -eq 'stl' }).Count
    $stepCount = @($Model.materialized_files | Where-Object { $_.bucket -eq 'step' }).Count
    $threeMfCount = @($Model.materialized_files | Where-Object { $_.bucket -eq '3mf' }).Count
    $imgCount = @($Model.materialized_files | Where-Object { $_.bucket -eq 'image' }).Count
    $vidCount = @($Model.materialized_files | Where-Object { $_.bucket -eq 'video' }).Count
    $docCount = @($Model.materialized_files | Where-Object { $_.bucket -eq 'doc' }).Count

    $sourceName = if ($Model.archive_ref) { $Model.archive_ref } else { (Split-Path $Model.host_dir -Leaf) }
    $sourceHash = ''
    if ($Model.archive_ref) {
        $arch = $Script:Archives | Where-Object { $_.archive_slug -eq $Model.archive_ref } | Select-Object -First 1
        if ($arch) { $sourceHash = $arch.sha256 }
    }

    $titleEsc = ($Model.title_clean -replace '"','\"')
    $origEsc  = ($Model.title_src -replace '"','\"')
    $hostEsc  = ($Model.host_dir -replace '"','\"').Replace('\','/')

    $yaml = @"
id: "$($Model.model_id)"
slug: "$($Model.slug)"
title: "$titleEsc"
original_title: "$origEsc"
category: "$($Model.category)"
category_confidence: $($Model.category_confidence)
status: "needs_review"
is_reviewed: false

tags:
$tagsLines
print_flags:
  is_flexi: $(($Model.is_flexi).ToString().ToLower())
  is_print_in_place: $(($Model.is_print_in_place).ToString().ToLower())
  is_multipart: $(($Model.is_multipart).ToString().ToLower())
  is_assembly: $(($Model.is_assembly).ToString().ToLower())
  supports_required: unknown

file_summary:
  stl_count: $stlCount
  step_count: $stepCount
  three_mf_count: $threeMfCount
  image_count: $imgCount
  video_count: $vidCount
  document_count: $docCount

paths:
  model_folder: "$($Model.dest_model_rel)"
  preview_image: $previewRel
  thumbnail: $thumbnailRel
  viewer_model: null
  package_zip: $packageRel

source:
  source_type: "$($Model.source_type)"
  source_name: "$sourceName"
  source_host_dir: "$hostEsc"
  source_hash_sha256: "$sourceHash"

geometry:
  bbox_mm:
    x: null
    y: null
    z: null
  triangle_count: null
  mesh_count: null

conversion:
  preview_status: "$($Model.preview_status)"
  viewer_status: "pending"
  errors: []

license:
  detected: false
  license_file: null

created_at: "$(Get-Date -Format 'o')"
updated_at: "$(Get-Date -Format 'o')"
"@
    return $yaml
}

function Invoke-Phase7Materialize {
    Write-Step "Phase 7: Materialize models on disk"

    $modelsRoot = Join-Path $OutputPath "models"
    $assetsPreviews = Join-Path $OutputPath "assets\previews"
    $assetsThumbs = Join-Path $OutputPath "assets\thumbnails"
    $packagesDir = Join-Path $OutputPath "packages\model_zip"

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $idx = 0
    $errs = 0
    foreach ($m in $Script:Models) {
        $idx++
        $modelDir = Join-Path $modelsRoot ($m.category + '\' + $m.slug)
        $m | Add-Member -NotePropertyName dest_model_dir -NotePropertyValue $modelDir -Force
        $m | Add-Member -NotePropertyName dest_model_rel -NotePropertyValue (Get-RelativePath -BasePath $OutputPath -TargetPath $modelDir) -Force

        # Создание подпапок
        foreach ($sub in @('print_files\stl','print_files\step','print_files\3mf','print_files\other',
                           'media\images','media\videos','generated','source','package')) {
            New-DirIfNeeded (Join-Path $modelDir $sub)
        }

        # Копирование файлов
        $matFiles = New-Object System.Collections.ArrayList
        $previewSrc = $m.preview_file
        foreach ($f in $m.files) {
            $isPreview = ($previewSrc -and $f.abs_path -ieq $previewSrc.abs_path)
            $subdir = Get-DestSubdir -FileEntry $f
            $destDir = Join-Path $modelDir $subdir
            $destPath = Resolve-UniqueFileName -Dir $destDir -Name $f.file_name
            try {
                Copy-FileSafe -Source $f.abs_path -Destination $destPath
            } catch {
                $errs++
                Write-Warn "Copy failed: $($f.abs_path) — $_"
                Add-Warning @{ level='warning'; type='copy_failed'; path=$f.abs_path; message=$_.ToString() }
                continue
            }
            $relPath = Get-RelativePath -BasePath $OutputPath -TargetPath $destPath
            $role = Get-FileRole -FileEntry $f -IsPreview $isPreview
            $ftype = Get-FileTypeFromBucket -Bucket $f.bucket
            [void]$matFiles.Add([pscustomobject]@{
                file_id = ("fil_{0}_{1:D4}" -f $m.model_id.Replace('mdl_',''), $matFiles.Count)
                model_id = $m.model_id
                file_name = [System.IO.Path]::GetFileName($destPath)
                original_file_name = $f.file_name
                extension = $f.ext
                file_type = $ftype
                role = $role
                relative_path = $relPath
                size_bytes = $f.size
                sha256 = $f.sha256
                is_primary = ($role -eq 'print_file')
                status = 'ready'
                bucket = $f.bucket
            })
        }
        $m | Add-Member -NotePropertyName materialized_files -NotePropertyValue $matFiles -Force

        # Preview материализация
        $previewDestRel = $null
        $thumbDestRel = $null
        if ($previewSrc) {
            if ($m.preview_status -eq 'extracted_from_3mf') {
                $previewOut = Join-Path $modelDir 'generated\preview.png'
                if (Get-3MFThumbnail -ZipPath $previewSrc.abs_path -OutPath $previewOut) {
                    Copy-FileSafe -Source $previewOut -Destination (Join-Path $modelDir 'generated\thumbnail.png') -Overwrite
                    Copy-FileSafe -Source $previewOut -Destination (Join-Path $assetsPreviews "$($m.model_id).png") -Overwrite
                    Copy-FileSafe -Source $previewOut -Destination (Join-Path $assetsThumbs "$($m.model_id).png") -Overwrite
                    $previewDestRel = Get-RelativePath -BasePath $OutputPath -TargetPath $previewOut
                    $thumbDestRel = Get-RelativePath -BasePath $OutputPath -TargetPath (Join-Path $modelDir 'generated\thumbnail.png')
                } else {
                    # Не удалось — placeholder
                    $m.preview_status = 'placeholder'
                }
            } else {
                # source_image_used — копируем уже скопированный media-файл в generated/
                $imgExt = $previewSrc.ext
                $previewOut = Join-Path $modelDir ("generated\preview" + $imgExt)
                $thumbOut = Join-Path $modelDir ("generated\thumbnail" + $imgExt)
                try {
                    Copy-FileSafe -Source $previewSrc.abs_path -Destination $previewOut -Overwrite
                    Copy-FileSafe -Source $previewSrc.abs_path -Destination $thumbOut -Overwrite
                    Copy-FileSafe -Source $previewSrc.abs_path -Destination (Join-Path $assetsPreviews "$($m.model_id)$imgExt") -Overwrite
                    Copy-FileSafe -Source $previewSrc.abs_path -Destination (Join-Path $assetsThumbs "$($m.model_id)$imgExt") -Overwrite
                    $previewDestRel = Get-RelativePath -BasePath $OutputPath -TargetPath $previewOut
                    $thumbDestRel = Get-RelativePath -BasePath $OutputPath -TargetPath $thumbOut
                } catch {
                    Write-Warn "Preview copy failed for $($m.model_id): $_"
                    $m.preview_status = 'placeholder'
                }
            }
        }
        $m | Add-Member -NotePropertyName preview_dest_rel -NotePropertyValue $previewDestRel -Force
        $m | Add-Member -NotePropertyName thumbnail_dest_rel -NotePropertyValue $thumbDestRel -Force

        # source_info.json
        $sourceInfo = [pscustomobject]@{
            model_id = $m.model_id
            slug = $m.slug
            source_type = $m.source_type
            source_host_dir = $m.host_dir
            source_archive_ref = $m.archive_ref
            file_count = $m.files.Count
            captured_at = (Get-Date -Format 'o')
        }
        Write-Utf8Json -Path (Join-Path $modelDir 'source\source_info.json') -Object $sourceInfo -Depth 5

        # original_archive_reference.txt
        if ($m.archive_ref) {
            $archInfo = $Script:Archives | Where-Object { $_.archive_slug -eq $m.archive_ref } | Select-Object -First 1
            if ($archInfo) {
                $refTxt = "archive_slug: $($archInfo.archive_slug)`r`nsource_name: $($archInfo.source_name)`r`nsource_path: $($archInfo.source_rel_path)`r`nsha256: $($archInfo.sha256)`r`nsize_bytes: $($archInfo.size)"
                Write-Utf8Text -Path (Join-Path $modelDir 'source\original_archive_reference.txt') -Content $refTxt
            }
        } else {
            $refTxt = "source_type: folder`r`nsource_host_dir: $($m.host_dir)"
            Write-Utf8Text -Path (Join-Path $modelDir 'source\original_archive_reference.txt') -Content $refTxt
        }

        # Per-model ZIP package
        $zipName = "$($m.slug)_all_files.zip"
        $zipPath = Join-Path $packagesDir $zipName
        $zipRel = Get-RelativePath -BasePath $OutputPath -TargetPath $zipPath
        $m | Add-Member -NotePropertyName package_zip_path -NotePropertyValue $zipPath -Force
        $m | Add-Member -NotePropertyName package_zip_rel -NotePropertyValue $zipRel -Force

        # model.yaml
        $yamlContent = New-ModelYaml -Model $m
        Write-Utf8Text -Path (Join-Path $modelDir 'model.yaml') -Content $yamlContent

        # Package zip — создаём из model directory (без generated/ дублирования и без package/ самого)
        try {
            if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
            $res = Invoke-SevenZipAdd -ZipPath $zipPath -SourceDir $modelDir -ExcludePatterns @('package')
            if ($res.ExitCode -ne 0) {
                Write-Warn "ZIP failed for $($m.slug): exit $($res.ExitCode)"
                Add-Warning @{ level='warning'; type='zip_failed'; model_id=$m.model_id; message="exit $($res.ExitCode)" }
            }
        } catch {
            Write-Warn "ZIP exception for $($m.slug): $_"
            Add-Warning @{ level='warning'; type='zip_exception'; model_id=$m.model_id; message=$_.ToString() }
        }

        if ($idx % 25 -eq 0 -or $idx -eq $Script:Models.Count) {
            $pct = [math]::Round(($idx / $Script:Models.Count) * 100, 1)
            Write-Info ("  models {0}/{1} ({2}%) elapsed={3}" -f $idx, $Script:Models.Count, $pct, $sw.Elapsed.ToString('mm\:ss'))
        }
    }
    $sw.Stop()
    Write-Info ("Phase 7 done in {0}. Errors: {1}" -f $sw.Elapsed.ToString('mm\:ss'), $errs)
}
#endregion

#region Phase 8 — Aggregates (CSV/JSON)
function ConvertTo-CsvCell {
    param($Value)
    if ($null -eq $Value) { return '' }
    $s = [string]$Value
    if ($s -match '[",\r\n]') {
        return '"' + ($s -replace '"','""') + '"'
    }
    return $s
}

function Invoke-Phase8Aggregates {
    Write-Step "Phase 8: Aggregates (CSV/JSON)"

    $databaseDir = Join-Path $OutputPath "database"
    $modelsCsvPath = Join-Path $databaseDir "models.csv"
    $filesCsvPath  = Join-Path $databaseDir "files.csv"
    $modelsJsonPath = Join-Path $databaseDir "models.json"
    $tagsCsvPath = Join-Path $databaseDir "tags.csv"
    $categoriesCsvPath = Join-Path $databaseDir "categories.csv"

    # === models.csv ===
    Write-Info "Writing models.csv..."
    $modelsCsvHeader = "id,title,slug,category,category_confidence,tags,model_folder,preview_image,thumbnail,viewer_model,package_zip,stl_count,step_count,three_mf_count,image_count,video_count,document_count,is_flexi,is_print_in_place,is_multipart,has_stl,has_step,has_3mf,has_images,has_video,source_type,source_name,source_hash,status,is_reviewed,notes"
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine($modelsCsvHeader)
    foreach ($m in $Script:Models) {
        $stlC = @($m.materialized_files | Where-Object { $_.bucket -eq 'stl' }).Count
        $stepC = @($m.materialized_files | Where-Object { $_.bucket -eq 'step' }).Count
        $threeMfC = @($m.materialized_files | Where-Object { $_.bucket -eq '3mf' }).Count
        $imgC = @($m.materialized_files | Where-Object { $_.bucket -eq 'image' }).Count
        $vidC = @($m.materialized_files | Where-Object { $_.bucket -eq 'video' }).Count
        $docC = @($m.materialized_files | Where-Object { $_.bucket -eq 'doc' }).Count
        $sourceName = if ($m.archive_ref) { $m.archive_ref } else { Split-Path $m.host_dir -Leaf }
        $sourceHash = ''
        if ($m.archive_ref) {
            $a = $Script:Archives | Where-Object { $_.archive_slug -eq $m.archive_ref } | Select-Object -First 1
            if ($a) { $sourceHash = $a.sha256 }
        }
        $cells = @(
            $m.model_id, $m.title_clean, $m.slug, $m.category, $m.category_confidence,
            (($m.tags) -join ';'),
            $m.dest_model_rel, $m.preview_dest_rel, $m.thumbnail_dest_rel, '', $m.package_zip_rel,
            $stlC, $stepC, $threeMfC, $imgC, $vidC, $docC,
            $m.is_flexi, $m.is_print_in_place, $m.is_multipart,
            ($stlC -gt 0), ($stepC -gt 0), ($threeMfC -gt 0), ($imgC -gt 0), ($vidC -gt 0),
            $m.source_type, $sourceName, $sourceHash,
            'needs_review', $false, ''
        )
        [void]$sb.AppendLine(($cells | ForEach-Object { ConvertTo-CsvCell $_ }) -join ',')
    }
    Write-Utf8Text -Path $modelsCsvPath -Content $sb.ToString() -Bom

    # === files.csv ===
    Write-Info "Writing files.csv..."
    $filesCsvHeader = "file_id,model_id,file_name,original_file_name,extension,file_type,role,relative_path,size_bytes,sha256,is_primary,status,detected_tags"
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine($filesCsvHeader)
    foreach ($m in $Script:Models) {
        foreach ($f in $m.materialized_files) {
            $cells = @(
                $f.file_id, $f.model_id, $f.file_name, $f.original_file_name,
                $f.extension, $f.file_type, $f.role, $f.relative_path,
                $f.size_bytes, $f.sha256, $f.is_primary, $f.status, ''
            )
            [void]$sb.AppendLine(($cells | ForEach-Object { ConvertTo-CsvCell $_ }) -join ',')
        }
    }
    Write-Utf8Text -Path $filesCsvPath -Content $sb.ToString() -Bom

    # === models.json ===
    Write-Info "Writing models.json..."
    $modelsJsonObj = [pscustomobject]@{
        format = 'meshnest-models'
        format_version = '1.0'
        created_at = (Get-Date -Format 'o')
        models = @()
    }
    $jsonModels = New-Object System.Collections.ArrayList
    foreach ($m in $Script:Models) {
        [void]$jsonModels.Add([pscustomobject]@{
            id = $m.model_id
            slug = $m.slug
            title = $m.title_clean
            original_title = $m.title_src
            category = $m.category
            category_confidence = $m.category_confidence
            tags = $m.tags
            paths = [pscustomobject]@{
                model_folder = $m.dest_model_rel
                preview_image = $m.preview_dest_rel
                thumbnail = $m.thumbnail_dest_rel
                viewer_model = $null
                package_zip = $m.package_zip_rel
            }
            print_flags = [pscustomobject]@{
                is_flexi = $m.is_flexi
                is_print_in_place = $m.is_print_in_place
                is_multipart = $m.is_multipart
                is_assembly = $m.is_assembly
            }
            status = 'needs_review'
            is_reviewed = $false
            preview_status = $m.preview_status
            viewer_status = 'pending'
            file_count = $m.materialized_files.Count
            source_type = $m.source_type
            source_archive_ref = $m.archive_ref
        })
    }
    $modelsJsonObj.models = $jsonModels
    Write-Utf8Json -Path $modelsJsonPath -Object $modelsJsonObj -Depth 8

    # === tags.csv ===
    Write-Info "Writing tags.csv..."
    $tagCounts = @{}
    foreach ($m in $Script:Models) {
        foreach ($t in $m.tags) {
            if (-not $tagCounts.ContainsKey($t)) { $tagCounts[$t] = 0 }
            $tagCounts[$t]++
        }
    }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("tag_slug,tag_name,type,model_count")
    foreach ($k in ($tagCounts.Keys | Sort-Object)) {
        $type = 'topic'
        if ($k -match '^has-|^source-') { $type = 'status' }
        elseif ($k -in @('flexi','articulated','print-in-place','bambu-3mf','multicolor','no-support')) { $type = 'print' }
        elseif ($k -in @('multipart','single-part','assembly','duplicate-detected','needs-review','loose-file','nested-archive','multi-model-suspect')) { $type = 'technical' }
        $cells = @($k, $k, $type, $tagCounts[$k])
        [void]$sb.AppendLine(($cells | ForEach-Object { ConvertTo-CsvCell $_ }) -join ',')
    }
    Write-Utf8Text -Path $tagsCsvPath -Content $sb.ToString() -Bom

    # === categories.csv ===
    Write-Info "Writing categories.csv..."
    $catCounts = @{}
    foreach ($m in $Script:Models) {
        $c = $m.category
        if (-not $catCounts.ContainsKey($c)) { $catCounts[$c] = 0 }
        $catCounts[$c]++
    }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("category_path,parent_path,name,model_count")
    foreach ($k in ($catCounts.Keys | Sort-Object)) {
        $parts = $k -split '/'
        $parent = if ($parts.Count -gt 1) { ($parts[0..($parts.Count - 2)] -join '/') } else { '' }
        $name = $parts[-1]
        $cells = @($k, $parent, $name, $catCounts[$k])
        [void]$sb.AppendLine(($cells | ForEach-Object { ConvertTo-CsvCell $_ }) -join ',')
    }
    Write-Utf8Text -Path $categoriesCsvPath -Content $sb.ToString() -Bom

    # === library.sql (опциональный SQL recovery script) ===
    Write-Info "Writing library.sql (DDL+INSERT)..."
    $sqlPath = Join-Path $databaseDir "library.sql"
    $sqlSb = New-Object System.Text.StringBuilder
    [void]$sqlSb.AppendLine("-- MeshNest library SQL recovery script")
    [void]$sqlSb.AppendLine("-- Generated: $(Get-Date -Format 'o')")
    [void]$sqlSb.AppendLine("CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, slug TEXT UNIQUE, title TEXT, category TEXT, category_confidence REAL, status TEXT, is_reviewed INTEGER);")
    [void]$sqlSb.AppendLine("CREATE TABLE IF NOT EXISTS files (file_id TEXT PRIMARY KEY, model_id TEXT, file_name TEXT, extension TEXT, file_type TEXT, role TEXT, relative_path TEXT, size_bytes INTEGER, sha256 TEXT);")
    [void]$sqlSb.AppendLine("CREATE TABLE IF NOT EXISTS tags (tag_slug TEXT PRIMARY KEY, type TEXT, model_count INTEGER);")
    [void]$sqlSb.AppendLine("CREATE TABLE IF NOT EXISTS categories (category_path TEXT PRIMARY KEY, parent_path TEXT, name TEXT, model_count INTEGER);")
    [void]$sqlSb.AppendLine("BEGIN TRANSACTION;")
    foreach ($m in $Script:Models) {
        $tEsc = ($m.title_clean -replace "'", "''")
        [void]$sqlSb.AppendLine("INSERT INTO models VALUES ('$($m.model_id)','$($m.slug)','$tEsc','$($m.category)',$($m.category_confidence),'needs_review',0);")
    }
    [void]$sqlSb.AppendLine("COMMIT;")
    Write-Utf8Text -Path $sqlPath -Content $sqlSb.ToString()

    Write-Info "Aggregates written: models.csv, files.csv, models.json, tags.csv, categories.csv, library.sql"
}
#endregion

#region Phase 9 — Reports + manifest
function Invoke-Phase9Reports {
    Write-Step "Phase 9: Reports + manifest"

    $reportsDir = Join-Path $OutputPath "reports"

    # === import_summary.md ===
    Write-Info "Writing import_summary.md..."
    $totalScanned = $Script:Files.Count
    $archivesFound = $Script:Archives.Count
    $archivesExtracted = @($Script:Archives | Where-Object { $_.status -eq 'extracted' }).Count
    $archivesFailed = @($Script:Archives | Where-Object { $_.status -in @('extract_failed','broken_archive','password_protected') }).Count
    $archivesDup = @($Script:Archives | Where-Object { $_.status -eq 'exact_dup_archive' }).Count
    $modelsCount = $Script:Models.Count
    $stlTotal = ($Script:Models | ForEach-Object { @($_.materialized_files | Where-Object { $_.bucket -eq 'stl' }).Count } | Measure-Object -Sum).Sum
    $stepTotal = ($Script:Models | ForEach-Object { @($_.materialized_files | Where-Object { $_.bucket -eq 'step' }).Count } | Measure-Object -Sum).Sum
    $threeMfTotal = ($Script:Models | ForEach-Object { @($_.materialized_files | Where-Object { $_.bucket -eq '3mf' }).Count } | Measure-Object -Sum).Sum
    $imgTotal = ($Script:Models | ForEach-Object { @($_.materialized_files | Where-Object { $_.bucket -eq 'image' }).Count } | Measure-Object -Sum).Sum
    $vidTotal = ($Script:Models | ForEach-Object { @($_.materialized_files | Where-Object { $_.bucket -eq 'video' }).Count } | Measure-Object -Sum).Sum
    $docTotal = ($Script:Models | ForEach-Object { @($_.materialized_files | Where-Object { $_.bucket -eq 'doc' }).Count } | Measure-Object -Sum).Sum
    $dupSha = @($Script:DedupMap.Values | Where-Object { $_.Count -gt 1 }).Count
    $unc = @($Script:Models | Where-Object { $_.category -eq 'uncategorized' }).Count
    $needsReview = @($Script:Models | Where-Object { 'needs-review' -in $_.tags }).Count

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("# MeshNest Local Import Summary")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("Input folder: ``$InputPath``")
    [void]$sb.AppendLine("Output folder: ``$OutputPath``")
    [void]$sb.AppendLine("Run ID: ``$($Script:RUN_ID)``")
    [void]$sb.AppendLine("Date: $(Get-Date -Format 'o')")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Result")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("- Total files scanned: $totalScanned")
    [void]$sb.AppendLine("- Archives found: $archivesFound")
    [void]$sb.AppendLine("- Archives extracted: $archivesExtracted")
    [void]$sb.AppendLine("- Archives failed: $archivesFailed")
    [void]$sb.AppendLine("- Archives skipped as exact duplicates: $archivesDup")
    [void]$sb.AppendLine("- Models detected: $modelsCount")
    [void]$sb.AppendLine("- STL files: $stlTotal")
    [void]$sb.AppendLine("- STEP/STP files: $stepTotal")
    [void]$sb.AppendLine("- 3MF files: $threeMfTotal")
    [void]$sb.AppendLine("- Images: $imgTotal")
    [void]$sb.AppendLine("- Videos: $vidTotal")
    [void]$sb.AppendLine("- Documents: $docTotal")
    [void]$sb.AppendLine("- Exact duplicate groups (by SHA): $dupSha")
    [void]$sb.AppendLine("- Uncategorized models: $unc")
    [void]$sb.AppendLine("- Needs review: $needsReview")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Categories")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("| Category | Count |")
    [void]$sb.AppendLine("|---|---:|")
    $catGroups = $Script:Models | Group-Object category | Sort-Object Count -Descending
    foreach ($g in $catGroups) {
        [void]$sb.AppendLine("| $($g.Name) | $($g.Count) |")
    }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Preview status")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("| Status | Count |")
    [void]$sb.AppendLine("|---|---:|")
    $prevGroups = $Script:Models | Group-Object preview_status | Sort-Object Count -Descending
    foreach ($g in $prevGroups) {
        [void]$sb.AppendLine("| $($g.Name) | $($g.Count) |")
    }
    Write-Utf8Text -Path (Join-Path $reportsDir "import_summary.md") -Content $sb.ToString()

    # === duplicate_files.md ===
    Write-Info "Writing duplicate_files.md..."
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("# Duplicate Files (Exact SHA256 matches)")
    [void]$sb.AppendLine("")
    $dupGroups = $Script:DedupMap.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 } | Sort-Object { $_.Value.Count } -Descending
    [void]$sb.AppendLine("Total duplicate groups: $(@($dupGroups).Count)")
    [void]$sb.AppendLine("")
    foreach ($g in $dupGroups) {
        [void]$sb.AppendLine("## SHA: ``$($g.Key.Substring(0,16))…`` ($($g.Value.Count) copies)")
        foreach ($p in $g.Value) {
            [void]$sb.AppendLine("- ``$p``")
        }
        [void]$sb.AppendLine("")
    }
    Write-Utf8Text -Path (Join-Path $reportsDir "duplicate_files.md") -Content $sb.ToString()

    # === uncategorized_models.md ===
    Write-Info "Writing uncategorized_models.md..."
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("# Uncategorized Models")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("These models could not be auto-categorized (confidence < $($Script:CATEGORY_CONFIDENCE_MIN)).")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("| Model ID | Title | Slug | Confidence | Source |")
    [void]$sb.AppendLine("|---|---|---|---:|---|")
    foreach ($m in ($Script:Models | Where-Object { $_.category -eq 'uncategorized' })) {
        $src = if ($m.archive_ref) { $m.archive_ref } else { Split-Path $m.host_dir -Leaf }
        [void]$sb.AppendLine("| $($m.model_id) | $($m.title_clean) | $($m.slug) | $($m.category_confidence) | $src |")
    }
    Write-Utf8Text -Path (Join-Path $reportsDir "uncategorized_models.md") -Content $sb.ToString()

    # === manifest.json ===
    Write-Info "Writing manifest.json..."
    $manifestPath = Join-Path $OutputPath "manifest.json"
    $manifest = [pscustomobject]@{
        format = 'meshnest-import'
        format_version = '1.0'
        created_by = "meshnest-local-organizer-ps (run $($Script:RUN_ID))"
        created_at = (Get-Date -Format 'o')
        source_root = $InputPath
        output_root = $OutputPath
        models_count = $modelsCount
        files_count = ($Script:Models | ForEach-Object { $_.materialized_files.Count } | Measure-Object -Sum).Sum
        categories_count = (@($Script:Models | Select-Object -ExpandProperty category -Unique)).Count
        tags_count = (@($Script:Models | ForEach-Object { $_.tags } | Select-Object -Unique)).Count
        archives_found = $archivesFound
        archives_extracted = $archivesExtracted
        archives_failed = $archivesFailed
        duplicates_found = $dupSha
        uncategorized_count = $unc
        database = [pscustomobject]@{
            models_json = "database/models.json"
            models_csv = "database/models.csv"
            files_csv = "database/files.csv"
            tags_csv = "database/tags.csv"
            categories_csv = "database/categories.csv"
            sqlite = $null
            sqlite_status = "deferred_to_server"
            library_sql = "database/library.sql"
        }
        package = [pscustomobject]@{
            path = "meshnest_import_package.zip"
            sha256 = ""
            size_bytes = 0
        }
    }
    Write-Utf8Json -Path $manifestPath -Object $manifest -Depth 8

    Write-Info "Reports + manifest written."
}
#endregion

#region Phase 10 — Build top-level import package
function Invoke-Phase10ImportPackage {
    Write-Step "Phase 10: Build meshnest_import_package.zip"

    $zipPath = Join-Path $OutputPath "meshnest_import_package.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Write-Info "Removing existing package zip..."
        Remove-Item -LiteralPath $zipPath -Force
    }

    Write-Info "Building meshnest_import_package.zip (excluding staging/ and original_sources/)..."
    $stdoutFile = [System.IO.Path]::GetTempFileName()
    try {
        # 7z a archive.zip <source_glob> -xr!staging -xr!original_sources -xr!logs -xr!meshnest_import_package.zip
        $output = & $Script:SevenZipPath a -tzip -mcu=on -bb0 -bd -y `
            "$zipPath" `
            (Join-Path $OutputPath 'manifest.json') `
            (Join-Path $OutputPath 'database') `
            (Join-Path $OutputPath 'models') `
            (Join-Path $OutputPath 'assets') `
            (Join-Path $OutputPath 'packages') `
            (Join-Path $OutputPath 'reports') 2>&1
        $exit = $LASTEXITCODE
        if ($exit -ne 0) {
            Write-Warn "7-Zip add returned exit $exit"
            $output | Select-Object -Last 5 | ForEach-Object { Write-Warn "  $_" }
        }

        if (-not (Test-Path -LiteralPath $zipPath)) {
            Write-Err "Package zip not created!"
            return
        }

        $zipSize = (Get-Item -LiteralPath $zipPath).Length
        $zipSizeMB = [math]::Round($zipSize / 1MB, 1)
        Write-Info "Package created: $zipSizeMB MB"
        if ($zipSize -ge $Script:IMPORT_PKG_WARN_SIZE) {
            Write-Warn "Package exceeds 4 GB ($zipSizeMB MB) — server may not accept single-upload."
        }

        # SHA256 of package
        Write-Info "Computing SHA256 of package..."
        $pkgSha = Get-FileSha256Fast -Path $zipPath

        # Patch manifest.json with package sha + size
        $manifestPath = Join-Path $OutputPath "manifest.json"
        $manifestObj = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $manifestObj.package.sha256 = $pkgSha
        $manifestObj.package.size_bytes = $zipSize
        Write-Utf8Json -Path $manifestPath -Object $manifestObj -Depth 8
        Write-Info "Manifest patched with package SHA: $($pkgSha.Substring(0,16))…"
    } finally {
        Remove-Item $stdoutFile -ErrorAction SilentlyContinue
    }
}
#endregion

#region Main
function Main {
    Write-Host ""
    Write-Host "================================================================"
    Write-Host " MeshNest Local Organizer v$($Script:VERSION)"
    Write-Host " Input  : $InputPath"
    Write-Host " Output : $OutputPath"
    Write-Host " Resume : $Resume"
    Write-Host "================================================================"

    Invoke-Phase0PreFlight
    Invoke-Phase1Scan
    Invoke-Phase2Hash
    Invoke-Phase3Extract
    Invoke-Phase4ReScan
    Invoke-Phase5GroupModels
    Invoke-Phase6Categorize
    Invoke-Phase7Materialize
    Invoke-Phase8Aggregates
    Invoke-Phase9Reports
    Invoke-Phase10ImportPackage

    $elapsed = (Get-Date) - $Script:STARTED_AT
    Write-Host ""
    Write-Host "================================================================"
    Write-Host " DONE in $($elapsed.ToString('hh\:mm\:ss'))"
    Write-Host "================================================================"
}

try {
    Main
} catch {
    Write-Err "FATAL: $_"
    Write-Err $_.ScriptStackTrace
    exit 1
}
#endregion
