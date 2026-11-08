"""data.go.kr 관세청 API 공통 호출기: 재시도, 오류 판별, XML→dict, 페이징."""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET

import requests

from .config import service_key


class ApiError(RuntimeError):
    pass


# data.go.kr 게이트웨이 오류 코드 중 재시도해도 소용없는 것
_FATAL = {"30": "등록되지 않은 서비스키", "31": "기한 만료된 서비스키", "32": "등록되지 않은 IP",
          "20": "서비스 접근 거부(활용신청 승인 필요)", "12": "해당 오픈API 서비스가 없거나 폐기됨",
          "22": "서비스 요청제한 횟수 초과"}


def parse_xml(text: str) -> tuple[list[dict], dict]:
    """응답 XML → (item 목록, 메타). 오류 응답이면 ApiError."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ApiError(f"XML 파싱 실패: {text[:200]!r}") from e

    # 게이트웨이 오류 형식: <OpenAPI_ServiceResponse><cmmMsgHeader>...
    hdr = root.find(".//cmmMsgHeader")
    if hdr is not None:
        code = (hdr.findtext("returnReasonCode") or "").strip()
        msg = (hdr.findtext("returnAuthMsg") or hdr.findtext("errMsg") or "").strip()
        raise ApiError(f"[{code}] {_FATAL.get(code, msg)} ({msg})")

    code = (root.findtext(".//header/resultCode") or "").strip()
    msg = (root.findtext(".//header/resultMsg") or "").strip()
    if code and code not in ("00", "0", "000"):
        # 03 = NODATA 는 오류가 아니라 빈 결과
        if code == "03" or "NODATA" in msg.upper():
            return [], {"resultCode": code}
        raise ApiError(f"[{code}] {msg}")

    items = []
    for it in root.iter("item"):
        items.append({c.tag: (c.text or "").strip() for c in it})
    meta = {}
    for k in ("totalCount", "numOfRows", "pageNo"):
        v = root.findtext(f".//body/{k}")
        if v and v.strip().isdigit():
            meta[k] = int(v)
    return items, meta


def call(url: str, params: dict, *, retries: int = 4, timeout: int = 30) -> str:
    q = {"serviceKey": service_key(), **params}
    last: Exception | None = None
    for i in range(retries):
        try:
            r = requests.get(url, params=q, timeout=timeout)
            if r.status_code >= 500 or r.status_code == 429:
                raise ApiError(f"HTTP {r.status_code}")
            r.encoding = r.encoding or "utf-8"
            text = r.text
            if r.status_code != 200:
                raise ApiError(f"HTTP {r.status_code}: {text[:200]}")
            # 게이트웨이의 치명적 오류는 즉시 중단
            try:
                parse_xml(text)
            except ApiError as e:
                if any(f"[{c}]" in str(e) for c in _FATAL):
                    raise SystemExit(f"API 오류 {url}: {e}") from e
                raise
            return text
        except (requests.RequestException, ApiError) as e:
            last = e
            time.sleep(2 ** i)
    raise ApiError(f"{url} {params} 호출 실패: {last}")


def fetch_all(url: str, params: dict, page_size: int = 1000) -> list[dict]:
    """페이징이 있으면 끝까지 받아서 item 전체 반환."""
    out: list[dict] = []
    page = 1
    while True:
        text = call(url, {**params, "numOfRows": page_size, "pageNo": page})
        items, meta = parse_xml(text)
        out.extend(items)
        total = meta.get("totalCount")
        if not items or total is None or len(out) >= total:
            return out
        page += 1
