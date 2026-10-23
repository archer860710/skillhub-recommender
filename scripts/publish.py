#!/usr/bin/env python3
"""一键发布到 GitHub / skillhub.cn / skillhub.club。

用法:
    python scripts/publish.py --dry-run
    python scripts/publish.py --bump patch --changelog "修正收藏率口径"
    python scripts/publish.py --only github
    python scripts/publish.py --only cn --token skh_xxx
    python scripts/publish.py --only club

环境变量:
    SKILLHUB_CN_TOKEN   skillhub.cn 的个人 API Token（skh_ 开头）
    SKILLHUB_CLUB_NPM   club CLI 的 npm registry（默认 registry.npmmirror.com，国内快）

说明：频率/排期不归本脚本管，这里只做「发版」。
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "SKILL.md"
CHANGELOG = ROOT / "CHANGELOG.md"
IS_WIN = os.name == "nt"


# ---------------------------------------------------------------- helpers

def run(cmd: list[str], *, dry: bool = False, check: bool = True, env: dict | None = None,
        cwd: Path | None = None) -> tuple[int, str]:
    printable = " ".join(shlex.quote(c) for c in cmd)
    print(f"    $ {printable}")
    if dry:
        return 0, ""
    full_env = {**os.environ, **(env or {})}
    argv = list(cmd)
    if IS_WIN and argv[0].lower().endswith((".cmd", ".bat")):
        # .cmd/.bat 无法被 CreateProcess 直接执行；用 bash -c 包一层，
        # 顺带避开 cmd.exe 的 GBK 编码把中文参数写坏。
        bash = shutil.which("bash")
        if bash:
            argv = [bash, "-c", " ".join(shlex.quote(c) for c in cmd)]
    try:
        p = subprocess.run(argv, cwd=str(cwd or ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=full_env)
    except FileNotFoundError:
        return 127, f"未找到命令：{cmd[0]}"
    out = (p.stdout or "") + (p.stderr or "")
    if out.strip():
        for line in out.strip().splitlines()[-12:]:
            print(f"      {line}")
    if check and p.returncode != 0:
        return p.returncode, out
    return p.returncode, out


def read_frontmatter() -> str:
    text = SKILL_MD.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    return text[: end if end != -1 else len(text)]


def current_version() -> str:
    for line in read_frontmatter().splitlines():
        s = line.strip()
        if s.startswith("version:"):
            return s.split(":", 1)[1].strip().strip("\"'")
    return "0.0.0"


def bump_version(cur: str, kind: str) -> str:
    major, minor, patch = (int(x) for x in cur.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_version(new: str) -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    fm, body = text[:end], text[end:]
    fm2 = re.sub(r"(^\s+version:\s*)([\"']?)[0-9]+\.[0-9]+\.[0-9]+(\2)",
                 rf"\g<1>\g<2>{new}\g<3>", fm, count=1, flags=re.M)
    SKILL_MD.write_text(fm2 + body, encoding="utf-8")


def prepend_changelog(version: str, note: str) -> None:
    today = date.today().isoformat()
    entry = f"## [{version}] - {today}\n\n- {note.strip()}\n\n"
    if CHANGELOG.exists():
        text = CHANGELOG.read_text(encoding="utf-8")
        if text.lstrip().startswith("# "):
            idx = text.find("\n\n")
            head, rest = (text[:idx], text[idx:].lstrip("\n")) if idx != -1 else (text, "")
            CHANGELOG.write_text(f"{head}\n\n{entry}{rest}", encoding="utf-8")
        else:
            CHANGELOG.write_text(entry + text, encoding="utf-8")
    else:
        CHANGELOG.write_text(f"# Changelog\n\n{entry}", encoding="utf-8")


def has_remote() -> bool:
    if not (ROOT / ".git").exists():
        return False
    code, out = run(["git", "remote"], check=False)
    return code == 0 and bool(out.strip())


def resolve_cn_cli() -> list[str] | None:
    """定位 skillhub CLI。官方安装脚本在 ~/.local/bin 放一个 bash wrapper，
    Windows 上不能直接执行无扩展名脚本，需要按 shebang 换解释器。"""
    cands: list[Path] = []
    w = shutil.which("skillhub")
    if w:
        cands.append(Path(w))
    for d in (Path.home() / ".local" / "bin", Path.home() / "bin", Path("/usr/local/bin")):
        f = d / "skillhub"
        if f.exists() and f not in cands:
            cands.append(f)
    for f in cands:
        if f.suffix.lower() in {".exe", ".cmd", ".bat"}:
            return [str(f)]
        try:
            head = f.read_text(encoding="utf-8", errors="ignore")[:200]
        except OSError:
            head = ""
        first = head.splitlines()[0] if head.startswith("#!") else ""
        if first:
            if "python" in first:
                return [sys.executable, str(f)]
            if IS_WIN:
                bash = shutil.which("bash")
                if bash:
                    return [bash, str(f)]
            return [str(f)]
        return [str(f)]
    return None


# ---------------------------------------------------------------- channels

def publish_github(version: str, note: str, dry: bool) -> str:
    print("\n[GitHub]")
    if not (ROOT / ".git").exists():
        print("  · 尚未 git init，跳过。先执行：git init && git remote add origin git@github.com:<账号>/skillhub-recommender.git")
        return "skip"
    if not has_remote():
        print("  · 未配置 remote，跳过。先执行：git remote add origin git@github.com:<账号>/skillhub-recommender.git")
        return "skip"

    run(["git", "add", "-A"], dry=dry)
    code, _ = run(["git", "diff", "--cached", "--quiet"], dry=dry, check=False)
    if code == 0 and not dry:
        print("  · 无文件变更，仅打 tag")
    else:
        run(["git", "commit", "-m", f"chore(release): v{version} — {note}"], dry=dry)
    run(["git", "push"], dry=dry, check=False)
    run(["git", "tag", "-a", f"v{version}", "-m", f"v{version}"], dry=dry, check=False)
    run(["git", "push", "--tags"], dry=dry, check=False)
    print(f"  ✓ GitHub 处理完成（tag v{version}）")
    return "ok"


def stage_payload(lean: bool = False) -> Path:
    """只把该发的文件放进 dist/_stage 再上传。

    直接发仓库根目录会把 .git/ .gitignore .gitattributes dist/ 一起带上，
    skillhub.cn 对扩展名有白名单，遇到 .gitattributes 直接 400。

    lean=True 给 skillhub.club 用：那边总量上限 100KB，而完整包 124KB。
    去掉的只有作者侧工具（三个脚本）和历史变更记录，文档一份不少。"""
    stage = ROOT / "dist" / ("_stage_lean" if lean else "_stage")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    # 注意：skillhub.cn 对文件扩展名有白名单，无扩展名的 LICENSE、.gitattributes
    # 都会被 400 拒掉。LICENSE 只留在 GitHub 仓库里，不进上传包。
    names = ("SKILL.md", "README.md") if lean else ("SKILL.md", "README.md", "CHANGELOG.md")
    for name in names:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, stage / name)
    dirs = ("assets", "references") if lean else ("assets", "references", "scripts")
    for d in dirs:
        src = ROOT / d
        if src.exists():
            shutil.copytree(src, stage / d,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # club 靠项目内的 .skillhub.json 识别工程，必须一并带过去
    cfg = ROOT / ".skillhub.json"
    if cfg.exists():
        shutil.copy2(cfg, stage / cfg.name)
    return stage


def cn_logged_in(cli: list[str]) -> bool:
    """CLI 已登录时不必再传 token。auth whoami 有 userId 输出即视为已登录。"""
    code, out = run(cli + ["auth", "whoami"], check=False)
    return code == 0 and "userId" in out


def publish_cn(version: str, note: str, dry: bool, token: str | None) -> str:
    print("\n[skillhub.cn]")
    cli = resolve_cn_cli()
    if not cli:
        print("  · 未找到 skillhub CLI。安装：")
        print("    curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash")
        return "skip"
    tok = token or os.environ.get("SKILLHUB_CN_TOKEN", "")
    if not tok and not dry and not cn_logged_in(cli):
        print("  · 既没有 Token，CLI 也未登录，跳过。二选一：")
        print("    skillhub login --key skh_xxx    # 或")
        print("    export SKILLHUB_CN_TOKEN=skh_xxx")
        return "skip"
    payload = stage_payload() if not dry else ROOT
    cmd = cli + ["publish", str(payload), "--version", version, "--changelog", note]
    if tok:
        cmd += ["--token", tok]
    code, out = run(cmd, dry=dry, check=False)
    if dry:
        print("  · dry-run：未实际发布")
        return "ok"
    if code != 0:
        print(f"  ! 发布失败（exit {code}）")
        return "fail"
    print("  ✓ 已提交 skillhub.cn")
    return "ok"


def publish_club(version: str, note: str, dry: bool) -> str:
    print("\n[skillhub.club]")
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("  · 未找到 npx，需要 Node.js 18+")
        return "skip"
    env = {}
    reg = os.environ.get("SKILLHUB_CLUB_NPM", "https://registry.npmmirror.com")
    if reg:
        env["npm_config_registry"] = reg
    base = [npx, "-y", "@skill-hub/cli"]
    payload = ROOT if dry else stage_payload(lean=True)
    # -f 必须带：不带会停在确认提示上等输入，在非交互环境里表现为无限挂起
    code, out = run(base + ["push", "--create", "-f", "-m", f"v{version} — {note}"],
                    dry=dry, check=False, env=env, cwd=payload)
    if not dry and "already exists" in (out or ""):
        print("  ! 远端已有同名技能，但本地没有它的 skill_id，无法覆盖更新。")
        print("    club 靠 .skillhub.json 里的 skill_id 定位远端技能；缺了它只能新建。")
        print("    处理办法（任选）：")
        print("      a) 到 skillhub.club 技能页取出 skill id，填进项目根的 .skillhub.json 后重试")
        print("      b) 在网页上删掉旧技能，再跑到这一步让它重建（会重新生成 skill_id）")
        print("    注意：skill_id 只在首次 create 时写入 .skillhub.json，别让暂存目录把它一起删了。")
        return "fail"
    code, _ = run(base + ["publish", "-y"], dry=dry, check=False, env=env, cwd=payload)
    if dry:
        print("  · dry-run：未实际发布（需先 npx @skill-hub/cli login 完成 OAuth）")
        return "ok"
    if code != 0:
        print("  ! 发布失败。首次使用需先登录：npx -y @skill-hub/cli login")
        print(f"    若提示 'Not a skill project'，先跑：npx -y @skill-hub/cli init -n {ROOT.name}")
        return "fail"
    print("  ✓ 已发布 skillhub.club（评级需等平台审核）")
    return "ok"


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="一键发布 SkillHub 技能包")
    ap.add_argument("--bump", choices=["none", "patch", "minor", "major"], default="none")
    ap.add_argument("--version", help="直接指定版本号（覆盖 --bump）")
    ap.add_argument("--changelog", default="", help="本次变更说明")
    ap.add_argument("--only", default="all", help="all / github / cn / club，可逗号分隔")
    ap.add_argument("--token", help="skillhub.cn Token（默认读环境变量 SKILLHUB_CN_TOKEN）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的命令")
    ap.add_argument("--no-build", action="store_true", help="跳过打包")
    ap.add_argument("--skip-validate", action="store_true", help="跳过预检（不建议）")
    args = ap.parse_args()

    print(f"技能包：{ROOT.name}")
    cur = current_version()
    version = args.version or (
        bump_version(cur, args.bump) if args.bump != "none" else cur
    )
    note = args.changelog.strip() or ("初始版本" if cur == "0.0.0" else "内容更新")
    targets = {t.strip().lower() for t in args.only.split(",") if t.strip()}
    if "all" in targets:
        targets = {"github", "cn", "club"}

    print(f"版本：{cur} → {version}（{note}）")
    print(f"目标：{' / '.join(sorted(targets))}{'  [dry-run]' if args.dry_run else ''}")

    # 1. 预检
    if not args.skip_validate:
        print("\n[预检]")
        code, _ = run([sys.executable, str(ROOT / "scripts" / "validate.py"), "--quiet"],
                      dry=args.dry_run, check=False)
        if code != 0 and not args.dry_run:
            print("\n预检未通过，已中止。")
            return 1

    # 2. 版本与 changelog
    if version != cur and not args.dry_run:
        write_version(version)
        prepend_changelog(version, note)
        print(f"\n[版本] SKILL.md → {version}，CHANGELOG.md 已追加")

    # 3. 打包
    if not args.no_build:
        print("\n[打包]")
        run([sys.executable, str(ROOT / "scripts" / "build.py"), "--force"],
            dry=args.dry_run, check=False)

    # 4. 各通道
    results: dict[str, str] = {}
    if "github" in targets:
        results["github"] = publish_github(version, note, args.dry_run)
    if "cn" in targets:
        results["cn"] = publish_cn(version, note, args.dry_run, args.token)
    if "club" in targets:
        results["club"] = publish_club(version, note, args.dry_run)

    # 5. 汇总
    mark = {"ok": "\u2713", "skip": "\u00b7", "fail": "\u2717"}
    label = {"ok": "完成", "skip": "跳过", "fail": "失败"}
    print("\n" + "=" * 46)
    for k, st in results.items():
        print(f"  {mark[st]} {k:<8} {label[st]}")
    print("=" * 46)
    failed = [k for k, st in results.items() if st == "fail"]
    if failed:
        print(f"\n有通道失败：{', '.join(failed)}。修好后可单独重试，例如 --only {failed[0]}")
        return 2
    if args.dry_run:
        print("\ndry-run 结束：未发出任何请求，也未改动版本号。")
    else:
        print(f"\n发布流程结束（v{version}）。git 若有未提交变更，记得再确认一次。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
