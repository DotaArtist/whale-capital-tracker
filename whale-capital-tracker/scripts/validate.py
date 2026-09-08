#!/usr/bin/env python3
"""flows.json 契约校验器。用法：python3 validate.py <flows.json> [--allow-demo]
--allow-demo: 允许低于门槛的条目，但 note 必须含「演示样本」标记（测试格式用）。"""
import json
import re
import sys
from pathlib import Path

EVENT_TYPES = {"ipo", "follow_on", "convertible", "bond", "spac", "despac",
               "gdr", "reits", "buyback", "ma", "dividend_special"}
STATUSES = {"announced", "priced", "completed", "withdrawn"}
REGIONS = {"north_america", "hong_kong", "mainland", "japan", "korea",
           "europe", "middle_east", "india", "apac"}
WINDOW_REGIONS = REGIONS | {"all"}
INDUSTRIES = {"tech_internet", "semiconductor", "auto_ev", "pharma", "finance",
              "consumer", "manufacturing", "energy_materials", "logistics", "media_telecom"}
REQUIRED = ["event_id", "event_type", "name", "name_en", "market", "region",
            "announce_date", "status", "amount_usd", "news_title",
            "source", "source_url", "note"]
OPTIONAL = {"ticker", "industry", "settle_date", "counterparty", "is_china_concept", "market_mic", "domicile_country"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
THRESHOLDS = {"ipo": 5, "follow_on": 5, "convertible": 5, "bond": 10, "spac": 3,
              "despac": 20, "gdr": 5, "reits": 3, "buyback": 20, "ma": 50,
              "dividend_special": 20}
TOP20_HINT = ("前20", "top 20", "Top 20")


def fail(errors, where, msg):
    errors.append(f"{where}: {msg}")


DEMO=set()

def check_event(rec, idx, errors, seen_ids, allow_demo=False):
    where = f"events[{idx}]"
    for k in REQUIRED:
        if k not in rec:
            fail(errors, where, f"缺必填字段 {k}")
    unknown = set(rec) - set(REQUIRED) - OPTIONAL
    if unknown:
        fail(errors, where, f"契约外字段（禁止发明字段）: {sorted(unknown)}")
    et = rec.get("event_type")
    if et not in EVENT_TYPES:
        fail(errors, where, f"event_type 非法: {et!r}（允许: {sorted(EVENT_TYPES)}）")
    status = rec.get("status")
    if status not in STATUSES:
        fail(errors, where, f"status 非法: {status!r}")
    if status == "priced" and et in {"buyback", "ma", "despac", "dividend_special"}:
        fail(errors, where, f"{et} 不适用 priced 态（证券发行类专属）")
    if rec.get("region") not in REGIONS:
        fail(errors, where, f"region 非法: {rec.get('region')!r}")
    if rec.get("industry") is not None and rec.get("industry") not in INDUSTRIES:
        fail(errors, where, f"industry 非法: {rec.get('industry')!r}")
    for dk in ("announce_date", "settle_date"):
        v = rec.get(dk)
        if v is not None and not DATE_RE.match(str(v)):
            fail(errors, where, f"{dk} 应为 yyyy-MM-dd: {v!r}")
    amt = rec.get("amount_usd")
    if not isinstance(amt, (int, float)) or isinstance(amt, bool):
        fail(errors, where, f"amount_usd 应为数字（亿美元）: {amt!r}")
    elif et in THRESHOLDS and amt < THRESHOLDS[et]:
        note = str(rec.get("note") or "")
        demo_ok = allow_demo and "演示样本" in note
        if not any(h in note for h in TOP20_HINT) and not demo_ok:
            fail(errors, where, f"amount_usd={amt} 低于 {et} 门槛 {THRESHOLDS[et]} 亿$（走前20资格需 note 注明；测试格式可加 --allow-demo 且 note 标注演示样本）")
    eid = rec.get("event_id")
    if not isinstance(eid, str) or eid.count(":") < 3:
        fail(errors, where, f"event_id 应为 type:market:ticker:yyyy-MM-dd: {eid!r}")
    if eid in seen_ids:
        fail(errors, where, f"event_id 重复: {eid}")
    seen_ids.add(eid)
    mic = rec.get("market_mic")
    if mic is not None and not re.match(r"^[A-Z0-9]{4}$", str(mic)):
        fail(errors, where, f"market_mic 应为 ISO 10383 四字符码(如 XNAS): {mic!r}")
    dc = rec.get("domicile_country")
    if dc is not None and not re.match(r"^[A-Z]{2}$", str(dc)):
        fail(errors, where, f"domicile_country 应为 ISO 3166-1 alpha-2: {dc!r}")
    if not isinstance(rec.get("is_china_concept", False), bool):
        fail(errors, where, "is_china_concept 应为 bool")
    url = rec.get("source_url")
    if not isinstance(url, str) or not url.startswith("http"):
        fail(errors, where, f"source_url 应为官方链接: {url!r}")


def main():
    args=[a for a in sys.argv[1:] if not a.startswith('--')]
    allow_demo='--allow-demo' in sys.argv
    if not args:
        print(__doc__)
        return 2
    path = Path(args[0])
    if not path.exists():
        print(f"文件不存在: {path}")
        return 2
    errors = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ 不是合法 JSON: {e}")
        return 1
    if not isinstance(doc, dict) or "meta" not in doc or "events" not in doc:
        print('❌ 顶层结构应为 {"meta": {...}, "events": [...]}')
        return 1
    meta, events = doc["meta"], doc["events"]
    if not isinstance(events, list):
        print("❌ events 应为数组")
        return 1
    if not DATE_RE.match(str(meta.get("snapshot_date", ""))):
        fail(errors, "meta", "snapshot_date 缺失或格式错误（yyyy-MM-dd）")
    window = meta.get("window") or {}
    for k in ("from", "to"):
        if not DATE_RE.match(str(window.get(k, ""))):
            fail(errors, "meta.window", f"{k} 缺失或格式错误（必须记录本次采集时间窗）")
    regions = window.get("regions")
    if not isinstance(regions, list) or not regions or not set(regions) <= WINDOW_REGIONS:
        fail(errors, "meta.window", f"regions 缺失或含非法 slug: {regions!r}")
    if meta.get("count") != len(events):
        fail(errors, "meta", f"count={meta.get('count')!r} 与 events 长度 {len(events)} 不一致")

    seen_ids = set()
    for i, rec in enumerate(events):
        if allow_demo and str(rec.get("note","")).find("演示样本")>=0:
            pass  # 演示标记已在 check_event 内通过 allow_demo+note 判定
        check_event(rec, i, errors, seen_ids, allow_demo)

    if errors:
        print(f"❌ {len(errors)} 个错误（{path.name}，{len(events)} 条事件）:")
        for e in errors[:50]:
            print("  " + e)
        return 1
    print(f"✅ 校验通过: {len(events)} 条巨鲸事件，"
          f"窗口 {window.get('from')}~{window.get('to')}，地域 {regions}，字段全部合规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
