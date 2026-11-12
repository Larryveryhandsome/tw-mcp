"""個資遮罩：把文字裡的電話、Email、身分證字號、LINE／IG／FB 帳號與社群連結蓋掉。

邏輯移植自 tw-local-needs 的 js/needs.js（redactText、maskContact），規則與順序相同：
先做 NFKC 正規化（全形數字／＠ → 半形）、去掉零寬字元、統一各種橫線，再比對，
避免用全形、空白、點、斜線、中文數字等寫法繞過。原則上擋常見格式，重要文件仍建議人工再看一遍。
"""
import re
import unicodedata

SEP = r"[\s.\-/()·•,_]*"
_ZERO_WIDTH = re.compile("[​-‍⁠﻿­]")
_DASHES = re.compile("[‐-―−－]")
_SOCIAL = r"(line|賴|ig|instagram|fb|facebook|wechat|weixin|微信|telegram|tg|whatsapp)"

# (類別, 正規式, 取代字串)；順序有意義，與原始 JS 相同
RULES = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9-]+(?:\s*\.\s*[A-Za-z0-9-]+)*\s*\.\s*[A-Za-z]{2,}"), "[Email已隱藏]"),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+\s*(?:\(at\)|\[at\]|\s+at\s+)\s*[A-Za-z0-9-]+(?:\s*(?:\(dot\)|\[dot\]|\s+dot\s+|\.)\s*[A-Za-z0-9-]+)*"
                         r"\s*(?:\(dot\)|\[dot\]|\s+dot\s+|\.)\s*[A-Za-z]{2,}", re.I), "[Email已隱藏]"),
    ("link", re.compile(r"(?:https?://)?(?:line\.me|lin\.ee|wa\.me|t\.me|m\.me|facebook\.com|fb\.com|instagram\.com)/\S+", re.I), "[連結已隱藏]"),
    ("national_id", re.compile(r"(?<![A-Za-z])[A-Z]\s?[12](?:\s?\d){8}(?!\d)", re.I), "[證號已隱藏]"),
    ("phone", re.compile(r"(?<!\d)\+?886" + SEP + r"\(?0?\)?(?:" + SEP + r"\d){8,9}(?!\d)"), "[電話已隱藏]"),
    ("phone", re.compile(r"(?<!\d)(?<!\d[-/.])\(?0(?:" + SEP + r"\d){8,9}(?!\d)"), "[電話已隱藏]"),
    ("phone", re.compile(r"[零〇○一二三四五六七八九]{8,}"), "[電話已隱藏]"),
    ("social", re.compile(r"(?<![A-Za-z])" + _SOCIAL + r"\s*(?:id|帳號)?\s*[:：=]\s*@?[A-Za-z0-9._-]{2,}", re.I), r"\1[已隱藏]"),
    ("social", re.compile(r"(?<![A-Za-z])" + _SOCIAL + r"\s*(?:id|帳號)\s*@?[A-Za-z0-9._-]{2,}", re.I), r"\1[已隱藏]"),
    ("social", re.compile(r"(?<![A-Za-z])(line|賴|ig|fb|wechat|微信|telegram|tg|whatsapp)\s*@?(?=[A-Za-z0-9._-]*\d)[A-Za-z0-9._-]{3,}", re.I), r"\1[已隱藏]"),
    ("social", re.compile(r"(?<![A-Za-z0-9._@])@[A-Za-z0-9._-]{4,}"), "[帳號已隱藏]"),
]
CATEGORY_ZH = {"email": "Email", "link": "社群連結", "national_id": "身分證／居留證號", "phone": "電話", "social": "社群帳號"}


def normalize(s) -> str:
    t = unicodedata.normalize("NFKC", "" if s is None else str(s))
    t = _ZERO_WIDTH.sub("", t)
    return _DASHES.sub("-", t)


def redact(s):
    """回傳 (遮罩後文字, {類別: 次數})"""
    t = normalize(s)
    counts = {}
    for cat, rx, repl in RULES:
        t, n = rx.subn(repl, t)
        if n:
            counts[cat] = counts.get(cat, 0) + n
    return t, counts


def redact_text(s) -> str:
    return redact(s)[0]


def mask_contact(s) -> str:
    """遮罩單一聯絡方式（列表顯示用）：0900-000-101 → 0900-***-101。"""
    t = "" if s is None else str(s)
    if len(t) <= 4:
        return "*" * len(t)
    keep_end = min(3, len(t) // 3)
    keep_start = min(4, len(t) // 3)
    middle = re.sub(r"[^\s\-]", "*", t[keep_start:len(t) - keep_end])
    return t[:keep_start] + middle + t[len(t) - keep_end:]
