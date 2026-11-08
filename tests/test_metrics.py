from tradestat import metrics


def _rows():
    out = []
    for ym, tot, cn in [("202510", 100, 30), ("202609", 90, 20), ("202610", 120, 40)]:
        out += [{"yymm": ym, "period": "D10", "cnty": "TOTAL", "exp": float(tot)},
                {"yymm": ym, "period": "D10", "cnty": "CN", "exp": float(cn)}]
    return out


def test_shift():
    assert metrics.shift("202601", -1) == "202512"
    assert metrics.shift("202612", 1) == "202701"
    assert metrics.shift("202610", -12) == "202510"


def test_yoy_mom_contribution():
    s = metrics.tenday_series(_rows())
    t = s["TOTAL"]["D10"][-1]
    assert t["ym"] == "202610" and t["yoy"] == 20.0 and t["mom"] == 33.3
    cn = s["CN"]["D10"][-1]
    assert cn["yoy"] == 33.3
    assert cn["cy"] == 10.0  # (40-30)/100*100


def test_latest_period_order():
    rows = _rows() + [{"yymm": "202610", "period": "D20", "cnty": "TOTAL", "exp": 1.0}]
    assert metrics.latest_period(rows) == ("202610", "D20")


def test_item_values_minus(monkeypatch):
    monkeypatch.setattr(metrics, "settings", lambda: {"items": [{"id": "x", "name": "x", "hs": ["84"], "minus": ["8471"]}]})
    rows = [{"yymm": "202609", "cnty": "US", "hs": "84", "exp": 100.0, "imp": 10.0},
            {"yymm": "202609", "cnty": "US", "hs": "8471", "exp": 30.0, "imp": 4.0}]
    p = metrics.item_values(rows)["x"]["US"][0]
    assert p["exp"] == 70 and p["imp"] == 6
