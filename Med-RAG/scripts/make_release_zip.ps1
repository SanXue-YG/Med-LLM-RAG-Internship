# Med-RAG Release Zip
# Usage: powershell -File Med-RAG/scripts/make_release_zip.ps1

$ErrorActionPreference = "Stop"
$HomeDir = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $HomeDir "dist"
$Stamp = Get-Date -Format "yyyyMMdd"
$ZipPath = Join-Path $OutDir "Med-RAG-$Stamp.zip"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

$temp = Join-Path $env:TEMP "med-rag-pack-$Stamp"
if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $temp | Out-Null

$dest = Join-Path $temp "Med-RAG"
robocopy $HomeDir $dest /E /XD `
  node_modules dist .git data\chroma data\bm25 data\raw_uploads data\chat data\logs data\documents `
  /XF *.sqlite *.zip `
  /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null

# Keep data skeleton + lexicons + processed placeholder
$keep = @(
  "data\README.md",
  "data\lexicons",
  "data\processed\.gitkeep",
  "data\chroma\.gitkeep",
  "data\chat\.gitkeep",
  "data\logs\.gitkeep",
  "data\raw_uploads\.gitkeep",
  "data\documents\sample\.gitkeep",
  "data\documents\full\.gitkeep",
  "data\bm25\.gitkeep"
)
foreach ($rel in $keep) {
  $src = Join-Path $HomeDir $rel
  $dst = Join-Path $dest $rel
  if (Test-Path $src) {
    $parent = Split-Path $dst -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item $src $dst -Recurse -Force
  }
}

# Data placement note inside zip
@"
# 数据放置说明

本 zip 不含向量库与大 JSONL。请任选：

1. 从完整仓库复制 Dataset 样本资产到 Med-RAG/data/（见 data/README.md）
2. 启动后用前端回形针 / POST /api/v1/ingest/upload 上传小样本

部署步骤见 docs/部署文档.md
"@ | Set-Content -Encoding UTF8 (Join-Path $dest "DATA_SETUP.txt")

Compress-Archive -Path $dest -DestinationPath $ZipPath -Force
Remove-Item $temp -Recurse -Force
Write-Output "Wrote $ZipPath"
Get-Item $ZipPath | Select-Object FullName, Length
