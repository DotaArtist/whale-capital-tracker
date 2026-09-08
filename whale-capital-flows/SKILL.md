---
name: whale-capital-flows
description: 采集公开市场的资本流向事件记录：大额募资（IPO/增发/可转债/债券）、巨型回购、并购、SPAC/GDR/REITs 等低频大金额且构成重大新闻的资金行为，统一输出为 flows.json 单一 JSON 文档（meta + events）。只使用稳定官方数据源（SEC EDGAR、港交所披露易、沪深交易所公告等）。Use whenever 用户要追踪资本流向、大额融资、巨额回购、大型并购、资金大事件、市场大额动向，或要生成/更新/校验 flows.json——即使只说"最近有什么大钱在动"。
license: MIT
---

# Whale Capital Flows · 巨鲸资本流向台账

一句话：**只记大钱**。低频、大金额、构成重大新闻的公开市场资金行为，一笔一条记录，统一格式，官方来源。

## 工作流（按序执行）

1. **确认范围（三要素，用户不指定就用默认并明说）**：
   - **地域**：region slug 或 `"all"`（默认全球）——来源按地域选（见 sources.md 分节）；
   - **时间窗**：`from`/`to`（默认：上次 meta.snapshot_date 次日 → 今天，增量）；
   - **事件类型**：默认全部十类。
   三要素**必须原样写入 flows.json 的 `meta.window`**，这是产出自述口径的一部分。
2. **读源目录**：打开 `references/sources.md`，按**事件类型**找官方渠道——本 skill 只允许列在 sources.md 里的官方源（交易所/监管披露/发行人正式公告），第三方财经媒体**只可用于交叉核对标题，不得作为数据来源**。
3. **抓取**：首选运行 `python3 scripts/collect.py --from <起> --to <止> --out <flows.json>`（内置 EDGAR+披露易双活源、金额提取、门槛过滤与已知坑规避）；需要细调或新源时手写 curl，带自标识 `User-Agent`，官方源限速串行（≥300ms）；HKEX 连发会软限流（返回空），失败等 ≥1 小时再试。
4. **大额过滤**：打开 `references/thresholds.md`，按事件类型套用金额门槛（或"当期全球前 20"备选资格）。**门槛之下的不写入**，但在摘要里报告"过滤掉 N 笔小额"。在途/预备事件（如 S-1 已递未定价）用**目标募资额**（proposed maximum aggregate offering price）过门槛，note 标注「目标募资」。
4.5 **管线刷新（每轮必做）**：除当日/窗口内新公告外，**重扫近 90 天的在途事件**（status=announced/priced 且未 completed 的记录），更新其状态与金额——休市日、公告淡日也能产出「预备信息」：IPO 管线（已递表待上市）、待执行回购计划、已宣布未交割并购。摘要单独一行报告「在途 N 条（较上轮 ±X）」。
5. **标准化**：打开 `references/schema.md` 逐字段映射。三条硬规则：
   - 金额统一折算**亿美元**写入 `amount_usd`（唯一金额字段）；
   - `event_id` 按规则生成（type:market:ticker/name:announce_date），保证幂等——重复采集同事件是**更新**而不是新增；
   - **字段极简**：必填 12 个 + 可选 4 个，`direction`/`amount_local`/`is_major` 等可派生字段一律不存（schema.md 有派生规则），校验器会拒绝契约外字段；
   - `news_title` 填官方公告原标题（可翻译为中文并在括号保留英文原题），`source_url` 必须指向官方页面。
6. **校验**：`python3 scripts/validate.py <flows.json>`，修到 0 错误。
7. **交付**：写出 `flows.json`（含 meta.window 口径）+ 摘要（各类型笔数/金额合计、Top5 大事件、被过滤的小额统计、失败源及原因）。

## 与 raising-collector 的分工

IPO/增发事件两边都可能采集：**明细与状态流转以 raising-collector 的 seed.ipos.jsonl 为准**；本 skill 只记金额过门槛的大额事件（可从 seed.ipos.jsonl 直接筛选生成，不必重新抓取）。回购/并购/债券/SPAC/GDR/REITs 是本 skill 独有范围。

## 范围边界

- 只覆盖**公开市场**：PE/VC 基金募集、私有公司融资不采集。
- 高频微额流量（tick 级资金流、日内南北向明细）不采集——那是行情 skill 的事。
- 资金面**指标**（VIX、利差、美元指数）不采集——本 skill 只记事件，不记环境。

## 快速示例

用户：「最近一个月全球有什么大额资本动向？」

执行：增量窗口 30 天 + 管线刷新 → sources.md 按类型过官方源 → 门槛过滤 → `validate.py` → 摘要：「共 23 笔：IPO 6 笔合计 87 亿$（最大 Circle 11 亿$）、巨型回购 3 笔（最大 Apple 900 亿$ 计划）、并购 2 笔（最大 xx 460 亿$）…已过滤 47 笔小额」
