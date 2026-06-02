# 04 阶段全量向量化 — GPU 环境补充脚本（PowerShell）
# 用法：在 med-rag-verify 已创建、01/02 依赖已安装后执行
#
#   cd "D:\谷歌"
#   .\setup_stage04_gpu.ps1
#
# 背景：setup_windows_env.ps1 按 01 requirements 从默认 PyPI 安装 torch，
#       Windows 会得到 CPU 版（x.y.z+cpu）。全量 610 万 chunks 嵌入需 CUDA 版。

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "04 全量向量化 — CUDA 版 PyTorch 安装" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$envExists = conda env list | Select-String "med-rag-verify"
if (-not $envExists) {
    Write-Host "[错误] 未找到 med-rag-verify 环境，请先运行 .\setup_windows_env.ps1" -ForegroundColor Red
    exit 1
}

function Invoke-MedRagPython {
    param([string[]]$Args)
    conda run -n med-rag-verify python @Args
}

Write-Host "步骤 1: 检查 NVIDIA 驱动" -ForegroundColor Cyan
try {
    nvidia-smi | Out-Host
} catch {
    Write-Host "[警告] nvidia-smi 不可用，请先安装 NVIDIA 显卡驱动" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "步骤 2: 卸载 CPU 版 torch（若存在）" -ForegroundColor Cyan
Invoke-MedRagPython -Args @("-m", "pip", "uninstall", "torch", "-y")

Write-Host ""
Write-Host "步骤 3: 安装 CUDA 12.4 版 PyTorch（约 2.5 GB，需耐心等待）" -ForegroundColor Cyan
Invoke-MedRagPython -Args @("-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cu124")

Write-Host ""
Write-Host "步骤 4: 安装 04 阶段依赖" -ForegroundColor Cyan
Invoke-MedRagPython -Args @("-m", "pip", "install", "-r", "04 向量化与索引构建\requirements.txt")

Write-Host ""
Write-Host "步骤 5: 修复 pyarrow（Windows 上损坏会导致 Jupyter 内核崩溃）" -ForegroundColor Cyan
Invoke-MedRagPython -Args @("-m", "pip", "install", "--force-reinstall", "pyarrow")

Write-Host ""
Write-Host "步骤 6: 验证 GPU + 嵌入模型" -ForegroundColor Cyan
Invoke-MedRagPython -Args @("-c", "import torch; from sentence_transformers import SentenceTransformer; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); m=SentenceTransformer('BAAI/bge-small-en-v1.5', device='cuda' if torch.cuda.is_available() else 'cpu'); print('bge dim:', m.get_embedding_dimension())")

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "完成。请打开 vectorize-index-full.ipynb 运行 C0 确认 cuda_available=True" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
