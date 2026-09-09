#!/usr/bin/env python3
"""whale-capital-tracker 统一采集器（EDGAR + HKEX 双活源；其余源状态上报）

用法（默认以日为单位：不带参数 = 采集今天一天）:
  python3 collect.py                                   # 采集今天，输出 daily-20260909.json
  python3 collect.py --date 2026-09-04                 # 采集指定某一天
  python3 collect.py --from 2026-09-01 --to 2026-09-08  # 跨日窗口（补采）
  python3 collect.py --out /tmp/today.json --max-per-type 6  # 显式指定输出文件时不用默认命名

输出文件默认命名：daily-{查询日期 YYYYMMDD}.json（单日，如 daily-20260909.json），
跨日窗口为 daily-{from}-{to}.json（如 daily-20260908-20260910.json）。

产出符合 schema v1.0 的 flows.json（只入过门槛事件；未过门槛的在摘要中报告）。

已知坑（详见 references/sources.md）：
- EDGAR FTS 的 _id 常指向费用表壳页（<20KB），真金额在同名公司后续的大主文件——
  本脚本按公司遍历多个 accession，跳过小文件。
- HKEX 对连发请求软限流（返回空/非 JSON），建议单轮间隔 ≥60s，失败等 1 小时再试。
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

UA = "whale-capital-tracker/1.0 (demo@example.com)"
THRESHOLDS = {"ipo": 5, "follow_on": 5, "convertible": 5, "bond": 10, "spac": 3,
              "despac": 20, "gdr": 5, "reits": 3, "buyback": 20, "ma": 50,
              "dividend_special": 20}
HKD_PER_USD = 7.8

SOURCE_STATUS = {
    "SEC EDGAR(美)": "active", "HKEX 披露易(港)": "active(限流敏感)",
    "上交所(沪)": "端点活/参数待调", "深交所(深)": "50x", "JPX TDnet(日)": "iframe 待定位",
    "FCA NSM(英)": "连接受限", "LSE RNS(英)": "SPA 待逆向", "AMF(法)": "Huwise 门户待逆向",
    "Unternehmensregister(德)": "门户待逆向", "SEDAR+(加)": "应用流待逆向",
    "SGX/ASX/TWSE": "SPA", "NSE/BSE/JSE/KRX/Tadawul": "反爬",
}


def curl(url, headers=None, timeout=20):
    cmd = ["curl", "-s", "--max-time", str(timeout), "-H", f"User-Agent: {UA}", "--compressed"]
    for h in headers or []:
        cmd += ["-H", h]
    cmd.append(url)
    return subprocess.run(cmd, capture_output=True, text=True).stdout


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
                    help="输出文件，默认 flows.daily.q{查询日期}.e{执行日期}.json")
    ap.add_argument("--max-per-type", type=int, default=4)
    ap.add_argument("--regions", default="all")
    args = ap.parse_args()
    log = lambda m: print(m, flush=True)

    frm = args.frm or args.date or exec_date
    to = args.to or args.date or exec_date
    c = lambda d: d.replace("-", "")
    file_part = c(frm) if frm == to else f"{c(frm)}-{c(to)}"
    out = args.out or f"daily-{file_part}.json"

    log(f"查询日期 {frm if frm == to else frm + ' ~ ' + to} | 执行日期 {exec_date} | 输出 {out}")
    events, rejected = [], []
    for fn, fargs in ((collect_edgar, (frm, to, args.max_per_type, log)),
                      (collect_hkex, (frm, to, log))):
        try:
            ev, rj = fn(*fargs)
            events += ev
            rejected += rj
        except Exception as e:
            log(f"  [{fn.__name__}] 失败: {e}")

    seen, dedup = set(), []
    for e in events:
        if e["event_id"] not in seen:
            seen.add(e["event_id"])
            dedup.append(e)
    regions = ["all"] if args.regions == "all" else args.regions.split(",")
    doc = {"meta": {"snapshot_date": to, "window": {"from": frm, "to": to,
            "regions": regions}, "count": len(dedup)}, "events": dedup}
    Path(out).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    log("\n=== 摘要 ===")
    log(f"入账 {len(dedup)} 条（已写 {out}）；门槛过滤 {len(rejected)} 笔小额")
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
