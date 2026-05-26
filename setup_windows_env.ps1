# Windows 环境配置脚本（PowerShell）
# 用法：在安装完 Miniconda 后，以管理员身份运行 PowerShell，执行此脚本
#
#   cd "D:\谷歌"
#   .\setup_windows_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "医学 RAG 实习工程 - Windows 环境配置" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 conda 是否可用
try {
    $condaVersion = conda --version
    Write-Host "[OK] Conda 已安装: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] Conda 未安装或未添加到 PATH" -ForegroundColor Red
    Write-Host "请先安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Yellow
    Write-Host "安装时勾选 'Add Miniconda3 to my PATH environment variable'" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "步骤 1: 创建 conda 环境 med-rag-verify (Python 3.11)" -ForegroundColor Cyan
Write-Host "---------------------------------------------------"

# 检查环境是否已存在
$envExists = conda env list | Select-String "med-rag-verify"
if ($envExists) {
    Write-Host "[跳过] 环境 med-rag-verify 已存在" -ForegroundColor Yellow
} else {
    Write-Host "正在创建环境..."
    conda create -n med-rag-verify python=3.11 -y
    Write-Host "[OK] 环境创建完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "步骤 2: 激活环境并安装依赖" -ForegroundColor Cyan
Write-Host "---------------------------------------------------"

# 激活环境并安装依赖
conda activate med-rag-verify

Write-Host "正在安装阶段 01 依赖（这可能需要几分钟）..."
pip install -r "01 验证模型\requirements.txt"

Write-Host "正在安装阶段 02 增补依赖..."
pip install -r "02 数据处理\requirements.txt"

Write-Host ""
Write-Host "[OK] 依赖安装完成" -ForegroundColor Green

Write-Host ""
Write-Host "步骤 3: 配置外接硬盘环境变量" -ForegroundColor Cyan
Write-Host "---------------------------------------------------"

$dataRoot = "E:\med-llm-rag-datasets"
Write-Host "外接硬盘数据目录: $dataRoot"

# 设置当前会话环境变量
$env:MED_RAG_DATA_ROOT = $dataRoot
$env:PMC_XML_ROOT = "$dataRoot\extracted"
$env:MED_RAG_JSONL = "$dataRoot\processed\oa_comm_slim.jsonl"

Write-Host ""
Write-Host "环境变量已设置（当前会话）:" -ForegroundColor Green
Write-Host "  MED_RAG_DATA_ROOT = $env:MED_RAG_DATA_ROOT"
Write-Host "  PMC_XML_ROOT      = $env:PMC_XML_ROOT"
Write-Host "  MED_RAG_JSONL     = $env:MED_RAG_JSONL"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "配置完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "后续步骤:" -ForegroundColor Yellow
Write-Host "1. 打开 VS Code，选择 File -> Open Folder -> D:\谷歌\02 数据处理"
Write-Host "2. 打开 notebooks/med-data-EDA-partB.ipynb"
Write-Host "3. 选择内核: med-rag-verify"
Write-Host "4. 等待外接硬盘数据迁移完成后，运行 notebook"
Write-Host ""
Write-Host "每次新开 PowerShell 需要重新设置环境变量:" -ForegroundColor Yellow
Write-Host '  $env:MED_RAG_DATA_ROOT = "E:\med-llm-rag-datasets"'
Write-Host '  $env:PMC_XML_ROOT = "$env:MED_RAG_DATA_ROOT\extracted"'
Write-Host '  $env:MED_RAG_JSONL = "$env:MED_RAG_DATA_ROOT\processed\oa_comm_slim.jsonl"'
