---
name: whale-capital-tracker
description: 采集全球资本流向事件记录：大额募资（IPO/增发/可转债/债券）、巨型回购、并购、SPAC/GDR/REITs、一级市场大额融资轮（SEC Form D，funding_round ≥2亿$）、基金募资/战略入股/分拆/私有化（词表新八类）等低频大金额且构成重大新闻的资金行为，另可选输出宏观资本流动快照（TIC/MOF/NBIM/SAMR，meta.flows）。默认以日为单位采集，输出 daily-{查询日期 YYYYMMDD}.json（如 daily-20260928.json，meta + events）。只使用稳定官方数据源（SEC EDGAR、SEC Form D、港交所披露易、巨潮、TDnet/EDINET、OpenDART、台湾 MOPS、KAP、TASE、巴西 CVM、SIX 等 12 源，见 sources.md）。Use whenever 用户要追踪资本流向、大额融资、巨额回购、大型并购、一级市场大额轮、资金大事件、市场大额动向，或要生成/更新/校验每日流向文件——即使只说"最近有什么大钱在动"。
license: PolyForm-Noncommercial-1.0.0
---

# Whale Capital Flows · 巨鲸资本流向台账（v2.0 · 2026-09-28）

> v2.0 基于 dotaartist/whale-capital-tracker v1 + 本地 `references/event_types.md` 词表 v0.1 扩展：
> 新增源 SEC Form D（美国一级市场官方全量）、宏观 flows 快照层、词表八类新事件类型。

一句话：**只记大钱**。低频、大金额、构成重大新闻的公开市场与一级市场资金行为，一笔一条记录，统一格式，官方来源。

## 工作流（按序执行）

1. **确认范围（三要素，用户不指定就用默认并明说）**：
   - **地域**：region slug 或 `"all"`（默认全球）——来源按地域选（见 sources.md 分节）；
   - **时间窗**：**默认以日为单位**——查询日期默认=执行当日（单日窗口 `from`=`to`=该日）；补采多日时**按日切分、每天一个文件**（自上次最大查询日期次日起逐日生成），不要合并成一个大窗口；
   - **事件类型**：默认全部十九类（v1 十一类 + v2 词表八类）。
   三要素**必须原样写入产出文件的 `meta.window`**，这是产出自述口径的一部分。
2. **读源目录**：打开 `references/sources.md`，按**事件类型**找官方渠道——本 skill 只允许列在 sources.md 里的官方源（交易所/监管披露/发行人正式公告），第三方财经媒体**只可用于交叉核对标题，不得作为数据来源**；事件判定边界查 `references/event_types.md`（21 类词表，v2 契约先纳其中八类）；新源评估与接入路线图查 `references/catalog.md`（《全球资本动向数据源目录》，仅公开免费源）。
3. **抓取**：首选运行 `python3 scripts/collect.py`（无参数=采集今天一天；`--date <日>` 采指定日；`--sources cninfo,mopsov` 只跑指定源；`--flows` 附宏观快照；内置 12 源：EDGAR/HKEX/巨潮/TDnet/EDINET/DART/MOPS/KAP/MAYA/CVM/SIX/**FormD**，含金额提取、门槛过滤与已知坑规避）；EDINET/DART 需免费 key（环境变量 `EDINET_KEY`/`OPENDART_KEY`，缺省自动跳过）；需要细调或新源时手写 curl，带自标识 `User-Agent`，官方源限速串行（≥300ms）；HKEX 连发会软限流（返回空），失败等 ≥1 小时再试。**Form D 发现路径只能走 daily-index master.idx**（FTS 不索引 Form D），部分出口对 daily-index 返回 AccessDenied——脚本会提示并跳过，换出口即可。
4. **大额过滤**：打开 `references/thresholds.md`，按事件类型套用金额门槛（或"当期全球前 20"备选资格）。**门槛之下的不写入**，但在摘要里报告"过滤掉 N 笔小额"。在途/预备事件（如 S-1 已递未定价）用**目标募资额**（proposed maximum aggregate offering price）过门槛，note 标注「目标募资」；funding_round 优先 Total Amount Sold（已售金额），未售新申报用 Total Offering Amount 并标「目标募资」。
4.5 **管线刷新（每轮必做）**：除当日/窗口内新公告外，**重扫近 90 天的在途事件**（status=announced/priced 且未 completed 的记录），更新其状态与金额——休市日、公告淡日也能产出「预备信息」：IPO 管线（已递表待上市）、待执行回购计划、已宣布未交割并购。摘要单独一行报告「在途 N 条（较上轮 ±X）」。
4.7 **宏观 flows 快照（用户要宏观动向或加 `--flows` 时）**：脚本已登记 TIC/MOF/NBIM/SAMR 四序列并探测可达性（meta.flows，value=null）；**agent 按 sources.md F 节逐序列人工核对官方页后填入 `as_of` 与 `value`**，note 记口径。宏观层只进 flows 快照，不生成事件。
5. **标准化**：打开 `references/schema.md` 逐字段映射。三条硬规则：
   - 金额统一折算**亿美元**写入 `amount_usd`（唯一金额字段）；
   - `event_id` 按规则生成（type:market:ticker/name:announce_date），保证幂等——重复采集同事件是**更新**而不是新增；
   - **字段极简**：必填 12 个 + 可选 4 个，`direction`/`amount_local`/`is_major` 等可派生字段一律不存（schema.md 有派生规则），校验器会拒绝契约外字段；
   - `news_title` 填官方公告原标题（可翻译为中文并在括号保留英文原题），`source_url` 必须指向官方页面。
6. **校验**：`python3 scripts/validate.py <产出文件>`，修到 0 错误。
7. **交付**：**输出文件默认命名 `daily-{查询日期 YYYYMMDD}.json`**（collect.py 已内置该默认值，如 `daily-20260909.json`）。跨日窗口由脚本**自动按日切分为多个文件**——每天一个 `daily-{YYYYMMDD}.json`（无事件的空日也落一个 count=0 文件，便于对账）；只有用户显式指定 `--out` 时才合并为单文件。外加摘要（各类型笔数/金额合计、Top5 大事件、被过滤的小额统计、失败源及原因）。

## 与 raising-collector 的分工（另一独立 skill，未包含在本仓库）

IPO/增发事件两边都可能采集：**明细与状态流转以 raising-collector 的 seed.ipos.jsonl 为准**；本 skill 只记金额过门槛的大额事件（可从 seed.ipos.jsonl 直接筛选生成，不必重新抓取）。回购/并购/债券/SPAC/GDR/REITs 是本 skill 独有范围。

## 范围边界

- **公开市场全覆盖**（v1 范围）+ **一级市场大额公司融资**（v2 新增）：`funding_round` ≥2亿$（Form D 官方源）、`fund_close` ≥2亿$（基金 final close）、`strategic_stake` ≥2亿$；小额私募轮、天使/A 轮不采集。
- 结构性重组事件（词表）：`spin_off`/`divestiture`/`going_private` ≥5亿$、`stake_reduction` ≥1亿$、`jv` 不设门槛。
- 宏观与跨境资本流动（TIC/央行/主权持仓）只进 `meta.flows` 快照，不生成事件；高频微额流量（tick 级资金流、日内南北向明细）不采集——那是行情 skill 的事。
- 资金面**指标**（VIX、利差、美元指数）不采集——本 skill 只记事件与官方流量，不记环境。
- 待接入（sources.md 二类）：SGX（GraphQL 持久化查询待逆向）、Oslo NewsWeb（API 域待解析）、ESAP（2027-07）。

## 快速示例

用户：「跑一下今天的资本动向」/「最近有什么大钱在动？」

执行：默认单日（今天）`python3 scripts/collect.py` → 输出 `daily-20260909.json` + 管线刷新 → `validate.py` → 摘要：「共 23 笔：IPO 6 笔合计 87 亿$（最大 Circle 11 亿$）、巨型回购 3 笔（最大 Apple 900 亿$ 计划）、并购 2 笔（最大 xx 460 亿$）…已过滤 47 笔小额」

用户：「补采上周的」（上次已采到上周二）

执行：自上次次日**逐日各跑一个文件**（`--date` 上周三/四/五…），每天产出 `daily-{该日 YYYYMMDD}.json`，不合并窗口。
