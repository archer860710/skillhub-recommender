# SkillHub API 参考

面向本 Skill 的抓取逻辑。所有端点均为公开只读，无需鉴权，国内直连可用（实测 0.3–1.3s，无需代理）。

## 目录

- [全站规模](#全站规模) —— 为什么覆盖率只有 0.1%
- [列表接口](#列表接口) —— 四路抓取的主入口
- [分类](#分类) —— 13 个分类 key
- [详情接口](#详情接口) —— 单技能详情与安全审核字段
- [字段口径](#字段口径最容易搞错的地方) —— `star_rate` / `downloads` 怎么读
- [已知坑](#已知坑)
- [已知的可视化数据](#已知的可视化数据截至-2026-10) —— 时效性快照

## 全站规模

`GET https://api.skillhub.cn/api/skills?page=1&pageSize=1`

返回 `data.total` —— 2026-10 快照为 **195,007**（约 19.5 万）。**这是个会涨的数**：任何写进代码或模板的绝对值都会过期，简报里的全站总量必须每期现取这个字段。按当前量级，任何"头部候选池"策略的覆盖率都在 0.1% 量级，**必须承认这一点并在简报里如实标注**，不要让读者以为扫了全站。

（技能总量增长不影响本策略的正确性，只影响覆盖率的分母：分母变大，覆盖率更低，更要在页脚说清楚「本期只扫了头部」。）

## 列表接口

```
GET https://api.skillhub.cn/api/skills
    ?page=1
    &pageSize=100
    &sortBy=downloads      # downloads | stars
    &order=desc
    &category={key}        # 可选
```

| 参数 | 说明 |
|---|---|
| `page` | 从 1 开始 |
| `pageSize` | **上限 100**，传 200/500 会被截断为 100 |
| `sortBy` | 只认 `downloads` 和 `stars`；其他值（`star_rate`、`hot`、`trending` 等）会被忽略或拒绝 |
| `category` | 见下方分类表 |

返回：

列表项的真实字段（2026-10 实测，`data.skills[]`）：

```json
{
  "data": {
    "total": 202661,
    "skills": [
      {
        "name": "self-improving agent",
        "slug": "self-improving-agent",
        "category": "ai-agent",
        "downloads": 1482610,
        "installs": 86140,
        "stars": 4536,
        "labels": { "requires_api_key": "false" },
        "description_zh": "记录自身发现以实现自我改进的技能",
        "namespace": "...",
        "ownerName": "...",
        "homepage": "...",
        "verified": false,
        "version": "..."
      }
    ]
  }
}
```

**列表里没有的东西（重要）**

| 你以为有 | 实际 | 怎么办 |
|---|---|---|
| `star_rate` | ❌ **列表不返回** | 自己算，见下方口径 |
| `rank`（全站排名） | ❌ 没有 | 用翻页序号近似，或在简报里写「榜内第 N」而不是「全站第 N」 |
| `author` | ❌ 叫 `ownerName` / `namespace` | 用这两个 |
| `securityReports` | ❌ 只在详情接口 | 见「详情接口」一节，只对入围项查 |

`total` 是字符串还是数字、具体值都在变 —— 只取 `data.total` 的当前值，不要照抄示例里的 202661。

## 分类

`GET https://api.skillhub.cn/api/v1/categories` → `{ count, items[] }`，每项含 `key` / `name`。

| key | 中文名 | 大致体量 |
|---|---|---|
| `pay-skill` | Pay Skill | 小 |
| `office-efficiency` | 办公效率 | 1.1 万 |
| `content-creation` | 内容创作 | 1.8 万 |
| `dev-programming` | 开发编程 | 2.1 万 |
| `data-analysis` | 数据分析 | 1.3 万 |
| `design-media` | 设计多媒体 | 1.4 万 |
| `ai-agent` | AI Agent | 2.2 万 |
| `knowledge-management` | 知识管理 | 0.9 万 |
| `business-ops` | 商业运营 | 2.9 万 |
| `education` | 教育学习 | 0.9 万 |
| `professional` | 行业专业 | 2.3 万 |
| `it-ops-security` | IT 运维与安全 | 1.2 万 |
| `life-service` | 生活服务 | 1.3 万 |

痛点 → 分类的映射参考：

| 痛点方向 | 分类 key |
|---|---|
| 摄影 / 影像 / 设计 | `content-creation`、`design-media` |
| 办公自动化 / 生活提效 | `office-efficiency`、`life-service`、`data-analysis` |
| AI 自身技能 / Agent 开发 | `ai-agent`、`dev-programming` |
| 内容创作 / 自媒体 | `content-creation`、`business-ops` |

## 详情接口

`GET https://api.skillhub.cn/api/v1/skills/{slug}`

**调用时机：不是对全池查。** 候选池 240–450 个，每个查一次就是几百次请求，大概率被限流、也白白拖慢任务。正确顺序是：

```
列表接口（4 路抓取）→ 去重 / 冷冻 / 收藏数门槛 → 定出入围的十余个 → 只对这十余个查详情
```

详情这一步只解决两件事：安全审核结果、`requires_api_key`、中文简介。前两步用列表数据就够。

推荐前需要的字段都在这里：

```json
{
  "skill": {
    "displayName": "Nano Banana Pro",
    "slug": "nano-banana-pro",
    "category": "design-media",
    "summary_zh": "…",
    "labels": { "requires_api_key": "true" },
    "sourceUrl": "https://clawhub.ai/steipete/nano-banana-pro",
    "stats": { "downloads": 172838, "stars": 473, "installs": 3086, "comments": 0, "versions": 1 }
  },
  "securityReports": {
    "keen":  { "status": "benign", "statusText": "安全，无风险", "reportUrl": "…" },
    "sanbu": { "status": "benign", "statusText": "安全，无风险", "reportUrl": "…" }
  }
}
```

| 字段 | 用途 |
|---|---|
| `labels.requires_api_key` | 卡片「风险提示」行的 API Key 标记 |
| `securityReports.keen.status` / `.sanbu.status` | 安全审核；**必须为 `benign`** 才推荐 |
| `sourceUrl` | 溯源（多为 clawhub 上游），可用于判断是否企业批量分发 |
| `stats.installs` | 真实安装数，比 downloads 更接近实际使用 |

## 字段口径（最容易搞错的地方）

### 收藏率要自己算（列表不返回 `star_rate`）

列表接口只有 `stars` 和 `downloads`，**必须自己算**：

```
收藏率(%) = stars ÷ downloads × 100，保留两位小数
```

实测算例（2026-10 收藏榜前排）：

| 技能 | stars | downloads | 收藏率 |
|---|---|---|---|
| self-improving agent | 4,536 | 1,482,610 | **0.31%** |
| self-improving | 1,618 | 580,490 | **0.28%** |
| find-skills | 1,800 | 1,376,836 | **0.13%** |
| humanizer | 1,113 | 435,959 | **0.26%** |
| gog | 945 | 220,160 | **0.43%** |

注意最后一行：`gog` 收藏数不到 `self-improving agent` 的四分之一，但收藏率高 39%，`downloads` 只有它的 15% —— 这正是不看收藏率会漏掉的类型。

### 两个坑

**坑 1：把收藏率当小数写。** `4536 ÷ 1482610 = 0.00306`，这个数直接乘 100 才是 0.31%。写成 0.00306% 就是差了 100 倍。判定标准：**全站量级 0.1%–0.5%，算出 0.00x% 或 30%+ 都是错的。**

**坑 2：以为有现成的 `star_rate` 字段可读。** 早期版本按「字段已是百分数，不要乘 100」处理 —— 那条规则针对的是详情接口历史上的返回，列表里压根没这个字段。读不到就老老实实算，不要因为找不到字段就去猜。

历史记录：早期版本曾把 0.2973 当成 29.73% 写进简报（虚高 100 倍），也曾用「收藏率 ≥ 10%」当门槛把全站技能全筛掉。两次都是同一个方向的错。

### `downloads` 与 `installs` 的区别

- `downloads` 累计下载次数，含镜像、批量分发、爬虫，虚高
- `installs` 真实安装数，量级小得多（典型 `downloads` 148 万 → `installs` 8.6 万）
- **判断「企业预装充数」时用 `downloads ÷ installs` 的比值**：比值畸形高（>50）多半不是真人用的
- 主排序信号仍然是 `stars`，`installs` 只作旁证，不要拿它替代门槛

### `downloads` 会骗人

下载量含企业预装与批量分发。实测样本：某编程类技能下载 381 万次、收藏 16 个。因此：

- `downloads` 只做「排名展示」和「潜力分」的一个加权项
- 质量门槛、排序、推荐理由**一律以 `stars` 为准**
- 卡片同时展示「收藏数 + 收藏率 + 全站排名」，让读者自己看出落差

### 池内 `stars` 分布（236 个样本，供定门槛参考）

| 分位 | stars |
|---|---|
| P100（最高） | 1613 |
| P90 | ~180 |
| P75 | ~60 |
| P50 | ~20 |
| P25 | ~6 |

因此「收藏数 ≥ 50」大约卡在池内 **前 25%**，是个合理的质量门槛；「≥ 20」可作为候选池快照的留存线。

## 已知坑

| 现象 | 处理 |
|---|---|
| `pageSize` > 100 被静默截断 | 用翻页，不要指望一次拉完 |
| 分类接口返回 `{count, items}`，不是数组 | 取 `.items` |
| 详情接口部分技能 `summary_zh` 为空 | 回退 `summary`（英文） |
| 部分技能 `securityReports` 缺失 | 视为「未审核」，**不推荐** |
| 接口偶发超时 / 5xx | 用已抓到的数据继续，页脚注明缺失范围 |
| `sortBy` 传不支持的值不报错但排序失效 | 只用 `downloads` / `stars` |

## 已知的可视化数据（2026-10 快照，会变）

> 下表只用于理解量级和定门槛，**不是常量**。全站数、分类数每期都要从接口重新取；收藏率中位数会随池子变化。

- 全站技能数：约 195,007（只增不减）
- 分类数：13（平台会新增分类，以 `/api/v1/categories` 返回为准）
- 下载榜 Top200 的收藏率中位数：约 0.03%
- 下载榜 Top100 ∩ 收藏榜 Top100 重叠：仅 38 个 → **两榜差异极大，必须都抓**
