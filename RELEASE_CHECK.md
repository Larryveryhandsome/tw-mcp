# RELEASE_CHECK｜tw-mcp 0.1.0

> 依 `release-quality-gate` 八道閘門。檢查日期 2026-11-12；受測版本為單一全新 commit（git 歷史只有 1 筆，noreply 身分）。
> **發布決定：✅ 公開**（作者 2026-11-12 決定：直接公開；廣告放 README 結尾、about 工具、MCP server instructions，工具結果不附廣告）。

## 結論

| # | 閘門 | 結果 | 證據 |
|---|---|---|---|
| 1 | 需求與設計 | ✅ | 5 個計算工具＋`about` 全在本機執行、不連外部 API、不需金鑰；輸入錯誤回中文原因（ToolError），其他例外不外露細節；`pdf_pages` 是唯一會寫檔的工具，標 `read_only_hint=false`、不覆蓋既有檔 |
| 2 | 程式本身 | ✅ | 單元測試 46 項全過；`pip-audit` 檢查 37 個相依套件：No known vulnerabilities found；commit 後自動安全審查提出 ZIP 解壓上限問題，已修並補測試 |
| 3 | 串接 | ✅ | `tests/test_server.py` 用官方 SDK 的 Client 實際 list_tools／call_tool；錯誤情境回 `is_error` 且帶中文訊息；斷言工具結果不含廣告、about 與 instructions 含正確 LINE／電話 |
| 4 | 完成使用者任務 | ✅ | Claude Code 實裝後用 `claude -p --model haiku` 依序呼叫 6 個工具全部成功（輸出見下） |
| 5 | 安全／效能／環境 | ✅ | 個資遮罩只在本機；`lvr_search` ZIP 解壓合計 500MB 上限＋實際讀取限量（不信任 ZIP 標頭）、同縣市只讀一檔、總列數 200 萬上限；`pdf_pages` 一次 200 頁、單邊 10000px、總像素 4000 萬上限；`pii_mask` 輸入上限 20 萬字。CI：Ubuntu＋Windows × Python 3.10／3.12／3.13 |
| 6 | 資料 | ✅ | 辦公日曆 2025～2027 由 DGPA 官方 CSV 轉檔（`tools/build_calendar.py`），測試核對 2026 全年放假 120 天、工作日 245 天、2025-02-08 補行上班；實價登錄示範資料全為虛構 |
| 7 | 交付版本 | ✅ | 從乾淨 clone＋全新 uv 快取跑 `uv run --with pytest pytest -q` → 46 passed；`claude mcp add tw -- uvx --from <clone> tw-mcp` → `✔ Connected` |
| 8 | 出事能恢復 | ✅ | 無狀態、無資料庫；移除只要 `claude mcp remove tw`；工具不修改使用者既有檔案 |

## 關鍵證據（本次實際輸出）

**乾淨 clone＋全新 uv 快取**
```
..............................................                           [100%]
46 passed in 1.72s
```

**Claude Code 實裝與呼叫（乾淨 clone、全新 UV_CACHE_DIR）**
```
tw: …/uvx.exe --from …/clone4 tw-mcp - ✔ Connected
[init] tw: ['connected'] ['mcp__tw__about', 'mcp__tw__labor_overtime', 'mcp__tw__lvr_search', 'mcp__tw__pdf_pages', 'mcp__tw__pii_mask', 'mcp__tw__tw_workdays']
[call] mcp__tw__labor_overtime {"wage": 36000, "hours": 2}
   is_error=False {"amount": 400, "legal_minimum": 400} | 結果含廣告電話: False
[call] mcp__tw__tw_workdays {"start": "2026-02-13", "add": 1}
   is_error=False {"result": "2026-02-23"} | 結果含廣告電話: False
[call] mcp__tw__pii_mask {"text": "請找王先生 0900-000-678，LINE ID: wang123"}
   is_error=False {"masked": "請找王先生 [電話已隱藏],LINE[已隱藏]"} | 結果含廣告電話: False
[call] mcp__tw__lvr_search {"county": "宜蘭縣", "limit": 2}
   is_error=False {"demo_data": true} | 結果含廣告電話: False
[call] mcp__tw__pdf_pages {"pdf_path": "…/demo.pdf", "dpi": 72, "out_dir": "…/out4"}
   is_error=False {"converted": 2} | 結果含廣告電話: False
[call] mcp__tw__about {}
   is_error=False {"author": "林其衞（留白事務所）", "customization.phone": "0928-880-392", "line": "https://line.me/ti/p/xzHT2IywOM"}
[final] … OK | is_error: False
```
測完已 `claude mcp remove -s local tw` 還原。

**加班費數字依據**：勞基法第 24 條「加給三分之一以上」→ 法定最低用分數 4/3 精確計算：150 × 2 × 4/3 ＝ 400 元；業界 1.34 進位算法 402 元另列於 `common_practice`。

## 去識別化掃描（`_tools/deep_audit.py`，含 git 全歷史）

真實金鑰、Token、LINE userId、我們的網域與 IP、只在歷史裡的內容、commit 作者信箱：**全部 0 筆**。其餘命中逐筆確認：

| 命中 | 位置 | 判定 |
|---|---|---|
| 身分證字號 A123456789 | `tests/test_pii.py`、本檔 | 教科書通用示範號碼，測試遮罩用（誤判） |
| 手機 0900-000-xxx | README、`pii.py`、tests、server 參數說明 | 示範假號碼（誤判） |
| 宜蘭（縣市對照表、測試參數） | `lvr.py`、`test_server.py` | 內政部開放資料檔名字母對照表與測試輸入 |
| 林其衞、留白 | README「🛠️ 需要客製化？」、NOTICE、`server.py` instructions 與 `ABOUT` | **作者 2026-11-12 指定的客製化廣告，刻意保留**（LINE https://line.me/ti/p/xzHT2IywOM、0928-880-392；不放 @812ibtir） |

## 已知問題

- 尚未上架 PyPI（用 git 或本機路徑安裝）。
- 國定假日／基本工資只內建 2026 年；辦公日曆內建 2025～2027 年。
- `lvr_search` 不會自動下載開放資料。
- 不含土地增值稅試算（作者 2026-11-12 決定不開源）。

## 發布門檻

| 門檻 | 狀態 |
|---|---|
| 核心流程通過 | ✅ |
| 無阻斷性缺陷 | ✅ |
| 重大風險有人決定 | ✅ 作者 2026-11-12：直接公開、廣告位置 README＋about＋instructions |
| 權限／個資 | ✅（全本機、無帳號） |
| 安裝驗證 | ✅ |
| 作者驗收 | ✅ 決定公開 |
