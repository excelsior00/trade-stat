"""텔레그램 첨부용 차트 PNG (matplotlib)."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from .metrics import PERIOD_LABEL  # noqa: E402

_KO = ["Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR", "Noto Sans KR"]
_have = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = next((f for f in _KO if f in _have), "sans-serif")
plt.rcParams["axes.unicode_minus"] = False

YEAR_COLORS = ["#b8c4d6", "#7b93b8", "#1f4e99"]
UP, DOWN = "#d64545", "#2f6fd1"  # 한국식: 증가 빨강, 감소 파랑


def tenday_png(series: dict, period: str, latest_ym: str, title: str) -> bytes:
    """좌: 최근 3년 같은 구간 월별 추이 + 우: 최근 12개월 전월동기대비."""
    pts = {p["ym"]: p for p in series[period]}
    y0 = int(latest_ym[:4])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), dpi=130)

    for i, y in enumerate(range(y0 - 2, y0 + 1)):
        xs, ys = [], []
        for m in range(1, 13):
            p = pts.get(f"{y}{m:02d}")
            if p and p.get("v") is not None:
                xs.append(m)
                ys.append(p.get("v") / 1e5)
        a1.plot(xs, ys, marker="o", ms=3, lw=2.4 if y == y0 else 1.6, color=YEAR_COLORS[i], label=str(y))
    a1.set_xticks(range(1, 13), [f"{m}월" for m in range(1, 13)], fontsize=8)
    a1.set_title(f"전년동기 비교 · {PERIOD_LABEL[period]} (억달러)", fontsize=10)
    a1.legend(frameon=False, fontsize=8)
    a1.grid(axis="y", alpha=.25)

    last12 = [p for p in series[period] if p["ym"] <= latest_ym][-12:]
    labels = [f"{p['ym'][2:4]}.{p['ym'][4:]}" for p in last12]
    moms = [p.get("mom") if p.get("mom") is not None else 0 for p in last12]
    a2.bar(labels, moms, color=[UP if m >= 0 else DOWN for m in moms])
    for x, p, m in zip(labels, last12, moms):
        a2.annotate(f"{m:+.1f}%\n{p.get('v') / 1e5:.0f}", (x, m), textcoords="offset points",
                    xytext=(0, 3 if m >= 0 else -16), ha="center", fontsize=6, color="#333")
    a2.axhline(0, color="#666", lw=.8)
    a2.margins(y=0.18)  # 음수 막대 아래 라벨이 축 눈금과 겹치지 않도록
    a2.set_title(f"최근 12개월 전월동기대비 · {PERIOD_LABEL[period]} (%, 아래 숫자=억달러)", fontsize=10)
    a2.tick_params(axis="x", labelsize=7, rotation=45)
    a2.grid(axis="y", alpha=.25)
    for a in (a1, a2):
        for s in ("top",):
            a.spines[s].set_visible(False)
    fig.suptitle(title, fontsize=12, fontweight="bold")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def yoy_bars_png(rows: list[tuple[str, float]], title: str) -> bytes:
    """국가/품목별 전년동기대비 가로 막대."""
    rows = [r for r in rows if r[1] is not None]
    rows.sort(key=lambda r: r[1])
    fig, a = plt.subplots(figsize=(6.5, 0.32 * len(rows) + 1.2), dpi=130)
    a.barh([r[0] for r in rows], [r[1] for r in rows],
           color=[("#888" if r[0] == "전체" else UP if r[1] >= 0 else DOWN) for r in rows])
    lo, hi = min(0, *(r[1] for r in rows)), max(0, *(r[1] for r in rows))
    pad = (hi - lo) * .18 or 1
    a.set_xlim(lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else 0))
    for i, (_, v) in enumerate(rows):
        a.text(v, i, f" {v:+.1f}% ", va="center", ha="left" if v >= 0 else "right", fontsize=7)
    a.axvline(0, color="#666", lw=.8)
    a.set_title(title, fontsize=11)
    a.tick_params(labelsize=8)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
