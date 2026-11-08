import pytest

from tradestat.api import ApiError, parse_xml
from tradestat.fetch import normalize_item, normalize_nation

OK = """<?xml version="1.0" encoding="UTF-8"?><response><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>
<body><items>
<item><year>2026.09</year><statCd>US</statCd><statCdCntnKor1>미국</statCdCntnKor1><hsCd>8542</hsCd><expDlr>1000</expDlr><impDlr>400</impDlr></item>
<item><year>2026.09</year><statCd>US</statCd><statCdCntnKor1>미국</statCdCntnKor1><hsCd>8542311000</hsCd><expDlr>600</expDlr><impDlr>100</impDlr></item>
<item><year>2026.08</year><statCd>US</statCd><statCdCntnKor1>미국</statCdCntnKor1><hsCd>8542311000</hsCd><expDlr>300</expDlr><impDlr>50</impDlr></item>
<item><year>2026.08</year><statCd>US</statCd><statCdCntnKor1>미국</statCdCntnKor1><hsCd>8542319000</hsCd><expDlr>200</expDlr><impDlr>50</impDlr></item>
</items><totalCount>4</totalCount></body></response>"""

GW_ERR = """<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg>
<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"""


def test_parse_ok():
    items, meta = parse_xml(OK)
    assert len(items) == 4 and meta["totalCount"] == 4 and items[0]["hsCd"] == "8542"


def test_parse_gateway_error():
    with pytest.raises(ApiError, match="30"):
        parse_xml(GW_ERR)


def _item(year, cnty, hs, exp):
    return {"year": year, "statCd": cnty, "hsCd": hs, "expDlr": str(exp), "impDlr": "0"}


def test_item_sums_children_per_country_and_all():
    items = [_item("총계", "-", "-", 1000),
             _item("2026.09", "US", "854231", 300), _item("2026.09", "US", "854232", 200),
             _item("2026.09", "CN", "854232", 400), _item("2026.08", "AE", "854231", 100)]
    rows = {(r["yymm"], r["cnty"]): r["exp"] for r in normalize_item(items, "8542", ["ALL", "US", "CN"], ["202607", "202608", "202609"])}
    assert rows[("202609", "US")] == 500
    assert rows[("202609", "ALL")] == 900
    assert rows[("202608", "ALL")] == 100          # 설정에 없는 국가도 ALL엔 포함
    assert rows[("202608", "CN")] == 0             # 공표된 달에 해당 국가 실적이 없으면 0
    assert ("202607", "ALL") not in rows           # 응답에 아예 없는 달(미공표)은 제외


def test_item_checksum_mismatch_raises():
    items = [_item("총계", "-", "-", 999), _item("2026.09", "US", "854231", 300)]
    with pytest.raises(RuntimeError, match="총계"):
        normalize_item(items, "8542", ["ALL"], ["202609"])


def test_tenday_wide_format():
    from tradestat.fetch import normalize_tenday
    it = {"priodMon": "202602", "priodDt": "01~28", **{f"itemUsdAmt{i:02d}": "1,000" for i in range(11)}}
    rows = normalize_tenday([it, {**it, "priodDt": "01~10"}])
    assert {r["period"] for r in rows} == {"M", "D10"} and len(rows) == 22
    assert rows[0]["cnty"] == "TOTAL" and rows[0]["exp"] == 1000.0


def test_nation_total_row():
    rows = normalize_nation([{"year": "2026.09", "statCd": "-", "statCdCntnKor1": "총계", "expDlr": "5", "impDlr": "3"},
                             {"year": "2026.09", "statCd": "US", "statCdCntnKor1": "미국", "expDlr": "2", "impDlr": "1"}])
    assert rows[0]["cnty"] == "TOTAL" and rows[1]["cnty"] == "US" and rows[0]["yymm"] == "202609"
