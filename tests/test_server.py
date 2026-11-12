"""MCP 層：用官方 SDK 的 in-process Client 列出並呼叫 5 個工具＋about。"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from mcp import Client
from PIL import Image

from tw_mcp.server import mcp

EXPECTED = {"lvr_search", "labor_overtime", "pii_mask", "tw_workdays", "pdf_pages", "about"}


def call(name, args):
    async def go():
        async with Client(mcp) as c:
            return await c.call_tool(name, args)
    r = asyncio.run(go())
    text = r.content[0].text
    return r.is_error, (json.loads(text) if not r.is_error else text)


class Server(unittest.TestCase):
    def test_list_tools(self):
        async def go():
            async with Client(mcp) as c:
                return await c.list_tools()
        tools = {t.name: t for t in asyncio.run(go()).tools}
        self.assertEqual(set(tools), EXPECTED)
        for name, t in tools.items():
            self.assertTrue(t.description and len(t.description) > 20, name)
            self.assertIsNotNone(t.annotations, name)
        self.assertTrue(tools["labor_overtime"].annotations.read_only_hint)
        self.assertFalse(tools["pdf_pages"].annotations.read_only_hint)
        self.assertFalse(tools["pdf_pages"].annotations.destructive_hint)

    def test_call_each_tool(self):
        err, r = call("labor_overtime", {"wage": 36000, "hours": 2})
        self.assertFalse(err)
        self.assertEqual((r["amount"], r["common_practice"]["amount"]), (400, 402))
        err, r = call("pii_mask", {"text": "電話 0900-000-678", "contacts": ["0900-000-101"]})
        self.assertEqual((err, r["found"], r["masked_contacts"]), (False, {"phone": 1}, ["0900-***-101"]))
        err, r = call("tw_workdays", {"start": "2026-02-13", "add": 1})
        self.assertEqual((err, r["result"]), (False, "2026-02-23"))
        err, r = call("lvr_search", {"districts": ["示範北區"], "limit": 3})
        self.assertFalse(err)
        self.assertTrue(r["demo_data"])
        self.assertLessEqual(len(r["transactions"]), 3)
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.pdf"
            Image.new("RGB", (200, 100), (0, 0, 0)).save(src, "PDF", resolution=72)
            err, r = call("pdf_pages", {"pdf_path": str(src), "dpi": 72})
            self.assertFalse(err)
            self.assertEqual(r["converted"], 1)
            self.assertTrue(Path(r["files"][0]["path"]).is_file())

    def test_ad_only_in_about_and_instructions(self):
        for name, args in [("labor_overtime", {"wage": 36000, "hours": 2}), ("pii_mask", {"text": "hi"}),
                           ("tw_workdays", {"start": "2026-10-10"}), ("lvr_search", {"county": "宜蘭縣", "limit": 1})]:
            err, r = call(name, args)
            self.assertFalse(err, name)
            self.assertNotIn("0928-880-392", json.dumps(r, ensure_ascii=False), name)   # 工具結果不附廣告
        err, r = call("about", {})
        self.assertFalse(err)
        self.assertEqual(r["customization"]["phone"], "0928-880-392")
        self.assertEqual(r["customization"]["line"], "https://line.me/ti/p/xzHT2IywOM")
        self.assertEqual(set(r["tools"]), EXPECTED - {"about"})
        self.assertIn("0928-880-392", mcp.instructions)
        self.assertNotIn("812ibtir", mcp.instructions + json.dumps(r, ensure_ascii=False))

    def test_errors_are_reported_not_crashing(self):
        err, msg = call("tw_workdays", {"start": "2019-01-01"})
        self.assertTrue(err)
        self.assertIn("沒有 2019 年", msg)
        err, _ = call("labor_overtime", {"wage": -1, "hours": 2})
        self.assertTrue(err)
        err, _ = call("tw_workdays", {"start": "2026-01-01", "end": "2026-01-31", "add": 3})
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
