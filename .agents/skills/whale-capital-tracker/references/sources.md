

## 源状态矩阵（2026-09-08 实测）

| 源 | 状态 | 实测结论 |
| --- | --- | --- |
| SEC EDGAR（美） | ✅ 端到端可用 | 全类型覆盖，多轮实证；User-Agent 必须 |
| HKEX 披露易（港） | ✅ 端到端可用 | **curl 必须加 `--compressed`（gzip！）**。字段映射：STOCK_CODE→ticker、TITLE→news_title、FILE_LINK→source_url、DATE_TIME→announce_date（dd/MM/yyyy HH:mm 港时）、LONG_TEXT→类别 |
| 上交所（沪） | ⚠️ 端点活/参数待调 | queryCompanyBulletinNew.do 200+正确结构但 result 空，securityType 组合需修 |
| 深交所（深） | ❌ 本轮未通 | annList POST 返回 50x，疑似接口变更或需浏览器态 |
| JPX TDnet（日） | ⚠️ 可达/数据待定位 | 根 200，frameset+iframe(/onsf/TDJFSearch/)，每日 zip 待定位 |
| KRX（韩） | ❌ 需浏览器态 | 404+SPA |
| LSE RNS（英） | ⚠️ SPA/接口未定位 | JS 渲染 |
| Euronext（欧） | ⚠️ SPA/接口未定位 | JS 渲染 |
| NSE corporates（印） | ❌ 反爬 403 | 需浏览器 cookie 会话 |
| Tadawul（沙特） | ❌ 反爬 403 | 需浏览器 cookie 会话 |

结论：**EDGAR + 披露易两大主力已可用**（恰为全球募资活动最大的两块）；A 股半通；其余需带会话的浏览器态自动化，列入后续迭代。

## 全球扩展源清单（2026-09-08 第二轮探测）

**监管侧 OAM（欧盟 ESMA 体系，每成员国一个，全部官方免费）**

| 源 | 状态 | 说明 |
| --- | --- | --- |
| 法国 AMF | ✅ 可达 | 域名已迁 **info-financiere.gouv.fr**（政府域），API 待映射 |
| 德国 Unternehmensregister | ✅ 可达 | 307→/de，官方商业登记+公告 |
| 英国 FCA NSM | ❌ 本环境连接失败 | nsm.fca.org.uk（监管档案库，含招股书），疑似地域/TLS 限制 |
| 泛欧聚合 | 📋 待接 | ESMA 的 EEAP 聚合入口可一次查全欧盟 OAM |
| 加拿大 SEDAR+ | ✅ 可达 | 302→应用页，官方备案系统（2023 替代 SEDAR） |

**交易所公告平台（SPA/需浏览器态）**：LSE RNS（api.londonstockexchange.com 存在但需逆向参数，400≠404）· ASX（澳）· SGX（新加坡，200 壳）· TWSE MOPS（台湾，302）· BSE（印度，403）· JSE（南非，403）· KRX（韩）

**尚未纳入版图**：巴西 CVM、墨西哥 BMV、土耳其 BIST、以色列 TASE、俄 MOEX
