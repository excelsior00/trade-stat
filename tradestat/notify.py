"""텔레그램 메시지 작성·발송."""
from __future__ import annotations

import html
import unicodedata

import requests

from . import charts
from .config import env
from .metrics import PERIOD_LABEL


def _eok(v_kusd) -> str:  # 천달러 → 억달러
    return "-" if v_kusd is None else f"{v_kusd / 1e5:,.1f}억$"


def _p(v) -> str:
    if v is None:
        return "  -  "
    arrow = "▲" if v > 0 else "▼" if v < 0 else "–"
    return f"{arrow}{abs(v):.1f}%"


def _w(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _l(s: str, n: int) -> str:  # 한글 폭(2칸)을 고려한 좌측 정렬
    return s + " " * max(0, n - _w(s))


def _r(s: str, n: int) -> str:
    return " " * max(0, n - _w(s)) + s


def _ym_label(ym: str) -> str:
    return f"{ym[:4]}년 {int(ym[4:])}월"


def _point(m: dict, cnty: str, ym: str, period: str) -> dict | None:
    s = m["tenday"].get(cnty, {}).get(period, [])
    return next((p for p in s if p["ym"] == ym), None)


def _flag(yoy, base, gap) -> str:
    """전체 증가율 대비 괴리가 gap(%p) 이상이면 🔺(상회)/🔻(하회)."""
    if yoy is None or base is None:
        return ""
    d = yoy - base
    return " 🔺" if d >= gap else " 🔻" if d <= -gap else ""


def _legend(base, gap) -> str:
    return f"<i>🔺/🔻 = 전체 전년비({_p(base)})보다 {gap:g}%p 이상 높음/낮음</i>" if base is not None else ""


def tenday_message(m: dict) -> str:
    ym, per = m["latest"]["ym"], m["latest"]["period"]
    gap = m["alertGap"]
    t = _point(m, "TOTAL", ym, per)
    py_wd = _point(m, "TOTAL", f"{int(ym[:4]) - 1}{ym[4:]}", per)
    lines = [
        f"📦 <b>수출 10일 잠정치 · {_ym_label(ym)} {PERIOD_LABEL[per]}</b>",
        "",
        f"<b>전체 {_eok(t.get('v'))}</b>",
        f"• 전년동기 {_p(t.get('yoy'))}  (일평균 {_p(t.get('dyoy'))})",
        f"• 전월동기 {_p(t.get('mom'))}  (일평균 {_p(t.get('dmom'))})",
        f"• 조업일수 {t['wd']:g}일" + (f" (전년 {py_wd['wd']:g}일)" if py_wd else ""),
        "",
        "<b>국가별</b>  금액 · 전년동기 · 전월동기 · 기여도",
        "<pre>",
    ]
    rows = []
    for c in m["countries"]:
        if c["code"] == "TOTAL":
            continue
        p = _point(m, c["code"], ym, per)
        if not p:
            continue
        flag = _flag(p.get("yoy"), t.get("yoy"), gap)
        cy = f"{p.get('cy'):+.1f}p" if p.get("cy") is not None else "-"
        rows.append((p.get("v") or 0, f"{_l(c['name'][:5], 10)}{_r(_eok(p.get('v')), 9)}{_r(_p(p.get('yoy')), 8)}{_r(_p(p.get('mom')), 8)}{_r(cy, 7)}{flag}"))
    lines += [html.escape(r[1]) for r in sorted(rows, reverse=True)]
    lines.append("</pre>")
    lines.append(_legend(t.get("yoy"), gap))
    if url := env("DASHBOARD_URL"):
        lines.append(f'🔗 <a href="{html.escape(url)}">대시보드 열기</a>')
    lines.append("<i>※ 잠정치, 일평균은 조업일수(토 0.5일) 보정</i>")
    return "\n".join(lines)


def monthly_message(m: dict, ym: str) -> str | None:
    """월 확정치(품목, 전체 국가 기준) 요약."""
    gap = m["alertGap"]
    tot = next((p for p in m["nation"].get("TOTAL", {}).get("points", []) if p["ym"] == ym), {})
    base = tot.get("eyoy")
    rows = []
    for it in m["items"]:
        s = m["item"].get(it["id"], {})
        pts = s.get("ALL") or None
        if pts is None:
            continue
        p = next((x for x in pts if x["ym"] == ym), None)
        if p:
            rows.append((it["name"], p))
    if not rows:
        return None
    rows.sort(key=lambda r: r[1]["exp"] or 0, reverse=True)
    lines = [f"📊 <b>품목별 수출 확정치 · {_ym_label(ym)}</b>", "",
             f"<b>전체 수출 {(tot.get('exp') or 0) / 1e8:,.1f}억$</b> · 전년동월 {_p(base)} · 전월 {_p(tot.get('emom'))}" if tot else "",
             "", "품목  수출액 · 전년동월 · 전월", "<pre>"]
    for name, p in rows:
        flag = _flag(p.get("eyoy"), base, gap)
        lines.append(html.escape(f"{_l(name[:6], 12)}{_r(f'{(p.get("exp") or 0) / 1e8:,.1f}억$', 11)}{_r(_p(p.get('eyoy')), 8)}{_r(_p(p.get('emom')), 8)}{flag}"))
    lines.append("</pre>")
    lines.append(_legend(base, gap))
    if url := env("DASHBOARD_URL"):
        lines.append(f'🔗 <a href="{html.escape(url)}#items">대시보드 열기</a>')
    lines.append("<i>※ 품목은 HS코드 기준 근사 분류</i>")
    return "\n".join(lines)


def tenday_charts(m: dict) -> list[bytes]:
    ym, per = m["latest"]["ym"], m["latest"]["period"]
    title = f"전체 수출 · {_ym_label(ym)} {PERIOD_LABEL[per]}"
    imgs = [charts.tenday_png(m["tenday"]["TOTAL"], per, ym, title)]
    bars = []
    for c in m["countries"]:
        p = _point(m, c["code"], ym, per)
        if p:
            bars.append((c["name"], p.get("yoy")))
    imgs.append(charts.yoy_bars_png(bars, f"국가별 전년동기대비 · {PERIOD_LABEL[per]}"))
    return imgs


# ── 전송 ─────────────────────────────────────────────────────────
def send(text: str, images: list[bytes] = (), dry_run: bool = False) -> None:
    if dry_run:
        print(text)
        print(f"[dry-run] 이미지 {len(images)}장")
        return
    token = env("TELEGRAM_BOT_TOKEN", required=True)
    chat = env("TELEGRAM_CHAT_ID", required=True)
    base = f"https://api.telegram.org/bot{token}"
    for img in images:
        r = requests.post(f"{base}/sendPhoto", data={"chat_id": chat},
                          files={"photo": ("chart.png", img, "image/png")}, timeout=30)
        r.raise_for_status()
    r = requests.post(f"{base}/sendMessage", timeout=30, data={
        "chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    if not r.ok:
        raise RuntimeError(f"텔레그램 전송 실패: {r.status_code} {r.text}")
