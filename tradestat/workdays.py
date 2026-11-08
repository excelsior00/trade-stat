"""조업일수 계산 (관세청 방식: 평일 1일, 토요일 0.5일, 일요일·공휴일 0일).

공휴일은 `holidays` 패키지(KR, 대체공휴일 포함)를 쓰고, 임시공휴일 등 누락분은
config/workdays_override.yaml 에서 날짜별 가중치로 덮어쓸 수 있다.
"""
from __future__ import annotations

import calendar
from datetime import date
from functools import lru_cache

import holidays
import yaml

from .config import ROOT

PERIOD_END = {"D10": 10, "D20": 20}  # "M" = 말일


@lru_cache
def _overrides() -> dict[date, float]:
    p = ROOT / "config" / "workdays_override.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {date.fromisoformat(str(k)): float(v) for k, v in raw.items()}


@lru_cache
def _kr(year: int):
    return holidays.KR(years=year)


def day_weight(d: date) -> float:
    ov = _overrides()
    if d in ov:
        return ov[d]
    if d.weekday() == 6 or d in _kr(d.year):
        return 0.0
    if d.weekday() == 5:
        return 0.5
    return 1.0


def period_end_day(yymm: str, period: str) -> int:
    y, m = int(yymm[:4]), int(yymm[4:])
    return PERIOD_END.get(period) or calendar.monthrange(y, m)[1]


def workdays(yymm: str, period: str = "M") -> float:
    """해당 월 1일 ~ 구간 말일까지의 조업일수."""
    y, m = int(yymm[:4]), int(yymm[4:])
    return sum(day_weight(date(y, m, d)) for d in range(1, period_end_day(yymm, period) + 1))
