# 数据源目录 · 按交易所

原则：**官方披露优先于第三方聚合**；每源先小批量试抓确认结构再全量；所有请求带 `User-Agent: raising-collector/1.0 (contact: local)` 风格的自标识头（SEC 强制，其他源也是好习惯）。频率：同一域名串行请求，间隔 ≥300ms。

## 美国 · NYSE / Nasdaq（覆盖最完整，从这里起步）

### SEC EDGAR（首选，结构化 JSON，免费）
- 新提交的注册文件：`https://efts.sec.gov/LATEST/search-index?q=&dateRange=custom&startdt=<yyyy-mm-dd>&enddt=<yyyy-mm-dd>&forms=S-1,S-1/A,F-1,F-1/A,424B4`
  实际可用端点：`https://efts.sec.gov/LATEST/search-index?q=%22%22&forms=S-1` → 用 **full-text search API**：
  `https://efts.sec.gov/LATEST/search-index?q="initial public offering"&forms=S-1&dateRange=custom&startdt=...&enddt=...`
- 提交结果 JSON：`https://data.sec.gov/submissions/CIK##########.json`（含表单、日期、地址→可推交易所）
- **424B4 = 最终招股书**：定价后的版本，从中取发行价、股数、承销商 → `priced`/`listed` 态的权威字段来源
- 头部必须：`User-Agent: <name> <email>`，否则 403。限速 10 req/s。
- 首日表现：EDGAR 没有 → 配合行情源（见下）。

### 行情/首日表现（补 first_day_return）
- Nasdaq 官方 API（无文档但稳定）：`https://api.nasdaq.com/api/quote/<TICKER>/info?assetclass=stocks`
- 首日收盘 vs 发行价：`first_day_return = (首日收盘 − price_local) / price_local × 100`

### 校验源
- `https://www.nasdaq.com/market-activity/ipos`（日历视图，人工核对用）

## 中国香港 · HKEX

- 披露易：`https://www1.hkexnews.hk/search/titlesearch.xhtml`（POST 表单，返回 HTML 表格；参数 `fromDate/toDate/...`）
- 新上市/申请进度：`https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities?sc_lang=zh-CN`（页面底部有新上市列表 JSON：`https://www1.hkex.com.hk/hkexwidget/data/getequitylist?...`，字段含上市日期/中文简称/代码）
- 招股书 PDF 在披露易（field: 「 Prospectuses」）→ 取发行价区间、保荐人
- 首日表现：用代码查行情（Yahoo Finance `0700.HK` 风格后缀 `.HK`）

## 中国内地 · 上交所 / 深交所 / 北交所

- 上交所项目信息：`https://project.sse.com.cn/`（注册制审核项目公示，JSON 接口 `.../queryAppStatus`），科创板/主板分表
- 深交所：`https://dc.szse.cn/`（发行上市审核网站，有公开 JSON）
- 北交所：`https://www.bse.cn/auditcentre/`
- 募资与发行价：待上市公告（`ipo.csrc.gov.cn` 亦可交叉）——**内地源以 HTML 为主**，字段要逐页解析，预算多留时间
- 首日表现：上市次日行情（新浪/东财公开接口 `hq.sinajs.cn`）

## 日本 · TSE / JPX

- 新上市日程：`https://www.jpx.co.jp/english/corporate/investors/ir/listing/`（HTML 表格，含预计上市日/代码/主办券商）
- 上市后数据补行情源

## 韩国 · KRX

- 新上市：`http://global.krx.co.kr/`（Statistics → New Listings，有 CSV/Excel 下载链接）

## 印度 · NSE/BSE

- NSE 新上市：`https://www.nseindia.com/market-data/new-listings`（需带浏览器风格头，否则 403）

## 欧洲 / 中东 / 其他

- LSE 新发行：`https://www.londonstockexchange.com/new-admissions`（HTML+内嵌 JSON）
- Euronext：`https://live.euronext.com/en/listing-view/ipo` 
- Tadawul（沙特）：月度统计 PDF（官网 Statistics 页）
- 兜底聚合（非官方、做交叉验证而非首选）：Wikipedia 年度 IPO 列表、Renaissance Capital 免费月报（us IPO 覆盖极好）

## 官方年度/月度统计（回答「总量」类问题直接引用，不必自行累加）

- 厘清覆盖口径后再引用：各交易所月报的「募资额」通常含增发，与 IPO 口径不同（见 raising-types.md）
