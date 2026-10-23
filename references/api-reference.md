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

返回 `data.total` —— 实测 **195,007**（约 19.5 万）。这意味着任何"头部候选池"策略的覆盖率都在 0.1% 量级，**必须承认这一点并在简报里如实标注**，不要让读者以为扫了全站。

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

```json
{
  "data": {
    "total": 195007,
    "skills": [
      {
        "name": "Nano Banana Pro",
        "slug": "nano-banana-pro",
        "category": "design-media",
        "downloads": 172838,
        "stars": 473,
        "star_rate": 0.2973,
        "rank": 87,
        "description_zh": "...",
        "author": "steipete"
      }
    ]
  }
}
```

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

### `star_rate` 已经是百分数

`0.2973` = **0.30%**，不是 29.73%。

- 全站量级：**0.1% – 0.5%**
- > 0.2% 已属优秀；池内最高约 0.44%
- **不要自己乘 100**，否则会写出"收藏率 29.73%"这种离谱数字
- 同一份数据里，早期版本曾误乘 100，导致"收藏率 ≥ 10%"的门槛把全站技能全筛掉 —— 这是本 Skill 最重要的历史坑

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

## 已知的可视化数据（截至 2026-10）

- 全站技能数：约 195,007
- 分类数：13
- 下载榜 Top200 的收藏率中位数：约 0.03%
- 下载榜 Top100 ∩ 收藏榜 Top100 重叠：仅 38 个 → **两榜差异极大，必须都抓**
