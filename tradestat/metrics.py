"""정규화 데이터 → 대시보드/텔레그램용 지표(JSON).

- 전년동기대비(yoy): 같은 월·같은 10일 구간의 전년 값 대비 %
- 전월동기대비(mom): 전월 같은 10일 구간 대비 %
- 일평균(d): 값 / 조업일수, dyoy·dmom 은 일평균 기준 증감률
- 기여도(cy): 국가별 증감액 / 전년 전체 수출 × 100 (%p)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .config import settings
from .workdays import workdays

PERIODS = ["D10", "D20", "M"]
PERIOD_LABEL = {"D10": "1~10일", "D20": "1~20일", "M": "월 전체"}
KST = timezone(timedelta(hours=9))


def pct(a, b):
    if a is None or b is None or b <= 0:
        return None
    return round((a / b - 1) * 100, 1)


def _compact(p: dict) -> dict:
    """JSON 크기 절감: 값이 없는 키 제거."""
    return {k: v for k, v in p.items() if v is not None}


def shift(yymm: str, months: int) -> str:
    y, m = int(yymm[:4]), int(yymm[4:])
    t = y * 12 + (m - 1) + months
    return f"{t // 12:04d}{t % 12 + 1:02d}"


def _r(v, n=1):
    return None if v is None else round(v, n)


# ── 10일 잠정치 ─────────────────────────────────────────────────
def tenday_series(rows: list[dict]) -> dict:
    by = defaultdict(dict)  # (cnty, period) -> {yymm: value}
    for r in rows:
        if r["exp"] is not None:
            by[(r["cnty"], r["period"])][r["yymm"]] = r["exp"]

    names = {c["code"]: c["name"] for c in settings()["countries"]}
    out: dict = {}
    for (cnty, period), vals in by.items():
        total = by.get(("TOTAL", period), {})
        pts = []
        for ym in sorted(vals):
            v = vals[ym]
            wd = workdays(ym, period)
            py, pm = vals.get(shift(ym, -12)), vals.get(shift(ym, -1))
            d = v / wd if wd else None
            dpy = py / workdays(shift(ym, -12), period) if py is not None else None
            dpm = pm / workdays(shift(ym, -1), period) if pm is not None else None
            p = {"ym": ym, "v": _r(v, 0), "wd": wd, "d": _r(d, 0),
                 "py": _r(py, 0), "yoy": pct(v, py), "pm": _r(pm, 0), "mom": pct(v, pm),
                 "dyoy": pct(d, dpy), "dmom": pct(d, dpm)}
            if cnty != "TOTAL" and py is not None and total.get(shift(ym, -12)):
                p["cy"] = round((v - py) / total[shift(ym, -12)] * 100, 2)
            pts.append(_compact(p))
        out.setdefault(cnty, {"name": names.get(cnty, cnty)})[period] = pts
    return out


def latest_period(rows: list[dict]) -> tuple[str, str] | None:
    keys = {(r["yymm"], r["period"]) for r in rows if r["cnty"] == "TOTAL" and r["exp"] is not None}
    if not keys:
        return None
    return max(keys, key=lambda k: (k[0], PERIODS.index(k[1])))


# ── 월 확정치 (국가) ─────────────────────────────────────────────
def _monthly_points(vals: dict[str, dict]) -> list[dict]:
    pts = []
    for ym in sorted(vals):
        e, i = vals[ym].get("exp"), vals[ym].get("imp")
        py, pm = vals.get(shift(ym, -12), {}), vals.get(shift(ym, -1), {})
        pts.append(_compact({"ym": ym, "exp": _r(e, 0), "imp": _r(i, 0),
                    "bal": _r(e - i, 0) if e is not None and i is not None else None,
                    "eyoy": pct(e, py.get("exp")), "emom": pct(e, pm.get("exp")),
                    "iyoy": pct(i, py.get("imp")), "imom": pct(i, pm.get("imp"))}))
    return pts


def nation_series(rows: list[dict]) -> dict:
    by = defaultdict(dict)
    names = {}
    for r in rows:
        by[r["cnty"]][r["yymm"]] = {"exp": r["exp"], "imp": r["imp"]}
        names[r["cnty"]] = r.get("cnty_name") or r["cnty"]
    if "TOTAL" not in by and by:  # 총계 행이 없으면 국가 합산
        tot = defaultdict(lambda: {"exp": 0.0, "imp": 0.0})
        for c, vals in by.items():
            for ym, v in vals.items():
                tot[ym]["exp"] += v["exp"] or 0
                tot[ym]["imp"] += v["imp"] or 0
        by["TOTAL"], names["TOTAL"] = dict(tot), "전체"
    return {c: {"name": names[c], "points": _monthly_points(v)} for c, v in by.items()}


# ── 월 확정치 (품목) ─────────────────────────────────────────────
def item_values(hs_rows: list[dict]) -> dict:
    """HS코드별 값 → 설정의 품목 정의(hs 합산, minus 차감)로 집계."""
    hs = defaultdict(dict)  # (cnty, hs) -> {ym: {exp, imp}}
    for r in hs_rows:
        hs[(r["cnty"], r["hs"])][r["yymm"]] = r
    cntys = {c for c, _ in hs}
    out: dict = {}
    for item in settings()["items"]:
        for c in cntys:
            acc: dict[str, dict] = {}
            for sign, codes in ((1, item["hs"]), (-1, item.get("minus", []))):
                for code in codes:
                    for ym, r in hs.get((c, code), {}).items():
                        a = acc.setdefault(ym, {"exp": 0.0, "imp": 0.0, "n": 0})
                        a["exp"] += sign * (r["exp"] or 0)
                        a["imp"] += sign * (r["imp"] or 0)
                        a["n"] += sign > 0
            # 구성 HS 중 일부만 있는 달은 불완전하므로 제외
            full = {ym: a for ym, a in acc.items() if a["n"] == len(item["hs"])}
            if full:
                out.setdefault(item["id"], {})[c] = _monthly_points(full)
    return out


# ── 잠정치 vs 확정치 ────────────────────────────────────────────
def prov_vs_final(ten: list[dict], nation: dict) -> list[dict]:
    """월 전체(M) 잠정치의 최초 공표값(exp_first) vs 국가별 월 확정치.
    최초 공표값은 수집을 시작한 이후 구간부터만 존재한다."""
    out = []
    for r in ten:
        if r["period"] != "M" or r.get("exp_first") is None:
            continue
        s = nation.get(r["cnty"])
        f = next((p["exp"] for p in s["points"] if p["ym"] == r["yymm"]), None) if s else None
        if f:
            prov = r["exp_first"] * 1000  # 천달러 → 달러
            out.append({"ym": r["yymm"], "cnty": r["cnty"], "prov": round(prov),
                        "final": f, "diff": round((f / prov - 1) * 100, 2)})
    return sorted(out, key=lambda x: (x["ym"], x["cnty"]))


def build(ten_rows: list[dict], nation_rows: list[dict], itemhs_rows: list[dict]) -> dict:
    nation = nation_series(nation_rows)
    lp = latest_period(ten_rows)
    s = settings()
    return {
        "generated": datetime.now(KST).isoformat(timespec="minutes"),
        "latest": {"ym": lp[0], "period": lp[1]} if lp else None,
        "periodLabel": PERIOD_LABEL,
        "countries": [{"code": c["code"], "name": c["name"]} for c in s["countries"]],
        "items": [{"id": i["id"], "name": i["name"], "hs": i["hs"], "minus": i.get("minus", [])}
                  for i in s["items"]],
        "tenday": tenday_series(ten_rows),
        "nation": nation,
        "item": item_values(itemhs_rows),
        "provFinal": prov_vs_final(ten_rows, nation),
        "alertGap": s["alert"]["yoy_gap_pp"],
    }
