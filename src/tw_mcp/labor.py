"""勞基法加班費（延長工時工資）試算。

主要金額＝「法定最低」：依勞動基準法條文用分數計算（加給三分之一＝×4/3、三分之二＝×5/3、二又三分之二＝×8/3），
以 Fraction 精確運算，最後才四捨五入到元（0.5 進位）。
另附「業界常用 1.34／1.67／2.67 進位倍率」的金額（common_practice）供對照——tw-shop-staff 預設即用這組倍率。

分段與日別邏輯移植自 tw-shop-staff 的 app/payroll.py（legal_pay、_tiers）：
- 平日延長工時（第 24 條第 1 項）：前 2 小時 ×4/3、再 2 小時 ×5/3
- 休息日出勤（第 24 條第 2 項）：前 2 小時 ×4/3、第 3～8 小時 ×5/3、第 9 小時起 ×8/3
- 國定假日出勤（第 39 條）：工資加倍（月薪制另加給一日工資；時薪制給兩倍），超過 8 小時的部分依平日延長工時計
- 例假日（第 36、40 條）：原則上不得出勤，比照國定假日加倍並提出警告
- 月薪制每小時工資額＝月薪 ÷ 30 ÷ 8（＝ ÷240）
- 一日正常工時＋延長工時合計不得超過 12 小時（第 32 條）

原則上僅供參考，不構成法律意見；實際以勞動部函釋、勞資約定與主管機關認定為準。
"""
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction as F
from importlib import resources

HOURLY_DIVISOR = 240           # 月薪 ÷ 30 ÷ 8
DAILY_REGULAR_MIN = 480        # 一日正常工時 8 小時
DAILY_MAX_MIN = 720            # 正常＋延長合計 12 小時
INF = 10 ** 9
# 法定最低倍率（分數）
OT_TIERS = [(120, F(4, 3)), (INF, F(5, 3))]
REST_TIERS = [(120, F(4, 3)), (480, F(5, 3)), (INF, F(8, 3))]
# 業界常用進位倍率（對照用）
PRACTICE_RATE = {F(4, 3): F("1.34"), F(5, 3): F("1.67"), F(8, 3): F("2.67"), F(1): F(1), F(2): F(2)}

DAY_TYPES = {
    "weekday": "平日",
    "rest_day": "休息日",
    "holiday": "國定假日",
    "regular_leave": "例假日",
}
LAW = {
    "weekday": "勞動基準法第 24 條第 1 項（平日延長工時：2 小時以內加給 1/3 以上，再延長 2 小時以內加給 2/3 以上）、第 32 條（每日合計不得超過 12 小時）",
    "rest_day": "勞動基準法第 24 條第 2 項（休息日出勤：2 小時以內另再加給 1又1/3 以上，第 3 小時起 1又2/3 以上，第 9 小時起 2又2/3 以上）、第 32 條",
    "holiday": "勞動基準法第 39 條（國定假日出勤工資加倍）、第 37 條、第 24 條第 1 項（超過 8 小時部分）",
    "regular_leave": "勞動基準法第 36 條、第 40 條（例假原則上不得出勤；因天災等出勤者工資加倍並補假）",
}
DISCLAIMER = "原則上僅供參考，不構成法律意見；實際金額以勞動部函釋、勞資約定與主管機關認定為準。"


def _labor_calendar() -> dict:
    with resources.files("tw_mcp.data").joinpath("labor_calendar.json").open(encoding="utf-8") as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if not k.startswith("_")}


def holiday_name(day: str):
    """勞基法國定假日：是的話回傳名稱，不是回傳 None；該年度沒有資料回傳 False。"""
    cal = _labor_calendar().get(day[:4])
    if not cal:
        return False
    return cal["holidays"].get(day)


def minimum_wage(year: int) -> dict:
    cal = _labor_calendar().get(str(year))
    return dict(cal["minimum_wage"], year=year) if cal else {}


def tiers_detail(minutes: int, tiers):
    """minutes 依 [(累計分鐘上限, 倍率), ...] 分段，回傳 [(分鐘, 倍率), ...]"""
    out, prev = [], 0
    for cap, rate in tiers:
        seg = max(0, min(minutes, cap) - prev)
        if seg:
            out.append((seg, rate))
        prev = cap
        if minutes <= cap:
            break
    return out


def round_half_up(x: F) -> int:
    return int((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _money2(x: F) -> float:
    return float((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _rate_txt(r: F) -> str:
    return str(r.numerator) if r.denominator == 1 else f"{r.numerator}/{r.denominator}"


def _fmt_h(minutes) -> str:
    h = F(minutes, 60)
    return str(h.numerator) if h.denominator == 1 else ("%.2f" % float(h)).rstrip("0").rstrip(".")


def _to_fraction(v, name):
    try:
        if isinstance(v, bool):
            raise ValueError
        return F(str(v))
    except (TypeError, ValueError, ZeroDivisionError):
        raise ValueError(f"{name} 要是數字")


def overtime_pay(wage, hours, day_type: str = "weekday", wage_type: str = "monthly", day: str = "") -> dict:
    """wage：月薪（monthly）或時薪（hourly）；hours：平日＝超過 8 小時的延長工時，其他日別＝當天出勤總時數。"""
    if wage_type not in ("monthly", "hourly"):
        raise ValueError("wage_type 只能是 monthly（月薪）或 hourly（時薪）")
    w = _to_fraction(wage, "wage")
    h = _to_fraction(hours, "hours")
    if w <= 0:
        raise ValueError("薪資要大於 0")
    if h <= 0 or h > 24:
        raise ValueError("時數要介於 0～24 小時之間")
    warnings, notes = [], []
    if day:
        try:
            date.fromisoformat(day)
        except ValueError:
            raise ValueError("day 日期格式要是 YYYY-MM-DD")
        hn = holiday_name(day)
        if hn is False:
            notes.append(f"{day[:4]} 年沒有內建國定假日資料，依你指定的日別（{DAY_TYPES.get(day_type, day_type)}）計算")
        elif hn and day_type in ("weekday", "rest_day"):
            warnings.append(f"{day} 是國定假日（{hn}），出勤應依第 39 條加倍；已改用國定假日計算")
            day_type = "holiday"
    if day_type not in DAY_TYPES:
        raise ValueError("day_type 只能是 " + "、".join(f"{k}（{v}）" for k, v in DAY_TYPES.items()))

    per_hour = w / HOURLY_DIVISOR if wage_type == "monthly" else w
    m = round_half_up(h * 60)
    parts = []          # [(說明, 分鐘, 法定倍率)]
    if day_type == "weekday":
        parts = [("延長工時", seg, r) for seg, r in tiers_detail(m, OT_TIERS)]
        total_day = DAILY_REGULAR_MIN + m
    elif day_type == "rest_day":
        parts = [("休息日出勤", seg, r) for seg, r in tiers_detail(m, REST_TIERS)]
        total_day = m
    else:
        base = min(m, DAILY_REGULAR_MIN)
        label = "國定假日出勤" if day_type == "holiday" else "例假日出勤"
        if wage_type == "hourly":
            parts.append((label + "（時薪制：工資兩倍）", base, F(2)))
        else:
            parts.append((label + "（月薪已含當日工資，另加給一倍）", base, F(1)))
        parts += [("超過 8 小時的延長工時", seg, r) for seg, r in tiers_detail(m - base, OT_TIERS)]
        total_day = m
        if day_type == "regular_leave":
            warnings.append("例假日原則上不得出勤（第 36、40 條），除天災、事變或突發事件外；出勤應加倍給薪並於事後補假休息")
    if total_day > DAILY_MAX_MIN:
        warnings.append(f"當日工時合計 {_fmt_h(total_day)} 小時，超過第 32 條每日 12 小時上限")

    def total(rate_of):
        return sum((per_hour * F(seg, 60) * rate_of(r) for _, seg, r in parts), F(0))

    legal = total(lambda r: r)
    practice = total(lambda r: PRACTICE_RATE[r])
    amount, practice_amount = round_half_up(legal), round_half_up(practice)
    breakdown = [{"item": lbl, "hours": float(F(seg, 60)), "rate": _rate_txt(r), "rate_decimal": round(float(r), 4),
                  "amount": _money2(per_hour * F(seg, 60) * r)} for lbl, seg, r in parts]
    ph = _money2(per_hour)
    rate_line = (f"每小時工資額＝月薪 {float(w):,.0f} ÷ {HOURLY_DIVISOR} ＝ {ph:,.2f} 元" if wage_type == "monthly"
                 else f"每小時工資額＝時薪 {ph:,.2f} 元")
    formula = rate_line + "；" + " ＋ ".join(f"{ph:,.2f}×{_fmt_h(seg)}h×{_rate_txt(r)}" for _, seg, r in parts) + f" ＝ {amount:,} 元"
    practice_formula = " ＋ ".join(f"{ph:,.2f}×{_fmt_h(seg)}h×{float(PRACTICE_RATE[r]):g}" for _, seg, r in parts) + f" ≈ {practice_amount:,} 元"

    y = int(day[:4]) if day else date.today().year
    mw = minimum_wage(y)
    if mw:
        if wage_type == "monthly" and w < mw["monthly"]:
            warnings.append(f"月薪 {float(w):,.0f} 低於 {y} 年基本工資 {mw['monthly']:,}（部分工時請改用時薪制）")
        if wage_type == "hourly" and w < mw["hourly"]:
            warnings.append(f"時薪 {float(w):,.0f} 低於 {y} 年基本工資時薪 {mw['hourly']}")
    else:
        notes.append(f"{y} 年沒有內建基本工資資料，未檢查是否低於基本工資")
    return {
        "amount": amount,
        "amount_basis": "法定最低（依條文分數 4/3、5/3、8/3 計算，最後四捨五入到元）",
        "legal_minimum": amount,
        "common_practice": {
            "amount": practice_amount,
            "rates": "1.34／1.67／2.67（業界常用的進位倍率，高於法定最低）",
            "formula": practice_formula,
        },
        "currency": "TWD",
        "day_type": day_type,
        "day_type_zh": DAY_TYPES[day_type],
        "wage_type": wage_type,
        "hourly_rate": ph,
        "hours": float(h),
        "breakdown": breakdown,
        "formula": formula,
        "law": LAW[day_type],
        "warnings": warnings,
        "notes": notes,
        "disclaimer": DISCLAIMER,
    }
