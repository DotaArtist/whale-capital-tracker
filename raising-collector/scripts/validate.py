#!/usr/bin/env python3
"""seed.ipos.jsonl 契约校验器。用法：python3 validate.py <file.jsonl> [--quiet]"""
import json
import re
import sys
from pathlib import Path

REGIONS = {"north_america", "hong_kong", "mainland", "japan", "korea",
           "europe", "middle_east", "india", "apac"}
INDUSTRIES = {"tech_internet", "semiconductor", "auto_ev", "pharma", "finance",
              "consumer", "manufacturing", "energy_materials", "logistics", "media_telecom"}
STATUSES = {"filed", "hearing", "subscription", "priced", "listed"}
REQUIRED = ["name", "name_en", "ticker", "exchange", "exchange_short", "region",
            "industry", "status", "listing_date", "currency", "note", "is_china_concept"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CURRENCIES = {"$", "HK$", "¥", "₩", "₹", "€", "£", "SAR", "AED", "CHF", "Rp", "C$", "A$", "待定"}


def fail(errors, line_no, msg):
    errors.append(f"line {line_no}: {msg}")


def check_record(rec, line_no, errors, seen_keys):
    for k in REQUIRED:
        if k not in rec:
            fail(errors, line_no, f"缺必填字段 {k}")
    if rec.get("region") not in REGIONS:
        fail(errors, line_no, f"region 非法: {rec.get('region')!r}（允许: {sorted(REGIONS)}）")
    if rec.get("industry") not in INDUSTRIES:
        fail(errors, line_no, f"industry 非法: {rec.get('industry')!r}")
    if rec.get("status") not in STATUSES:
        fail(errors, line_no, f"status 非法: {rec.get('status')!r}")
    for dk in ("listing_date", "filed_date"):
        v = rec.get(dk)
        if v is not None and not DATE_RE.match(str(v)):
            fail(errors, line_no, f"{dk} 日期格式应为 yyyy-MM-dd: {v!r}")
    if rec.get("status") == "listed" and rec.get("first_day_return") is None:
        fail(errors, line_no, "已上市但缺 first_day_return（如确实未披露填 0.0 并在 note 说明）")
    if rec.get("status") != "listed" and rec.get("first_day_return") is not None:
        fail(errors, line_no, "非 listed 态不应有 first_day_return")
    if rec.get("price_range") is not None and rec.get("status") not in {"subscription", "priced", "filed", "hearing"}:
        fail(errors, line_no, "price_range 只应出现在招股/在途阶段")
    cur = rec.get("currency")
    if cur is not None and cur not in CURRENCIES and not re.match(r"^[A-Z$¥₩₹€£]{1,3}$", str(cur)):
        fail(errors, line_no, f"currency 可疑: {cur!r}")
    for nk in ("raise_usd", "valuation_usd", "price_local", "first_day_return"):
        v = rec.get(nk)
        if v is not None and not isinstance(v, (int, float)):
            fail(errors, line_no, f"{nk} 应为数字或 null: {v!r}")
    key = (str(rec.get("ticker")), str(rec.get("exchange")))
    if key in seen_keys:
        fail(errors, line_no, f"重复记录 ticker+exchange: {key}")
    seen_keys.add(key)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"文件不存在: {path}")
        return 2
    errors, n, meta = [], 0, None
    seen_keys = set()
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as e:
            fail(errors, i, f"JSON 解析失败: {e}")
            continue
        if "_meta" in rec:
            if i != 1:
                fail(errors, i, "_meta 必须是首行")
            meta = rec["_meta"]
            continue
        n += 1
        check_record(rec, i, errors, seen_keys)
    if meta is not None and meta.get("count") is not None and meta["count"] != n:
        errors.append(f"_meta.count={meta['count']} 与实际数据行数 {n} 不一致")
    if meta is not None and not DATE_RE.match(str(meta.get("snapshot_date", ""))):
        errors.append("_meta.snapshot_date 缺失或格式错误（yyyy-MM-dd）")

    if errors:
        print(f"❌ {len(errors)} 个错误（{path.name}，{n} 条记录）:")
        for e in errors[:50]:
            print("  " + e)
        if len(errors) > 50:
            print(f"  ...另有 {len(errors) - 50} 个")
        return 1
    print(f"✅ 校验通过: {n} 条记录，枚举/日期/去重/口径全部合规"
          + (f"，snapshot_date={meta['snapshot_date']}" if meta else "（无 _meta 首行）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
