"""測試案例移植自 tw-lvr-map 的 tests/lvr.test.js、lvr.more.test.js、test_convert.py。地址全部虛構。"""
import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from tw_mcp import lvr as L

HEAD_ZH = ["鄉鎮市區", "交易標的", "土地位置建物門牌", "土地移轉總面積平方公尺", "交易年月日", "移轉層次", "總樓層數", "建物型態",
           "建築完成年月", "建物移轉總面積平方公尺", "建物現況格局-房", "建物現況格局-廳", "建物現況格局-衛", "總價元",
           "單價元平方公尺", "車位類別", "車位移轉總面積(平方公尺)", "車位總價元", "備註", "編號"]

T = [
    dict(district="甲區", buildingType="住宅大樓", subject="房地(土地+建物)", date="2025-03-01", totalPrice=1200, unitPrice=40,
         area=30, age=5, address="示範路1號", note="", special=False),
    dict(district="乙區", buildingType="公寓", subject="房地(土地+建物)", date="2025-06-01", totalPrice=800, unitPrice=25,
         area=32, age=35, address="測試街2號", note="親友間交易", special=True),
    dict(district="甲區", buildingType="透天厝", subject="房地(土地+建物)", date="2024-12-01", totalPrice=2000, unitPrice=None,
         area=60, age=20, address="示範路9號", note="", special=False),
    dict(district="乙區", buildingType="", subject="土地", date="2025-01-01", totalPrice=500, unitPrice=None, area=None,
         age=None, address="某段1地號", note="", special=False),
]


def row(**kw):
    base = dict.fromkeys(HEAD_ZH, "")
    base.update({"鄉鎮市區": "示範區", "交易標的": "房地(土地+建物)+車位", "土地位置建物門牌": "示範區示範路１００號５樓",
                 "交易年月日": "1130512", "移轉層次": "五層", "總樓層數": "十二層", "建物型態": "住宅大樓(11層含以上有電梯)",
                 "建築完成年月": "1000301", "建物移轉總面積平方公尺": "132.23", "建物現況格局-房": "3",
                 "建物現況格局-廳": "2", "建物現況格局-衛": "2", "總價元": "15000000", "單價元平方公尺": "120000",
                 "車位類別": "坡道平面", "車位移轉總面積(平方公尺)": "33.06", "車位總價元": "1500000", "編號": "X1"})
    base.update(kw)
    return [base[h] for h in HEAD_ZH]


def csv_bytes(rows, enc="utf-8-sig", english=True):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEAD_ZH)
    if english:
        w.writerow(["The villages and towns urban district"] + ["x"] * (len(HEAD_ZH) - 1))
    w.writerows(rows)
    return buf.getvalue().encode(enc)


class Convert(unittest.TestCase):
    def test_units_and_fields(self):
        rows = list(L.iter_rows(csv_bytes([row()]).decode("utf-8-sig"), "t"))
        t = L.convert_row(rows[0], 0)
        self.assertEqual(t["date"], "2024-05-12")
        self.assertEqual(t["totalPrice"], 1500)
        self.assertEqual(t["unitPrice"], 39.67)
        self.assertEqual(t["area"], 40.0)
        self.assertEqual((t["floor"], t["totalFloors"]), (5, 12))
        self.assertEqual(t["age"], 13.2)
        self.assertEqual(t["layout"], "3房2廳2衛")
        self.assertEqual(t["parkingPrice"], 150)
        self.assertFalse(t["special"])

    def test_helpers(self):
        self.assertEqual([L.zh_floor(x) for x in ("十二層", "地下一層", "全", "三層，四層", "二十三層")], [12, -1, None, 3, 23])
        self.assertIsNone(L.roc_date("123"))
        self.assertEqual(L.roc_date("113/05/12"), "2024-05-12")
        self.assertEqual(L.roc_date("20240512"), "2024-05-12")
        self.assertIsNone(L.age_at("", "2024-01-01"))

    def test_special_and_missing_columns(self):
        rows = list(L.iter_rows(csv_bytes([row(備註="親友、員工或其他特殊關係間之交易")]).decode("utf-8-sig"), "t"))
        self.assertTrue(L.convert_row(rows[0], 0)["special"])
        with self.assertRaises(ValueError):
            list(L.iter_rows("甲,乙\n1,2\n", "bad.csv"))


class FilterStats(unittest.TestCase):
    def test_short_type(self):
        self.assertEqual([L.short_type(t["buildingType"]) for t in T], ["大樓", "公寓", "透天", "土地/車位"])
        self.assertEqual(L.short_type("店面(店鋪)"), "店面")

    def test_filter(self):
        f = L.filter_rows
        self.assertEqual(len(f(T, {})), 4)
        self.assertEqual(len(f(T, {"districts": ["甲區"]})), 2)
        self.assertEqual(len(f(T, {"types": ["公寓", "透天"]})), 2)
        self.assertEqual(len(f(T, {"date_from": "2025-01-01", "date_to": "2025-05-31"})), 2)
        self.assertEqual(len(f(T, {"price_min": 900, "price_max": 1500})), 1)
        self.assertEqual(len(f(T, {"unit_min": 30})), 1)
        self.assertEqual(len(f(T, {"keyword": "示範路"})), 2)
        self.assertEqual(len(f(T, {"hide_special": True})), 3)
        self.assertEqual(len(f(T, {"buildings_only": True})), 3)

    def test_stats(self):
        self.assertEqual(L.median([3, 1, 2]), 2)
        self.assertEqual(L.median([4, 1, 3, 2]), 2.5)
        self.assertIsNone(L.median([None, None]))
        s = L.stats(T)
        self.assertEqual([s["count"], s["unitMedian"], s["unitAvg"], s["totalMedian"]], [4, 32.5, 32.5, 1000])
        self.assertEqual(list(s["byDistrict"]), ["甲區", "乙區"])
        self.assertEqual(s["byDistrict"]["甲區"]["count"], 2)

    def test_buildings_only_median(self):
        rows = [dict(district="A", subject="房地(土地+建物)", unitPrice=50, totalPrice=1500),
                dict(district="A", subject="房地(土地+建物)", unitPrice=54, totalPrice=1600),
                dict(district="A", subject="土地", unitPrice=8, totalPrice=800),
                dict(district="A", subject="土地", unitPrice=9, totalPrice=700)]
        self.assertEqual(L.stats(rows)["unitMedian"], 29.5)
        self.assertEqual(L.stats([r for r in rows if "建物" in r["subject"]])["unitMedian"], 52)

    def test_sort_nulls_last(self):
        self.assertEqual([t["unitPrice"] for t in L.sort_rows(T, "unitPrice", "desc")], [40, 25, None, None])
        self.assertEqual([t["unitPrice"] for t in L.sort_rows(T, "unitPrice", "asc")], [25, 40, None, None])
        self.assertEqual(L.sort_rows(T, "date", "desc")[0]["date"], "2025-06-01")


class Search(unittest.TestCase):
    def test_demo_data_is_labeled_fake(self):
        r = L.search()
        self.assertTrue(r["demo_data"])
        self.assertIn("虛構", r["disclaimer"])
        self.assertGreaterEqual(r["total_rows"], 100)
        self.assertTrue(all(t["address"].startswith("示範") for t in r["transactions"]))
        self.assertLessEqual(len(r["transactions"]), 20)

    def test_filters_and_roc_dates(self):
        r = L.search(districts=["示範東區"], date_from="1130101", sort_by="unitPrice", limit=5)
        self.assertTrue(all(t["district"] == "示範東區" for t in r["transactions"]))
        prices = [t["unitPrice"] for t in r["transactions"] if t["unitPrice"] is not None]
        self.assertEqual(prices, sorted(prices, reverse=True))
        with self.assertRaises(ValueError):
            L.search(date_from="2024/1/1")
        with self.assertRaises(ValueError):
            L.search(sort_by="hack")

    def test_real_csv_and_zip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b_lvr_land_a.csv"
            p.write_bytes(csv_bytes([row(), row(編號="X2", 備註="親友間交易"), row(編號="X1")]))   # X1 重複只算一次
            r = L.search(str(p))
            self.assertFalse(r["demo_data"])
            self.assertEqual((r["total_rows"], r["matched"], r["excluded_special"]), (2, 1, 1))
            self.assertEqual(r["transactions"][0]["county"], "臺中市")
            self.assertIn("政府資料開放授權條款", r["source"])
            self.assertEqual(L.search(str(p), include_special=True)["matched"], 2)
            big5 = Path(d) / "a_lvr_land_a.csv"
            big5.write_bytes(csv_bytes([row(編號="B1")], enc="cp950"))
            self.assertEqual(L.search(str(big5))["transactions"][0]["district"], "示範區")
            z = Path(d) / "lvr_landcsv.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.write(p, "b_lvr_land_a.csv")
                zf.write(big5, "a_lvr_land_a.csv")
                zf.writestr("b_lvr_land_b.csv", "預售屋不讀")
            self.assertEqual(L.search(str(z))["total_rows"], 3)
            self.assertEqual(L.search(str(z), county="臺中市")["total_rows"], 2)
            with self.assertRaises(ValueError):
                L.search(str(z), county="火星市")

    def test_size_cap_zip_bomb(self):
        with tempfile.TemporaryDirectory() as d:
            z = Path(d) / "bomb.zip"
            with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("a_lvr_land_a.csv", b"x" * 300_000)        # 壓縮後很小、解壓後超過上限
                zf.writestr("dup/a_lvr_land_a.csv", b"y" * 300_000)    # 同縣市第二個檔不讀
            old = L.MAX_BYTES
            try:
                L.MAX_BYTES = 200_000
                with self.assertRaisesRegex(ValueError, "合計超過"):
                    L.load(str(z))
                big = Path(d) / "a_lvr_land_a.csv"
                big.write_bytes(b"x" * 300_000)
                with self.assertRaisesRegex(ValueError, "合計超過"):
                    L.load(str(big))
            finally:
                L.MAX_BYTES = old

    def test_bad_paths(self):
        with self.assertRaises(ValueError):
            L.search("C:/no/such/file.csv")
        with self.assertRaises(ValueError):
            L.search(__file__)              # 不是 .csv/.zip 不讀


if __name__ == "__main__":
    unittest.main()
