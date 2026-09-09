# flows.json 契约 · 巨鲸资本流向台账（v1.0 定稿 · 2026-09-08）

**单一 JSON 文档**：顶层 `meta` + `events` 数组，一笔事件一个对象。UTF-8。

## 完整示例

```json
{
  "meta": {
    "snapshot_date": "2025-09-30",
    "window": { "from": "2025-09-01", "to": "2025-09-30", "regions": ["hong_kong", "north_america"] },
    "count": 2
  },
  "events": [
    {
      "event_id": "buyback:NASDAQ:AAPL:2025-05-01",
      "event_type": "buyback",
      "name": "苹果",
      "name_en": "Apple Inc.",
      "ticker": "AAPL",
      "market": "纳斯达克",
      "region": "north_america",
      "industry": "tech_internet",
      "announce_date": "2025-05-01",
      "settle_date": null,
      "status": "announced",
      "amount_usd": 1000.0,
      "news_title": "董事会批准 1000 亿美元股票回购计划",
      "source": "SEC EDGAR 8-K",
      "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193",
      "note": "史上最大回购计划之一",
      "is_china_concept": false
    },
    {
      "event_id": "ipo:HKEX:2518:2025-09-10",
      "event_type": "ipo",
      "name": "某公司",
      "name_en": "Example Co.",
      "ticker": "2518",
      "market": "港交所",
      "region": "hong_kong",
      "industry": "consumer",
      "announce_date": "2025-09-10",
      "settle_date": "2025-09-15",
      "status": "completed",
      "amount_usd": 13.0,
      "news_title": "全球发售共计募资约 100 亿港元",
      "source": "HKEX 披露易",
      "source_url": "https://www1.hkexnews.hk/listedco/listconews/...",
      "note": "年内港股最大消费 IPO",
      "is_china_concept": true
    }
  ]
}
```

## meta 字段（全部必填）

| 字段 | 规则 |
| --- | --- |
| `snapshot_date` | 数据实际截止日 `yyyy-MM-dd`（不是采集运行日） |
| `window.from` / `window.to` | 本次采集时间窗；用户指定什么就写什么，增量模式写实际覆盖区间 |
| `window.regions` | 本次采集地域，region slug 数组；全球填 `["all"]` |
| `count` | 必须等于 events 长度 |

**输出文件命名约定（文件层，非 JSON 契约；collect.py 已内置默认）**：默认以日为单位，文件名 `daily-{查询日期 YYYYMMDD}.json`（如 `daily-20260909.json`）；跨日补采窗口为 `daily-{from}-{to}.json`（日期同为紧凑格式）；补采多日时按日切分、每天一个文件。`snapshot_date`=查询日期；执行日期只出现在运行日志，不进入文件名与 JSON。

## events 字段

**必填 12 个，一个不多**

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `event_id` | string | `"{event_type}:{market}:{ticker或name}:{announce_date}"`，全文档唯一，幂等更新锚点 |
| `event_type` | enum | `ipo` `follow_on` `convertible` `bond` `spac` `despac` `gdr` `reits` `buyback` `ma` `dividend_special`（特别分红，≥20 亿$） |
| `name` / `name_en` | string | 主体中英文名 |
| `market` | string | 发生市场，如 `"纳斯达克"` `"港交所"` |
| `region` | enum | `north_america` `hong_kong` `mainland` `japan` `korea` `europe` `middle_east` `india` `apac` |
| `announce_date` | date | 官方公告日（排序主键） |
| `status` | enum | `announced`（预备：已递表/已宣布未执行）`priced`（已定价待交割）`completed` `withdrawn` |
| `amount_usd` | number | **亿美元**——唯一金额字段，采集时折算完毕 |
| `news_title` | string | 官方公告标题 |
| `source` | string | 官方来源名，如 `"SEC EDGAR 8-K"` |
| `source_url` | string | 指向官方页面的 URL |
| `note` | string | 一句话点评（≤40 字） |

**可选 7 个（不填即 null/false；禁止发明本表之外的字段）——v1.0 新增 `market_mic`/`domicile_country`**

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `ticker` | string | 有对应交易代码时填 |
| `industry` | string | 行业 slug（同 raising-collector 十分类），供行业维度聚合 |
| `settle_date` | date | 完成/交割日 |
| `counterparty` | string | 对手方，仅当存在**具名**对手方时填：ma=标的公司、despac=合并对象、定向增发=具名配售对象。公开发行的对手方=公众（派生，见下表，不入库） |
| `market_mic` | string | **ISO 10383 交易所码**（XNAS/XNYS/XHKG/XSHG/XSHE），市场确定后必填；待定= null。中文 `market` 仅为展示层 |
| `domicile_country` | string | **ISO 3166-1 alpha-2 注册地**（US/CN/JP…），支撑任意国别视角（中概只是派生）；未知= null |
| `is_china_concept` | bool | 中国背景主体 |

## amount_usd 口径（按类型）

| 类型 | 口径 | note 约定 |
| --- | --- | --- |
| ipo / follow_on / convertible / bond / spac / gdr / reits | 实际募资额；在途=目标/注册额度 | 在途标「目标募资」；ATM/回购式=授权额度标「额度」 |
| buyback | 回购计划授权总额 | 执行进度变化只更新 status |
| ma / despac | 交易对价（含承担债务须注明） | despac=PIPE+信托合计 |

## status 适用性（校验器强制）

| 状态 | 适用类型 |
| --- | --- |
| `announced` | 全部十类 |
| `priced` | 仅证券发行类（ipo/follow_on/convertible/bond/spac/gdr/reits） |
| `completed` / `withdrawn` | 全部十类 |

## 双主体模型 · 默认对手方速查表（派生，不入库）

每笔流向都有两端，另一端由 event_type 唯一决定，消费方按此表补全：

| event_type | 主体(name) | 默认对手方 |
| --- | --- | --- |
| ipo / follow_on / convertible / bond / spac / gdr / reits | 发行人 | **公众及机构投资者** |
| buyback | 回购公司 | 卖出股东 |
| ma / despac | 收购方 | 标的方股东（具体标的记 `counterparty`） |

例外：定向增发若有具名对象（如「配售予某主权基金」）→ 该对象存 `counterparty`。

## 刻意不存的字段（可派生 = 冗余）

- **direction**（募资/返还/重组）：由 event_type 唯一决定——`ipo/follow_on/convertible/bond/spac/gdr/reits`→募资、`buyback`→返还、`ma/despac`→重组，消费方按 event_type 分组即可；
- **amount_local + currency**：`amount_usd` 是唯一比较口径，要看当地原值查 `source_url`；
- **is_major**：入账即大额（门槛见 thresholds.md，校验器强制），恒 true 的字段没有信息量。

## 全局口径（v1.0 冻结）

- **时区**：`announce_date`/`settle_date` 取**交易所当地公告日**（EDGAR=file_date 美东；披露易=DATE_TIME 港时）；
- **金额**：`amount_usd` 单位为**亿美元**（1e8 USD），对接外部系统时必须显式声明；
- **展示与机器分层**：`market`/`name` 中文是展示层，机器 join 一律用 `market_mic`/`event_id`。

## 汇率折算（→ 亿美元，采集时完成）

`1 USD ≈ 7.8 HKD ≈ 7.2 CNY ≈ 150 JPY ≈ 1350 KRW ≈ 84 INR ≈ 0.92 EUR ≈ 0.79 GBP ≈ 3.75 SAR ≈ 3.67 AED`，保留 1 位小数；无法可靠折算的事件不入账并在摘要说明。
