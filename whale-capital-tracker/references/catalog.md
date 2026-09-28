# 全球资本投资动向 · 数据源目录

> 参考项目:[whale-capital-tracker](https://github.com/dotaartist/whale-capital-tracker)(只记公开市场大额事件,11 个官方源白名单)。
> 本目录把范围扩展为三大板块:**A 公开市场**(IPO/增发/债/回购/M&A/SPAC/REITs)、**B 一级市场**(VC/PE/Growth 融资与基金募资)、**C 宏观与跨境资本流动**(央行/TIC/主权基金/基金流向)。
>
> 端点验证时间:2026-09-28(本机 curl 实测)。**本目录仅收录公开/免费数据源,已剔除全部商业付费数据库。** 状态分三级:**✅ 已验证可用 / 🔑 免费可用但需 key / ⚠️ 被拦或无 API(需逆向/换出口)**。

---

## 0. 继承自参考项目的契约(建议沿用)

| 原则 | 内容 |
|---|---|
| 官方优先 | 监管披露/交易所为唯一主源;财经媒体只作交叉核对 |
| 金额门槛 | IPO≥5亿$、债券≥10亿$、回购≥20亿$、并购≥50亿$,或当期全球前 20;门槛下不写入,摘要报过滤数 |
| 幂等 | `event_id = type:market:ticker/name:announce_date` |
| 归档 | 按日 `daily-{YYYYMMDD}.json`,空日落 count=0;近 90 天在途事件每轮重扫 |
| 限速 | 串行、≥300ms/请求;被软限流(HKEX)等 ≥1h 再试 |

---

## A. 公开市场披露源

### A1. 基线:whale-capital-tracker 已接入的 11 源(直接复用)

| 源 | 地区 | 状态 | 备注 |
|---|---|---|---|
| SEC EDGAR(efts FTS) | 美国 | ✅(本文再次验证) | 8-K/S-1/F-1;需自标识 UA |
| HKEX 披露易 | 香港 | ✅ | 必须 `--compressed`;连发会被软限流 |
| 巨潮 cninfo | 沪深京 | ✅ | 走 http(https 海外 403);限速 ≥1.5s |
| JPX TDnet | 日本 | ✅ | 仅当日列表,须每日跑 |
| EDINET v2 | 日本 | 🔑 | `EDINET_KEY` 免费注册;元数据无金额 |
| OpenDART | 韩国 | 🔑 | `OPENDART_KEY`;2万次/日 |
| TWSE MOPS | 台湾 | ✅ | 用 `mopsov.twse.com.tw` 镜像;民国纪年−1911 |
| KAP | 土耳其 | ✅ | 公司级已验证 |
| TASE/MAYA | 以色列 | ✅ | 需旧版 IE UA + referer |
| CVM 开放数据 | 巴西 | ✅ | zip 分号分隔;登记滞后约一季度 |
| SER/SIX RSS | 瑞士 | ✅ | `ser-ag.com/itf-data/official-notices/rss-en.xml` |

**已知缺口**(原项目自认):欧洲泛欧(等 ESAP 2027)、印度(反爬)、欧元大额债券(各国 OAM 分散)。下面 A2 逐个补。

### A2. 新增推荐(按地区)

#### 北美

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| SEC EDGAR 全文检索(`efts.sec.gov/LATEST/search-index`) | 上述+Form D 一级市场 | 同基线,`forms=D` 过滤 | ✅ 端点活着 |
| MSRB EMMA | 美国市政债发行/交易 | 网页 ✗ 反爬(实测 403);正式 [EMMA API](https://emma.msrb.org) 需签数据协议 | ⚠️ |
| 加拿大 SEDAR+ | 全部披露 | 无 API,ToS 禁止自动化 | ⚠️ 只能人工导出 |
| TSX/CTV 新上市 | 加拿大 IPO | tsx.com listing 页面 | ⚠️ |

#### 欧洲

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| 法国 AMF ODS | 法国公开要约/募资 | `data.amf-france.fr` ODS API,无 key,53.5万条 | ⚠️ geo 封锁,换欧洲出口即可 |
| 德国 publikations-plattform | 德国 §37w 增发公告 | 免费检索页;Unternehmensregister 无 API | ⚠️ |
| EQS News(德奥瑞) | 德语区公司公告 | eqs-news.com RSS/检索 | ✅ RSS 免费 |
| 英国 LSE RNS | 英国全监管公告(RNS) | SPA 需逆向;`api.londonstockexchange.com` 有隐藏 JSON | ⚠️ |
| Euronext(巴黎/阿姆/布鲁塞尔/米兰等) | 泛欧上市/增发 | SPA,`live.euronext.com` 有待逆向端点 | ⚠️ |
| Nasdaq Nordic(斯德哥尔摩/赫尔辛基/哥本哈根) | 北欧公告/交易 | 旧 `nasdaqomxnordic.com` 端点实测 301 → nasdaq.com,需重新逆向 | ⚠️ 已改版 |
| **Oslo Børs NewsWeb** | 挪威全部公告(含增发/并购) | `newsweb.oslobors.no`,实测 200,有 JSON 检索端点 | ✅ **优先接入** |
| ESAP(欧盟 27 国一站式) | 全欧 OAM | 法定 2027-07 全面运营,届时提供 API+批量下载 | ⚠️ 每季度复查 |

#### 中东

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| 沙特 Tadawul | 沙特全部 | WAF+DNS;存在未文档化 JSON | ⚠️ |
| 迪拜 DFM / 阿布扎比 ADX | UAE 公告 | 官网公告检索,部分 JSON | ⚠️ |

#### 亚太(补 whale 缺口)

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| **新加坡 SGX** | 新加坡公告+IPO+债 | `api2.sgx.com/content-api?category=announcement&...` **实测 200** | ✅ **优先接入** |
| 泰国 SET | 泰国公告/新上市 | set.or.th 新闻门户,网页检索 | ⚠️ API 待逆向 |
| 马来西亚 Bursa | 马来公告 | SPA 检索 | ⚠️ |
| 印尼 IDX | 印尼公告 | Cloudflare | ⚠️ |
| 菲律宾 PSE EDGE | 菲律宾披露 | `edge.pse.com.ph` 网页检索,免费 | ⚠️ |
| 越南 HOSE/HNX | 越南公告 | 网页/JSON 混合 | ⚠️ |
| 澳洲 ASX | 澳洲公告平台 | Imperva 反爬 | ⚠️ |
| 印度 BSE/NSE | 印度公司行动/公告 | Akamai 拦截(实测连不通);需印度 IP+浏览器 cookie | ⚠️ |
| 印度 SEBI | 监管层公告 | sebi.gov.in 公告检索可用 | ⚠️ 部分可用 |
| 上交所(备用交叉核对) | 沪市 | `query.sse.com.cn` + `Referer: https://www.sse.com.cn/`,**实测 200** | ✅ |

#### 拉美/非洲

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| 墨西哥 BMV | 墨西哥公告 | 网页 | ⚠️ |
| 智利 CMF | 智利开放数据 | cmf.cl 有开放数据集 | ⚠️ 待验证 |
| 南非 JSE SENS | 南非公告 | jse.co.za 网页检索 | ⚠️ |

---

## B. 一级市场(VC/PE/Growth)——参考项目明确不覆盖,本目录重点补

### B1. 官方登记源(免费,首选)

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| **SEC Form D**(EDGAR) | 美国 VC/PE/Growth 融资(>$0 豁免发行必须报) | `efts.sec.gov/LATEST/search-index` `forms=D`;结构化数据集 `go.usa.gov` / EDGAR D 检索;含金额/轮次投资人 | ✅ **最高优先级,免费且官方** |
| **英国 Companies House** | 英国全部私人公司股本变更(SH01=增资) | `api.company-information.service.gov.uk`,免费 key(实测 401=需 key,端点正常) | 🔑 |
| 中国国家企业信用信息公示系统 | 中国股权变更 | 网页免费,无 API | ⚠️ |
| 中基协 AMBERS 公示 | 中国私募基金/管理人登记与基金规模 | `gs.amac.org.cn` 公示查询 | ✅ 网页 |

> Form D 是一级市场的"官方大锅饭":美国私募融资(>$0 豁免发行)必须申报,含目标募资额、轮次、投资人,延迟数天——商业数据库的美国数据大半源于此。英国 SH01 同理。**中印一级市场无官方逐笔公开源,用公开通稿与行业媒体补(见 B2)。** 欧洲大陆各国官方登记处(德国共同登记门户 handelsregister.de、法国 Infogreffe、荷兰 KVK)检索免费、部分文件有法定小额费用,需要时再评估。

### B2. 公开通稿与行业媒体(免费;补登记源覆盖不到的地区与轮次叙事)

| 源 | 覆盖 | 接入 | 状态 |
|---|---|---|---|
| 公司官方 newsroom / PR Newswire / Business Wire | 全球融资通稿(全文免费) | 检索页 + RSS | ✅ |
| TechCrunch Funding Rounds | 全球一级市场(美/欧强) | `techcrunch.com/category/funding-rounds/` + RSS | ✅ |
| Sifted(FT 旗下免费层) | 欧洲一级市场 | sifted.eu,免费注册 | ✅ |
| Inc42 / YourStory | 印度一级市场 | 新闻 + 统计页 | ✅ |
| 晚点 LatePost / 36氪 | 中国一级市场 | 免费文章 | ✅ |
| Y Combinator 公司目录 | YC 系公司融资去向 | `ycombinator.com/companies` | ✅ |

### B3. 免费/协会统计(用于月度校准,非逐笔)

| 源 | 内容 | 状态 |
|---|---|---|
| NVCA | 美国 VC 季度报告(免费下载) | ✅ 免费 PDF |
| Invest Europe | 欧洲私募募资统计 | ✅ 免费 |
| AVCJ | 亚洲私募简讯 | 部分 ✅ |
| 中基协季度报告 | 中国私募规模 | ✅ |

---

## C. 宏观与跨境资本流动

### C1. 官方统计(全部免费)

| 源 | 内容 | 接入 | 状态 |
|---|---|---|---|
| **美联储 TIC** | 月度跨境证券买卖、各国持美债(外资买美股/美债的金标准) | home.treasury.gov/data/treasury-international-capital-tic-system,**实测 200**,CSV 直下 | ✅ **优先接入** |
| IMF | BOP/IIP/CPIS(组合投资协同调查,双边资本流动矩阵) | 新门户 `data.imf.org`;旧 SDMX JSON 端点实测连不通(退役迁移中) | ⚠️ 用新门户 |
| BIS | 银行跨境头寸(LBS)、国际债券发行 | `stats.bis.org/api/v1/data/{flow}/{key}` SDMX(实测根路径 400=正常,须带 flow) | ✅ |
| ECB SDW | 欧元区国际收支/基金持仓(SHS)/Target2 | `data-api.ecb.europa.eu/service/data/{flow}`(根 404 正常) | ✅ |
| 日本财务省 | 周度对外/对内证券投资(外资买日股债,最高频免费源) | mof.go.jp CSV 直下 | ✅ |
| 中国外管局 SAFE | 国际收支、QFII/RQFII 额度、银行结售汇 | safe.gov.cn 公开数据 | ⚠️ 海外访问慢 |
| 韩国央行/台湾央行 | 外资证券投资周报 | 官网开放数据 | ✅ |

### C2. 基金流向

| 源 | 内容 | 状态 |
|---|---|---|
| ICI | 美国长期基金/货基周度申赎 | 数据免费发布;官网实测 403 反爬,改从报告 PDF/镜像取 |
| ETF 单只流向 | 交易所官网日频份额/规模,自算净申赎 | ✅ 免费 |
| 基金公司官网日度 AUM/净值 | 大型基金公司( Vanguard/BlackRock 等)每日披露,可自算申赎 | ✅ 免费 |

### C3. 主权基金与国家资本(逐笔)

| 源 | 内容 | 状态 |
|---|---|---|
| **挪威 GPFG(NBIM)** | 1.7万亿$ 全量持仓 CSV 公开下载 + 季报 | ✅ **免费最全的主权基金持仓源** |
| Temasek/GIC/PIF/ADIA/中投年报 | 年度组合与投向 | ✅ 免费 PDF |
| SWFI(Sovereign Wealth Fund Institute) | 主权基金交易 tracker | 站点活着,rankings 路径已变(实测 404),需更新路径 |
| 美国 CFIUS 年报 | 外资审查动向 | ✅ 免费 |
| 欧盟 FDI Screening 年报 | 对欧 FDI 审查 | ✅ 免费 |

### C4. 债券发行专项

| 源 | 内容 | 状态 |
|---|---|---|
| 美国财政部拍卖日历/结果 | 国债拍卖 | ✅ CSV |
| ECB 购债(CSPP/PEPP) | 央行购债明细 | ✅ |
| SIFMA 统计 | 美国券种发行量月度 | ✅ 免费 |
| MSRB EMMA | 美国市政债(网页免费,API 需签协议) | ⚠️ |

### C5. M&A 监管申报(免费、独家信息)

| 源 | 内容 | 状态 |
|---|---|---|
| 中国 SAMR 经营者集中简易案件公示 | 大额并购在华申报(公告日≈交割临近) | ✅ 免费 |
| FTC/DOJ HSR 统计 | 美国并购申报量(先行指标) | ✅ |
| 欧盟 DG COMP 案件库 | 并购与反垄断审查 | ✅ |

---

## D. 交叉核对新闻源(不作主源,均免费)

TechCrunch(融资轮)、PR Newswire/Business Wire(公司通稿)、Sifted(欧洲一级,免费注册)、Inc42/YourStory(印度)、智通财经/格隆汇(港A,免费注册)、晚点/36氪(中国一级)。

---

## E. 接入优先级建议

| 优先级 | 源 | 理由 |
|---|---|---|
| **P0(本周可做)** | SEC Form D、SGX、Oslo NewsWeb、美联储 TIC、NBIM 持仓、SAMR 公示 | 免费、已验证、分别补齐一级市场/新欧亚节点/宏观/主权四大缺口 |
| **P1(需 key 或小工程)** | Companies House(免费 key)、AMF ODS(换出口)、EQS RSS、日本财务省周度、BIS/ECB SDMX、ICI(PDF)、B2 通稿源(RSS 聚合) | 免费但需注册/出口/解析 |
| **P2(等条件成熟)** | ESAP(2027-07)、BSE/NSE、ASX、IDX、SEDAR+ | 反爬/无 API/政策未到 |

**一二级打通要点**:Form D(美国一级)+ EDGAR(美国二级)同源同格式;Companies House SH01 ↔ LSE 上市公告同主体;用这四个可先建"美国+英国全市场资本事件"闭环,再横向复制到其他地区。

---

## F. 与参考项目的分工建议

> **2026-09-28 更新**:本目录的 P0 源已落地为 `whale-capital-tracker` skill v2.0(`.agents/skills/whale-capital-tracker/`):Form D 已接入 collect.py(funding_round 事件)、TIC/MOF/NBIM/SAMR 进 `--flows` 宏观快照层、SGX/Oslo 逆向结论记档在 sources.md 二类。

whale-capital-tracker 保持"公开市场大额事件"定位不动;本目录扩展的 B/C 板块建议另建 `capital-flows-tracker`:
- **事件层**(复用 whale 契约与门槛):A 板块
- **融资层**(新契约,轮次/投资人/估值字段):B 板板
- **流量层**(时间序列,非事件,CVS/SDMX 拉取入库):C 板块

三层共用 `event_id`/`series_id` 命名规范,便于后续做联合分析(如"一级市场降温 → 12 个月后 IPO 管线收缩"的先行指标验证)。
