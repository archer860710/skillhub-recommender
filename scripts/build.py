#!/usr/bin/env python3
"""打包：把技能包打成 dist/<name>-v<version>.zip，并生成 manifest.json。

用法:
    python scripts/build.py           # 先预检，通过后打包
    python scripts/build.py --force   # 跳过预检强制打包（不建议）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
EXCLUDE_DIRS = {".git", "dist", "__pycache__", ".skillhub", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}


def read_version() -> str:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    fm = text[: end if end != -1 else len(text)]
    for line in fm.splitlines():
        s = line.strip()
        if s.startswith("version:"):
            return s.split(":", 1)[1].strip().strip("\"'")
    return "0.0.0"


def collect() -> list[Path]:
    out: list[Path] = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_dir():
            continue
        if set(p.relative_to(ROOT).parts) & EXCLUDE_DIRS:
            continue
        if p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIX:
            continue
        out.append(p)
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 SkillHub 技能包")
    ap.add_argument("--force", action="store_true", help="跳过预检")
    args = ap.parse_args()

    if not args.force:
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate.py"), "--quiet"],
            cwd=ROOT,
        )
        if r.returncode != 0:
            print("\n预检未通过，已中止打包。修复后用 --force 可跳过（不建议）。")
            return 1
        print()

    name = ROOT.name
    version = read_version()
    DIST.mkdir(exist_ok=True)
    target = DIST / f"{name}-v{version}.zip"

    files = collect()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            # 顶层目录包裹：zip 内为 <name>/SKILL.md
            zf.write(f, arcname=f"{name}/{f.relative_to(ROOT).as_posix()}")

    manifest = {
        "name": name,
        "version": version,
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "zip": target.name,
        "size_bytes": target.stat().st_size,
        "sha256": sha256(target),
        "files": [f.relative_to(ROOT).as_posix() for f in files],
    }
    (DIST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"已打包：{target.relative_to(ROOT)}")
    print(f"  文件数 {len(files)} ｜ 体积 {target.stat().st_size / 1024:.1f} KB")
    print(f"  sha256 {manifest['sha256'][:16]}…")
    print(f"  清单   dist/manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
