# Whale Capital Tracker · 全球资本流向采集技能包

两个配套的 agent skill：从**官方稳定数据源**采集公开市场资金动向，输出**统一契约的 JSON 数据文件**。

## whale-capital-tracker · 巨鲸资本流向台账

只记大钱：低频、大金额、构成重大新闻的公开市场资金行为（IPO / 增发 / 可转债 / 债券 / SPAC / De-SPAC / GDR / REITs / 回购 / 并购 / 特别分红）。

```bash
# 一键采集（内置 SEC EDGAR + HKEX 披露易双活源）
python3 scripts/collect.py --from 2026-09-01 --to 2026-09-08 --out flows.json

# 契约校验
python3 scripts/validate.py flows.json
```

产出单一 JSON 文档（13 必填 + 7 可选字段，v1.0 冻结契约）：

```json
{
  "meta": { "snapshot_date": "...", "window": { "from": "...", "to": "...", "regions": ["all"] }, "count": 9 },
  "events": [{
    "event_id": "buyback:NASDAQ:AAPL:2025-05-01", "event_type": "buyback",
    "name": "苹果", "market": "纳斯达克", "region": "north_america",
    "announce_date": "2025-05-01", "status": "announced", "amount_usd": 1000.0,
    "news_title": "董事会批准 1000 亿美元回购计划",
    "source": "SEC EDGAR 8-K", "source_url": "https://www.sec.gov/...", "note": "..."
  }]
}
```

设计原则：**只允许官方源**（SEC EDGAR、交易所披露易等白名单；财经媒体仅交叉核对）；**金额门槛制**（IPO≥5亿$、债券≥10亿$、回购≥20亿$、并购≥50亿$，或当期前 20）；**常量派生不入库**（direction、默认对手方由 event_type 推导）；**机器层/展示层分离**（market_mic + domicile_country 国际标准码，中文仅为展示）。

实战沉淀的坑与规避（写进代码与文档）：EDGAR FTS 费用表壳页、承销协议样板条款假金额、HKEX gzip 与软限流。

## raising-collector · IPO 明细采集（companion）

采集 IPO 全量明细 → `seed.ipos.jsonl`（一行一司 20 字段：slug 枚举、日期、定价、募资/估值亿美元、首日表现、承销商）。与 whale-capital-tracker 共享 region/industry 枚举与汇率口径，两份数据可直接 join。

## 安装

```bash
npx skills add <owner>/whale-capital-tracker@whale-capital-tracker
npx skills add <owner>/whale-capital-tracker@raising-collector
```

## License

MIT
