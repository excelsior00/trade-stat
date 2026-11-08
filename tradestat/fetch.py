"""3개 API 수집 + 정규화."""
from __future__ import annotations

import re
from datetime import datetime

from . import store
from .api import fetch_all
from .config import settings
from .metrics import KST, shift

EP = lambda k: settings()["endpoints"][k]  # noqa: E731


def _num(v) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _yymm(v: str) -> str | None:
    m = re.match(r"^\s*(\d{4})\D?(\d{1,2})", str(v or ""))
    return f"{m.group(1)}{int(m.group(2)):02d}" if m else None


def this_month() -> str:
    return datetime.now(KST).strftime("%Y%m")


def year_chunks(start: str, end: str):
    """[start, end] 를 최대 12개월 구간으로 분할 (API 조회기간 1년 제한)."""
    cur = start
    while cur <= end:
        stop = min(shift(cur, 11), end)
        yield cur, stop
        cur = shift(stop, 1)


# ── 10일 잠정치 ─────────────────────────────────────────────────
def _period(v: str) -> str | None:
    """'01~10' → D10, '01~20' → D20, '01~28/29/30/31' → M."""
    m = re.search(r"(\d{1,2})\s*$", str(v))
    if not m:
        return None
    end = int(m.group(1))
    return {10: "D10", 20: "D20"}.get(end, "M" if end >= 28 else None)


def normalize_tenday(items: list[dict]) -> list[dict]:
    """10일 잠정치 응답(행=월×구간, 열=국가) → [{yymm, period, cnty, exp(천달러)}]."""
    f = settings()["tenday_fields"]
    out = []
    for it in items:
        ym, per = _yymm(it.get(f["yymm"], "")), _period(it.get(f["period"], ""))
        if not ym or not per:
            continue
        for code, col in f["columns"].items():
            out.append({"yymm": ym, "period": per, "cnty": code, "exp": _num(it.get(col))})
    return out


def update_tenday(start: str | None = None, snapshot: bool = True) -> int:
    """snapshot=True 이면 처음 보는 구간의 값을 exp_first(최초 공표값)로 보관.
    API는 지난 구간을 정정치로 덮어쓰므로, 잠정 vs 확정 비교에는 이 값이 필요하다."""
    end = this_month()
    start = start or shift(end, -3)  # 최근 3개월 재조회로 정정치 반영
    rows = []
    for a, b in year_chunks(start, end):
        rows += normalize_tenday(fetch_all(EP("tenday"), {"strtYymm": a, "endYymm": b}))
    return store.upsert("tenday", rows, snapshot=snapshot)


# ── 국가별 월 확정치 ─────────────────────────────────────────────
def normalize_nation(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        ym = _yymm(it.get("year", ""))
        code = (it.get("statCd") or "").strip()
        name = (it.get("statCdCntnKor1") or "").strip()
        if not ym:
            continue
        if not code or code == "-" or name in ("총계", "전체", "합계"):  # ZZ는 '기타국'이므로 제외
            code, name = "TOTAL", "전체"
        out.append({"yymm": ym, "cnty": code, "cnty_name": name,
                    "exp": _num(it.get("expDlr")), "imp": _num(it.get("impDlr"))})
    return out


def update_nation(start: str | None = None) -> int:
    end = shift(this_month(), -1)
    start = start or shift(end, -2)
    rows = []
    for a, b in year_chunks(start, end):
        rows += normalize_nation(fetch_all(EP("nation"), {"strtYymm": a, "endYymm": b}))
    return store.upsert("nation", rows)


# ── 품목별 국가별 월 확정치 ──────────────────────────────────────
def hs_codes() -> list[str]:
    codes = []
    for it in settings()["items"]:
        for c in it["hs"] + it.get("minus", []):
            if c not in codes:
                codes.append(c)
    return codes


def normalize_item(items: list[dict], hs: str, countries: list[str], months: list[str]) -> list[dict]:
    """국가 미지정 hsSgn 조회 결과(모든 국가 × 하위 HS 행) → 국가별·월별 합계.

    API는 요청 코드의 한 단계 하위 코드(예: 8542 → 854231…)로 쪼개서 주므로, 요청 코드와
    정확히 일치하는 행이 있으면 그것만, 없으면 가장 세분화된 단위의 행만 합산(이중 합산 방지).
    '총계' 행으로 합계를 검증하고, 데이터가 없는 달·국가는 0으로 채운다.
    """
    rows = []
    for it in items:
        ym = _yymm(it.get("year", ""))
        code = re.sub(r"\D", "", it.get("hsCd", ""))
        if ym and code.startswith(hs):
            rows.append({**it, "_ym": ym, "_hs": code})
    exact = [r for r in rows if r["_hs"] == hs]
    if not exact and rows:
        depth = max(len(r["_hs"]) for r in rows)
        exact = [r for r in rows if len(r["_hs"]) == depth]

    total = next((it for it in items if str(it.get("year", "")).strip() == "총계"), None)
    if total and exact and len(exact) == len(rows):
        got, want = sum(_num(r.get("expDlr")) or 0 for r in exact), _num(total.get("expDlr")) or 0
        if abs(got - want) > 1:
            raise RuntimeError(f"HS {hs}: 행 합계 {got:,.0f} ≠ 총계 {want:,.0f} (응답 잘림 의심)")

    # 응답에 한 행도 없는 달 = 아직 공표 전 → 0으로 채우지 않고 제외
    published = {r["_ym"] for r in rows}
    acc: dict[tuple[str, str], list[float]] = {}
    for r in exact:
        for c in ("ALL", (r.get("statCd") or "").strip()):
            a = acc.setdefault((r["_ym"], c), [0.0, 0.0])
            a[0] += _num(r.get("expDlr")) or 0
            a[1] += _num(r.get("impDlr")) or 0
    return [{"yymm": ym, "cnty": c, "hs": hs, "exp": acc.get((ym, c), [0, 0])[0], "imp": acc.get((ym, c), [0, 0])[1]}
            for ym in months if ym in published for c in countries]


def _months(a: str, b: str) -> list[str]:
    out, cur = [], a
    while cur <= b:
        out.append(cur)
        cur = shift(cur, 1)
    return out


def update_items(start: str | None = None, codes: list[str] | None = None) -> int:
    """HS코드마다 국가 미지정으로 1년 단위 조회 → 설정된 국가 + 전체(ALL)를 한 번에 저장."""
    end = shift(this_month(), -1)
    start = start or shift(end, -2)
    countries = settings()["item_countries"]
    changed = 0
    for hs in codes or hs_codes():
        rows = []
        for a, b in year_chunks(start, end):
            rows += normalize_item(fetch_all(EP("item"), {"strtYymm": a, "endYymm": b, "hsSgn": hs}),
                                   hs, countries, _months(a, b))
        changed += store.upsert("itemhs", rows)  # HS 단위 저장 → 중단돼도 이어받기 쉬움
        print(f"  HS {hs}: {len(rows)}행")
    return changed
