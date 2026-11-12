"""測試案例移植自 tw-local-needs/tests/needs.test.js（去識別化相關）。電話、證號都是公認的假資料。"""
import re
import unittest

from tw_mcp.pii import mask_contact, redact, redact_text


class PiiMask(unittest.TestCase):
    def test_basic(self):
        t, counts = redact("請找王先生 0900-000-678 或 02-2345-6789，信箱 a.b@example.com，LINE ID: wang123，"
                           "證號 A123456789，約 25 份 2026-10-04 共 1000 元")
        for leak in ["0900", "2345-6789", "a.b@example.com", "wang123", "A123456789"]:
            self.assertNotIn(leak, t)
        self.assertIn("25 份", t)
        self.assertIn("1000 元", t)
        self.assertEqual(counts, {"email": 1, "national_id": 1, "phone": 2, "social": 1})

    def test_variants(self):
        leaks = ["０９０００００６７８", "0900.000.678", "0900/000/678", "09 00 00 06 78", "+886900000678", "＋886 900 000 678",
                 "+886-900-000-678", "零九零零零零零六七八", "abc＠gmail.com", "abc @ gmail.com", "abc at gmail dot com",
                 "0900​000678", "0900‑000‑678"]
        for s in leaks:
            t = redact_text("請聯絡 " + s + " 謝謝")
            self.assertRegex(t, "已隱藏", f"沒蓋掉：{s} → {t}")
            self.assertFalse(re.search("678|gmail|六七八", t), f"漏字：{s} → {t}")
        for s in ["加賴 mysecret99", "Ｌｉｎｅ：abc_123", "IG: foo.bar", "@wang_999", "https://line.me/ti/p/abc123",
                  "身分證 Ａ１２３４５６７８９", "a1 23456789"]:
            self.assertRegex(redact_text(s), "已隱藏", s)

    def test_no_false_positive(self):
        ok = "約 25 份 2026-10-04 共 1000 元 0.75 公斤 預算 100000000"
        self.assertEqual(redact_text(ok), ok)
        self.assertEqual(redact(ok)[1], {})

    def test_mask_contact(self):
        self.assertEqual(mask_contact("0900-000-101"), "0900-***-101")
        self.assertEqual(mask_contact("abc"), "***")
        self.assertEqual(mask_contact(""), "")
        self.assertEqual(mask_contact(None), "")
        self.assertNotIn("id_demo", mask_contact("line_id_demo123"))

    def test_none_and_long(self):
        self.assertEqual(redact_text(None), "")
        t, c = redact(("一般文字 " * 20000) + "0900-000-678")
        self.assertEqual(c, {"phone": 1})
        self.assertNotIn("678", t)


if __name__ == "__main__":
    unittest.main()
