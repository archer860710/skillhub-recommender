# 发布：GitHub / skillhub.cn / skillhub.club

三个平台互不相通，但都认同一份 `SKILL.md`。所以策略是：**一份源，三处分发**，靠 `scripts/publish.py` 一条命令完成。

## 三条通道的真实情况

| 平台 | 通道 | 命令 | 需要什么 |
|---|---|---|---|
| GitHub | git | `git push` | SSH key（本机已有）或 PAT |
| **skillhub.cn** | 官方 CLI | `skillhub publish <dir>` | `skh_` 开头的个人 API Token |
| **skillhub.club** | npm CLI | `npx @skill-hub/cli push` + `publish` | 浏览器 OAuth 登录一次 |

> 状态说明：三条命令的**帮助文本与参数均已在本机核对**（`skillhub publish --help`、`@skill-hub/cli@0.1.9` 的 `init/push/publish` 实现），但首次真实发布仍需用户完成登录。发布前一律先跑 `--dry-run`。

## 版本号规则

- 权威版本在 `SKILL.md` 的 `metadata.version`
- 语义化：`1.0.0` → 内容修订 `1.0.1` → 新增机制 `1.1.0` → 破坏性变更 `2.0.0`
- 每次发布追加 `CHANGELOG.md` 一段
- `scripts/publish.py --bump patch|minor|major` 会自动改版本 + 写 changelog

## frontmatter 必需字段（踩过的坑）

`skillhub.cn` 的 CLI 在 `publish` 时会逐项校验，缺一个就报错退出（实测会依次报「缺少 slug」→「缺少 displayName」）：

| 字段 | 必需 | 说明 |
|---|---|---|
| `name` | ✅ | 必须与目录名一致 |
| `slug` | ✅ | 安装与链接用的标识，通常与 name 相同 |
| `displayName` | ✅ | 展示名，可以用中文，如「SkillHub 技能推荐」 |
| `description` | ✅ | 说清「什么时候该用」，建议 200–600 字 |
| `metadata.version` | ✅ | 语义化版本 |
| `license` | 建议 | MIT |

本仓库的 frontmatter 已按此配好；`scripts/validate.py` 会提前拦住缺失。

## 一、GitHub

```bash
# 首次：先在 github.com 网页建空仓库 skillhub-recommender（不要 init README）
git init
git add .
git commit -m "feat: skillhub-recommender v1.0.0"
git branch -M main
git remote add origin git@github.com:<你的账号>/skillhub-recommender.git
git push -u origin main
git tag -a v1.0.0 -m "v1.0.0" && git push --tags
```

后续更新就是 `git add . && git commit && git push`。

**本机注意**：这台机器的 `github.com:443` 被封，只能用 SSH（22 端口）。所以 remote 必须是 `git@github.com:...`，不要用 HTTPS + PAT。

## 二、skillhub.cn（腾讯生态，国内优先）

CLI 已装：`skillhub 2026.8.5`（位于 `~/.local/bin/skillhub`）。

```bash
# 1. 取 Token：登录 skillhub.cn → 个人设置 → API Token（skh_ 开头）
skillhub login --key skh_xxxxxxxx        # 或直接 export SKILLHUB_CN_TOKEN=skh_xxx

# 2. 预检（不联网，只校验 metadata + 打包）
skillhub publish ./ --dry-run

# 3. 正式发布
skillhub publish ./ --version 1.0.1 --changelog "修正收藏率口径说明"
```

其他可用参数：

| 参数 | 用途 |
|---|---|
| `--token skh_...` | 临时覆盖已登录 Token（CI 用） |
| `--host` | 默认 `https://api.skillhub.cn`，一般不用改 |
| `--json` | 机器可读输出，给脚本用 |
| 路径参数 | 目录或 `.zip` 均可，**目录/zip 内必须含 SKILL.md** |

校验状态：`skillhub auth whoami` 查看当前 Token 身份，`skillhub verify` 校验本机技能与平台签名是否一致。

## 三、skillhub.club（国际向，AI 评分制）

npm 包 `@skill-hub/cli`（当前 0.1.9）。工作流是 **登录 → init → push → publish** 四步：

```bash
# 1. 登录（浏览器 OAuth，支持 GitHub / Google / Email）
npx -y @skill-hub/cli login

# 2. 首次：在技能目录初始化项目（会写本地配置，已被 .gitignore 忽略）
npx -y @skill-hub/cli init -n skillhub-recommender -d "扫描 SkillHub 按痛点推荐技能" -c productivity

# 3. 推送文件到远端（首次要 --create）
npx -y @skill-hub/cli push --create -m "v1.0.0 初始版本"

# 4. 上架公开目录
npx -y @skill-hub/cli publish -y
```

补充：

- `init --link <skill-id>` 可关联已存在的远端技能（避免重复创建）
- `push` 有 `-f/--force` 强制推送，版本迭代用 `-m` 写变更说明
- 国内拉 npm 包慢时：`npm_config_registry=https://registry.npmmirror.com npx -y @skill-hub/cli ...`
- 发布后技能页形如 `https://www.skillhub.club/skills/<slug>`
- 平台会给技能做 AI 评估（S/A/B/C 级）与安全审核，**上架不即时，评级要等**

## 四、一条命令发三处

```bash
python scripts/publish.py --dry-run                       # 全流程预检，不发任何请求
python scripts/publish.py --bump patch --changelog "..."   # 建议版本 + 全平台发布
python scripts/publish.py --only github                    # 只推 GitHub
python scripts/publish.py --only cn --token skh_xxx        # 只发 skillhub.cn
python scripts/publish.py --only club                      # 只发 skillhub.club
```

Token 从环境变量读，**不要写进文件**：

```bash
export SKILLHUB_CN_TOKEN=skh_xxxxxxxx
```

Windows PowerShell：`$env:SKILLHUB_CN_TOKEN = "skh_xxxxxxxx"`

## 发布前检查清单

- [ ] `SKILL.md` 的 `name` 与目录名完全一致（`skillhub-recommender`）
- [ ] frontmatter 有 `name` 和 `description`，且 `description` 说清「什么时候用」
- [ ] `metadata.version` 已递增，`CHANGELOG.md` 有对应段落
- [ ] 无 Token、无本地绝对路径、无私人信息（`scripts/validate.py` 会扫）
- [ ] 体积合理（zip < 1 MB）
- [ ] `--dry-run` 通过

## 常见失败

| 报错 | 原因 | 处理 |
|---|---|---|
| `Error: SKILL.md 缺少 slug` | skillhub.cn 要求 slug 字段 | frontmatter 加 `slug: <name>` |
| `Error: SKILL.md 缺少 displayName` | 同上，缺展示名 | 加 `displayName: 中文名` |
| `Not logged in. Run 'skillhub login' first.` | club CLI 未登录 | 先跑 `npx @skill-hub/cli login` |
| `Not a skill project. Run 'skillhub init' first.` | 该目录没 init 过 | 跑 `init`（只需一次） |
| `Skill not pushed yet. Run 'skillhub push' first.` | 直接 publish 了 | 先 `push --create` |
| `目录/zip 内必须含 SKILL.md` | 传错路径 | 传技能根目录，不是 references/ |
| `Permission denied (publickey)` | GitHub 走错协议 | 改用 `git@github.com:` remote |
| name 与目录名不符 | 打包时被拒 | 改目录名或改 frontmatter 的 name |
