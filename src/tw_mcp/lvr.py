"""實價登錄查詢：讀內政部「實價登錄開放資料」CSV（或整包 ZIP），篩選、排除特殊交易、算行情統計。

- CSV 讀取與欄位轉換（民國日期、坪數、單價、樓層、屋齡、特殊交易判斷）移植自 tw-lvr-map 的 tools/convert_open_data.py
- 篩選、統計、排序移植自 tw-lvr-map 的 js/lvr.js（filter、stats、sortBy、shortType、median）

資料來源：內政部不動產交易實價查詢服務網 → 開放資料下載 https://plvr.land.moi.gov.tw/DownloadOpenData
授權：政府資料開放授權條款－第 1 版（可自由利用，需標示出處）。
沒有指定檔案時用內建的「虛構」示範資料（tools 產生，地址與價格都不是真的）。
"""
import codecs
import csv
import io
import re
import zipfile
from datetime import date
from importlib import resources
from pathlib import Path

SQM_PER_PING = 3.305785
ATTRIBUTION = "資料來源：內政部不動產交易實價查詢服務網（政府資料開放授權條款－第 1 版）"
DEMO_NOTE = "示範資料：隨機產生的虛構資料，地址與價格都不是真的，不代表任何真實行情。"
DISCLAIMER = "實價登錄為政府公開資料的整理，原則上僅供行情參考，不構成估價或投資建議。"
MAX_ROWS = 2_000_000
MAX_BYTES = 500 * 1024 * 1024     # 一次讀入（解壓後）合計上限
COUNTY = {  # 開放資料檔名第一個字母 → 縣市
    "a": "臺北市", "b": "臺中市", "c": "基隆市", "d": "臺南市", "e": "高雄市", "f": "新北市", "g": "宜蘭縣",
    "h": "桃園市", "i": "嘉義市", "j": "新竹縣", "k": "苗栗縣", "m": "南投縣", "n": "彰化縣", "o": "新竹市",
    "p": "雲林縣", "q": "嘉義縣", "t": "屏東縣", "u": "花蓮縣", "v": "臺東縣", "w": "金門縣", "x": "澎湖縣", "z": "連江縣",
}
SPECIAL_RE = re.compile(r"親友|員工|特殊關係|瑕疵|凶宅|債權|急買|急賣|含裝潢|政府機關|法拍")

# ---------- 欄位轉換（移植自 convert_open_data.py） ----------


def roc_date(s):
    """'1130512' 或 '113/05/12' → '2024-05-12'；看不懂回 None。"""
    s = re.sub(r"\D", "", str(s or ""))
    if len(s) < 6:
        return None
    y, m, d = int(s[:-4]), int(s[-4:-2]), int(s[-2:])
    if y >= 1900:
        y -= 1911
    try:
        return date(y + 1911, m, d).isoformat()
    except ValueError:
        return None


def age_at(build, deal_iso):
    s = re.sub(r"\D", "", str(build or ""))
    if len(s) < 5 or not deal_iso:
        return None
    y, m = int(s[:-4]) + 1911, int(s[-4:-2]) or 1
    dy, dm = int(deal_iso[:4]), int(deal_iso[5:7])
    months = (dy - y) * 12 + (dm - m)
    return round(months / 12, 1) if 0 <= months < 12 * 150 else None


def num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


ZH = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def zh_floor(s):
    """'十二層' → 12、'地下一層' → -1、'全' → None。"""
    s = re.split(r"[，,、]", str(s or ""))[0]
    neg = s.startswith("地下")
    s = s.replace("地下", "").replace("層", "").strip()
    if s.isdigit():
        n = int(s)
    else:
        m = re.fullmatch(r"(?:([一二三四五六七八九])?(十))?([一二三四五六七八九])?", s)
        if not s or not m:
            return None
        n = ((ZH[m.group(1)] if m.group(1) else 1) * 10 if m.group(2) else 0) + ZH.get(m.group(3), 0)
    if not n:
        return None
    return -n if neg else n


def convert_row(r: dict, idx: int, county: str = "") -> dict:
    deal = roc_date(r.get("交易年月日"))
    total = num(r.get("總價元"))
    unit_m2 = num(r.get("單價元平方公尺"))
    area_m2 = num(r.get("建物移轉總面積平方公尺"))
    park_price = num(r.get("車位總價元")) or 0
    rooms = [r.get("建物現況格局-房"), r.get("建物現況格局-廳"), r.get("建物現況格局-衛")]
    note = (r.get("備註") or "").strip()
    return {
        "id": r.get("編號") or f"row-{idx}",
        "county": county,
        "district": (r.get("鄉鎮市區") or "").strip(),
        "address": (r.get("土地位置建物門牌") or "").strip(),
        "subject": (r.get("交易標的") or "").strip(),
        "date": deal,
        "buildingType": re.sub(r"\(.*\)", "", r.get("建物型態") or "").strip(),
        "totalPrice": round(total / 10000, 1) if total else None,            # 萬元
        "unitPrice": round(unit_m2 * SQM_PER_PING / 10000, 2) if unit_m2 else None,   # 萬/坪（已扣車位）
        "area": round(area_m2 / SQM_PER_PING, 2) if area_m2 else None,       # 建坪
        "floor": zh_floor(r.get("移轉層次")),
        "totalFloors": zh_floor(r.get("總樓層數")),
        "age": age_at(r.get("建築完成年月"), deal),
        "layout": "{}房{}廳{}衛".format(*[(x or "0").strip() for x in rooms]) if any(rooms) else "",
        "parking": (r.get("車位類別") or "").strip(),
        "parkingPrice": round(park_price / 10000, 1) if park_price else None,
        "note": note,
        "special": bool(SPECIAL_RE.search(note)),
    }


REQUIRED = ["鄉鎮市區", "交易年月日", "總價元", "土地位置建物門牌"]
ALIASES = {
    "單價元/平方公尺": "單價元平方公尺", "單價(元/平方公尺)": "單價元平方公尺", "單價元每平方公尺": "單價元平方公尺",
    "車位移轉總面積(平方公尺)": "車位移轉總面積平方公尺", "車位移轉總面積(m2)": "車位移轉總面積平方公尺",
    "建物移轉總面積(平方公尺)": "建物移轉總面積平方公尺", "土地移轉總面積(平方公尺)": "土地移轉總面積平方公尺",
    "建物現況格局－房": "建物現況格局-房", "建物現況格局－廳": "建物現況格局-廳", "建物現況格局－衛": "建物現況格局-衛",
    "總價(元)": "總價元", "交易年月日(民國)": "交易年月日", "鄉鎮市區名稱": "鄉鎮市區",
}


def norm_header(h) -> str:
    h = re.sub(r"\s+", "", str(h or "")).replace("（", "(").replace("）", ")").replace("／", "/")
    return ALIASES.get(h, h)


def _decode_stream(raw: bytes) -> str:
    try:
        codecs.getincrementaldecoder("utf-8-sig")().decode(raw[: 2 * 1024 * 1024], final=False)
        return raw.decode("utf-8-sig", errors="replace")
    except UnicodeDecodeError:
        return raw.decode("cp950", errors="replace")


def iter_rows(text: str, name: str):
    reader = csv.reader(io.StringIO(text))
    first = next(reader, None)
    if not first:
        return
    head = [norm_header(h) for h in first]
    miss = [c for c in REQUIRED if c not in head]
    if miss:
        raise ValueError(f"{name} 缺少必要欄位：{'、'.join(miss)}。請用「不動產買賣」的 CSV（檔名結尾 _lvr_land_a.csv；"
                         f"預售屋 _b、租賃 _c 欄位不同）。")
    second = True
    for r in reader:
        if second:
            second = False
            if r and re.match(r"^[A-Za-z ]", r[0] or ""):
                continue   # 第 2 列是英文欄名
        if any(c.strip() for c in r):
            yield dict(zip(head, r))


def _county_of(name: str) -> str:
    m = re.match(r"^([a-z])_lvr_land_a", Path(name).name, re.I)
    return COUNTY.get(m.group(1).lower(), "") if m else ""


def load(path: str = "", county: str = ""):
    """回傳 (交易 list, 來源說明, 是否示範資料)。path 可以是 .csv 或開放資料整包 .zip（只讀其中的 *_lvr_land_a.csv）。"""
    if not path:
        raw = resources.files("tw_mcp.data").joinpath("demo_lvr_land_a.csv").read_bytes()
        rows = [convert_row(r, i) for i, r in enumerate(iter_rows(_decode_stream(raw), "示範資料"))]
        return rows, DEMO_NOTE, True
    p = Path(path).expanduser()
    if p.suffix.lower() not in (".csv", ".zip"):
        raise ValueError("只接受實價登錄開放資料的 .csv 或 .zip 檔")
    if not p.is_file():
        raise ValueError(f"找不到檔案：{p}")
    want = {k for k, v in COUNTY.items() if county and (county in v or v in county or county.lower() == k)}
    if county and not want:
        raise ValueError(f"看不懂的縣市「{county}」，請用例如 臺北市、臺中市，或開放資料檔名字母 a、b")
    sources, total, letters = [], 0, set()
    too_big = f"資料解壓後合計超過 {MAX_BYTES // 1024 // 1024}MB，請改用單一縣市的 CSV 或指定 county"
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                n = Path(info.filename).name
                m = re.match(r"^([a-z])_lvr_land_a\.csv$", n, re.I)
                if not m or (want and m.group(1).lower() not in want) or m.group(1).lower() in letters:
                    continue          # 同一縣市只讀第一個檔
                letters.add(m.group(1).lower())
                if total + info.file_size > MAX_BYTES:
                    raise ValueError(too_big)
                with z.open(info) as f:            # 不信任 ZIP 標頭的大小：實際讀取時也限量
                    raw = f.read(MAX_BYTES - total + 1)
                total += len(raw)
                if total > MAX_BYTES:
                    raise ValueError(too_big)
                sources.append((n, raw))
        if not sources:
            raise ValueError("ZIP 裡找不到符合的「不動產買賣」CSV（*_lvr_land_a.csv）" + (f"（縣市：{county}）" if county else ""))
    else:
        if p.stat().st_size > MAX_BYTES:
            raise ValueError(too_big)
        sources.append((p.name, p.read_bytes()))
    rows, seen, idx = [], set(), 0
    for name, raw in sources:
        cty = _county_of(name)
        for r in iter_rows(_decode_stream(raw), name):
            t = convert_row(r, idx, cty)
            idx += 1
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            rows.append(t)
            if len(rows) > MAX_ROWS:
                raise ValueError(f"資料超過 {MAX_ROWS:,} 筆，請改用單一縣市的 CSV 或指定 county")
    return rows, ATTRIBUTION + "；檔案：" + "、".join(n for n, _ in sources), False

# ---------- 篩選與統計（移植自 js/lvr.js） ----------


def short_type(t) -> str:
    s = str(t or "")
    for key, name in (("住宅大樓", "大樓"), ("華廈", "華廈"), ("公寓", "公寓"), ("透天", "透天"), ("套房", "套房")):
        if key in s:
            return name
    if "店面" in s or "店舖" in s:
        return "店面"
    if "辦公" in s:
        return "辦公"
    if "工廠" in s or "廠辦" in s:
        return "廠房"
    return "其他" if s else "土地/車位"


def _in_range(v, lo, hi) -> bool:
    return (lo is None or (v is not None and v >= lo)) and (hi is None or (v is not None and v <= hi))


def filter_rows(rows, f: dict):
    kw = str(f.get("keyword") or "").strip()
    districts = f.get("districts") or []
    types = f.get("types") or []
    out = []
    for t in rows:
        if districts and t["district"] not in districts:
            continue
        if types and short_type(t["buildingType"]) not in types:
            continue
        if f.get("date_from") and not (t["date"] and t["date"] >= f["date_from"]):
            continue
        if f.get("date_to") and not (t["date"] and t["date"] <= f["date_to"]):
            continue
        if not (_in_range(t["totalPrice"], f.get("price_min"), f.get("price_max"))
                and _in_range(t["unitPrice"], f.get("unit_min"), f.get("unit_max"))
                and _in_range(t["area"], f.get("area_min"), f.get("area_max"))
                and _in_range(t["age"], f.get("age_min"), f.get("age_max"))):
            continue
        if f.get("hide_special") and t["special"]:
            continue
        if f.get("buildings_only") and "建物" not in t["subject"]:
            continue
        if kw and kw not in " ".join([t["address"], t["district"], t["note"], t["buildingType"]]):
            continue
        out.append(t)
    return out


def median(nums):
    a = sorted(n for n in nums if isinstance(n, (int, float)))
    if not a:
        return None
    m = len(a) // 2
    return a[m] if len(a) % 2 else (a[m - 1] + a[m]) / 2


def _round(n, d):
    return None if n is None else round(n, d)


def quantile(sorted_vals, p):
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def stats(rows) -> dict:
    units = [t["unitPrice"] for t in rows if t["unitPrice"] is not None]
    su = sorted(units)
    by = {}
    for t in rows:
        by.setdefault(t["district"], []).append(t["unitPrice"])
    by_district = {k: {"count": len(v), "unitMedian": _round(median(v), 2)} for k, v in by.items()}
    by_district = dict(sorted(by_district.items(), key=lambda kv: -(kv[1]["unitMedian"] or 0)))
    return {
        "count": len(rows),
        "unitMedian": _round(median(units), 2),
        "unitAvg": _round(sum(units) / len(units), 2) if units else None,
        "unitP25": quantile(su, 0.25),
        "unitP75": quantile(su, 0.75),
        "totalMedian": _round(median([t["totalPrice"] for t in rows]), 1),
        "byDistrict": by_district,
    }


def sort_rows(rows, key: str, direction: str = "desc"):
    present = [t for t in rows if t.get(key) is not None]
    missing = [t for t in rows if t.get(key) is None]
    present.sort(key=lambda t: t[key], reverse=(direction != "asc"))
    return present + missing       # 空值永遠排最後


SORT_KEYS = ("date", "unitPrice", "totalPrice", "area", "age")
OUT_FIELDS = ("date", "county", "district", "address", "buildingType", "totalPrice", "unitPrice", "area", "floor",
              "totalFloors", "age", "layout", "parking", "parkingPrice", "note", "special")


def search(path="", county="", districts=None, types=None, date_from="", date_to="", price_min=None, price_max=None,
           unit_min=None, unit_max=None, area_min=None, area_max=None, age_min=None, age_max=None, keyword="",
           include_special=False, buildings_only=True, sort_by="date", order="desc", limit=20) -> dict:
    for k, v in (("date_from", date_from), ("date_to", date_to)):
        if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            conv = roc_date(v) if re.fullmatch(r"\d{6,7}", v) else None
            if not conv:
                raise ValueError(f"{k} 請用 2024-01-01 或民國 1130101 的格式")
            if k == "date_from":
                date_from = conv
            else:
                date_to = conv
    if sort_by not in SORT_KEYS:
        raise ValueError("sort_by 只能是 " + "、".join(SORT_KEYS))
    limit = max(1, min(int(limit or 20), 200))
    rows, source, demo = load(path, county)
    f = dict(districts=districts or [], types=types or [], date_from=date_from, date_to=date_to,
             price_min=price_min, price_max=price_max, unit_min=unit_min, unit_max=unit_max,
             area_min=area_min, area_max=area_max, age_min=age_min, age_max=age_max, keyword=keyword,
             hide_special=not include_special, buildings_only=buildings_only)
    hit = filter_rows(rows, f)
    excluded_special = 0 if include_special else len(filter_rows(rows, dict(f, hide_special=False))) - len(hit)
    picked = sort_rows(hit, sort_by, order)[:limit]
    return {
        "demo_data": demo,
        "source": source,
        "total_rows": len(rows),
        "matched": len(hit),
        "excluded_special": excluded_special,
        "units": {"totalPrice": "萬元", "unitPrice": "萬元/坪（已扣車位）", "area": "坪（建物移轉面積）", "age": "年"},
        "stats": stats(hit),
        "transactions": [{k: t.get(k) for k in OUT_FIELDS} for t in picked],
        "districts_available": sorted({t["district"] for t in rows if t["district"]}),
        "disclaimer": DISCLAIMER + ("　" + DEMO_NOTE if demo else ""),
    }
