"""정규화된 데이터를 CSV로 보관 (키 기준 upsert)."""
from __future__ import annotations

import csv
from pathlib import Path

from .config import DATA_DIR

FILES = {
    "tenday": (DATA_DIR / "tenday.csv", ["yymm", "period", "cnty"], ["exp", "exp_first"]),
    "nation": (DATA_DIR / "monthly_country.csv", ["yymm", "cnty"], ["cnty_name", "exp", "imp"]),
    "itemhs": (DATA_DIR / "monthly_item_hs.csv", ["yymm", "cnty", "hs"], ["exp", "imp"]),
}
NUMERIC = {"exp", "imp", "exp_first"}


def _path(kind: str) -> tuple[Path, list[str], list[str]]:
    return FILES[kind]


def load(kind: str) -> list[dict]:
    path, keys, vals = _path(kind)
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in NUMERIC & r.keys():
            r[k] = float(r[k]) if r[k] not in ("", None) else None
    return rows


def upsert(kind: str, new_rows: list[dict], snapshot: bool = False) -> int:
    """키가 같은 행은 새 값으로 교체. 변경된 행 수 반환.
    exp_first 열이 있으면 기존 값을 유지하고, 새 행이면서 snapshot=True 일 때만 exp 로 채운다."""
    path, keys, vals = _path(kind)
    cur = {tuple(r[k] for k in keys): r for r in load(kind)}
    changed = 0
    for r in new_rows:
        k = tuple(str(r[c]) for c in keys)
        old = cur.get(k)
        if "exp_first" in vals:
            r = {**r, "exp_first": old.get("exp_first") if old else (r["exp"] if snapshot else None)}
        if old is None or any(_ne(old.get(v), r.get(v)) for v in vals):
            changed += 1
        cur[k] = {**{c: str(r[c]) for c in keys}, **{v: r.get(v) for v in vals}}
    rows = sorted(cur.values(), key=lambda r: tuple(r[k] for k in keys))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys + vals)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in keys + vals})
    return changed


def _ne(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) > 1e-6
        except (TypeError, ValueError):
            return a != b
    return str(a) != str(b)


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.0f}" if v == int(v) else f"{v:.3f}"
    return "" if v is None else v
