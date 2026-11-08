from tradestat.workdays import workdays


def test_jan_2026_first_ten_days():
    # 1/1(목) 신정 0, 2(금) 1, 3(토) .5, 4(일) 0, 5~9 평일 5, 10(토) .5
    assert workdays("202601", "D10") == 7.0


def test_month_has_more_days_than_d20():
    assert workdays("202603", "M") > workdays("202603", "D20") > workdays("202603", "D10")


def test_chuseok_2025_reduces_workdays():
    # 2025 추석 연휴 10/5~10/8 + 개천절 10/3 + 한글날 10/9
    assert workdays("202510", "D10") < workdays("202410", "D10")
