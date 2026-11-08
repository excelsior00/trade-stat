"""CLI.

  python -m tradestat backfill [--only tenday|nation|item] [--hs 8542,8703]
  python -m tradestat update            # 증분 수집 + build + (신규 구간이면) 알림
  python -m tradestat build             # docs/data/metrics.json 재생성
  python -m tradestat notify [--force] [--dry-run]
"""
from __future__ import annotations

import argparse
import json

from . import fetch, metrics, notify, store
from .config import DATA_DIR, DOCS_DATA_DIR, settings

STATE = DATA_DIR / "state.json"


def _state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def _save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def build() -> dict:
    m = metrics.build(store.load("tenday"), store.load("nation"), store.load("itemhs"))
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA_DIR / "metrics.json").write_text(
        json.dumps(m, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"build: 최신 구간 {m['latest']}")
    return m


def do_notify(m: dict, force: bool, dry_run: bool) -> None:
    st = _state()
    if m["latest"]:
        key = f"{m['latest']['ym']}-{m['latest']['period']}"
        if force or st.get("tenday_sent") != key:
            notify.send(notify.tenday_message(m), notify.tenday_charts(m), dry_run)
            if not dry_run:
                st["tenday_sent"] = key
        else:
            print(f"10일 잠정치 {key} 는 이미 발송됨")
    # 품목 월 확정치: 가장 최근 월
    yms = [p["ym"] for s in m["item"].values() for pts in s.values() for p in pts]
    if yms:
        ym = max(yms)
        if force or st.get("monthly_sent") != ym:
            msg = notify.monthly_message(m, ym)
            if msg:
                notify.send(msg, [], dry_run)
                if not dry_run:
                    st["monthly_sent"] = ym
    if not dry_run:
        _save_state(st)


def main() -> None:
    ap = argparse.ArgumentParser(prog="tradestat")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backfill")
    b.add_argument("--only", choices=["tenday", "nation", "item"])
    b.add_argument("--hs", help="품목 백필할 HS코드 (쉼표 구분, 기본 전체)")
    b.add_argument("--start", help="시작년월 YYYYMM")
    u = sub.add_parser("update")
    u.add_argument("--no-notify", action="store_true")
    u.add_argument("--dry-run", action="store_true")
    sub.add_parser("build")
    n = sub.add_parser("notify")
    n.add_argument("--force", action="store_true")
    n.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    s = settings()
    if a.cmd == "backfill":
        mstart = a.start or metrics.shift(fetch.this_month(), -12 * s["monthly_backfill_years"])
        if a.only in (None, "tenday"):
            print("10일 잠정치:", fetch.update_tenday(a.start or s["tenday_start"], snapshot=False), "행 변경")
        if a.only in (None, "nation"):
            print("국가별 월:", fetch.update_nation(mstart), "행 변경")
        if a.only in (None, "item"):
            codes = a.hs.split(",") if a.hs else None
            print("품목별 월:", fetch.update_items(mstart, codes=codes), "행 변경")
        build()
    elif a.cmd == "update":
        print("10일 잠정치:", fetch.update_tenday(), "행 변경")
        # 월 확정치는 매월 15일경 전월분이 나옴 → 14~20일에만 조회 (트래픽·시간 절약).
        # 단, 전전월 데이터까지 비어 있으면(실행 누락 등) 날짜와 무관하게 조회.
        day = int(fetch.datetime.now(metrics.KST).strftime("%d"))
        prev2 = metrics.shift(fetch.this_month(), -2)
        if 14 <= day <= 20 or not any(r["yymm"] == prev2 for r in store.load("nation")):
            print("국가별 월:", fetch.update_nation(), "행 변경")
        if 14 <= day <= 20 or not any(r["yymm"] == prev2 for r in store.load("itemhs")):
            print("품목별 월:", fetch.update_items(), "행 변경")
        m = build()
        if not a.no_notify:
            do_notify(m, False, a.dry_run)
    elif a.cmd == "build":
        build()
    elif a.cmd == "notify":
        do_notify(build(), a.force, a.dry_run)


if __name__ == "__main__":
    main()
