# 按阶段顺序安装全部 Python 依赖（路径含空格时 pip -r 根清单不可用）
# 用法：
#   cd "D:\谷歌"
#   .\install_all_requirements.ps1
#
# 前置：conda activate med-rag-verify

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

$Stages = @(
    "01 验证模型\requirements.txt",
    "02 数据处理\requirements.txt",
    "04 向量化与索引构建\requirements.txt",
    "05 检索系统开发第一部分\requirements.txt",
    "06 检索系统开发第二部分\requirements.txt",
    "07 生成模块与提示词工程第一部分\requirements.txt",
    "08 生成模块与提示词工程第二部分\requirements.txt",
    "09 生成答案评估，缓存策略与批量处理\requirements.txt",
    "10 强约束规则开发与幻觉抑制\requirements.txt"
    # 11：待阶段 0 创建 requirements.txt（fastapi/uvicorn）后再加入
)

Write-Host "安装医学 RAG 工程依赖（01→10，跳过 03 无新增）..." -ForegroundColor Cyan

foreach ($rel in $Stages) {
    $path = Join-Path $Root $rel
    if (-not (Test-Path $path)) {
        Write-Host "[跳过] 不存在: $rel" -ForegroundColor Yellow
        continue
    }
    Write-Host ">> pip install -r $rel" -ForegroundColor Green
    pip install -r $path
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "[完成] 全部阶段依赖已安装。" -ForegroundColor Green
Write-Host "04 全量 GPU 向量化请另运行: .\setup_stage04_gpu.ps1" -ForegroundColor Yellow
