"""把行政院人事行政總處「中華民國政府行政機關辦公日曆表」CSV 轉成 tw-mcp 用的 JSON。

資料來源：政府資料開放平臺 dataset 14718（https://data.gov.tw/dataset/14718）
授權：政府資料開放授權條款－第 1 版（可自由利用，需標示出處）。

CSV 欄位：西元日期(YYYYMMDD), 星期, 是否放假(2=放假, 0=上班), 備註
用法：
  python tools/build_calendar.py 115年辦公日曆表.csv [更多.csv ...]
  → 寫到 src/tw_mcp/data/calendar_<西元年>.json（一年一個檔）

每年 6 月左右人事行政總處會公告下一年度的辦公日曆表；下載新年度 CSV 跑一次這支程式即可。
"""
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "tw_mcp" / "data"
SOURCE = "行政院人事行政總處「中華民國政府行政機關辦公日曆表」（政府資料開放平臺 dataset 14718，政府資料開放授權條款－第 1 版）"


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp950"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path.name} 看不懂的編碼（不是 UTF-8 也不是 Big5）")


def convert(path: Path) -> dict:
    rows = list(csv.reader(io.StringIO(read_text(path))))
    if not rows or len(rows[0]) < 3:
        raise ValueError(f"{path.name} 不是辦公日曆表格式")
    off, makeup, years = {}, {}, set()
    for r in rows[1:]:
        if len(r) < 3 or not r[0].strip().isdigit():
            continue
        ymd = r[0].strip()
        d = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))
        years.add(d.year)
        note = (r[3] if len(r) > 3 else "").strip()
        flag = r[2].strip()
        if flag == "2":
            off[d.isoformat()] = note
        elif flag == "0" and d.weekday() >= 5:
            makeup[d.isoformat()] = note or "補行上班"
    if len(years) != 1:
        raise ValueError(f"{path.name} 跨了不只一個年份：{sorted(years)}")
    year = years.pop()
    n_days = (date(year, 12, 31) - date(year, 1, 1)).days + 1
    if len(rows) - 1 < n_days:
        print(f"  警告：{path.name} 只有 {len(rows) - 1} 列，少於 {n_days} 天", file=sys.stderr)
    return {"year": year, "source": SOURCE, "file": path.name, "off": off, "makeup_workdays": makeup}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    for p in map(Path, argv):
        data = convert(p)
        out = OUT / f"calendar_{data['year']}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{p.name} → {out.name}：放假 {len(data['off'])} 天、補行上班 {len(data['makeup_workdays'])} 天")
    return 0


if __name__ == "__main__":
    sys.exit(main())
