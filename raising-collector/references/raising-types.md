# 资本市场募资方式分类（口径参考）

采集时先判断事件类型，再决定进哪个文件。**seed.ipos.jsonl 只收 IPO/挂牌类**。

| 方式 | 说明 | 典型案例 | 归档 |
| --- | --- | --- | --- |
| **IPO 首次公开发行** | 新股 + 上市 + 募资，五态推进 | 阿里巴巴、Circle | `seed.ipos.jsonl` |
| **直接上市 Direct Listing** | 上市不发行新股（老股流通）；部分变体也募资 | Spotify、Slack | seed（status 直接 listed，raise 常为 null，note 注明「直接上市」） |
| **SPAC 上市** | 空壳先 IPO 募资（trust 形式） | 早期 Chamath 系列 | SPAC 本身 → `spacs.jsonl` |
| **De-SPAC 合并** | 目标公司反向合并上市并募资（PIPE） | Lucid、Grab | seed（note 注明「De-SPAC」，raise_usd 记 PIPE 额） |
| **第二上市 / 双重主要上市** | 已异地上市公司再来一处挂牌；可同步发行新股募资 | 阿里 2014 美股→2019 港股二次上市；A+H | seed（note 注明；exchange 填新市场） |
| **GDR / ADR 存托凭证** | 跨市场存托凭证发行（如伦交所 GDR、美股 ADR Level III 募资型） | 多家 A 股公司发瑞士 GDR | `dr.jsonl`（除非用户明确要并入 seed） |
| **增发 / 再融资 SEO** | 已上市公司发新股：现金增发、定向增发（私募）、配股（rights，按比例向老股东） | 腾讯 2021 配股 | `followons.jsonl`（type: `seo`/`placement`/`rights`） |
| **ATM 增持** | 按市价随行就市持续小额发行 | 生物科技股常用 | `followons.jsonl`（type: `atm`） |
| **可转债 CB** | 债 + 转股权；华人市场另有可交换债 EB | 阿里 2020 可转债 | `converts.jsonl` |
| **债券发行** | 公司债/中票/高收益债等纯债融资 | 各大企业 | 超出本 skill 范围（建议 Wind/Bloomberg） |
| **REITs 公募** | 不动产信托首发 | 首批公募 REITs | `reits.jsonl` |
| **私募股权（Pre-IPO 轮）** | 一级市场融资，未公开市场 | VC/PE 轮次 | 不采集（不属于公开市场募资） |

## 口径陷阱（引用交易所统计时必查）

1. 交易所月报的「funds raised」通常 = **IPO + 增发 + 债券** 合计，和 IPO 口径差数倍；
2. 港股「募资额」分上市前发售/发售量调整权（greenshoe 行使前后总额不同）——以最终 424B4/结果公告为准；
3. 美股「IPO 募资」通常不含同时进行的私募配售（concurrent private placement）；
4. SPAC IPO 在多数统计里单列，混入会显著抬高「平均首日涨幅」（SPAC 首日几乎都是 ±0.x%）。
