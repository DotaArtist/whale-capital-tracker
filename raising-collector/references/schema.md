# JSONL 契约 · seed.ipos.jsonl

一行一个 JSON 对象（UTF-8，无 BOM，换行 `\n`）。首行可选 `_meta`。

## 示例

```jsonl
{"_meta": {"snapshot_date": "2025-09-30", "version": 1, "count": 3}}
{"name": "Circle", "name_en": "Circle Internet", "ticker": "CRCL", "exchange": "纽约证交所", "exchange_short": "纽交所", "region": "north_america", "industry": "finance", "status": "listed", "listing_date": "2025-06-05", "filed_date": "2025-03-20", "price_local": 31.0, "price_range": null, "currency": "$", "raise_usd": 11.0, "valuation_usd": 69.0, "first_day_return": 168.5, "lead_brokers": ["摩根大通", "花旗"], "note": "USDC 稳定币发行方", "is_china_concept": false}
{"name": "宇树科技", "name_en": "Unitree Robotics", "ticker": "待定", "exchange": "上交所科创板", "exchange_short": "科创板", "region": "mainland", "industry": "manufacturing", "status": "filed", "listing_date": "2026-12-31", "filed_date": "2025-07-01", "price_local": null, "price_range": null, "currency": "¥", "raise_usd": null, "valuation_usd": 10.0, "first_day_return": null, "lead_brokers": ["中信证券"], "note": "已完成上市辅导备案", "is_china_concept": true}
```

## 字段表

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `name` | string | ✅ | 中文简称（无中文时用英文名） |
| `name_en` | string | ✅ | 英文/拼音名 |
| `ticker` | string | ✅ | 未分配填 `"待定"` |
| `exchange` | string | ✅ | 市场全名，如 `"香港交易所主板"` |
| `exchange_short` | string | ✅ | 表格短名，如 `"港交所"`（≤4 字） |
| `region` | enum | ✅ | 见下方枚举 |
| `industry` | enum | ✅ | 见下方枚举；按主业归类，拿不准选最接近的 |
| `status` | enum | ✅ | `filed` `hearing` `subscription` `priced` `listed`（五态单调递进） |
| `listing_date` | date | ✅ | `yyyy-MM-dd`；listed=实际挂牌日，在途=**预计**日 |
| `filed_date` | date | 可空 | 递表/备案日 |
| `price_local` | number | 可空 | 当地货币发行价 |
| `price_range` | string | 可空 | 招股区间，如 `"19–21"`；仅 subscription 态常有 |
| `currency` | string | ✅ | 显示符号：`$` `HK$` `¥` `₩` `₹` `€` `£` `SAR` `AED` `CHF` `Rp` 等 |
| `raise_usd` | number | 可空 | **亿美元**；在途=目标募资 |
| `valuation_usd` | number | 可空 | **亿美元**，发行估值 |
| `first_day_return` | number | 可空 | 百分数（`168.5` 即 +168.5%）；仅 listed |
| `lead_brokers` | string[] | 可空 | 主承销/保荐人 |
| `note` | string | ✅ | 一句话点评（≤40 字） |
| `is_china_concept` | bool | ✅ | 中概/中国背景 |

## 枚举映射表

**region**

| slug | 显示名 | 覆盖 |
| --- | --- | --- |
| `north_america` | 北美 | NYSE, Nasdaq, AMEX, TSX |
| `hong_kong` | 中国香港 | HKEX 主板/GEM |
| `mainland` | 中国内地 | 上交所/深交所/北交所 |
| `japan` | 日本 | TSE 等 JPX |
| `korea` | 韩国 | KRX |
| `europe` | 欧洲 | LSE, Deutsche Börse, Euronext, SIX 等 |
| `middle_east` | 中东 | Tadawul, DFM, ADX |
| `india` | 印度 | NSE, BSE |
| `apac` | 其他亚太 | ASX, SGX, IDX, TWSE 等 |

**industry**：`tech_internet` 科技互联网 · `semiconductor` 半导体 · `auto_ev` 新能源与汽车 · `pharma` 医药健康 · `finance` 金融保险 · `consumer` 消费零售 · `manufacturing` 工业制造 · `energy_materials` 能源材料 · `logistics` 运输物流 · `media_telecom` 电信传媒

**status 推进判定**（映射原始披露时的参考）：

| 原始状态 | status |
| --- | --- |
| 已递交招股书 / 辅导备案 / S-1 F-1 提交 | `filed` |
| 已过聆讯 / 注册生效 / 问询中后段 | `hearing` |
| 正在招股 / 路演簿记 / 区间已公布 | `subscription` |
| 已定价待挂牌 / 配售结果公布 | `priced` |
| 已挂牌交易（有首日收盘价） | `listed` |

## `_meta` 首行

```json
{"_meta": {"snapshot_date": "2025-09-30", "version": 1, "count": 3}}
```

`snapshot_date` 是全下游时间口径的锚点（滚动一年窗口、当年默认值），**必须等于数据实际截止日**，不是采集日。`count` 必须等于数据行数（校验器会核对）。

## 汇率折算（折成亿美元）

- 先得当地货币募资额：`price_local × 发行股数`，或披露的总募资额。
- 参考汇率（近似，写入 note 不必，仅供折算）：`1 USD ≈ 7.8 HKD ≈ 7.2 CNY ≈ 150 JPY ≈ 1350 KRW ≈ 84 INR ≈ 0.92 EUR ≈ 0.79 GBP ≈ 3.75 SAR ≈ 3.67 AED`
- 结果保留 1 位小数；无法折算时置 null，不要估。
