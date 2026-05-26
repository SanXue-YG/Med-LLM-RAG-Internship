"""全量期（阶段 B）工具：下载、解压校验、构建 slim、与验证期对比。"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DATA_ROOT = os.environ.get("MED_RAG_DATA_ROOT") or (
    "E:/med-llm-rag-datasets" if os.name == "nt" else "/Volumes/Lexar/med-llm-rag-datasets"
)
# NCBI 2026-04 起 legacy 包迁至 deprecated/（见 https://www.ncbi.nlm.nih.gov/pmc/tools/ftp/）
OA_COMM_FTP_XML_DIR = (
    "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_bulk/oa_comm/xml/"
)
OA_COMM_FTP_BASE = OA_COMM_FTP_XML_DIR  # 兼容旧名
FILE_LIST_CACHE_MARKER = "# pmc_source: deprecated/oa_bulk/oa_comm/xml"
_NCBI_USER_AGENT = "med-rag-eda/1.0 (research; contact: local)"


@dataclass
class FullScalePaths:
    data_root: str
    raw_dir: str
    extracted_dir: str
    processed_dir: str
    stats_dir: str
    slim_jsonl: str
    pmcid_index: str
    skipped_log: str

    @classmethod
    def from_env(cls, data_root: str | None = None) -> FullScalePaths:
        root = os.path.abspath(
            data_root or os.environ.get("MED_RAG_DATA_ROOT") or DEFAULT_DATA_ROOT
        )
        proc = os.path.join(root, "processed")
        return cls(
            data_root=root,
            raw_dir=os.path.join(root, "raw"),
            extracted_dir=os.path.join(root, "extracted"),
            processed_dir=proc,
            stats_dir=os.path.join(proc, "stats"),
            slim_jsonl=os.path.join(proc, "oa_comm_slim.jsonl"),
            pmcid_index=os.path.join(proc, "pmcid_index.jsonl"),
            skipped_log=os.path.join(proc, "skipped_no_abstract.txt"),
        )

    def ensure_dirs(self) -> None:
        for d in (
            self.raw_dir,
            self.extracted_dir,
            self.processed_dir,
            self.stats_dir,
        ):
            os.makedirs(d, exist_ok=True)

    def apply_env(self) -> None:
        """写入 os.environ，供 build_jsonl / notebook 使用。"""
        os.environ["MED_RAG_DATA_ROOT"] = self.data_root
        os.environ["PMC_XML_ROOT"] = self.extracted_dir
        os.environ["MED_RAG_JSONL"] = self.slim_jsonl
        self.ensure_dirs()


@dataclass
class ExtractReport:
    archive: str
    xml_in_tar: int
    extracted_ok: bool
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "archive": self.archive,
            "xml_in_tar": self.xml_in_tar,
            "extracted_ok": self.extracted_ok,
            "error": self.error,
        }


def check_data_root_mount(paths: FullScalePaths) -> dict[str, Any]:
    """检查外接盘是否挂载、可写。"""
    root = paths.data_root
    ok = os.path.isdir(root)
    writable = False
    if ok:
        test = os.path.join(root, ".write_test_notebook")
        try:
            with open(test, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test)
            writable = True
        except OSError:
            writable = False
    usage = shutil.disk_usage(root) if ok else None
    return {
        "data_root": root,
        "mounted": ok,
        "writable": writable,
        "disk_total_gb": round(usage.total / 1e9, 1) if usage else None,
        "disk_free_gb": round(usage.free / 1e9, 1) if usage else None,
    }


def _urlopen(url: str, *, timeout: int = 120):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _NCBI_USER_AGENT},
    )
    return urllib.request.urlopen(req, timeout=timeout)


def _parse_ftp_html_tar_gz_list(html: str) -> list[str]:
    """从 Apache 目录页解析 .tar.gz 链接。"""
    names = re.findall(r'href="([^"/]+\.tar\.gz)"', html, flags=re.IGNORECASE)
    return sorted(set(names))


def fetch_oa_comm_file_list(
    *,
    cache_path: str | None = None,
    timeout: int = 120,
    force_refresh: bool = False,
    baseline_only: bool = False,
    include_incr: bool = True,
    xml_dir_url: str = OA_COMM_FTP_XML_DIR,
) -> list[str]:
    """拉取 PMC oa_comm XML bulk 包文件名（解析 FTP 目录页，非已废弃的 file_list.txt）。"""
    if (
        cache_path
        and os.path.isfile(cache_path)
        and not force_refresh
    ):
        with open(cache_path, encoding="utf-8") as f:
            lines = f.readlines()
        if lines and FILE_LIST_CACHE_MARKER in lines[0]:
            names = [
                ln.strip()
                for ln in lines[1:]
                if ln.strip().endswith(".tar.gz")
            ]
            if names:
                return _filter_archive_names(
                    names,
                    baseline_only=baseline_only,
                    include_incr=include_incr,
                )

    listing_url = xml_dir_url.rstrip("/") + "/"
    with _urlopen(listing_url, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    names = _parse_ftp_html_tar_gz_list(html)
    if not names:
        raise RuntimeError(
            f"未能从目录页解析 tar.gz 列表: {listing_url}\n"
            "请检查网络，或查阅 https://www.ncbi.nlm.nih.gov/pmc/tools/ftp/"
        )

    names = _filter_archive_names(
        names,
        baseline_only=baseline_only,
        include_incr=include_incr,
    )

    if cache_path:
        os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(FILE_LIST_CACHE_MARKER + "\n")
            f.write("\n".join(names) + "\n")
    return names


def _filter_archive_names(
    names: list[str],
    *,
    baseline_only: bool,
    include_incr: bool,
) -> list[str]:
    out: list[str] = []
    for n in names:
        is_baseline = ".baseline." in n
        is_incr = ".incr." in n
        if baseline_only and not is_baseline:
            continue
        if not include_incr and is_incr:
            continue
        if is_baseline or is_incr:
            out.append(n)
    return sorted(out)


def download_archives(
    names: list[str],
    dest_dir: str,
    *,
    max_files: int | None = None,
    skip_existing: bool = True,
    base_url: str = OA_COMM_FTP_XML_DIR,
) -> list[dict[str, Any]]:
    """下载 tar.gz 到 dest_dir；返回每文件状态。"""
    os.makedirs(dest_dir, exist_ok=True)
    todo = names[:max_files] if max_files else names
    results: list[dict[str, Any]] = []

    for i, name in enumerate(todo, 1):
        dest = os.path.join(dest_dir, name)
        if skip_existing and os.path.isfile(dest) and os.path.getsize(dest) > 0:
            results.append(
                {"name": name, "status": "skipped", "path": dest, "bytes": os.path.getsize(dest)}
            )
            continue
        url = base_url + name
        print(f"[{i}/{len(todo)}] 下载 {name} …")
        try:
            urllib.request.urlretrieve(url, dest)
            results.append(
                {
                    "name": name,
                    "status": "ok",
                    "path": dest,
                    "bytes": os.path.getsize(dest),
                }
            )
        except Exception as e:
            results.append({"name": name, "status": "error", "error": str(e)})
    return results


def _xml_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    return [
        m
        for m in tar.getmembers()
        if m.isfile() and m.name.lower().endswith(".xml")
    ]


def _check_archive_extracted(
    archive_path: str,
    extract_root: str,
    sample_ratio: float = 0.1,
) -> tuple[bool, int, int]:
    """检查压缩包是否已解压完成（通过抽样检查XML文件是否存在）。
    
    Returns:
        (is_complete, total_files, existing_files)
    """
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            members = _xml_members(tar)
            if not members:
                return False, 0, 0
            
            total = len(members)
            # 抽样检查：至少检查10个，最多检查100个
            sample_size = max(10, min(100, int(total * sample_ratio)))
            step = max(1, total // sample_size)
            samples = members[::step][:sample_size]
            
            existing = 0
            for m in samples:
                target_path = Path(extract_root) / m.name
                if target_path.exists() and target_path.stat().st_size > 0:
                    existing += 1
            
            # 如果抽样中90%以上文件存在，认为已解压完成
            is_complete = (existing / len(samples)) >= 0.9 if samples else False
            return is_complete, total, existing
    except Exception:
        return False, 0, 0


def extract_archive(
    archive_path: str,
    extract_root: str,
    *,
    dry_run: bool = False,
    skip_existing: bool = False,
) -> ExtractReport:
    """解压单个 tar.gz；校验包内 XML 成员是否均可解压。
    
    Args:
        skip_existing: 如果为True，检测已解压的文件并跳过
    """
    name = os.path.basename(archive_path)
    try:
        # 检查是否已解压完成
        if skip_existing:
            is_complete, total, existing = _check_archive_extracted(
                archive_path, extract_root
            )
            if is_complete:
                print(f"    [跳过] 已解压完成 ({total} 个XML文件)")
                return ExtractReport(name, total, True)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            members = _xml_members(tar)
            if dry_run:
                return ExtractReport(name, len(members), True)
            
            # 支持增量解压：只解压不存在的文件
            if skip_existing:
                members_to_extract = []
                for m in members:
                    target_path = Path(extract_root) / m.name
                    if not target_path.exists():
                        members_to_extract.append(m)
                
                if not members_to_extract:
                    print(f"    [跳过] 所有文件已存在")
                    return ExtractReport(name, len(members), True)
                
                print(f"    解压 {len(members_to_extract)}/{len(members)} 个文件...")
                tar.extractall(path=extract_root, members=members_to_extract)
            else:
                # 仅解压 XML（oa_comm 包内通常全是 XML）
                if members:
                    tar.extractall(path=extract_root, members=members)
                else:
                    tar.extractall(path=extract_root)
            
            return ExtractReport(name, len(members), True)
    except Exception as e:
        return ExtractReport(name, 0, False, error=str(e))


def extract_all_archives(
    raw_dir: str,
    extract_root: str,
    *,
    pattern: str = "*.tar.gz",
    dry_run: bool = False,
    skip_existing: bool = False,
) -> list[ExtractReport]:
    """解压所有压缩包。
    
    Args:
        skip_existing: 如果为True，跳过已解压完成的包（支持断点续传）
    """
    archives = sorted(Path(raw_dir).glob(pattern))
    reports: list[ExtractReport] = []
    os.makedirs(extract_root, exist_ok=True)
    
    skipped = 0
    for i, arch in enumerate(archives, 1):
        print(f"[{i}/{len(archives)}] 解压 {arch.name} …")
        report = extract_archive(
            str(arch), extract_root, 
            dry_run=dry_run, 
            skip_existing=skip_existing
        )
        reports.append(report)
        if skip_existing and report.extracted_ok and "跳过" in str(report):
            skipped += 1
    
    if skip_existing:
        print(f"\n总计: {len(archives)} 个包, 跳过 {skipped} 个已完成")
    
    return reports


def remove_archives(
    archive_paths: list[str],
    *,
    only_if_ok: bool = True,
    ok_names: set[str] | None = None,
) -> list[str]:
    """删除已校验通过的压缩包，释放空间。"""
    removed: list[str] = []
    for p in archive_paths:
        name = os.path.basename(p)
        if only_if_ok and ok_names is not None and name not in ok_names:
            continue
        if os.path.isfile(p):
            os.remove(p)
            removed.append(p)
    return removed


def count_xml_files(xml_root: str, use_cache: bool = True) -> int:
    """统计XML文件数量。大目录耗时较长，可使用缓存。"""
    cache_file = Path(xml_root) / ".xml_count_cache.txt"
    
    if use_cache and cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            pass
    
    count = sum(1 for _ in Path(xml_root).rglob("*.xml"))
    
    if use_cache:
        try:
            with open(cache_file, "w") as f:
                f.write(str(count))
        except IOError:
            pass
    
    return count


def count_tar_gz(raw_dir: str) -> int:
    return len(list(Path(raw_dir).glob("*.tar.gz")))


def list_pmc_subdirs(extracted_dir: str) -> list[dict[str, Any]]:
    """快速列出extracted下的PMC子文件夹及其基本信息（不递归统计XML数量）。"""
    subdirs = []
    root = Path(extracted_dir)
    if not root.exists():
        return subdirs
    
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name.startswith("PMC"):
            subdirs.append({
                "name": d.name,
                "path": str(d),
            })
    return subdirs


def quick_check_data_root(paths: "FullScalePaths") -> dict[str, Any]:
    """快速检查数据目录（不统计文件数量，避免大目录耗时）。"""
    root = paths.data_root
    ok = os.path.isdir(root)
    writable = False
    if ok:
        test = os.path.join(root, ".write_test_notebook")
        try:
            with open(test, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test)
            writable = True
        except OSError:
            writable = False
    usage = shutil.disk_usage(root) if ok else None
    
    # 快速检查子目录存在性
    raw_exists = os.path.isdir(paths.raw_dir)
    extracted_exists = os.path.isdir(paths.extracted_dir)
    processed_exists = os.path.isdir(paths.processed_dir)
    
    return {
        "data_root": root,
        "mounted": ok,
        "writable": writable,
        "disk_total_gb": round(usage.total / 1e9, 1) if usage else None,
        "disk_free_gb": round(usage.free / 1e9, 1) if usage else None,
        "raw_exists": raw_exists,
        "extracted_exists": extracted_exists,
        "processed_exists": processed_exists,
    }


def run_project_script(
    script_name: str,
    project_dir: str,
    extra_args: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """在 02 工程下执行脚本（跨平台：Windows 用 Python 等效实现，Unix 用 shell）。"""
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    run_env["PROJECT_DIR"] = project_dir

    # Windows: 调用等效 Python 脚本
    if os.name == "nt":
        py_script = os.path.join(project_dir, "scripts", script_name.replace(".sh", ".py"))
        if os.path.isfile(py_script):
            cmd = ["python", py_script] + (extra_args or [])
        else:
            raise FileNotFoundError(
                f"Windows 不支持 .sh 脚本，且未找到等效 Python 脚本: {py_script}\n"
                f"请手动运行或使用 WSL/Git Bash。"
            )
    else:
        # Unix: 使用 zsh/bash
        script = os.path.join(project_dir, "scripts", script_name)
        if not os.path.isfile(script):
            raise FileNotFoundError(script)
        shell = "zsh" if os.path.exists("/bin/zsh") else "bash"
        cmd = [shell, script] + (extra_args or [])

    print("执行:", " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=project_dir,
        env=run_env,
        capture_output=True,
        text=True,
    )


def read_jsonl_sample(
    jsonl_path: str,
    n: int,
    *,
    seed: int = 42,
    reservoir: bool = True,
) -> list[dict[str, Any]]:
    """从超大 jsonl 均匀抽样 n 行（reservoir sampling）。"""
    if n <= 0:
        return []
    rng = random.Random(seed)
    sample: list[dict[str, Any]] = []
    with open(jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            if not reservoir:
                if i < n:
                    sample.append(row)
                else:
                    break
                continue
            if i < n:
                sample.append(row)
            else:
                j = rng.randint(0, i)
                if j < n:
                    sample[j] = row
    return sample


def count_jsonl_lines(jsonl_path: str) -> int:
    n = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for _ in f:
            n += 1
    return n


def count_skipped(skipped_log: str) -> int:
    if not os.path.isfile(skipped_log):
        return 0
    with open(skipped_log, encoding="utf-8") as f:
        return sum(1 for ln in f if ln.strip())


def load_verify_baseline(tables_dir: str) -> dict[str, Any]:
    """读取验证期 outputs/tables 中的对照指标。"""
    import pandas as pd

    base: dict[str, Any] = {"n_clean": 97, "n_sample": 100}
    pct_path = os.path.join(tables_dir, "token_percentiles.csv")
    if os.path.isfile(pct_path):
        pct = pd.read_csv(pct_path)
        row = pct[pct["field"] == "title+abstract"]
        if not row.empty:
            base["p95_retrieval"] = float(row["p95"].iloc[0])
            base["p99_retrieval"] = float(row["p99"].iloc[0])
    chunk_path = os.path.join(tables_dir, "chunk_strategy_summary.csv")
    if os.path.isfile(chunk_path):
        cs = pd.read_csv(chunk_path)
        cs = cs[cs["pmcid"] != "__summary__"]
        base["single_pct"] = round(100 * (cs["n_chunks"] == 1).mean(), 1)
        base["multi_pct"] = round(100 * (cs["n_chunks"] > 1).mean(), 1)
    base["pct_over_512"] = round(100 * 14 / 97, 1)  # 验证期 14/97
    return base


def compare_to_baseline(
    full_metrics: dict[str, Any],
    baseline: dict[str, Any],
    *,
    tolerances: dict[str, float] | None = None,
):
    """生成验证期 vs 全量（抽样）对比表。"""
    import pandas as pd

    tol = tolerances or {
        "abstract_skip_rate_pct": 2.0,
        "p95_retrieval": 150.0,
        "pct_over_512": 8.0,
        "single_pct": 12.0,
    }
    rows = []

    def add_row(metric: str, verify_val, full_val, tol_key: str | None = None):
        delta = None
        ok = None
        if verify_val is not None and full_val is not None:
            try:
                delta = float(full_val) - float(verify_val)
                if tol_key and tol_key in tol:
                    ok = abs(delta) <= tol[tol_key]
            except (TypeError, ValueError):
                pass
        rows.append(
            {
                "metric": metric,
                "verify_97": verify_val,
                "full_sample": full_val,
                "delta": delta,
                "within_tolerance": ok,
            }
        )

    add_row(
        "abstract 丢弃率 (%)",
        round(100 * 3 / 100, 1),
        full_metrics.get("abstract_skip_rate_pct"),
        "abstract_skip_rate_pct",
    )
    add_row(
        "P95 retrieval tokens",
        baseline.get("p95_retrieval"),
        full_metrics.get("p95_retrieval"),
        "p95_retrieval",
    )
    add_row(
        ">512 占比 (%)",
        baseline.get("pct_over_512"),
        full_metrics.get("pct_over_512"),
        "pct_over_512",
    )
    add_row(
        "单块占比 (%)",
        baseline.get("single_pct"),
        full_metrics.get("single_pct"),
        "single_pct",
    )
    add_row(
        "多块占比 (%)",
        baseline.get("multi_pct"),
        full_metrics.get("multi_pct"),
        "single_pct",
    )
    return pd.DataFrame(rows)


def strategy_verdict(compare_df) -> str:
    """根据对比表给出是否沿用验证期策略的简短结论。"""
    import pandas as pd

    if compare_df.empty:
        return "无法评估：缺少对比数据。"
    fails = compare_df[
        compare_df["within_tolerance"].eq(False)
    ]
    if fails.empty:
        return (
            "全量抽样指标与验证期 97 篇在约定容差内一致，"
            "建议**沿用** chunk_strategy_config.json（400/80；body 512/80；首轮仅索引 title+abstract）。"
        )
    bad = ", ".join(fails["metric"].astype(str).tolist())
    return (
        f"以下指标偏离验证期较多：{bad}。"
        "建议先复核 slim 构建与抽样规模，再决定是否微调切块参数或清洗规则；"
        "并更新《RAG数据分析与设计说明》「全量 vs 验证期」小节。"
    )


def build_jsonl_for_subdir(
    subdir_path: str,
    output_path: str,
    *,
    slim: bool = True,
    skip_no_abstract: bool = True,
    skipped_log_path: str | None = None,
) -> dict[str, Any]:
    """为单个PMC子文件夹构建jsonl（用于分批处理）。"""
    import sys
    sys.path.insert(0, os.path.join(os.environ.get("PROJECT_DIR", "."), "src"))
    
    from parse_pmc import has_abstract, parse_pmc_xml, record_for_jsonl
    from tqdm import tqdm
    
    stats = {"ok": 0, "skipped": 0, "failed": 0, "dropped_no_abstract": 0}
    xml_files = sorted(Path(subdir_path).rglob("*.xml"))
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    skipped_fout = None
    if skipped_log_path:
        os.makedirs(os.path.dirname(os.path.abspath(skipped_log_path)), exist_ok=True)
        skipped_fout = open(skipped_log_path, "a", encoding="utf-8")
    
    try:
        with open(output_path, "w", encoding="utf-8") as fout:
            for xml_path in tqdm(xml_files, desc=Path(subdir_path).name):
                try:
                    rec = parse_pmc_xml(xml_path)
                except Exception:
                    stats["failed"] += 1
                    continue
                
                pmcid = (rec.get("pmcid") or "").strip()
                if not pmcid:
                    stats["skipped"] += 1
                    continue
                
                if skip_no_abstract and not has_abstract(rec):
                    stats["dropped_no_abstract"] += 1
                    if skipped_fout:
                        skipped_fout.write(pmcid + "\n")
                    continue
                
                line_rec = record_for_jsonl(rec, slim=slim)
                fout.write(json.dumps(line_rec, ensure_ascii=False) + "\n")
                stats["ok"] += 1
    finally:
        if skipped_fout:
            skipped_fout.close()
    
    return stats


def get_batch_progress(processed_dir: str) -> dict[str, Any]:
    """获取分批处理进度。"""
    shards_dir = os.path.join(processed_dir, "shards")
    progress_file = os.path.join(shards_dir, "progress.json")
    
    if os.path.isfile(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {"completed": [], "stats": {}}


def save_batch_progress(processed_dir: str, progress: dict[str, Any]) -> None:
    """保存分批处理进度。"""
    shards_dir = os.path.join(processed_dir, "shards")
    os.makedirs(shards_dir, exist_ok=True)
    progress_file = os.path.join(shards_dir, "progress.json")
    
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def build_jsonl_batched(
    extracted_dir: str,
    processed_dir: str,
    *,
    slim: bool = True,
    skip_no_abstract: bool = True,
    resume: bool = True,
) -> dict[str, Any]:
    """分批构建jsonl（按PMC子文件夹），支持断点续传。
    
    每个子文件夹生成一个shard文件：processed/shards/PMCxxxxx.jsonl
    进度保存在：processed/shards/progress.json
    
    Returns:
        {"completed": [...], "stats": {...}, "total_ok": int}
    """
    shards_dir = os.path.join(processed_dir, "shards")
    os.makedirs(shards_dir, exist_ok=True)
    
    subdirs = list_pmc_subdirs(extracted_dir)
    if not subdirs:
        print("未找到PMC子文件夹")
        return {"completed": [], "stats": {}, "total_ok": 0}
    
    # 加载或初始化进度
    progress = get_batch_progress(processed_dir) if resume else {"completed": [], "stats": {}}
    completed_set = set(progress["completed"])
    
    skipped_log = os.path.join(processed_dir, "skipped_no_abstract.txt")
    total_ok = sum(progress["stats"].get(name, {}).get("ok", 0) for name in completed_set)
    
    print(f"共 {len(subdirs)} 个子文件夹，已完成 {len(completed_set)} 个")
    
    for i, subdir in enumerate(subdirs, 1):
        name = subdir["name"]
        
        if name in completed_set:
            print(f"[{i}/{len(subdirs)}] {name} — 已完成，跳过")
            continue
        
        shard_path = os.path.join(shards_dir, f"{name}.jsonl")
        print(f"[{i}/{len(subdirs)}] 处理 {name} ...")
        
        stats = build_jsonl_for_subdir(
            subdir["path"],
            shard_path,
            slim=slim,
            skip_no_abstract=skip_no_abstract,
            skipped_log_path=skipped_log,
        )
        
        # 更新进度
        progress["completed"].append(name)
        progress["stats"][name] = stats
        total_ok += stats["ok"]
        save_batch_progress(processed_dir, progress)
        
        print(f"    完成: ok={stats['ok']}, dropped={stats['dropped_no_abstract']}, failed={stats['failed']}")
    
    progress["total_ok"] = total_ok
    save_batch_progress(processed_dir, progress)
    
    return progress


def merge_jsonl_shards(
    processed_dir: str,
    output_path: str,
) -> int:
    """合并所有shard文件到最终jsonl。"""
    shards_dir = os.path.join(processed_dir, "shards")
    shard_files = sorted(Path(shards_dir).glob("PMC*.jsonl"))
    
    total_lines = 0
    with open(output_path, "w", encoding="utf-8") as fout:
        for shard in shard_files:
            print(f"合并 {shard.name} ...")
            with open(shard, "r", encoding="utf-8") as fin:
                for line in fin:
                    if line.strip():
                        fout.write(line)
                        total_lines += 1
    
    print(f"合并完成: {total_lines} 行 → {output_path}")
    return total_lines


__all__ = [
    "DEFAULT_DATA_ROOT",
    "OA_COMM_FTP_BASE",
    "OA_COMM_FTP_XML_DIR",
    "FILE_LIST_CACHE_MARKER",
    "ExtractReport",
    "FullScalePaths",
    "build_jsonl_batched",
    "build_jsonl_for_subdir",
    "check_data_root_mount",
    "compare_to_baseline",
    "count_jsonl_lines",
    "count_skipped",
    "count_tar_gz",
    "count_xml_files",
    "download_archives",
    "extract_all_archives",
    "extract_archive",
    "fetch_oa_comm_file_list",
    "get_batch_progress",
    "list_pmc_subdirs",
    "load_verify_baseline",
    "merge_jsonl_shards",
    "quick_check_data_root",
    "read_jsonl_sample",
    "remove_archives",
    "run_project_script",
    "save_batch_progress",
    "strategy_verdict",
]
