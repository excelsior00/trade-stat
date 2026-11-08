"""API 구조 탐색: 실제 호출해서 응답 필드·경로·제약을 확인하고 data/probe/에 원본 저장.

사용: .venv/Scripts/python scripts/probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tradestat.api import ApiError, parse_xml  # noqa: E402
from tradestat.config import DATA_DIR, service_key, settings  # noqa: E402

OUT = DATA_DIR / "probe"
OUT.mkdir(parents=True, exist_ok=True)
EP = settings()["endpoints"]

OPS = {
    "tenday": ["", "/getCntyMmUtPrviExpAcrs", "/getCntyMmUtPrviExpAcrsList"],
    "nation": ["", "/getNationtradeList"],
    "item": ["", "/getNitemtradeList"],
}

CASES = [
    ("tenday", "recent", {"strtYymm": "202601", "endYymm": "202611"}),
    ("tenday", "longrange", {"strtYymm": "201601", "endYymm": "202611"}),
    ("nation", "allcnty", {"strtYymm": "202609", "endYymm": "202609"}),
    ("nation", "us_1y", {"strtYymm": "202510", "endYymm": "202609", "cntyCd": "US"}),
    ("nation", "us_2y", {"strtYymm": "202410", "endYymm": "202609", "cntyCd": "US"}),
    ("nation", "eu", {"strtYymm": "202609", "endYymm": "202609", "cntyCd": "EU"}),
    ("item", "us_8542", {"strtYymm": "202601", "endYymm": "202609", "cntyCd": "US", "hsSgn": "8542"}),
    ("item", "nocnty_8542", {"strtYymm": "202609", "endYymm": "202609", "hsSgn": "8542"}),
    ("item", "us_84", {"strtYymm": "202609", "endYymm": "202609", "cntyCd": "US", "hsSgn": "84"}),
    ("item", "us_89", {"strtYymm": "202609", "endYymm": "202609", "cntyCd": "US", "hsSgn": "89"}),
]


def try_call(api: str, params: dict) -> tuple[str, str] | None:
    for op in OPS[api]:
        url = EP[api].rstrip("/") + op
        try:
            r = requests.get(url, params={"serviceKey": service_key(), **params}, timeout=30)
        except requests.RequestException as e:
            print(f"   {url}: {e}")
            continue
        if r.status_code == 200 and "<" in r.text:
            return url, r.text
        print(f"   {url}: HTTP {r.status_code} {r.text[:120]!r}")
    return None


def main() -> None:
    for api, name, params in CASES:
        print(f"\n=== {api}/{name} {params}")
        res = try_call(api, params)
        if not res:
            continue
        url, text = res
        (OUT / f"{api}_{name}.xml").write_text(text, encoding="utf-8")
        print(f"   URL OK: {url}")
        try:
            items, meta = parse_xml(text)
        except ApiError as e:
            print(f"   오류: {e}")
            continue
        print(f"   meta={meta} rows={len(items)}")
        if items:
            print(f"   fields={list(items[0].keys())}")
            for it in items[:4]:
                print(f"   {it}")
            if len(items) > 4:
                print(f"   ... last: {items[-1]}")


if __name__ == "__main__":
    main()
