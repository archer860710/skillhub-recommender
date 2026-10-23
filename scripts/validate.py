#!/usr/bin/env python3
"""发布前预检：结构、frontmatter、命名一致性、敏感信息、体积。

用法:
    python scripts/validate.py            # 检查当前技能包
    python scripts/validate.py --quiet    # 只输出结论
退出码: 0 = 通过, 1 = 有问题
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = ["SKILL.md", "README.md", "LICENSE"]
SKIP_DIRS = {".git", "dist", "__pycache__", ".skillhub", ".idea", ".vscode"}

SECRET_PATTERNS = [
    (r"skh_[A-Za-z0-9]{8,}", "SkillHub API Token (skh_…)"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub PAT (ghp_…)"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained PAT"),
    (r"sk-[A-Za-z0-9]{20,}", "疑似 OpenAI/Anthropic Key"),
    (r"AKID[A-Za-z0-9]{10,}", "腾讯云 SecretId"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥"),
]

LOCAL_PATH_PATTERNS = [
    (r"[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._-]+", "Windows 用户绝对路径"),
    (r"/Users/[A-Za-z0-9._-]+/", "macOS 用户绝对路径"),
    (r"D:\\\\?WorkBuddy Projects", "本机工作区路径"),
]

# 这四项在就说明「条数/周期由用户定」的能力还在；少了任意一项，多半是又被写死了
PREF_ANCHORS = ["《SkillHub推荐偏好》", "每条痛点推荐数", "跨领域补充数", "冷冻期"]

# 痛点必须由用户本人给，这些是"工具作者替你定好"的痕迹，出现即视为回归
PRESET_PAIN_BLACKLIST = [
    "办公自动化 / 内容创作 / 数据分析 / 生活提效",
    "痛点用「办公自动化",
    "先来一份通用的」，痛点",
]

PAIN_ANCHORS = ["不在提示词里固化任何具体痛点", "全领域均衡"]

# 交付链路和分级门槛是两次真事故换来的，删掉任意一项用户都会白等一期 / 冷门方向直接空掉
ROBUSTNESS_ANCHORS = [
    "不等于交付",      # 写完文件 ≠ 交付给用户
    "兜底",            # 收藏数门槛必须有第二档
    "候选池深度",      # 池子撑不了几期要显式告诉用户
]


class Report:
    def __init__(self, quiet: bool = False) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.ok: list[str] = []
        self.quiet = quiet

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def good(self, msg: str) -> None:
        self.ok.append(msg)

    def render(self) -> None:
        if not self.quiet:
            for m in self.ok:
                print(f"  \u2713 {m}")
            for m in self.warns:
                print(f"  ! {m}")
        for m in self.errors:
            print(f"  \u2717 {m}")
        print()
        if self.errors:
            print(f"预检未通过：{len(self.errors)} 个错误，{len(self.warns)} 个警告")
        else:
            print(f"预检通过：{len(self.ok)} 项检查，{len(self.warns)} 个警告")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """极简 YAML frontmatter 解析，只支持本 Skill 用到的写法。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end]
    body = text[end + 4 :].lstrip("\n")
    data: dict = {}
    key = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal key, buf
        if key is not None:
            data[key] = " ".join(x.strip() for x in buf).strip()
        key, buf = None, []

    for raw in block.splitlines():
        if not raw.strip():
            continue
        if raw[:1] in " \t" or raw.strip() in (">", "|"):
            if raw.strip() not in (">", "|"):
                buf.append(raw.strip())
            continue
        if ":" in raw:
            flush()
            k, v = raw.split(":", 1)
            k, v = k.strip(), v.strip()
            if v in (">", "|", ">-", "|-"):
                key, buf = k, []
            else:
                data[k] = v.strip("\"'")
    flush()
    return data, body


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & SKIP_DIRS:
            continue
        if p.suffix in {".pyc"}:
            continue
        yield p


def check_structure(rep: Report) -> dict:
    meta: dict = {}
    skill_md = ROOT / "SKILL.md"
    if not skill_md.exists():
        rep.error("缺少 SKILL.md")
        return meta

    text = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if not fm:
        rep.error("SKILL.md 缺少 YAML frontmatter（--- 开头）")
    else:
        rep.good("frontmatter 可解析")

    name = fm.get("name", "")
    if not name:
        rep.error("frontmatter 缺 name")
    elif name != ROOT.name:
        rep.error(f"name（{name}）与目录名（{ROOT.name}）不一致 —— 平台会拒收")
    else:
        rep.good(f"name 与目录名一致：{name}")

    # skillhub.cn CLI 的 publish 硬性要求（实测：缺任一项直接报错退出）
    slug = fm.get("slug", "")
    if not slug:
        rep.error("frontmatter 缺 slug —— skillhub.cn publish 会直接拒绝")
    elif name and slug != name:
        rep.warn(f"slug（{slug}）与 name（{name}）不同，检索与安装链接会不一致")
    else:
        rep.good(f"slug = {slug}")

    dn = fm.get("displayName", "")
    if not dn:
        rep.error("frontmatter 缺 displayName —— skillhub.cn publish 会直接拒绝")
    else:
        rep.good(f"displayName = {dn}")

    desc = fm.get("description", "")
    if len(desc) < 40:
        rep.error("description 过短（<40 字），无法被 Agent 正确触发")
    elif len(desc) > 1200:
        rep.warn(f"description 偏长（{len(desc)} 字），建议 200–600 字")
    else:
        rep.good(f"description 长度 {len(desc)} 字")

    version = ""
    m = re.search(r"^\s+version:\s*[\"']?([0-9]+\.[0-9]+\.[0-9]+)", fm_text(text), re.M)
    if m:
        version = m.group(1)
        rep.good(f"version = {version}")
    else:
        rep.error("frontmatter 缺 metadata.version（语义化版本）")

    if not fm.get("license"):
        rep.warn("frontmatter 缺 license 字段")

    repo = re.search(r"^\s+repository:\s*(\S+)", fm_text(text), re.M)
    if repo:
        rep.warn(f"frontmatter 声明了仓库地址 {repo.group(1)} —— 发布前确认它能打开，404 的链接比没有更伤可信度")

    if len(body.strip()) < 500:
        rep.warn("SKILL.md 正文偏短（<500 字）")

    for f in REQUIRED_FILES:
        if (ROOT / f).exists():
            rep.good(f"存在 {f}")
        else:
            rep.error(f"缺少 {f}")

    # 关键内容自检
    tp = ROOT / "references" / "task-prompt.md"
    if tp.exists():
        t = tp.read_text(encoding="utf-8")
        if "【SkillHub 技能推荐简报" in t:
            rep.good("task-prompt.md 含完整任务提示词")
        else:
            rep.error("task-prompt.md 似乎不是完整任务提示词（未找到标题行）")
        if "star_rate" not in t and "收藏率" not in t:
            rep.warn("task-prompt.md 未提及收藏率口径，易被误解")
        missing = [k for k in PREF_ANCHORS if k not in t]
        if missing:
            rep.error(f"task-prompt.md 缺少口径可配置锚点：{missing} —— 会被退回成把条数写死")
        else:
            rep.good("task-prompt.md 保留口径可配置（偏好文档驱动）")
        missing_pain = [k for k in PAIN_ANCHORS if k not in t]
        if missing_pain:
            rep.error(f"task-prompt.md 缺少痛点必须由用户提供的锚点：{missing_pain}")
        else:
            rep.good("task-prompt.md 要求痛点由用户提供，不代填")
        missing_robust = [k for k in ROBUSTNESS_ANCHORS if k not in t]
        if missing_robust:
            rep.error(f"task-prompt.md 缺少健壮性锚点：{missing_robust} —— 交付会断 / 冷门方向会空")
        else:
            rep.good("task-prompt.md 保留交付降级链与分级门槛")
    else:
        rep.warn("缺少 references/task-prompt.md（用户建定时任务需要它）")

    if all(k in text for k in ("每条痛点推荐数", "跨领域补充数", "冷冻期")):
        rep.good("SKILL.md 保留可配置口径表")
    else:
        rep.warn("SKILL.md 未展示可配置口径表，用户不知道能改什么")

    tp_test = ROOT / "references" / "test-prompts.md"
    if not tp_test.exists():
        rep.warn("缺少 references/test-prompts.md（别人装完不知道怎么验证）")
    else:
        t = tp_test.read_text(encoding="utf-8")
        if "不应触发" in t and "不合格" in t:
            rep.good("test-prompts.md 覆盖正常 / 边界 / 不应触发")
        else:
            rep.warn("test-prompts.md 缺少边界或反例说明")

    meta["name"] = name
    meta["version"] = version
    meta["description"] = desc
    return meta


def fm_text(text: str) -> str:
    end = text.find("\n---", 3)
    return text[: end if end != -1 else len(text)]


def check_template(rep: Report) -> None:
    tpl = ROOT / "assets" / "briefing-template.html"
    if not tpl.exists():
        rep.warn("缺少 assets/briefing-template.html（产出一致性会变差）")
        return
    h = tpl.read_text(encoding="utf-8")
    for tag in ("div", "section", "span", "code", "button"):
        o = len(re.findall(rf"<{tag}[\s>]", h))
        c = len(re.findall(rf"</{tag}>", h))
        if o != c:
            rep.error(f"模板 {tag} 标签不闭合：{o} 开 / {c} 闭")
    if "width=device-width" not in h:
        rep.error("模板缺少 viewport meta")
    if "~/.workbuddy" in h or "/Users/" in h:
        rep.error("模板里写死了作者环境的安装路径 —— 改用 {{INSTALL_DIR}}")
    ext = [u for u in re.findall(r'(?:src|href)="(https?://[^"]+)"', h)]
    if ext:
        rep.error(f"模板含外部引用（离线会白屏）：{ext[:3]}")
    else:
        rep.good("模板零外链、标签闭合")


def looks_placeholder(value: str) -> bool:
    """skh_xxxxxxxx / skh_0000 这类文档占位符不算泄露。"""
    body = value.split("_", 1)[1] if "_" in value else value
    return bool(body) and set(body.lower()) <= set("x0*.-_")


def check_secrets(rep: Report) -> None:
    hits = 0
    for p in iter_files(ROOT):
        if p.suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".webp", ".ico"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = p.relative_to(ROOT)
        for pat, label in SECRET_PATTERNS:
            for m in re.finditer(pat, text):
                if looks_placeholder(m.group(0)):
                    continue
                rep.error(f"疑似密钥 {label} @ {rel}: {m.group(0)[:24]}…")
                hits += 1
        for pat, label in LOCAL_PATH_PATTERNS:
            for m in re.finditer(pat, text):
                rep.warn(f"本机路径 {label} @ {rel}: {m.group(0)}")
                hits += 1
    if hits == 0:
        rep.good("未发现密钥与本机路径")


def check_preset_pains(rep: Report) -> None:
    """痛点只能来自用户，文档里出现"作者预设清单"就是回归。"""
    hits = 0
    for p in iter_files(ROOT):
        if p.suffix.lower() not in {".md", ".html"}:
            continue
        if p.resolve() == Path(__file__).resolve():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for bad in PRESET_PAIN_BLACKLIST:
            if bad in text:
                rep.error(f"发现预设痛点清单 @ {p.relative_to(ROOT)}：{bad}")
                hits += 1
    if hits == 0:
        rep.good("未发现预设痛点清单（痛点由用户提供）")


def check_no_stale_numbers(rep: Report) -> None:
    """模板里不许出现写死的全站规模 / 分类数 —— 这些每期都会变。"""
    tpl = ROOT / "assets" / "briefing-template.html"
    if not tpl.exists():
        return
    h = tpl.read_text(encoding="utf-8")
    stale = [n for n in ("195,007", "195007", "19.5 万", "19 万") if n in h]
    if stale:
        rep.error(f"模板里写死了会变的数据：{stale} —— 改用 {{TOTAL_SKILLS}} / {{CATEGORY_COUNT}}")
    else:
        rep.good("模板未写死全站规模")

    tp = ROOT / "references" / "task-prompt.md"
    if tp.exists() and "data.total" not in tp.read_text(encoding="utf-8"):
        rep.error("task-prompt.md 未要求从 data.total 现取全站规模，数字会过期")


def check_size(rep: Report) -> None:
    files = list(iter_files(ROOT))
    total = sum(p.stat().st_size for p in files)
    rep.good(f"{len(files)} 个文件，合计 {total / 1024:.1f} KB")
    if total > 900 * 1024:
        rep.warn(f"体积偏大（{total / 1024:.0f} KB），zip 可能超 1 MB")
    big = [p for p in files if p.stat().st_size > 200 * 1024]
    for p in big:
        rep.warn(f"单文件偏大：{p.relative_to(ROOT)}（{p.stat().st_size / 1024:.0f} KB）")


def check_zip_integrity(rep: Report) -> None:
    """若 dist 下已有 zip，校验其结构与可读性。"""
    dist = ROOT / "dist"
    if not dist.exists():
        return
    for z in sorted(dist.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                bad = zf.testzip()
                names = zf.namelist()
            if bad:
                rep.error(f"{z.name} 内文件损坏：{bad}")
                continue
            if not any(n.endswith("SKILL.md") for n in names):
                rep.error(f"{z.name} 内无 SKILL.md")
            else:
                rep.good(f"{z.name} 结构正常（{len(names)} 个文件）")
        except zipfile.BadZipFile:
            rep.error(f"{z.name} 不是合法 zip")


def main() -> int:
    ap = argparse.ArgumentParser(description="SkillHub 技能包发布前预检")
    ap.add_argument("--quiet", action="store_true", help="只输出结论与错误")
    args = ap.parse_args()

    print(f"预检目录：{ROOT}\n")
    rep = Report(quiet=args.quiet)
    check_structure(rep)
    check_template(rep)
    check_no_stale_numbers(rep)
    check_preset_pains(rep)
    check_secrets(rep)
    check_size(rep)
    check_zip_integrity(rep)
    print()
    rep.render()
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
