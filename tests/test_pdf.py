"""頁碼、檔名測試移植自 tw-pdf2jpg/tests/pdf2img.test.js；轉圖用 Pillow 現做的測試 PDF。"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tw_mcp import pdf as P


def make_pdf(path: Path, n=3, password=None):
    colors = [(255, 0, 0), (0, 160, 0), (0, 0, 255), (200, 200, 0)]
    pages = [Image.new("RGB", (595, 842), colors[i % 4]) for i in range(n)]   # A4 72dpi
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=72)


class Helpers(unittest.TestCase):
    def test_parse_page_range(self):
        self.assertEqual(P.parse_page_range("", 3), ([1, 2, 3], []))
        self.assertEqual(P.parse_page_range("1-3,5,8-", 10)[0], [1, 2, 3, 5, 8, 9, 10])
        self.assertEqual(P.parse_page_range("2，4、6", 6)[0], [2, 4, 6])
        self.assertEqual(P.parse_page_range("2～3", 5)[0], [2, 3])
        pages, errors = P.parse_page_range("5-2,9,abc", 5)
        self.assertEqual(pages, [])
        self.assertEqual(len(errors), 3)
        self.assertEqual(P.parse_page_range("-2", 5)[0], [1, 2])

    def test_names(self):
        self.assertEqual(P.page_file_name("報告.PDF", 1, 12, "jpg"), "報告_p001.jpg")
        self.assertEqual(P.page_file_name("a.pdf", 7, 1500, "png"), "a_p0007.png")
        self.assertEqual(P.base_name('a/b:c*?.pdf'), "a_b_c__")
        self.assertEqual(P.base_name("...pdf"), "document")
        used = set()
        self.assertEqual([P.unique_name("a.jpg", used) for _ in range(3)], ["a.jpg", "a (2).jpg", "a (3).jpg"])

    def test_dpi_and_scale(self):
        self.assertEqual(P.clamp_dpi(10), 36)
        self.assertEqual(P.clamp_dpi(9999), 600)
        self.assertEqual(P.clamp_dpi("x"), 150)
        s = P.safe_scale(595, 842, 600 / 72, max_side=4000)
        self.assertLessEqual(842 * s, 4000.001)
        self.assertEqual(P.format_bytes(500), "500 B")
        self.assertEqual(P.format_bytes(2048), "2.0 KB")


class Convert(unittest.TestCase):
    def test_convert_pages(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "測試 文件.pdf"
            make_pdf(src, 3)
            r = P.convert(str(src), pages="1,3", dpi=72)
            self.assertEqual((r["total_pages"], r["converted"]), (3, 2))
            self.assertEqual([f["page"] for f in r["files"]], [1, 3])
            first = Image.open(r["files"][0]["path"])
            self.assertEqual(first.size, (595, 842))
            self.assertGreater(first.getpixel((10, 10))[0], 200)              # 第 1 頁紅色
            self.assertGreater(Image.open(r["files"][1]["path"]).getpixel((10, 10))[2], 200)   # 第 3 頁藍色
            self.assertTrue(r["files"][0]["path"].endswith("測試 文件_p001.jpg"))
            # 再轉一次不覆蓋既有檔
            r2 = P.convert(str(src), pages="1", dpi=72)
            self.assertTrue(r2["files"][0]["path"].endswith("_p001 (2).jpg"))
            # PNG、指定資料夾、超出範圍的頁碼回報警告
            out = Path(d) / "out"
            r3 = P.convert(str(src), pages="2,9", dpi=144, fmt="png", out_dir=str(out))
            self.assertEqual(r3["converted"], 1)
            self.assertTrue(r3["warnings"])
            self.assertEqual(Image.open(r3["files"][0]["path"]).size, (1190, 1684))

    def test_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                P.convert(str(Path(d) / "none.pdf"))
            bad = Path(d) / "bad.pdf"
            bad.write_bytes(b"not a pdf")
            with self.assertRaises(ValueError):
                P.convert(str(bad))
            txt = Path(d) / "a.txt"
            txt.write_text("x")
            with self.assertRaises(ValueError):
                P.convert(str(txt))
            src = Path(d) / "a.pdf"
            make_pdf(src, 2)
            with self.assertRaises(ValueError):
                P.convert(str(src), pages="5")


if __name__ == "__main__":
    unittest.main()
