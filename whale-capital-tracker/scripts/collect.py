#!/usr/bin/env python3
"""whale-capital-tracker 统一采集器 v2.0（12 源：EDGAR/HKEX/巨潮/TDnet/EDINET/DART/MOPS/KAP/MAYA/CVM/SIX/FormD）

v2.0（2026-09-28）基于 dotaartist/whale-capital-tracker v1 + 本地 event_types.md 词表 v0.1 扩展：
- 新增源 collect_formd：SEC EDGAR daily-index → Form D/D-A 私募申报 → funding_round（一级市场大额融资）
- 新增 --flows：宏观资本流动快照（TIC/MOF/NBIM/SAMR 可达性探测，数值由 agent 按 sources.md F 节手工填）
- 新增事件类型（词表）：funding_round/fund_close/strategic_stake/spin_off/divestiture/going_private/stake_reduction/jv

用法（默认以日为单位：不带参数 = 采集今天一天）:
  python3 collect.py                                   # 采集今天，输出 daily-20260909.json
  python3 collect.py --date 2026-09-04                 # 采集指定某一天
  python3 collect.py --from 2026-09-01 --to 2026-09-08  # 跨日补采：自动按日切分，
                                                        #   每天一个 daily-YYYYMMDD.json（含空日文件）
  python3 collect.py --from 2026-09-01 --to 2026-09-08 --out merged.json  # 显式 --out 才合并单文件
  python3 collect.py --sources cninfo,mopsov --date 2026-09-24  # 只跑指定源（逗号分隔）
  python3 collect.py --flows --date 2026-09-28         # 附带宏观 flows 快照（meta.flows）

输出文件默认命名：daily-{查询日期 YYYYMMDD}.json（如 daily-20260909.json）；
跨日窗口按日切分为多个文件（每天一个，日期各自入文件名）。

产出符合 schema v2.0 的 flows.json（只入过门槛事件；未过门槛的在摘要中报告）。

已知坑（详见 references/sources.md）：
- EDGAR FTS 的 _id 常指向费用表壳页（<20KB），真金额在同名公司后续的大主文件——
  本脚本按公司遍历多个 accession，跳过小文件。
- HKEX 对连发请求软限流（返回空/非 JSON），建议单轮间隔 ≥60s，失败等 1 小时再试。
- Form D：EDGAR 全文检索（FTS）不索引 Form D（实测 2026-09-28），必须走 daily-index master.idx；
  部分出口对 daily-index 返回 S3 AccessDenied——collect_formd 打印提示并跳过，其余源不受影响。

带 key 的源（均免费申请，详见 references/sources.md）：
  EDINET_KEY（api.edinet-fsa.go.jp，注册+MFA）、OPENDART_KEY（opendart.fss.or.kr）

2026-09 新增源的实测坑（详见 sources.md）：
- 巨潮必须走 http（https 从海外 IP 403），连发限速 ≥1.5s。
- TDnet 列表页仅当日（31 天滚动窗口），历史补采不支持——务必每日跑。
- MOPS 日期参数是 b_date/e_date（不是 day），年份为民国纪年（西元-1911）；主域拦海外，走 mopsov 镜像。
- TASE/MAYA 需旧版 IE UA + referer 过 WAF；报告端点待逆向，本轮只报实体 API 健康度。
- SGX api2 为 GraphQL 持久化查询（queryId 在懒加载 chunk）；Oslo NewsWeb 已迁
  obns-api.dev.euronext.cloud（本出口 NXDOMAIN）——两者待逆向，详见 sources.md 二类。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = "whale-capital-tracker/2.0 (demo@example.com)"
THRESHOLDS = {"ipo": 5, "follow_on": 5, "convertible": 5, "bond": 10, "spac": 3,
              "despac": 20, "gdr": 5, "reits": 3, "buyback": 20, "ma": 50,
              "dividend_special": 20,
              # v2.0 词表新增类型（门槛与 event_types.md §5 对齐，亿美元）
              "funding_round": 2, "fund_close": 2, "strategic_stake": 2,
              "spin_off": 5, "divestiture": 5, "going_private": 5,
              "stake_reduction": 1, "jv": 0}
HKD_PER_USD = 7.8
# 1 USD 兑当地币（采集时折算 → 亿美元；与 references/schema.md 汇率表同步维护）
FX_PER_USD = {"CNY": 7.2, "JPY": 150, "KRW": 1350, "TWD": 32, "TRY": 34,
              "BRL": 5.4, "ILS": 3.7, "CHF": 0.88,
              "SGD": 1.34, "NOK": 10.8, "SEK": 10.5}

SOURCE_STATUS = {
    "SEC EDGAR(美)": "active", "HKEX 披露易(港)": "active(限流敏感)",
    "巨潮(沪深京)": "active(http直连/限速1.5s)", "TDnet(日)": "active(仅当日,31天滚动)",
    "EDINET(日)": "active(需EDINET_KEY,管线候选)", "OpenDART(韩)": "active(需OPENDART_KEY,管线候选)",
    "MOPS mopsov(台)": "active(民国年/b_date)", "KAP(土)": "active(公司级已验,全市场参数待调)",
    "TASE/MAYA(以)": "实体API通(报告端点待逆向)", "CVM(巴西)": "active(批量CSV,登记滞后:2026至今仅3条)",
    "SER/SIX(瑞)": "active(RSS)",
    "SEC FormD(美一级)": "v2新增(daily-index;FTS不索引D;部分出口AccessDenied)",
    "SSE直连(沪)": "备用校验源(需Referer)", "深交所(深)": "50x",
    "AMF(法)": "本出口TCP被拦(ODS API有据)", "LSE/Euronext/ASX/IDX/BSE/Tadawul": "反爬/SPA",
    "SGX(新加坡)": "GraphQL持久化query待逆向(2026-09-28)",
    "Oslo NewsWeb(挪)": "已迁obns-api.dev.euronext.cloud(本出口NXDOMAIN,待逆向)",
    "SEDAR+(加)": "ToS禁自动采集", "ESAP(欧盟聚合)": "2027-07 观察",
    "宏观flows(TIC/MOF/NBIM/SAMR)": "--flows探测+agent手工填数(sources.md F节)",
}


def curl(url, headers=None, timeout=20, data=None, json_body=None, redir=False):
    cmd = ["curl", "-s", "--max-time", str(timeout), "--compressed"]
    if redir:
        cmd.append("-L")
    if not any(h.lower().startswith("user-agent:") for h in headers or []):
        cmd += ["-H", f"User-Agent: {UA}"]
    for h in headers or []:
        cmd += ["-H", h]
    if json_body is not None:
        cmd += ["-H", "Content-Type: application/json",
                "-d", json.dumps(json_body, ensure_ascii=False), "-X", "POST"]
    elif data is not None:
        cmd += ["-H", "Content-Type: application/x-www-form-urlencoded",
                "-d", data, "-X", "POST"]
    cmd.append(url)
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def local_yi(amount_local, cur):
    """当地货币原始金额（如 3.5e9 JPY）→ 亿美元；无汇率返回 None"""
    p = FX_PER_USD.get(cur)
    if not p:
        return None
    try:
        return round(float(str(amount_local).replace(",", "")) / p / 1e8, 2)
    except (TypeError, ValueError):
        return None


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).replace("&nbsp;", " ").strip()


def iter_days(from_d, to_d, cap=10):
    d, end = datetime.strptime(from_d, "%Y-%m-%d"), datetime.strptime(to_d, "%Y-%m-%d")
    out = []
    while d <= end and len(out) < cap:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def to_yi_usd(num, unit):
    """原始金额（数字+单位）→ 亿美元"""
    n = float(str(num).replace(",", ""))
    if unit == "billion":
        return round(n * 10, 2)
    if unit == "million":
        return round(n / 100, 2)
    if n >= 1e6:  # 无单位的原始美元数
        return round(n / 1e8, 2)
    return None


# ---------------- EDGAR ----------------

EDGAR_QUERIES = {
    "ipo": [("424B4", '"initial public offering"'), ("S-1", '"aggregate offering price"')],
    "follow_on": [("424B5", '"underwritten public offering"')],
    "convertible": [("424B5,424B2", '"convertible notes"')],
    "bond": [("424B2,424B5", '"aggregate principal amount"')],
    "buyback": [("8-K", '"share repurchase program"')],
    "ma": [("8-K", '"merger agreement"')],
    "spac": [("S-1", '"blank check company"')],
}
AMOUNT_CTX = {
    "ipo": [r'(?:gross proceeds|aggregate offering price)[^.]{0,140}?\$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?',
            r'Registered[^$]{0,400}?\$\s?([\d,]{7,})'],
    "follow_on": [r'(?:gross proceeds|aggregate offering price of)[^.]{0,140}?\$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?'],
    "convertible": [r'aggregate principal amount of \$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?'],
    "bond": [r'aggregate principal amount of \$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?'],
    "buyback": [r'(?:repurchase|buy-?back)[^.]{0,160}?up to \$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?',
                r'(?:repurchase|buy-?back) program[^.]{0,140}?\$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)'],
    "ma": [r'(?:aggregate|total|approximately)[^.]{0,110}?consideration[^.]{0,110}?\$\s?([\d,.]+)\s?(million|billion)?',
           r'merger agreement[^.]{0,250}?\$\s?([\d,.]+)\s?(billion|million)'],
    "spac": [r'(?:trust|units)[^.]{0,130}?\$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?'],
}
STATUS_BY_FORM = {"424B4": "priced", "424B5": "priced", "424B2": "priced",
                  "8-K": "announced", "S-1": "announced"}


def edgar_fts(query, forms, from_d, to_d, n=30):
    """FTS 命中（刻意不去重：同名公司常有壳页+主文件多个 accession，按序试到拿到大文件）"""
    url = (f"https://efts.sec.gov/LATEST/search-index?q={urllib.parse.quote(query)}"
           f"&forms={forms}&startdt={from_d}&enddt={to_d}")
    try:
        d = json.loads(curl(url))
        out = []
        for h in d.get("hits", {}).get("hits", [])[:n]:
            s = h.get("_source", {})
            raw = s.get("display_names", ["?"])[0]
            cik = raw.split("(CIK")[-1].split(")")[0].strip()
            out.append({"name": raw.split("(")[0].strip(), "cik": cik,
                        "date": s.get("file_date", ""), "form": s.get("form", ""),
                        "_id": h.get("_id", "")})
        return out
    except Exception:
        return []


def edgar_doc_text(cik, _id):
    try:
        acc, fn = _id.split(":", 1)
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{fn}"
        t = curl(url)
        if not t:
            return "", ""
        return re.sub(r"&#\d+;|&[a-z]+;", " ", re.sub(r"<[^>]+>", " ", t)), url
    except Exception:
        return "", ""


def extract_amount(text, patterns):
    """返回 (金额亿$, 是否为上限表述)"""
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            unit = m.group(2) if (m.lastindex and m.lastindex >= 2 and m.group(2)) else None
            amt = to_yi_usd(m.group(1), unit)
            if amt and amt > 0.05:
                ctx = text[max(0, m.start() - 80):m.end() + 40]
                cap = bool(re.search(r"less than|not exceed|up to \$?\s?[\d,.]+\s?(?:of )?\$?" , ctx, re.I)) and "up to" not in ctx
                cap = bool(re.search(r"less than|not exceed", ctx, re.I))
                return amt, cap
    return None, False


def collect_edgar(from_d, to_d, max_per_type, log):
    events, rejected = [], []
    for et, specs in EDGAR_QUERIES.items():
        got, done_names = 0, set()
        for forms, query in specs:
            for rec in edgar_fts(query, forms, from_d, to_d):
                if got >= max_per_type or rec["name"] in done_names:
                    continue
                text, url = edgar_doc_text(rec["cik"], rec["_id"])
                time.sleep(0.3)
                if len(text) < 20000:  # 费用表壳页，真金额在后面的主文件
                    continue
                # S-1 只认费用表 Registered 列——"aggregate offering price of at least $X" 是承销样板条款，会命中假金额
                patterns = ([AMOUNT_CTX["ipo"][1]] if rec["form"] == "S-1"
                            else AMOUNT_CTX.get(et, []))
                amt, is_cap = extract_amount(text, patterns)
                if not amt:
                    continue
                done_names.add(rec["name"])
                thr = THRESHOLDS[et]
                if amt < thr:
                    rejected.append((et, rec["name"], amt, thr))
                    continue
                events.append({
                    "event_id": f"{et}:EDGAR:{rec['name'].replace(' ', '-')[:24]}:{rec['date']}",
                    "event_type": et, "name": rec["name"], "name_en": rec["name"],
                    "ticker": None, "market": "美股(交易所待定)", "region": "north_america",
                    "industry": None, "announce_date": rec["date"], "settle_date": None,
                    "status": STATUS_BY_FORM.get(rec["form"], "announced"), "amount_usd": amt,
                    "news_title": f"{rec['form']}：金额提取自注册文件原文",
                    "source": f"SEC EDGAR {rec['form']}", "source_url": url,
                    "note": ("目标募资" if rec["form"] == "S-1" else "金额句级核验")
                            + ("；金额为上限表述(less than)" if is_cap else ""),
                    "market_mic": None, "domicile_country": None, "is_china_concept": False,
                })
                got += 1
                log(f"  [EDGAR] {et:12s} {rec['name'][:30]:32s} {amt:>8.1f} 亿$")
    return events, rejected


# ---------------- HKEX ----------------

HK_KEYWORDS = ["配售", "供股", "全球发售", "公开发售", "先旧后新", "回购", "收购", "合并", "可换股", "可转换股"]
HK_TYPE_MAP = [("回购", "buyback"), ("先旧后新", "follow_on"), ("配售", "follow_on"), ("供股", "follow_on"),
               ("全球发售", "ipo"), ("公开发售", "ipo"), ("可换股", "convertible"), ("可转换股", "convertible"),
               ("收购", "ma"), ("合并", "ma")]


def collect_hkex(from_d, to_d, log):
    url = ("https://www1.hkexnews.hk/search/titleSearchServlet.do?sortDir=0&sortByOptions=DateTime"
           f"&category=0&market=SEHK&stockId=-1&documentType=-1&fromDate={from_d.replace('-', '')}"
           f"&toDate={to_d.replace('-', '')}&title=&searchType=1&t1code=-2&t2Gcode=-2&t2code=-2&rowRange=500&lang=zh")
    raw = curl(url)
    try:
        d = json.loads(raw)
        recs = json.loads(d.get("resultAsString", "[]"))
    except Exception:
        log(f"  [HKEX] 限流或非 JSON（{len(raw)}B）——本轮跳过，建议 ≥60s 后重试")
        return [], []
    events, rejected = [], []
    log(f"  [HKEX] 公告总数 {len(recs)}")
    for r in recs:
        title = r.get("TITLE", "")
        if not any(k in title for k in HK_KEYWORDS):
            continue
        m = re.search(r"约?\s?([\d,]+(?:\.\d+)?)\s*亿(港元|美元)", title)
        if not m:
            continue
        val = float(m.group(1).replace(",", ""))
        amt = round(val / HKD_PER_USD, 2) if m.group(2) == "港元" else val
        et = next((t for k, t in HK_TYPE_MAP if k in title), None)
        if not et:
            continue
        dm = re.match(r"(\d{2})/(\d{2})/(\d{4})", r.get("DATE_TIME", ""))
        date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else from_d
        code = r.get("STOCK_CODE", "")
        thr = THRESHOLDS[et]
        if amt < thr:
            rejected.append((et, r.get("STOCK_NAME", code), amt, thr))
            continue
        events.append({
            "event_id": f"{et}:XHKG:{code or 'NA'}:{date}",
            "event_type": et, "name": r.get("STOCK_NAME", code), "name_en": r.get("STOCK_NAME", code),
            "ticker": code or None, "market": "港交所", "region": "hong_kong",
            "industry": None, "announce_date": date, "settle_date": None,
            "status": "announced", "amount_usd": amt, "news_title": title,
            "source": "HKEX 披露易",
            "source_url": "https://www1.hkexnews.hk" + r.get("FILE_LINK", ""),
            "note": f"金额取自公告标题（{m.group(0)}）", "market_mic": "XHKG",
            "domicile_country": None, "is_china_concept": None,
        })
        log(f"  [HKEX] {et:12s} {r.get('STOCK_NAME', '')[:14]:16s} {amt:>7.1f} 亿$ | {title[:34]}")
    return events, rejected


# ---------------- 巨潮 cninfo（A 股·沪深京统一披露） ----------------

CN_KEYWORDS = {"ipo": "首次公开发行", "follow_on": "向特定对象发行", "convertible": "可转换公司债券",
               "buyback": "回购股份", "ma": "重大资产重组"}


def collect_cninfo(from_d, to_d, log):
    """巨潮历史公告检索。必须走 http（https 海外 403）；标题带金额才入账（与 HKEX 同策略），
    金额在 PDF 正文里的公告会被门槛天然滤掉——那些留给人工/后续解析。"""
    events, rejected = [], []
    for et, kw in CN_KEYWORDS.items():
        body = urllib.parse.urlencode({
            "pageNum": 1, "pageSize": 30, "column": "szse", "tabName": "fulltext",
            "plate": "", "stock": "", "searchkey": kw, "secid": "", "category": "",
            "trade": "", "seDate": f"{from_d}~{to_d}", "sortName": "", "sortType": "",
            "isHLtitle": "true"})
        try:
            d = json.loads(curl("http://www.cninfo.com.cn/new/hisAnnouncement/query", data=body))
        except Exception:
            d = {}
        time.sleep(1.5)  # 巨潮对海外连发敏感，≥1.5s
        anns = d.get("announcements") or []
        if anns:
            log(f"  [巨潮] 「{kw}」命中 {len(anns)} 条（金额多在 PDF 正文，标题带金额才入账——其余为管线候选）")
        for a in d.get("announcements") or []:
            title = re.sub(r"</?em>", "", a.get("announcementTitle", ""))
            m = re.search(r"([\d,]+(?:\.\d+)?)\s*亿元", title)
            if not m:
                continue
            code = a.get("secCode", "")
            amt = local_yi(float(m.group(1).replace(",", "")) * 1e8, "CNY")
            date_d = datetime.fromtimestamp((a.get("announcementTime") or 0) / 1000).strftime("%Y-%m-%d")
            market, mic = (("上交所", "XSHG") if code.startswith("6")
                           else ("深交所", "XSHE") if code.startswith(("0", "3"))
                           else ("北交所", "XBJE"))
            name = a.get("secName", code)
            thr = THRESHOLDS[et]
            if not amt or amt < thr:
                rejected.append((et, name, amt, thr))
                continue
            events.append({
                "event_id": f"{et}:{mic}:{code or 'NA'}:{date_d}",
                "event_type": et, "name": name, "name_en": name,
                "ticker": code or None, "market": market, "region": "mainland",
                "industry": None, "announce_date": date_d, "settle_date": None,
                "status": "announced", "amount_usd": amt, "news_title": title,
                "source": "巨潮资讯", "source_url": "http://static.cninfo.com.cn/" + a.get("adjunctUrl", ""),
                "note": f"金额取自公告标题（{m.group(0)}）", "market_mic": mic,
                "domicile_country": "CN", "is_china_concept": True,
            })
            log(f"  [巨潮] {et:12s} {name[:14]:16s} {amt:>7.1f} 亿$ | {title[:34]}")
    return events, rejected


# ---------------- TDnet（日·交易所及时披露） ----------------

JP_TYPE_MAP = [("第三者割当増資", "follow_on"), ("転換社債", "convertible"), ("新株予約権付社債", "convertible"),
               ("自己株式", "buyback"), ("合併", "ma"), ("募集", "follow_on"), ("社債", "bond")]


def collect_tdnet(from_d, to_d, log):
    """TDnet 适時開示列表（当日 HTML 分页）。31 天滚动窗口且历史页无静态 URL——只支持采当天。"""
    today = time.strftime("%Y-%m-%d")
    if from_d != today or to_d != today:
        log("  [TDnet] 列表页仅当日（31 天滚动，无历史静态 URL）——非当日窗口跳过")
        return [], []
    events, rejected = [], []
    for page in range(4):  # I_main_00..03，每页约百条
        html = curl(f"https://www.release.tdnet.info/inbs/I_main_0{page}.html")
        time.sleep(0.4)
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            text = " ".join(cells)
            et = next((t for k, t in JP_TYPE_MAP if k in text), None)
            if not et:
                continue
            m = re.search(r"([\d,]+(?:\.\d+)?)\s*億円", text)
            if not m:
                continue
            code = next((c for c in cells if re.fullmatch(r"\d{4,5}", c)), "")
            name = next((c for c in cells if re.search(r"[ぁ-んァ-ヶ一-龥]", c)), code)
            amt = local_yi(float(m.group(1).replace(",", "")) * 1e8, "JPY")
            href = re.search(r'href="([^"]+)"', tr)
            thr = THRESHOLDS[et]
            if not amt or amt < thr:
                rejected.append((et, name, amt, thr))
                continue
            events.append({
                "event_id": f"{et}:XJPX:{code or name[:12]}:{today}",
                "event_type": et, "name": name, "name_en": name,
                "ticker": code or None, "market": "东证", "region": "japan",
                "industry": None, "announce_date": today, "settle_date": None,
                "status": "announced", "amount_usd": amt, "news_title": text[:80],
                "source": "JPX TDnet",
                "source_url": ("https://www.release.tdnet.info" + href.group(1)
                               if href else "https://www.release.tdnet.info/inbs/I_main_00.html"),
                "note": f"金额取自标题（{m.group(0)}）", "market_mic": "XJPX",
                "domicile_country": "JP", "is_china_concept": False,
            })
            log(f"  [TDnet] {et:12s} {name[:14]:16s} {amt:>7.1f} 亿$ | {text[:34]}")
        if 'class="no-hit"' in html or not html:
            break
    return events, rejected


# ---------------- EDINET（日·监管申报，管线候选） ----------------

def collect_edinet(from_d, to_d, log):
    """有価証券届出書（IPO/募集/売出し之源）。v2 API 元数据不含金额——只报管线候选（SKILL 4.5）。"""
    key = os.environ.get("EDINET_KEY")
    if not key:
        log("  [EDINET] 未设 EDINET_KEY（api.edinet-fsa.go.jp 免费注册+MFA），本轮跳过")
        return [], []
    cand = []
    for dd in iter_days(from_d, to_d):
        try:
            d = json.loads(curl(f"https://api.edinet-fsa.go.jp/api/v2/documents.json?date={dd}&type=1",
                                headers=[f"Ocp-Apim-Subscription-Key: {key}"]))
        except Exception:
            continue
        if d.get("StatusCode") not in (None, 200):
            log(f"  [EDINET] {d.get('message', '')[:60]}")
            return [], []
        for r in d.get("results", []):
            desc = r.get("description", "")
            if "有価証券届出書" not in desc and "発行登録" not in desc:
                continue
            et = ("ipo" if "新規公開" in desc else
                  "convertible" if "転換社債" in desc else "follow_on")
            cand.append((et, r.get("filerName", ""), desc, dd))
        time.sleep(0.5)
    log(f"  [EDINET] 管线候选 {len(cand)} 件（届出/发行登録，金额在原文待核）")
    for et, nm, desc, dd in cand[:5]:
        log(f"    {dd} {et:10s} {nm[:26]} | {desc[:30]}")
    return [], []


# ---------------- OpenDART（韩·监管披露，管线候选） ----------------

DART_TYPE_MAP = [("기업공개", "ipo"), ("증권신고서", "ipo"), ("유상증자", "follow_on"),
                 ("전환사채", "convertible"), ("신주인수권부사채", "convertible"),
                 ("사채", "bond"), ("자사주", "buyback"), ("합병", "ma")]


def collect_dart(from_d, to_d, log):
    """金监院 OpenDART（免费 key，2 万次/日）。list.json 元数据不含金额——只报管线候选。"""
    key = os.environ.get("OPENDART_KEY")
    if not key:
        log("  [DART] 未设 OPENDART_KEY（opendart.fss.or.kr 免费注册），本轮跳过")
        return [], []
    try:
        d = json.loads(curl(
            f"https://opendart.fss.or.kr/api/list.json?crtfc_key={key}"
            f"&bgn_de={from_d.replace('-', '')}&end_de={to_d.replace('-', '')}&page_count=100"))
    except Exception as e:
        log(f"  [DART] 请求失败: {e}")
        return [], []
    if str(d.get("status")) != "000":
        log(f"  [DART] {d.get('message', '')[:60]}")
        return [], []
    cand = []
    for r in d.get("list", []):
        nm = r.get("report_nm", "")
        et = next((t for k, t in DART_TYPE_MAP if k in nm), None)
        if et:
            rc = r.get("rcept", "")
            cand.append((et, r.get("corp_name", ""), nm, f"{rc[:4]}-{rc[4:6]}-{rc[6:8]}"))
    log(f"  [DART] 管线候选 {len(cand)} 件（增资/公司债/回购/合并申报，金额在原文待核）")
    for et, nm, rnm, dd in cand[:5]:
        log(f"    {dd} {et:10s} {nm[:26]} | {rnm[:30]}")
    return [], []


# ---------------- 台湾 MOPS（mopsov 海外镜像） ----------------

TW_TYPE_MAP = [("現金增資", "follow_on"), ("轉換公司債", "convertible"), ("GDR", "gdr"),
               ("庫藏股", "buyback"), ("公司債", "bond"), ("合併", "ma")]


def collect_mopsov(from_d, to_d, log):
    """重大訊息当日全市场（mopsov.twse.com.tw，主域拦海外）。日期=民国年，参数是 b_date/e_date。"""
    events, rejected = [], []
    for dd in iter_days(from_d, to_d):
        y, m, d = (int(x) for x in dd.split("-"))
        body = (f"TYPEK=sii&year={y - 1911}&month={m:02d}"
                f"&b_date={d:02d}&e_date={d:02d}&co_id=&firstin=true&step=1")
        html = curl("https://mopsov.twse.com.tw/mops/web/ajax_t05st01", data=body)
        time.sleep(1.0)
        rows = kw_hits = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if len(cells) < 5:
                continue
            rows += 1
            subj = cells[4]
            et = next((t for k, t in TW_TYPE_MAP if k in subj), None)
            if not et:
                continue
            kw_hits += 1  # 主旨多不带金额（金额在附件）——命中即管线候选，供 4.5 管线刷新追 PDF
            m = re.search(r"([\d,]+(?:\.\d+)?)\s*億元", subj)
            if not m:
                continue
            dm = re.match(r"(\d+)/(\d+)/(\d+)", cells[2])
            date_d = (f"{int(dm.group(1)) + 1911}-{dm.group(2)}-{dm.group(3)}"
                      if dm else dd)
            code, name = cells[0], cells[1]
            amt = local_yi(float(m.group(1).replace(",", "")) * 1e8, "TWD")
            thr = THRESHOLDS[et]
            if not amt or amt < thr:
                rejected.append((et, name, amt, thr))
                continue
            events.append({
                "event_id": f"{et}:XTAI:{code or 'NA'}:{date_d}",
                "event_type": et, "name": name, "name_en": name,
                "ticker": code or None, "market": "台交所", "region": "apac",
                "industry": None, "announce_date": date_d, "settle_date": None,
                "status": "announced", "amount_usd": amt, "news_title": subj[:80],
                "source": "TWSE MOPS 重大訊息",
                "source_url": "https://mopsov.twse.com.tw/mops/web/t05st01",
                "note": f"金额取自主旨（{m.group(0)}）", "market_mic": "XTAI",
                "domicile_country": "TW", "is_china_concept": None,
            })
            log(f"  [MOPS] {et:12s} {name[:14]:16s} {amt:>7.1f} 亿$ | {subj[:34]}")
        if rows:
            log(f"  [MOPS] {dd} 重大訊息 {rows} 行（类型关键词命中 {kw_hits} 条——金额多在附件，作管线候选）")
    return events, rejected


# ---------------- KAP（土·官方披露平台） ----------------

TR_TYPE_MAP = [("sermaye art", "follow_on"), ("bedelsiz", None), ("geri al", "buyback"),
               ("birleşme", "ma"), ("borçlanma aracı", "bond"), ("pay alma teklifi", "ma")]


def collect_kap(from_d, to_d, log):
    """KAP 无登录 JSON API。公司级查询已端到端验证；全市场 byCriteria 的成员过滤语义未公开，
    空成员列表实测返回空——保留探测，参数定位后扩展。"""
    events, rejected = [], []
    for cls in ("BDS", "FR", "ODA"):
        body = {"fromDate": from_d, "toDate": to_d, "disclosureClass": cls, "subjectList": [],
                "mkkMemberOidList": [], "inactiveMkkMemberOidList": [], "bdkMemberOidList": [],
                "fromSrc": False, "disclosureIndexList": []}
        try:
            arr = json.loads(curl("https://www.kap.org.tr/tr/api/disclosure/members/byCriteria",
                                  json_body=body))
        except Exception:
            arr = []
        time.sleep(1.0)
        if not isinstance(arr, list) or not arr:
            continue
        for r in arr:
            text = strip_tags(" ".join(str(r.get(k, "")) for k in
                                       ("title", "disclosureTitle", "summary", "pdks")))
            et = next((t for k, t in TR_TYPE_MAP if k in text.lower()), None)
            if not et:
                continue
            m = re.search(r"([\d.,]+)\s*(milyar|milyon)?\s*TL", text)
            if not m:
                continue
            mult = {"milyar": 1e9, "milyon": 1e6}.get(m.group(2), 1.0)
            val = m.group(1).replace(".", "").replace(",", ".")
            amt = local_yi(float(val) * mult, "TRY")
            code = r.get("stockCode") or ""
            date_d = (r.get("publishDate") or from_d)[:10]
            name = r.get("membersTitle") or r.get("kapTitle") or code
            thr = THRESHOLDS[et]
            if not amt or amt < thr:
                rejected.append((et, name, amt, thr))
                continue
            events.append({
                "event_id": f"{et}:XIST:{code or name[:12]}:{date_d}",
                "event_type": et, "name": name, "name_en": name,
                "ticker": code or None, "market": "BIST", "region": "europe",
                "industry": None, "announce_date": date_d, "settle_date": None,
                "status": "announced", "amount_usd": amt, "news_title": text[:80],
                "source": "KAP", "source_url": "https://www.kap.org.tr",
                "note": f"金额取自披露摘要（{m.group(0)}）", "market_mic": "XIST",
                "domicile_country": "TR", "is_china_concept": False,
            })
            log(f"  [KAP] {et:12s} {name[:14]:16s} {amt:>7.1f} 亿$ | {text[:34]}")
    return events, rejected


# ---------------- TASE/MAYA（以·脚手架） ----------------

MAYA_UA = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; FSL 7.0.6.01001)"


def collect_maya(from_d, to_d, log):
    """实体 API 已验证（需旧 IE UA + referer 过 WAF）；即时报告端点待逆向——本轮只报健康度。"""
    try:
        arr = json.loads(curl(
            "https://api.tase.co.il/api/content/searchentities?lang=2",
            headers=[f"User-Agent: {MAYA_UA}", "referer: https://www.tase.co.il/",
                     "Content-Type: application/json"]))
        log(f"  [MAYA] 实体 API 健康（{len(arr)} 实体）；报告端点待逆向，本轮 0 事件")
    except Exception as e:
        log(f"  [MAYA] 实体 API 异常: {e}")
    return [], []


# ---------------- CVM（巴西·开放数据批量 CSV） ----------------

CVM_ZIP_URL = "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip"
CVM_CACHE = Path("/tmp/cvm_oferta.zip")


def collect_cvm(from_d, to_d, log):
    """Ofertas Públicas 全量登记（日更 zip ~5.6MB）。latin-1 + 分号分隔；
    事件日期用 Data_Registro_Oferta（Inicio 列 2022 年后停更），登记滞后约一季度。"""
    import csv
    import io
    import zipfile
    if not CVM_CACHE.exists() or time.time() - CVM_CACHE.stat().st_mtime > 20 * 3600:
        subprocess.run(["curl", "-sS", "-m", "300", "-H", f"User-Agent: {UA}",
                        "-o", str(CVM_CACHE), CVM_ZIP_URL], check=False)
    if not CVM_CACHE.exists():
        log("  [CVM] zip 下载失败，本轮跳过")
        return [], []
    events, rejected, agg = [], [], {}  # 同发行人同日多股份类别 → 聚合为一笔（否则 event_id 撞车）
    with zipfile.ZipFile(CVM_CACHE) as z:
        csv_name = next((n for n in z.namelist() if n.endswith("oferta_distribuicao.csv")), None)
        if not csv_name:
            log("  [CVM] zip 内无 csv，本轮跳过")
            return [], []
        for r in csv.DictReader(io.TextIOWrapper(z.open(csv_name), encoding="latin-1"), delimiter=";"):
            ativo = r.get("Tipo_Ativo") or ""
            if not (ativo.startswith("AÇÕES") or ativo.startswith("DEBÊNTURES")):
                continue
            dd = r.get("Data_Registro_Oferta") or r.get("Data_Abertura_Processo") or ""
            if not (from_d <= dd <= to_d):
                continue
            try:
                brl = float(r.get("Valor_Total") or 0)
            except ValueError:
                continue
            if ativo.startswith("DEBÊNTURES"):
                et = "bond"
            else:
                et = "ipo" if r.get("Oferta_Inicial") == "Y" else "follow_on"
            amt = local_yi(brl, "BRL")
            name = r.get("Nome_Emissor", "").strip()
            thr = THRESHOLDS[et]
            if not amt or amt < thr:
                rejected.append((et, name, amt, thr))
                continue
            key = (et, r.get("CNPJ_Emissor") or name, dd)
            if key not in agg:
                agg[key] = {"et": et, "name": name, "ticker": r.get("CNPJ_Emissor") or None,
                            "dd": dd, "amt": 0.0, "title": f"{r.get('Tipo_Oferta', '')} {ativo}",
                            "rows": 0}
            agg[key]["amt"] = round(agg[key]["amt"] + amt, 2)
            agg[key]["rows"] += 1
    for key, a in agg.items():
        events.append({
            "event_id": f"{a['et']}:BVMF:{(a['ticker'] or a['name'])[:14]}:{a['dd']}",
            "event_type": a["et"], "name": a["name"], "name_en": a["name"],
            "ticker": a["ticker"], "market": "B3", "region": "south_america",
            "industry": None, "announce_date": a["dd"], "settle_date": None,
            "status": "announced", "amount_usd": a["amt"], "news_title": a["title"],
            "source": "CVM Ofertas Públicas",
            "source_url": "https://dados.cvm.gov.br/dataset/oferta-distrib",
            "note": "登记制全量数据集（滞后约一季度）；金额=Valor_Total"
                    + ("；同日多类合并" if a["rows"] > 1 else ""),
            "market_mic": "BVMF", "domicile_country": "BR", "is_china_concept": False,
        })
        log(f"  [CVM] {a['et']:12s} {a['name'][:14]:16s} {a['amt']:>7.1f} 亿$ | {a['title'][:20]}")
    return events, rejected


# ---------------- SER/SIX（瑞士·官方公告 RSS） ----------------

SIX_TYPE_MAP = [("takeover", "ma"), ("offer", "ma"), ("merger", "ma"),
                ("capital increase", "follow_on"), ("buyback", "buyback"), ("repurchase", "buyback")]


def collect_six(from_d, to_d, log):
    """SIX Exchange Regulation 官方通知 RSS（并购/增减资/回购等监管公告）。"""
    raw = curl("https://www.ser-ag.com/itf-data/official-notices/rss-en.xml")
    events, rejected = [], []
    for it in re.findall(r"<item>(.*?)</item>", raw, re.S):
        tm = re.search(r"<title>(.*?)</title>", it, re.S)
        pm = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        lm = re.search(r"<link>(.*?)</link>", it, re.S)
        if not (tm and pm):
            continue
        try:
            dd = parsedate_to_datetime(strip_tags(pm.group(1))).strftime("%Y-%m-%d")
        except Exception:
            continue
        if not (from_d <= dd <= to_d):
            continue
        title = strip_tags(tm.group(1))
        low = title.lower()
        et = next((t for k, t in SIX_TYPE_MAP if k in low), None)
        if not et:
            continue
        m = re.search(r"CHF\s?([\d,]+(?:\.\d+)?)\s?(million|billion)?", title, re.I)
        if not m:
            continue
        mult = {"billion": 1e9, "million": 1e6}.get((m.group(2) or "").lower(), 1.0)
        amt = local_yi(float(m.group(1).replace(",", "")) * mult, "CHF")
        name = title.split(",")[0][:24]
        thr = THRESHOLDS[et]
        if not amt or amt < thr:
            rejected.append((et, name, amt, thr))
            continue
        events.append({
            "event_id": f"{et}:XSWX:{name.replace(' ', '-')[:20]}:{dd}",
            "event_type": et, "name": name, "name_en": name,
            "ticker": None, "market": "SIX", "region": "europe",
            "industry": None, "announce_date": dd, "settle_date": None,
            "status": "announced", "amount_usd": amt, "news_title": title[:80],
            "source": "SIX SER Official Notices",
            "source_url": strip_tags(lm.group(1)) if lm else
            "https://www.ser-ag.com/en/resources/notifications-market-participants/official-notices.html",
            "note": f"金额取自公告标题（{m.group(0)}）", "market_mic": "XSWX",
            "domicile_country": "CH", "is_china_concept": False,
        })
        log(f"  [SIX] {et:12s} {name[:14]:16s} {amt:>7.1f} 亿$ | {title[:34]}")
    return events, rejected


# ---------------- SEC Form D（美·一级市场私募申报 → funding_round） ----------------

def _formd_amount(text):
    """Form D 主文档提取 (已售金额亿$, 目标金额亿$)。原始值为美元整数（无单位词）。
    优先 Total Amount Sold（实际成交）；新申报常为 0 → 退回 Total Offering Amount（目标）。"""
    out = []
    for label in (r"Total Amount Sold", r"totalAmountSold",
                  r"Total Offering Amount", r"totalOfferingAmount"):
        m = re.search(label + r"[\s:$]{0,80}([\d,]{7,})", text)
        out.append(to_yi_usd(m.group(1), None) if m else None)
    return (out[0] or out[1]) or None, (out[2] or out[3]) or None


def collect_formd(from_d, to_d, log, max_docs=60):
    """Form D/D-A 私募豁免申报（美国一级市场的官方全量源）→ funding_round 事件。

    发现路径必须走 daily-index master.idx（EDGAR FTS 不索引 Form D，实测 2026-09-28）；
    master.idx 仅交易日存在，非交易日/被拦（部分出口 S3 AccessDenied）自动跳过。
    Form D 单日约 200-400 条，逐条取主文档限额 max_docs，其余留待人工/下轮。"""
    events, rejected = [], []
    thr = THRESHOLDS["funding_round"]
    for dd in iter_days(from_d, to_d):
        dt = datetime.strptime(dd, "%Y-%m-%d")
        if dt.weekday() >= 5:  # 周末无 master.idx
            continue
        ymd = dd.replace("-", "")
        idx_url = (f"https://www.sec.gov/Archives/edgar/daily-index/"
                   f"{dt.year}/Q{(dt.month - 1) // 3 + 1}/master.{ymd}.idx")
        raw = curl(idx_url, timeout=60)
        time.sleep(0.4)
        if not raw or "AccessDenied" in raw or not re.search(r"^\d{10}\|", raw, re.M):
            log(f"  [FormD] {dd} daily-index 不可达或为空（部分出口被 S3 AccessDenied，"
                f"换出口即可用；FTS 不索引 Form D）——跳过该日")
            continue
        rows = [l for l in raw.splitlines()
                if re.match(r"\d{10}\|", l) and re.search(r"\|D(/A)?\|", l)]
        log(f"  [FormD] {dd} Form D/D-A 申报 {len(rows)} 条（取前 {max_docs} 条主文档）")
        fetched = 0
        for line in rows:
            if fetched >= max_docs:
                break
            parts = line.split("|")
            if len(parts) < 5:
                continue
            cik, name, ftype, fdate, path = parts[0], parts[1], parts[2], parts[3], parts[4]
            doc_url = "https://www.sec.gov/Archives/" + path
            doc = curl(doc_url, timeout=30)
            fetched += 1
            time.sleep(0.25)
            if len(doc) < 500:
                continue
            text = re.sub(r"&#\d+;|&[a-z]+;", " ", re.sub(r"<[^>]+>", " ", doc))
            sold, target = _formd_amount(text)
            amt = sold if (sold and sold >= thr) else target
            if not amt:
                continue
            if amt < thr:
                rejected.append(("funding_round", name, amt, thr))
                continue
            is_target = not (sold and sold >= thr)
            events.append({
                "event_id": f"funding_round:EDGAR:{name.replace(' ', '-')[:24]}:{dd}",
                "event_type": "funding_round", "name": name, "name_en": name,
                "ticker": None, "market": "私募市场(Form D)", "region": "north_america",
                "industry": None, "announce_date": dd, "settle_date": None,
                "status": "announced", "amount_usd": amt,
                "news_title": f"Form D {ftype}：私募豁免申报"
                              + ("（目标）" if is_target else "（已售金额）"),
                "source": "SEC EDGAR Form D", "source_url": doc_url,
                "note": ("目标募资" if is_target else "已售金额")
                        + ("；修正申报 D/A" if ftype == "D/A" else "")
                        + "；Reg D 私募轮",
                "market_mic": None, "domicile_country": "US", "is_china_concept": False,
            })
            log(f"  [FormD] funding_round {name[:30]:32s} {amt:>8.1f} 亿$"
                f"{'(目标)' if is_target else ''}")
    return events, rejected


# ---------------- 宏观 flows 快照（可达性探测 + agent 手工填数） ----------------

FLOWS_SOURCES = [
    {"series_id": "us_tic_monthly", "title": "美联储 TIC 月度跨境证券流动",
     "url": "https://home.treasury.gov/data/treasury-international-capital-tic-system",
     "unit": "亿美元/月"},
    {"series_id": "jp_mof_weekly", "title": "日本财务省 周度对外/对内证券投资",
     "url": "https://www.mof.go.jp/policy/international_policy/reference/into_invest/",
     "unit": "亿日元/周"},
    {"series_id": "no_gpfg_holdings", "title": "挪威 GPFG 全量持仓（季度）",
     "url": "https://www.nbim.no/en/the-fund/market-value/", "unit": "亿美元"},
    {"series_id": "cn_samr_simple_cases", "title": "市监总局 经营者集中简易案件公示",
     "url": "https://www.samr.gov.cn/", "unit": None},
]


def collect_flows(log):
    """宏观资本流动层：本脚本只做可达性探测与登记，数值(as_of/value)由 agent 按
    references/sources.md F 节手工填——官方页面多为 JS 渲染，自动解析易碎，契约允许 value=null。"""
    flows = []
    for s in FLOWS_SOURCES:
        try:
            raw = curl(s["url"], timeout=15, redir=True)
            ok = len(raw) > 1000
        except Exception:
            ok = False
        time.sleep(0.5)
        flows.append({"series_id": s["series_id"], "title": s["title"],
                      "url": s["url"], "unit": s["unit"], "as_of": None,
                      "value": None,
                      "note": "可达，数值待 agent 手工填（sources.md F 节）" if ok
                              else "本轮不可达，人工复查"})
        log(f"  [flows] {s['series_id']:20s} {'✓可达' if ok else '✗不可达'} | {s['title']}")
    return flows


def main():
    exec_date = time.strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default=None,
                    help="查询起始日 yyyy-MM-dd，默认=查询日（以日为单位）")
    ap.add_argument("--to", dest="to", default=None,
                    help="查询截止日 yyyy-MM-dd，默认=查询日（以日为单位）")
    ap.add_argument("--date", dest="date", default=None,
                    help="单日查询快捷参数：等价 --from=--to=该日")
    ap.add_argument("--out", default=None,
                    help="输出文件；默认 daily-{查询日期}.json，跨日自动按日切分多文件")
    ap.add_argument("--max-per-type", type=int, default=4)
    ap.add_argument("--regions", default="all")
    ap.add_argument("--sources", default=None,
                    help="逗号分隔的源列表（如 cninfo,mopsov）；默认全部")
    ap.add_argument("--flows", action="store_true",
                    help="附带宏观资本流动快照（TIC/MOF/NBIM/SAMR 探测+登记，写入 meta.flows）")
    args = ap.parse_args()
    log = lambda m: print(m, flush=True)

    frm = args.frm or args.date or exec_date
    to = args.to or args.date or exec_date
    if frm > to:
        log(f"日期区间反了：{frm} > {to}")
        return 2
    c = lambda d: d.replace("-", "")
    if args.out:
        out_desc = args.out
    elif frm == to:
        out_desc = f"daily-{c(frm)}.json"
    else:
        out_desc = f"daily-{c(frm)}.json … daily-{c(to)}.json（按日切分，每天一个文件）"

    log(f"查询日期 {frm if frm == to else frm + ' ~ ' + to} | 执行日期 {exec_date} | 输出 {out_desc}")
    collectors = {
        "edgar": lambda f, t, l: collect_edgar(f, t, args.max_per_type, l),
        "hkex": collect_hkex, "cninfo": collect_cninfo, "tdnet": collect_tdnet,
        "edinet": collect_edinet, "dart": collect_dart, "mopsov": collect_mopsov,
        "kap": collect_kap, "maya": collect_maya, "cvm": collect_cvm, "six": collect_six,
        "formd": collect_formd,
    }
    selected = ([s.strip() for s in args.sources.split(",") if s.strip()] if args.sources
                else list(collectors))
    events, rejected = [], []
    for name in selected:
        fn = collectors.get(name)
        if not fn:
            log(f"  未知源（跳过）: {name}")
            continue
        try:
            ev, rj = fn(frm, to, log)
            events += ev
            rejected += rj
        except Exception as e:
            log(f"  [{name}] 失败: {e}")

    seen, dedup = set(), []
    for e in events:
        if e["event_id"] not in seen:
            seen.add(e["event_id"])
            dedup.append(e)
    regions = ["all"] if args.regions == "all" else args.regions.split(",")

    flows = collect_flows(log) if args.flows else None

    def dump(path, d_from, d_to, evs):
        meta = {"snapshot_date": d_to, "window": {"from": d_from, "to": d_to,
                "regions": regions}, "count": len(evs)}
        if flows is not None:
            meta["flows"] = flows
        doc = {"meta": meta, "events": evs}
        Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.out or frm == to:
        out = args.out or f"daily-{c(frm)}.json"
        dump(out, frm, to, dedup)
        log("\n=== 摘要 ===")
        log(f"入账 {len(dedup)} 条（已写 {out}）；门槛过滤 {len(rejected)} 笔小额")
    else:
        # 跨日窗口按日切分：整体采集一次，按 announce_date 分桶，每天一个文件（空日也落档）
        from datetime import date, timedelta
        d0, d1 = date(*map(int, frm.split("-"))), date(*map(int, to.split("-")))
        days, dd = [], d0
        while dd <= d1:
            days.append(dd.isoformat())
            dd += timedelta(days=1)
        by_day = {d: [] for d in days}
        clamped = 0
        for e in dedup:
            d = e.get("announce_date")
            if d not in by_day:  # 窗口外日期（解析回退等边缘情况）：就近夹到窗口边界日
                d = min(max(d, frm), to)
                clamped += 1
            by_day[d].append(e)
        log("\n=== 摘要 ===")
        log(f"入账 {len(dedup)} 条，按日切分 {len(days)} 个文件"
            f"（空日 {sum(1 for v in by_day.values() if not v)} 个）；门槛过滤 {len(rejected)} 笔小额")
        for d in days:
            log(f"  daily-{c(d)}.json  {len(by_day[d])} 条")
        if clamped:
            log(f"  注：{clamped} 条公告日期落在窗口外，已就近归入边界日文件")
        for d in days:
            dump(f"daily-{c(d)}.json", d, d, by_day[d])
    by = {}
    for e in dedup:
        by.setdefault(e["event_type"], []).append(e)
    for et, evs in sorted(by.items()):
        log(f"  {et:16s} {len(evs)} 条  合计 {sum(x['amount_usd'] for x in evs):.1f} 亿$")
    if rejected:
        log("  小额样本(未入账): " + "；".join(f"{n} {a}亿$" for _, n, a, _ in rejected[:5]))
    log("源状态: " + "；".join(f"{k}={v}" for k, v in SOURCE_STATUS.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
