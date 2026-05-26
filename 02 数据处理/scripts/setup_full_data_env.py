#!/usr/bin/env python
"""全量期外接盘环境变量设置（跨平台 Python 版本）

Windows 用法（PowerShell）：
    python scripts/setup_full_data_env.py
    # 然后根据输出设置环境变量，或直接在 Python/notebook 中调用 setup_env()

Unix 用法：
    source ./scripts/setup_full_data_env.sh  # 原 shell 版本仍可用
"""

import os
import sys
from pathlib import Path


def get_default_data_root() -> str:
    """根据操作系统返回默认数据根目录"""
    if os.name == "nt":
        return "E:/med-llm-rag-datasets"
    else:
        return "/Volumes/Lexar/med-llm-rag-datasets"


def setup_env(data_root: str | None = None) -> dict[str, str]:
    """设置环境变量并返回配置字典"""
    root = data_root or get_default_data_root()
    root_path = Path(root)

    config = {
        "MED_RAG_DATA_ROOT": root,
        "PMC_XML_ROOT": str(root_path / "extracted"),
        "MED_RAG_JSONL": str(root_path / "processed" / "oa_comm_slim.jsonl"),
    }

    for k, v in config.items():
        os.environ[k] = v

    return config


def main():
    root = get_default_data_root()
    root_path = Path(root)

    if not root_path.exists():
        print(f"警告: 数据目录不存在 — {root}")
        print("请确保外接硬盘已连接，或修改 data_root 参数")
        print()

    config = setup_env(root)

    print("=" * 60)
    print("全量数据环境变量配置")
    print("=" * 60)
    for k, v in config.items():
        print(f"{k}={v}")
    print()

    if os.name == "nt":
        print("在 PowerShell 中设置环境变量：")
        for k, v in config.items():
            print(f'$env:{k} = "{v}"')
        print()
        print("或在 CMD 中：")
        for k, v in config.items():
            print(f'set {k}={v}')
    else:
        print("在 shell 中设置环境变量：")
        for k, v in config.items():
            print(f'export {k}="{v}"')

    print()
    print("创建目录结构...")
    for subdir in ["raw", "extracted", "processed/stats"]:
        p = root_path / subdir
        p.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {p}")

    print()
    print("完成！")


if __name__ == "__main__":
    main()
