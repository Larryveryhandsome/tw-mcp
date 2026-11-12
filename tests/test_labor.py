import unittest
from fractions import Fraction as F

from tw_mcp.labor import OT_TIERS, REST_TIERS, overtime_pay, tiers_detail


class LaborOvertime(unittest.TestCase):
    def test_demo_value_400_legal_minimum(self):
        r = overtime_pay(36000, 2)                       # 月薪 36,000、平日加班 2 小時：150 × 2 × 4/3 ＝ 400
        self.assertEqual(r["amount"], 400)
        self.assertEqual(r["legal_minimum"], 400)
        self.assertEqual(r["common_practice"]["amount"], 402)   # 業界 1.34 進位
        self.assertEqual(r["hourly_rate"], 150.0)
        self.assertEqual(r["breakdown"][0]["rate"], "4/3")
        self.assertIn("第 24 條第 1 項", r["law"])
        self.assertIn("150.00×2h×4/3", r["formula"])
        self.assertIn("僅供參考", r["disclaimer"])

    def test_exact_fraction_no_float_drift(self):
        # 時薪 196 × 1.5 小時 × 4/3 ＝ 392（float 1.3333 會算成 391.99）
        self.assertEqual(overtime_pay(196, 1.5, wage_type="hourly")["amount"], 392)
        # 0.5 進位：月薪 36,001 → 每小時 150.004…，2h×4/3 ＝ 400.011 → 400
        self.assertEqual(overtime_pay(36001, 2)["amount"], 400)

    def test_weekday_tiers_after_2h(self):
        r = overtime_pay(36000, 3)
        self.assertEqual(r["amount"], 650)                   # 400 ＋ 150×5/3
        self.assertEqual(r["common_practice"]["amount"], 653)  # 402 ＋ 250.5，0.5 進位
        self.assertEqual([b["rate"] for b in r["breakdown"]], ["4/3", "5/3"])

    def test_over_12_hours_warns(self):
        self.assertTrue(any("12 小時" in w for w in overtime_pay(36000, 5)["warnings"]))
        self.assertFalse(overtime_pay(36000, 4)["warnings"])

    def test_rest_day(self):
        r = overtime_pay(200, 8, day_type="rest_day", wage_type="hourly")
        self.assertEqual(r["amount"], 2533)                  # 勞動部常見例：200×4/3×2 ＋ 200×5/3×6 ≈ 2533
        r10 = overtime_pay(36000, 10, day_type="rest_day")
        self.assertEqual([b["rate"] for b in r10["breakdown"]], ["4/3", "5/3", "8/3"])
        self.assertEqual(r10["amount"], 2700)                # 150 ×（8/3 ＋ 10 ＋ 16/3）

    def test_holiday_monthly_vs_hourly(self):
        self.assertEqual(overtime_pay(36000, 8, day_type="holiday")["amount"], 1200)                    # 月薪：另加給一日
        self.assertEqual(overtime_pay(200, 8, day_type="holiday", wage_type="hourly")["amount"], 3200)  # 時薪：兩倍
        self.assertEqual(overtime_pay(36000, 10, day_type="holiday")["amount"], 1600)   # 1200 ＋ 150×2×4/3

    def test_regular_leave_warns(self):
        r = overtime_pay(36000, 4, day_type="regular_leave")
        self.assertTrue(any("例假" in w for w in r["warnings"]))
        self.assertIn("第 40 條", r["law"])

    def test_date_auto_detects_national_holiday(self):
        r = overtime_pay(36000, 8, day_type="rest_day", day="2026-10-10")
        self.assertEqual(r["day_type"], "holiday")
        self.assertTrue(any("國慶日" in w for w in r["warnings"]))
        self.assertEqual(overtime_pay(36000, 2, day="2026-10-12")["day_type"], "weekday")

    def test_minimum_wage_check(self):
        self.assertTrue(any("基本工資" in w for w in overtime_pay(25000, 1, day="2026-03-02")["warnings"]))
        self.assertTrue(any("基本工資時薪" in w for w in overtime_pay(150, 1, wage_type="hourly", day="2026-03-02")["warnings"]))
        self.assertTrue(any("沒有內建基本工資" in n for n in overtime_pay(36000, 1, day="2031-03-03")["notes"]))

    def test_bad_input(self):
        for kw in (dict(wage=0, hours=1), dict(wage=36000, hours=0), dict(wage=36000, hours=25),
                   dict(wage=36000, hours=1, day_type="x"), dict(wage=36000, hours=1, wage_type="daily"),
                   dict(wage=36000, hours=1, day="2026/01/01"), dict(wage="abc", hours=1)):
            with self.assertRaises(ValueError, msg=str(kw)):
                overtime_pay(**kw)

    def test_tiers(self):
        self.assertEqual(tiers_detail(120, OT_TIERS), [(120, F(4, 3))])
        self.assertEqual(tiers_detail(300, OT_TIERS), [(120, F(4, 3)), (180, F(5, 3))])
        self.assertEqual(tiers_detail(600, REST_TIERS), [(120, F(4, 3)), (360, F(5, 3)), (120, F(8, 3))])


if __name__ == "__main__":
    unittest.main()
