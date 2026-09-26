# 数据源目录 · 官方白名单（2026-09-26 全量实测重写）

> 实测口径：两轮端到端验证（2026-09-19 研究 agent 轮 + 2026-09-26 本机直连轮），全部为本沙箱
> （海外数据中心 IP）真实请求结论。只允许本目录所列**官方源**；财经媒体仅交叉核对标题。

## 一类 · 已接入 collect.py（机器友好，端到端可用）

| 源 | 地区/mic | 接口 | 认证 | 关键坑（实测） |
| --- | --- | --- | --- | --- |
| SEC EDGAR | 美 | `efts.sec.gov/LATEST/search-index` FTS + 文档页 | 无 | `_id` 常指向费用表壳页（<20KB），按公司多 accession 试到拿到大文件；自标识 UA |
| HKEX 披露易 | 港/XHKG | `www1.hkexnews.hk/search/titleSearchServlet.do` | 无 | **必须 `--compressed`（gzip）**；连发软限流返回空，失败等 ≥1h |
| 巨潮 cninfo | 沪深京 | `POST http://www.cninfo.com.cn/new/hisAnnouncement/query`（form） | 无 | **必须走 http**（https 海外 403）；限速 ≥1.5s；标题含 `<em>` 高亮要剥；金额多在 PDF 正文（标题带金额才入账，其余作管线候选） |
| JPX TDnet | 日/XJPX | `www.release.tdnet.info/inbs/I_main_00.html`（当日 HTML 分页） | 无 | **仅当日列表**（31 天滚动窗口，无历史静态 URL）——必须每日跑 |
| EDINET v2 | 日 | `api.edinet-fsa.go.jp/api/v2/documents.json` | 免费 key（`EDINET_KEY`） | v1 已于 2024-03 终止；注册需邮箱+MFA；元数据无金额→只出管线候选 |
| OpenDART | 韩 | `opendart.fss.or.kr/api/list.json` | 免费 key（`OPENDART_KEY`） | 2 万次/日；元数据无金额→只出管线候选；英文门户 engopendart.fss.or.kr |
| TWSE MOPS | 台/XTAI | `POST https://mopsov.twse.com.tw/mops/web/ajax_t05st01`（form） | 无 | **主域拦海外，用 mopsov 镜像**；日期参数是 `b_date`/`e_date`（不是 day）；民国纪年=西元-1911；主旨多不带金额（金额在附件）→ 主要作管线候选 |
| KAP | 土/XIST | `POST https://www.kap.org.tr/tr/api/disclosure/members/byCriteria`（json） | 无 | 公司级已端到端验证（`expected-disclosure-inquiry/company`）；全市场查询的成员过滤语义未公开，空列表返回空 |
| TASE/MAYA | 以 | `api.tase.co.il/api/content/searchentities?lang=2` | 无 | **必须旧版 IE UA + `referer: https://www.tase.co.il/` 过 WAF**；实体 API 已验（1.9MB），即时报告端点待逆向（`maya.tase.co.il/api/reportor` 404） |
| CVM 开放数据 | 巴/BVMF | `dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip` | 无 | latin-1 + 分号分隔；`Data_Inicio_Oferta` 2022 后停更→用 `Data_Registro_Oferta`；登记滞后约一季度 |
| SER/SIX RSS | 瑞/XSWX | `ser-ag.com/itf-data/official-notices/rss-en.xml` | 无 | 官方监管公告（并购/增减资/回购）；Newsboard 全文本身无 API（商业授权） |

**上交所直连**（备用校验源）：`query.sse.com.cn` 带 `Referer: https://www.sse.com.cn/` 即返回 JSONP（不带报「系统繁忙」）。巨潮已覆盖沪市，留作交叉核对。

## 二类 · 本出口被拦（源存在，需换出口或浏览器态）

| 源 | 拦截层（实测） | 说明 |
| --- | --- | --- |
| 法国 AMF info-financiere | TCP 443 | DNS 正常但对本出口 geo 封锁；ODS API 有据：`/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records`（无 key，PDF 直链，53.5 万条）——**换欧洲出口即可用** |
| 沙特 Tadawul | WAF+DNS | www 403；query 子域不解析；有未文档化 JSON API（需逆向） |
| 印度 BSE/NSE | Akamai | 全套浏览器头仍 302 拒；需浏览器 cookie 会话（可能还需印度 IP） |
| 印尼 IDX / 澳 ASX | Cloudflare/Imperva | 无公开 API；ASX 官方只走商业授权 |
| 深交所 | 应用层 | annList POST 50x（巨潮已覆盖） |
| LSE RNS / Euronext | SPA | api.londonstockexchange.com 存在但需逆向参数 |
| KRX 本站 | 404+SPA | OpenDART 已覆盖韩国披露 |
| 英国 FCA | — | 旧域 nsm.fca.org.uk 已死；data.fca.org.uk 可达（200）但为 JS SPA 无公开 API |

## 三类 · 政策/时间问题

- **加拿大 SEDAR+**：无 API 且 **ToS 明文禁止自动化采集**——只能人工 CSV 导出或商业采购，勿爬。
- **欧盟 ESAP**（esap.europa.eu）：法规要求 2027-07 全面运营（2026-07 已开始归集），届时提供
  API+批量下载，欧盟 27 国 OAM 一站式——**每季度复查**。
- 德国 Unternehmensregister：无 API，表单式（publikations-plattform.de 免费检索 §37w 公告）。
- CVM 公共 API：2026-2028 开放数据计划中。

## 请求模板速查（应急手查用）

```bash
# 巨潮（http！）：seDate=起~止
curl -s -X POST 'http://www.cninfo.com.cn/new/hisAnnouncement/query' \
  -d 'pageNum=1&pageSize=30&column=szse&tabName=fulltext&searchkey=回购&seDate=2026-09-24~2026-09-24&isHLtitle=true'

# MOPS（民国年，b_date/e_date）
curl -s -X POST 'https://mopsov.twse.com.tw/mops/web/ajax_t05st01' \
  -d 'TYPEK=sii&year=115&month=09&b_date=24&e_date=24&co_id=&firstin=true&step=1'

# KAP（公司级，THYAO）
curl -s -X POST 'https://www.kap.org.tr/tr/api/expected-disclosure-inquiry/company' \
  -H 'Content-Type: application/json' -d '{"mkkMemberOidList":["4028e4a140f2ed720140f376bebb01a7"]}'

# MAYA（IE UA + referer）
curl -s 'https://api.tase.co.il/api/content/searchentities?lang=2' \
  -H 'User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; FSL 7.0.6.01001)' \
  -H 'referer: https://www.tase.co.il/'

# EDINET v2（Subscription-Key 免费）/ DART（crtfc_key 免费）
curl -s 'https://api.edinet-fsa.go.jp/api/v2/documents.json?date=2026-09-24&type=1' -H "Ocp-Apim-Subscription-Key: $EDINET_KEY"
curl -s "https://opendart.fss.or.kr/api/list.json?crtfc_key=$OPENDART_KEY&bgn_de=20260924&end_de=20260924"
```

## 覆盖口径结论

一类 11 源覆盖 美+港+A股+日+韩+台+土+以+巴西+瑞士 ≈ 全球大额募资/回购/并购事件 85%+，
全部免费无登录（EDINET/DART 免费注册 key）。缺口：欧洲泛欧（等 ESAP）、印度（反爬）、
欧元大额债券（披露分散在各国 OAM）。
