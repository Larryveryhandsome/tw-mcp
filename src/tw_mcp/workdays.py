"""台灣工作日：依行政院人事行政總處「政府行政機關辦公日曆表」判斷上班日、放假日、補行上班日。

tw-duty-roster 的排班引擎沒有國定假日資料（日期工具邏輯：YYYY-MM-DD 字串、範圍上限、起訖檢查 移植自它的 scheduler.js），
這裡改接政府開放資料（data.gov.tw dataset 14718），由 tools/build_calendar.py 轉成 data/calendar_<年>.json。
沒有資料的年份會明確報錯，不會自己猜。
"""
import json
from datetime import date, timedelta
from functools import lru_cache
from importlib import resources

WEEKDAY_ZH = "一二三四五六日"
MAX_RANGE_DAYS = 3660          # 一次最多算 10 年
MAX_ADD = 2600                 # 最多往前／往後推 2600 個工作日（約 10 年）
NOTE = ("依政府行政機關辦公日曆表（人事行政總處公告）判斷；民間企業依勞基法放國定假日，"
        "補假、調移日期可能與公務機關不同，原則上請以公司公告為準。")


def _available_years():
    years = []
    for p in resources.files("tw_mcp.data").iterdir():
        n = p.name
        if n.startswith("calendar_") and n.endswith(".json"):
            years.append(int(n[9:13]))
    return sorted(years)


@lru_cache(maxsize=None)
def _year(y: int) -> dict:
    f = resources.files("tw_mcp.data").joinpath(f"calendar_{y}.json")
    if not f.is_file():
        yrs = _available_years()
        raise ValueError(f"沒有 {y} 年的辦公日曆資料（目前內建 {yrs[0]}～{yrs[-1]} 年）。"
                         f"新年度請下載人事行政總處辦公日曆表 CSV，跑 tools/build_calendar.py 加進去。")
    with f.open(encoding="utf-8") as fh:
        return json.load(fh)


def parse(s) -> date:
    try:
        return date.fromisoformat(str(s).strip())
    except ValueError:
        raise ValueError(f"日期格式要是 YYYY-MM-DD：{s}")


def day_info(d: date) -> dict:
    cal = _year(d.year)
    iso = d.isoformat()
    if iso in cal["off"]:
        note = cal["off"][iso]
        kind = "holiday" if note else "weekend"
        return {"date": iso, "weekday": "週" + WEEKDAY_ZH[d.weekday()], "workday": False, "kind": kind,
                "name": note or "週末"}
    if iso in cal["makeup_workdays"]:
        return {"date": iso, "weekday": "週" + WEEKDAY_ZH[d.weekday()], "workday": True, "kind": "makeup_workday",
                "name": cal["makeup_workdays"][iso]}
    return {"date": iso, "weekday": "週" + WEEKDAY_ZH[d.weekday()], "workday": True, "kind": "workday", "name": ""}


def is_workday(d: date) -> bool:
    return day_info(d)["workday"]


def count_between(start: date, end: date) -> dict:
    """含頭含尾。"""
    if end < start:
        raise ValueError("結束日不能早於起始日")
    span = (end - start).days + 1
    if span > MAX_RANGE_DAYS:
        raise ValueError(f"一次最多算 {MAX_RANGE_DAYS} 天")
    work, off, holidays, makeup = 0, 0, [], []
    d = start
    while d <= end:
        info = day_info(d)
        if info["workday"]:
            work += 1
            if info["kind"] == "makeup_workday":
                makeup.append(info)
        else:
            off += 1
            if info["kind"] == "holiday":
                holidays.append({"date": info["date"], "weekday": info["weekday"], "name": info["name"]})
        d += timedelta(days=1)
    return {"start": start.isoformat(), "end": end.isoformat(), "calendar_days": span, "workdays": work,
            "off_days": off, "holidays": holidays, "makeup_workdays": makeup}


def add_workdays(start: date, n: int) -> dict:
    """從 start 起算第 n 個工作日（不含 start 當天；n 為負數往回推）。n=0 時：start 是工作日就回傳 start，否則順延到下一個工作日。"""
    if abs(n) > MAX_ADD:
        raise ValueError(f"最多推算 {MAX_ADD} 個工作日")
    d = start
    if n == 0:
        while not is_workday(d):
            d += timedelta(days=1)
        return {"start": start.isoformat(), "add": 0, "result": d.isoformat(), "result_info": day_info(d), "skipped_holidays": []}
    step = 1 if n > 0 else -1
    left, skipped = abs(n), []
    while left:
        d += timedelta(days=step)
        info = day_info(d)
        if info["workday"]:
            left -= 1
        elif info["kind"] == "holiday":
            skipped.append({"date": info["date"], "name": info["name"]})
    return {"start": start.isoformat(), "add": n, "result": d.isoformat(), "result_info": day_info(d), "skipped_holidays": skipped}


def coverage() -> str:
    yrs = _available_years()
    return f"{yrs[0]}～{yrs[-1]}"
