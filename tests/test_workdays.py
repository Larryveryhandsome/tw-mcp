import unittest
from datetime import date

from tw_mcp import workdays as W


class Workdays(unittest.TestCase):
    def test_single_days(self):
        self.assertFalse(W.day_info(date(2026, 10, 10))["workday"])
        self.assertEqual(W.day_info(date(2026, 10, 10))["name"], "國慶日")
        self.assertEqual(W.day_info(date(2026, 10, 9))["name"], "補假")
        self.assertEqual(W.day_info(date(2026, 10, 3))["kind"], "weekend")
        self.assertTrue(W.day_info(date(2026, 10, 12))["workday"])
        self.assertEqual(W.day_info(date(2026, 10, 12))["weekday"], "週一")

    def test_makeup_workday_2025(self):
        info = W.day_info(date(2025, 2, 8))     # 114 年 2/8（週六）補行上班
        self.assertTrue(info["workday"])
        self.assertEqual(info["kind"], "makeup_workday")

    def test_count_lunar_new_year_2026(self):
        r = W.count_between(date(2026, 2, 1), date(2026, 2, 28))
        # 28 天＝週末 8 天＋平日放假 6 天（除夕、春節×3、補假 2/20、2/27）＋工作日 14 天
        self.assertEqual(r["calendar_days"], 28)
        self.assertEqual(r["workdays"], 14)
        names = [h["name"] for h in r["holidays"]]
        self.assertIn("農曆除夕", names)
        self.assertIn("和平紀念日", names)

    def test_count_whole_year(self):
        r = W.count_between(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(r["calendar_days"], 365)
        self.assertEqual(r["off_days"], 120)
        self.assertEqual(r["workdays"], 245)

    def test_add_workdays(self):
        r = W.add_workdays(date(2026, 2, 13), 1)          # 週五 → 跳過週末、春節、補假 → 2/23（週一）
        self.assertEqual(r["result"], "2026-02-23")
        self.assertTrue(any(h["name"] == "春節" for h in r["skipped_holidays"]))
        self.assertEqual(W.add_workdays(date(2026, 2, 23), -1)["result"], "2026-02-13")
        self.assertEqual(W.add_workdays(date(2026, 10, 10), 0)["result"], "2026-10-12")
        self.assertEqual(W.add_workdays(date(2026, 10, 12), 0)["result"], "2026-10-12")

    def test_cross_year(self):
        self.assertEqual(W.add_workdays(date(2026, 12, 31), 1)["result"], "2027-01-04")   # 2027/1/1 開國紀念日（週五）＋週末

    def test_errors(self):
        with self.assertRaises(ValueError):
            W.day_info(date(2019, 1, 2))                  # 沒有資料的年份要明講，不能猜
        with self.assertRaises(ValueError):
            W.count_between(date(2026, 3, 1), date(2026, 2, 1))
        with self.assertRaises(ValueError):
            W.parse("2026/01/01")
        with self.assertRaises(ValueError):
            W.add_workdays(date(2026, 1, 5), 99999)

    def test_coverage(self):
        self.assertEqual(W.coverage(), "2025～2027")


if __name__ == "__main__":
    unittest.main()
