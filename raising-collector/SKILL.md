---
name: raising-collector
description: 自动采集全球各交易所的募资/融资数据（IPO、增发、可转债、SPAC 等），清洗为标准化 JSONL（seed.ipos.jsonl + meta.json 契约）并校验数据质量。Use whenever the user asks to fetch, update, collect, or scrape IPO / 上市 / 募资 / 融资 / 打新 data for any exchange or region (纳斯达克、纽交所、港交所、上交所、深交所、东证等), or wants to generate, validate, or repair the seed.ipos.jsonl data file for the IPO Radar app — even if they just say "更新一下数据" or "看看最近有哪些新股".
license: MIT
---

# Raising Collector · 全球募资数据采集

把「各类网站的原始披露」加工成**一份标准 JSONL**：一行一家公司，App / 下游只认这份契约。

## 工作流（按序执行）

1. **确认范围**：哪些交易所/地区（默认全球主要交易所）＋ 时间窗口（默认：自上次 meta.json 的 snapshot_date 起，增量）。用户没说就按默认并在产出摘要里说明。
2. **读源目录**：打开 `references/sources.md`，只读涉及到的交易所小节。每个小节写明端点、格式、频率限制和已知的坑——照着做，不要自己发明端点。
3. **抓取**：优先用 `curl`（SEC 系必须带 `User-Agent` 头，否则 403）；HTML 源用结构化提取，不要全文 dump。单源失败先重试一次，仍失败记录到摘要里继续下一个源，不要中断整轮采集。
4. **标准化**：打开 `references/schema.md`，逐字段映射成契约格式。三条硬规则：
   - 枚举只允许 schema 里的 slug（region/industry/status），映射表在 schema.md；
   - 金额统一折算**亿美元**（汇率表 + 折算说明在 schema.md 末尾），当地货币原值放 `price_local`；
   - `listing_date` 对在途项目填**预计**日，宁可粗略不可缺失（它是排序与年份统计的依据）。
5. **校验**：运行 `python3 scripts/validate.py <文件.jsonl>`。有错误就修到 0 错误再交付；校验器的报错带行号，按行修。
6. **交付**：写出 `seed.ipos.jsonl`（首行 `_meta`，见 schema）与 `meta.json`，并给用户一段摘要：本轮新增/更新 N 家、按地区和 status 的分布、失败的数据源及原因、建议下次采集时间。

## 范围与边界

- **本 skill 的强项是 IPO/挂牌类事件**（filed→hearing→subscription→priced→listed 五态）。
- 增发、配股、可转债、SPAC 等其他募资方式：字段口径见 `references/raising-types.md`，采集时**不要混入 seed.ipos.jsonl**（那是 IPO 契约），放独立的 `followons.jsonl` / `converts.jsonl` 并在摘要里注明。
- 数据完整性口径：免费源对美股/港股可接近全覆盖，其余市场是「重要样本」而非全量。产出摘要必须如实标注覆盖性质，不得冒充全市场统计。

## 快速示例（期望的用户交互）

用户：「帮我抓一下最近一个月美股和港股的 IPO，更新到 seed.ipos.jsonl」

执行：读 sources.md 的 US/HK 小节 → curl EDGAR + HKEX → 映射字段（美元/港元→亿美元）→ `validate.py` 0 错误 → 覆盖写 `seed.ipos.jsonl`，`_meta.snapshot_date` 更新为今天 → 摘要：「美股新增 11 家（listed 9 / priced 2），港股新增 4 家；字段缺口：3 家未披露 first_day_return…」

## 何时不适用

- 用户要的是**行情报价/股价**而非募资事件 → 不要触发本 skill。
- 用户要的是历史统计报表（如「2024 年全球 IPO 募资排名」）→ 可以用本 skill 采集后自行聚合，但优先建议用户直接查交易所年度统计页（sources.md 附链接）。
