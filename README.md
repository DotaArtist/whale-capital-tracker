# Whale Capital Tracker · 全球资本流向 Agent Skill

从**官方稳定数据源**采集公开市场资金动向，输出**统一契约的每日 JSON 数据文件**（`daily-{查询日期 YYYYMMDD}.json`）的 agent skill。

## whale-capital-tracker · 巨鲸资本流向台账

只记大钱：低频、大金额、构成重大新闻的公开市场资金行为（IPO / 增发 / 可转债 / 债券 / SPAC / De-SPAC / GDR / REITs / 回购 / 并购 / 特别分红）。

```bash
# 每日采集（默认以日为单位：不带参数 = 采集今天一天）
python3 scripts/collect.py                    # → daily-20260909.json
python3 scripts/collect.py --date 2026-09-08  # 补采指定某一天

# 契约校验
python3 scripts/validate.py daily-20260908.json
```

**输出文件命名**：`daily-{查询日期 YYYYMMDD}.json`，每天一个文件、按日归档，查询日期记录在文件名里；跨日补采窗口**自动按日切分为多个文件**（无事件的空日也落一个 count=0 文件，便于对账），仅显式 `--out` 时合并为单文件。

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

## 使用要求

python3 与 curl（系统自带）；能访问 SEC EDGAR / 港交所披露易的网络。作为 agent skill 安装后，对它说「看看最近有什么大额资金动向」「采集 8 月的巨鲸事件到 flows.json」即可自动触发；脚本亦可独立运行（见上方命令）。

## 安装

```bash
npx skills add DotaArtist/whale-capital-tracker
```

## License

**PolyForm Noncommercial 1.0.0**——个人学习、研究、爱好者项目及非营利组织**免费**；任何**商业用途需另行获得授权**，联系：desplode@outlook.com。

> 注：v1.0 早期版本（2026-09-09 前的提交）曾以 MIT 发布，那些历史版本对已获取者仍按 MIT 授权；本协议自此之后的所有版本生效。
