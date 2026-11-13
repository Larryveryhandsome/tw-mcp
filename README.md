# tw-mcp｜台灣在地工具箱（MCP server）

> 🎬 25 秒預告片：[v0.1.0 發布頁](https://github.com/Larryveryhandsome/tw-mcp/releases/tag/v0.1.0)（mp4＋字幕檔）

讓 **Claude Code、Claude Desktop、Cursor** 寫台灣的 App 或處理台灣的資料時，直接呼叫「台灣才有的計算」：

| 工具 | 做什麼 | 例子 |
|---|---|---|
| `labor_overtime` 勞基法加班費 | 平日延長工時、休息日、國定假日、例假日加班費，依條文分數（4/3、5/3）精確算法定最低，附業界 1.34 算法對照、公式、法條、警告 | 月薪 36,000、平日加班 2 小時 → 法定最低 **400 元**（業界 1.34 算法 402 元） |
| `tw_workdays` 台灣工作日 | 依人事行政總處辦公日曆表判斷上班日、國定假日、補假、補行上班；算區間工作日、推算第 N 個工作日 | 2026/2/13（週五）＋1 個工作日 → **2026/2/23**（跳過春節） |
| `pii_mask` 個資遮罩 | 蓋掉台灣手機／市話（含 +886、全形、中文數字）、Email、身分證字號、LINE／IG／FB 帳號 | `LINE ID: wang123` → `LINE[已隱藏]` |
| `lvr_search` 實價登錄查詢 | 讀內政部實價登錄開放資料 CSV／ZIP，篩選並**預設排除親友、特殊關係、法拍等交易**，回傳單價中位數、四分位數、各區統計與明細 | 「臺中市西屯區 屋齡 10 年內大樓，近一年單價中位數？」 |
| `pdf_pages` PDF 轉圖 | PDF 指定頁轉 JPG／PNG 存在本機（謄本、合約貼 LINE 用），不上傳、不覆蓋既有檔 | `pages: "1-3,5"`、`dpi: 150` |

- 全部在你的電腦上計算，**不需要任何金鑰、不連外部 API**。
- 另有 `about` 工具：介紹各工具、資料來源、授權與作者聯絡方式。
- Python 3.10 以上；用 [uv](https://docs.astral.sh/uv/) 一行安裝。

## 安裝

先裝 uv（已經有就跳過）：Windows `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`；macOS／Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`。

### Claude Code

```bash
claude mcp add tw -- uvx --from git+https://github.com/Larryveryhandsome/tw-mcp tw-mcp
```

下載到本機的話（例如放在 `~/tw-mcp`）：

```bash
claude mcp add tw -- uvx --from ~/tw-mcp tw-mcp
```

裝好後在 Claude Code 輸入 `/mcp` 應該看到 `tw` 已連線、5 個工具＋`about`。

### Claude Desktop

設定 → 開發者 → 編輯設定（`claude_desktop_config.json`），加入：

```json
{
  "mcpServers": {
    "tw": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Larryveryhandsome/tw-mcp", "tw-mcp"]
    }
  }
}
```

存檔後重開 Claude Desktop。

### Cursor

`~/.cursor/mcp.json`（或專案裡的 `.cursor/mcp.json`）內容同上（`mcpServers` → `tw`）。

> 尚未上架 PyPI，所以用 `--from git+https://…` 或本機路徑安裝。

## 怎麼用（直接用中文問）

**勞基法加班費**

> 月薪 36,000，平日加班 2 小時，加班費多少？

```json
{"amount": 400, "legal_minimum": 400,
 "formula": "每小時工資額＝月薪 36,000 ÷ 240 ＝ 150.00 元；150.00×2h×4/3 ＝ 400 元",
 "common_practice": {"amount": 402, "rates": "1.34／1.67／2.67（業界常用的進位倍率，高於法定最低）"},
 "law": "勞動基準法第 24 條第 1 項（平日延長工時：2 小時以內加給 1/3 以上……）、第 32 條（每日合計不得超過 12 小時）"}
```

- `day_type`：`weekday` 平日（hours＝超過 8 小時的部分）、`rest_day` 休息日、`holiday` 國定假日、`regular_leave` 例假日（後三種 hours＝當天出勤總時數）。
- 給 `date` 的話，2026 年會自動辨識國定假日（例如休息日剛好是國慶日，會改用國定假日計算並提醒），也會檢查是否低於當年度基本工資。
- `amount` 是**法定最低**：勞基法寫「加給三分之一以上」「三分之二以上」，所以用分數 4/3、5/3、8/3 精確計算（Fraction），最後才四捨五入到元；`common_practice` 另附業界常用的 1.34／1.67／2.67 進位算法，金額會略高。
- 月薪制每小時工資額＝月薪 ÷ 240。

**台灣工作日**

> 2026 年 2 月有幾個工作天？　／　今天起 10 個工作天後是幾號？　／　2026-10-09 要上班嗎？

- 只給 `start`：查那一天（上班日／週末／國定假日／補假／補行上班）。
- `start`＋`end`：算區間（含頭尾）有幾個工作日，列出期間的國定假日。
- `start`＋`add`：推算第 N 個工作日（負數往回推）。
- 內建 **2025～2027 年**；超出範圍會明確報錯，不會自己猜。

**個資遮罩**

> 把這段客戶留言的電話、Email、LINE 蓋掉再貼給我：「請找王先生 0900-000-678，LINE ID: wang123」

```json
{"masked": "請找王先生 [電話已隱藏]，LINE[已隱藏]", "found": {"phone": 1, "social": 1}, "total": 2}
```

另可傳 `contacts: ["0900-000-101"]` 取得列表用的部分遮罩 `0900-***-101`。

**實價登錄查詢**

1. 到 [內政部不動產交易實價查詢服務網 → 開放資料下載](https://plvr.land.moi.gov.tw/DownloadOpenData) 下載「不動產買賣」CSV（例如臺中市是 `b_lvr_land_a.csv`），或整包 ZIP。
2. 問：

> 用 C:\data\b_lvr_land_a.csv 查西屯區 2025 年以後的大樓，單價中位數多少？列 10 筆最近的。

- 預設排除備註含「親友、員工、特殊關係、瑕疵、凶宅、債權、急買急賣、含裝潢、政府機關、法拍」的交易（`excluded_special` 會告訴你排除幾筆），要看全部設 `include_special: true`。
- 預設只算有建物的交易（排除純土地、純車位）。單價為萬元／坪（開放資料已扣車位）。
- 日期可用西元 `2025-01-01` 或民國 `1140101`。
- **沒給檔案時用內建的虛構示範資料**（回傳 `demo_data: true`，地址都是「示範○區」），只能拿來試用。

**PDF 轉圖**

> 把 D:\文件\謄本.pdf 第 1～2 頁轉成 JPG

圖檔預設存在 PDF 旁邊的 `謄本_pages\` 資料夾（`謄本_p001.jpg`…），同名不覆蓋（自動加 `(2)`）；有密碼的 PDF 傳 `password`。一次最多 200 頁、DPI 36～600。

## 資料來源與每年更新

| 資料 | 來源 | 授權 | 更新方式 |
|---|---|---|---|
| 辦公日曆（`tw_workdays`） | 行政院人事行政總處「中華民國政府行政機關辦公日曆表」，[data.gov.tw dataset 14718](https://data.gov.tw/dataset/14718) | 政府資料開放授權條款－第 1 版 | 每年約 6 月公告次年度；下載 CSV 後 `python tools/build_calendar.py 新年度.csv` |
| 國定假日、基本工資（`labor_overtime`） | 勞動部公告、紀念日及節日實施條例 | — | 編輯 `src/tw_mcp/data/labor_calendar.json` 加一個年度 |
| 實價登錄（`lvr_search`） | 內政部不動產交易實價查詢服務網開放資料（使用者自行下載） | 政府資料開放授權條款－第 1 版 | 每月 1、11、21 日發布，自行下載新檔即可 |

工具邏輯移植自同作者的開源專案：[tw-shop-staff](https://github.com/Larryveryhandsome/tw-shop-staff)（算薪）、[tw-duty-roster](https://github.com/Larryveryhandsome/tw-duty-roster)（日期工具）、[tw-local-needs](https://github.com/Larryveryhandsome/tw-local-needs)（個資遮罩）、[tw-lvr-map](https://github.com/Larryveryhandsome/tw-lvr-map)（實價登錄）、[tw-pdf2jpg](https://github.com/Larryveryhandsome/tw-pdf2jpg)（PDF 轉圖）。

## 開發與測試

```bash
git clone https://github.com/Larryveryhandsome/tw-mcp && cd tw-mcp
uv run --with pytest pytest -q
```

測試含：示範值 400 元（法定最低）與 402 元（1.34 對照）、分數精確計算、休息日／國定假日倍率、國定假日自動辨識、2026 春節工作日、跨年推算、個資遮罩的全形／+886／中文數字／at-dot 變形與不誤傷一般數字、實價登錄 Big5／ZIP／重複編號／特殊交易排除、PDF 頁碼範圍與不覆蓋，以及 MCP 層實際列出並呼叫 5 個工具＋about，確認工具結果不附廣告。

## 免責聲明

- 加班費、工作日、實價登錄統計**原則上僅供參考**，不構成法律、稅務、估價或投資意見；實際以勞動部函釋、勞資約定、主管機關認定、公司公告為準。
- 民間企業依勞基法放國定假日，補假、調移日期可能與公務機關辦公日曆不同。
- 個資遮罩擋的是常見格式，無法保證百分之百；對外公開前仍建議人工再看一遍。
- 實價登錄為政府公開資料的整理；內建示範資料完全虛構。

## 已知問題

- 尚未上架 PyPI（用 git 或本機路徑安裝）。
- 國定假日／基本工資只內建 2026 年；辦公日曆內建 2025～2027 年。
- `lvr_search` 不會自動下載開放資料（要先自己下載 CSV／ZIP）；整包全國 ZIP 很大，建議指定 `county`。
- 不含土地增值稅試算。

## 授權

程式碼：[Apache License 2.0](LICENSE)，轉散布請保留 [NOTICE](NOTICE)。辦公日曆與實價登錄資料依政府資料開放授權條款利用。

完整的發布前檢查（八道閘門）見 [RELEASE_CHECK.md](RELEASE_CHECK.md)。

## 🛠️ 需要客製化？

這個工具是開源的，可以免費使用。如果你想要：
- 加上你們公司自己的計算（獎金、抽成、排班、報價……）包成 AI 能直接呼叫的工具
- 串接你現在在用的系統（LINE、Google 表單、POS、會計軟體……）
- 幫你安裝、教學，或長期維護

歡迎加 LINE 跟我們聊。我們會依需求的範圍與複雜度報價，原則上以實際報價單為準。

<a href="https://line.me/ti/p/xzHT2IywOM"><img src="https://scdn.line-apps.com/n/line_add_friends/btn/zh-Hant.png" alt="加入好友" height="36"></a>

- 💬 LINE：[林其衞](https://line.me/ti/p/xzHT2IywOM)（請註明「tw-mcp 客製化」）
- 📞 電話：0928-880-392
- 🏢 留白事務所：網頁設計、AI 自動化、遠端助理
- 👤 作者：[留白事務所](https://github.com/Larryveryhandsome)
