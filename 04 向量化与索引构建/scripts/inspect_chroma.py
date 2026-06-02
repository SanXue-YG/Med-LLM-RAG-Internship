"""临时脚本：检查 chroma.sqlite3 与 HNSW 目录状态。"""
import sqlite3
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else r"E:\med-llm-rag-datasets\chroma_db")
db = path / "chroma.sqlite3"
print(f"dir: {path}")
print(f"sqlite exists: {db.exists()} size GB: {db.stat().st_size/1e9:.2f}" if db.exists() else "no sqlite")
for d in path.iterdir():
    if d.is_dir():
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        print(f"  uuid dir {d.name}: {size/1e6:.1f} MB")

if db.exists():
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print("tables:", tables)
    for t in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            n = cur.fetchone()[0]
            if n:
                print(f"  {t}: {n:,}")
        except Exception as e:
            print(f"  {t}: err {e}")
    con.close()

print("\ntry chromadb count (10s timeout not enforced)...")
import chromadb

try:
    c = chromadb.PersistentClient(path=str(path))
    col = c.get_collection("pmc_oa_comm_full")
    print("count:", col.count())
except Exception as e:
    print("chromadb error:", type(e).__name__, e)
