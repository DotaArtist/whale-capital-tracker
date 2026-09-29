# Whale Capital Tracker 事件类型词表 v0.1

三层语义分工，任何数据源的映射都必须遵守：

| 层 | 字段 | 回答的问题 |
|---|---|---|
| 类型 | `event_type` | 发生了什么（本文件的 21 类，受控） |
| 状态 | `status` / `stage` | 走到哪一步（通用状态机 / IPO 生命周期） |
| 方向 | `direction` | 资金向哪流（由类型推导，见 §3） |

新增类型须先穷尽"能否用 `event_type + 字段/标签表达"——能表达就不加类型，21 类封顶，保证聚合口径稳定。

## 1. 事件类型总表

### 进入（inflow）——资本下注

| 代码 | 中文 | 判定边界 |
|---|---|---|
| `ipo` | 首次公开发行 | 未上市主体首次向公开市场募股。递表/定价/上市是它的 stage |
| `direct_listing` | 直接上市 | 不发行新股的上市（Spotify 型），由"无募资额 + 直接上市"标记判 |
| `spac` | SPAC 募资与合并 | 发行主体是空白支票公司（US S-1 资产池性质；HK 特殊目的收购公司）。de-SPAC 合并同属此类，用 stage 区分 |
| `reverse_merger` | 借壳上市 | 非上市资产注入已上市壳（CN 重组上市、US shell merger） |
| `dual_listing` | 第二/双重主要上市 | 已在 A 市场上市的公司的 B 市场上市，含 GDR/ADR 跨市场发行 |
| `seo` | 公开再融资 | 面向不特定对象的增发、配股、供股（US 424B5；HK 配售/供股；CN 公开增发/配股） |
| `private_placement` | 定向增发 | 面向特定对象（CN 向特定对象发行；US PIPE；JP 第三者割当） |
| `convertible_bond` | 可转债 | 转股型债券发行（CN 可转债、US/F-3 可换股票据） |
| `bond_issuance` | 债券发行 | 非转股的公司信用债（投资级/高收益/绿色债）。只收发行人主体可归行业的，主权债不入库 |
| `funding_round` | 一级市场融资 | 未上市主体的私募轮（天使到 Pre-IPO）。轮次放 `note` 或扩展字段，不设新类型 |
| `fund_close` | 基金募资关闭 | PE/VC 基金的 final/close 公告，主体是基金而非运营公司 |
| `strategic_stake` | 战略入股 | 不取得控制权的少数股权收购（触发 13D/13G、权益披露线的单列于此；含 CVC 战投） |
| `jv` | 合资公司 | 两方以上共同出资设立新主体 |

### 整合（consolidation）——控制权与资产重组

| 代码 | 中文 | 判定边界 |
|---|---|---|
| `ma` | 收购并购 | 取得控制权的交易：协议收购、要约收购、换股合并、吸收合并。横向/纵向/跨界放标签，不设新类型 |
| `spin_off` | 分拆 | 现有股东按比例获得新主体（spin-off），或分拆子公司独立上市（分拆上市预案也归此类，用 stage 表达） |
| `divestiture` | 资产剥离出售 | 出售业务/子公司/资产换取对价（与 spin_off 的区别：钱进公司 vs 股进股东）。含售后回租 |
| `bankruptcy_restructuring` | 破产重整/清算 | 进入司法重整程序（Chapter 11、CN 重整计划裁定）及 363 Sale 式资产处置 |

### 退出（outflow）——资本离场与回流

| 代码 | 中文 | 判定边界 |
|---|---|---|
| `stake_reduction` | 减持/大宗出售 | 股东降低持股（不导致控制权变更）：VC/PE 退出、大股东减持、大宗/协议转让 |
| `buyback` | 股票回购 | 公司回购自身股份并注销或库存。回购导致退市的归 `going_private` |
| `going_private` | 私有化/退市 | 要约私有化、财团收购下市、被动退市（交易所摘牌）。US 走 13E3/Schedule TO；HK 走要约/协议安排 |
| `debt_restructuring` | 债务重组 | 交换要约、同意征集、展期、减记（房企境外债重组为典型） |

## 2. 状态词表

### 通用状态机（`status`，交易生命周期类型适用）

主链：`announced → filed → approved → priced → completed`
旁路（任何时候可发生）：`scheduled`（已排定未来日期）、`amended`（条款修订）、`withdrawn`（申报撤回）、`terminated`（交易终止/失败）

### IPO 生命周期（`stage`，完全继承 global-ipo-tracker v1.2）

`filed / filed_update / listening / prospectus / priced / allotment / listed / scheduled`

### 两套状态的适用规则

| 类型族 | 字段 | 类型 |
|---|---|---|
| 上市生命周期族 | `stage` | `ipo` `direct_listing` `spac` `reverse_merger` `dual_listing` |
| 交易生命周期族 | `status` | `ma` `seo` `private_placement` `convertible_bond` `going_private` `spin_off` `divestiture` `bankruptcy_restructuring` `debt_restructuring` `bond_issuance` `jv` `funding_round` `fund_close` `strategic_stake` |
| 单点事件族 | `status` 取 `announced`/`completed` 即可 | `buyback`（公告/执行完毕）`stake_reduction`（披露即事件） |

## 3. direction 推导表（入库时由类型自动填）

| direction | 类型 |
|---|---|
| `inflow` | ipo, direct_listing, spac, reverse_merger, dual_listing, seo, private_placement, convertible_bond, bond_issuance, funding_round, fund_close, strategic_stake, jv |
| `consolidation` | ma, spin_off, divestiture, bankruptcy_restructuring |
| `outflow` | stake_reduction, buyback, going_private, debt_restructuring |

## 4. 易混淆边界判定

- **`ipo` vs `spac`**：发行主体本身是空白支票公司 → `spac`；de-SPAC 合并（S-4）也归 `spac`，stage 用交易状态机。
- **`strategic_stake` vs `ma`**：5% 披露线只是披露义务线，不是分类线；看**控制权是否转移**。取得控制权（含要约）→ `ma`。
- **`spin_off` vs `divestiture`**：股东拿股票 → `spin_off`；公司拿对价 → `divestiture`。
- **`seo` vs `private_placement`**：面向不特定对象（公开认购/配售+供股混合按主要成分）→ `seo`；定向 → `private_placement`。CN 的"向特定对象发行"一律是 `private_placement`。
- **`buyback` vs `going_private`**：回购计划以退市为目的或导致流通股低于摘牌线 → `going_private`。
- **同一交易多阶段**：一条交易在生命周期的每个被观测节点各生成一条事件记录（stage/status 不同），**不做跨阶段合并**——合并是下游 `v_active_deals` 视图的职责（见 schema.md §5）。

## 5. 巨鲸门槛（whale threshold）

本 skill 的定位是**大型**资本活动，防止噪声淹没。门槛只在**查询/聚合层**生效，入库不做过滤（宁可多存，报告时收紧）。建议默认值（等值美元，可通过 `--min-usd` 覆盖）：

| 类型 | 默认门槛 |
|---|---|
| `ma` `spin_off` `divestiture` `going_private` | ≥ 500M USD |
| `ipo` `seo` `private_placement` `bond_issuance` `convertible_bond` `funding_round` `fund_close` `strategic_stake` | ≥ 200M USD |
| `buyback` `stake_reduction` `debt_restructuring` `bankruptcy_restructuring` | ≥ 100M USD |
| `jv` `dual_listing` `direct_listing` `spac` `reverse_merger` | 不设金额门槛（事件本身稀缺，见一条记一条） |
