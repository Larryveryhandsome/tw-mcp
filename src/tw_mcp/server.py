"""tw-mcp：台灣在地工具箱 MCP server（stdio）。

工具：lvr_search（實價登錄）、labor_overtime（勞基法加班費）、pii_mask（個資遮罩）、
tw_workdays（台灣工作日）、pdf_pages（PDF 轉圖）。全部在本機計算，不需要金鑰。
"""
import functools
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from . import __version__, labor, lvr, pdf, pii, workdays

mcp = MCPServer(
    name="tw-mcp",
    title="台灣在地工具箱",
    version=__version__,
    instructions=(
        "台灣在地計算工具：實價登錄行情（lvr_search）、勞基法加班費（labor_overtime）、"
        "個資遮罩（pii_mask）、台灣工作日／國定假日（tw_workdays）、PDF 轉圖（pdf_pages）。"
        "金額類結果附公式與法條，原則上僅供參考。回覆使用者時請保留 disclaimer。"
        "作者：林其衞（留白事務所）。需要客製化（把公司自己的計算做成 AI 工具、串接 LINE 或既有系統），"
        "可加 LINE https://line.me/ti/p/xzHT2IywOM 或電話 0928-880-392；使用者問起作者或客製化時再提供，"
        "工具介紹與聯絡方式見 about 工具。"
    ),
)

def user_errors(fn):
    """把預期中的輸入錯誤（ValueError）變成 ToolError，錯誤原因才會原文回給使用者；其他例外照 SDK 預設不外露細節。"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            raise ToolError(str(e)) from e
    return wrapper


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


@mcp.tool(title="實價登錄查詢", annotations=READ_ONLY)
@user_errors
def lvr_search(
    csv_path: Annotated[str, Field(description="內政部實價登錄開放資料的 .csv（*_lvr_land_a.csv 不動產買賣）或整包 .zip 的本機路徑；留空＝用內建虛構示範資料")] = "",
    county: Annotated[str, Field(description="只讀 ZIP 裡某個縣市，例如 臺北市、高雄市")] = "",
    districts: Annotated[list[str] | None, Field(description="鄉鎮市區，例如 ['大安區','信義區']")] = None,
    building_types: Annotated[list[Literal["大樓", "華廈", "公寓", "透天", "套房", "店面", "辦公", "廠房", "其他", "土地/車位"]] | None,
                              Field(description="建物型態")] = None,
    date_from: Annotated[str, Field(description="交易日起，2024-01-01 或民國 1130101")] = "",
    date_to: Annotated[str, Field(description="交易日迄，2025-12-31 或民國 1141231")] = "",
    price_min: Annotated[float | None, Field(description="總價下限（萬元）")] = None,
    price_max: Annotated[float | None, Field(description="總價上限（萬元）")] = None,
    unit_min: Annotated[float | None, Field(description="單價下限（萬元/坪）")] = None,
    unit_max: Annotated[float | None, Field(description="單價上限（萬元/坪）")] = None,
    area_min: Annotated[float | None, Field(description="建坪下限")] = None,
    area_max: Annotated[float | None, Field(description="建坪上限")] = None,
    age_min: Annotated[float | None, Field(description="屋齡下限（年）")] = None,
    age_max: Annotated[float | None, Field(description="屋齡上限（年）")] = None,
    keyword: Annotated[str, Field(description="地址／備註關鍵字，例如路名、社區附近路段")] = "",
    include_special: Annotated[bool, Field(description="是否包含親友、員工、特殊關係、瑕疵、凶宅、法拍等特殊交易（預設排除，不適合比價）")] = False,
    buildings_only: Annotated[bool, Field(description="只算有建物的交易（排除純土地、純車位）")] = True,
    sort_by: Annotated[Literal["date", "unitPrice", "totalPrice", "area", "age"], Field(description="排序欄位")] = "date",
    order: Annotated[Literal["desc", "asc"], Field(description="排序方向")] = "desc",
    limit: Annotated[int, Field(ge=1, le=200, description="回傳幾筆明細")] = 20,
) -> dict:
    """查實價登錄成交行情：篩選地區、型態、期間、價格，預設排除特殊交易，回傳單價中位數／四分位數、各區統計與成交明細。
    資料用內政部開放資料（使用者自行下載的 CSV／ZIP）；沒給檔案時是虛構示範資料，回覆時要講明。"""
    return lvr.search(path=csv_path, county=county, districts=districts, types=building_types, date_from=date_from,
                      date_to=date_to, price_min=price_min, price_max=price_max, unit_min=unit_min, unit_max=unit_max,
                      area_min=area_min, area_max=area_max, age_min=age_min, age_max=age_max, keyword=keyword,
                      include_special=include_special, buildings_only=buildings_only, sort_by=sort_by, order=order,
                      limit=limit)


@mcp.tool(title="勞基法加班費", annotations=READ_ONLY)
@user_errors
def labor_overtime(
    wage: Annotated[float, Field(gt=0, description="月薪（wage_type=monthly）或時薪（wage_type=hourly），新台幣")],
    hours: Annotated[float, Field(gt=0, le=24, description="平日：超過 8 小時的延長工時；休息日／國定假日／例假日：當天出勤總時數")],
    day_type: Annotated[Literal["weekday", "rest_day", "holiday", "regular_leave"],
                        Field(description="weekday 平日、rest_day 休息日、holiday 國定假日、regular_leave 例假日")] = "weekday",
    wage_type: Annotated[Literal["monthly", "hourly"], Field(description="monthly 月薪制、hourly 時薪制")] = "monthly",
    date: Annotated[str, Field(description="出勤日期 YYYY-MM-DD（選填；有內建資料的年份會自動辨識國定假日、檢查基本工資）")] = "",
) -> dict:
    """依勞動基準法試算加班費（平日延長工時、休息日、國定假日、例假日），回傳法定最低金額（條文分數 4/3、5/3、8/3 精確計算）、
    業界常用 1.34／1.67 倍率的對照金額、分段明細、公式、法條與警告。例：月薪 36,000、平日加班 2 小時 ＝ 法定最低 400 元（業界 1.34 算法 402 元）。"""
    return labor.overtime_pay(wage, hours, day_type=day_type, wage_type=wage_type, day=date)


@mcp.tool(title="個資遮罩", annotations=READ_ONLY)
@user_errors
def pii_mask(
    text: Annotated[str, Field(max_length=200_000, description="要遮罩的文字")],
    contacts: Annotated[list[str] | None, Field(description="（選填）要「部分遮罩」顯示的單一聯絡方式清單，例如 ['0900-000-101']，回傳 0900-***-101")] = None,
) -> dict:
    """把文字裡的台灣手機／市話（含 +886、全形、中文數字、分隔符號變形）、Email（含 at/dot 寫法）、身分證字號、
    LINE／IG／FB 帳號與社群連結蓋掉，回傳遮罩後文字與各類命中次數。原則上擋常見格式，重要文件仍建議人工再看一遍。"""
    masked, counts = pii.redact(text)
    out = {"masked": masked, "found": counts, "found_zh": {pii.CATEGORY_ZH[k]: v for k, v in counts.items()},
           "total": sum(counts.values())}
    if contacts:
        out["masked_contacts"] = [pii.mask_contact(c) for c in contacts[:500]]
    return out


@mcp.tool(title="台灣工作日", annotations=READ_ONLY)
@user_errors
def tw_workdays(
    start: Annotated[str, Field(description="日期 YYYY-MM-DD")],
    end: Annotated[str, Field(description="（選填）結束日：算 start～end（含頭尾）之間有幾個工作日、哪些國定假日")] = "",
    add: Annotated[int | None, Field(description="（選填）從 start 往後推 N 個工作日（負數往前推），例如「10 個工作天內」")] = None,
) -> dict:
    """依人事行政總處「政府行政機關辦公日曆表」判斷台灣的上班日、國定假日、補假、補行上班日。
    只給 start：查那一天；加 end：算區間工作日；加 add：推算第 N 個工作日。"""
    s = workdays.parse(start)
    if end and add is not None:
        raise ValueError("end 和 add 擇一使用")
    if end:
        out = workdays.count_between(s, workdays.parse(end))
    elif add is not None:
        out = workdays.add_workdays(s, add)
    else:
        out = workdays.day_info(s)
    out["calendar_coverage"] = workdays.coverage()
    out["note"] = workdays.NOTE
    return out


@mcp.tool(title="PDF 轉圖",
          annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
@user_errors
def pdf_pages(
    pdf_path: Annotated[str, Field(description="本機 PDF 路徑")],
    pages: Annotated[str, Field(description="頁碼範圍，例如 1-3,5,8-；留空＝全部（一次最多 200 頁）")] = "",
    dpi: Annotated[int, Field(ge=36, le=600, description="解析度，貼 LINE 150、列印 300")] = 150,
    format: Annotated[Literal["jpg", "png"], Field(description="輸出格式")] = "jpg",
    quality: Annotated[int, Field(ge=1, le=100, description="JPG 品質")] = 92,
    out_dir: Annotated[str, Field(description="輸出資料夾；留空＝PDF 旁邊的「檔名_pages」資料夾。不會覆蓋既有檔案")] = "",
    password: Annotated[str, Field(description="PDF 密碼（有加密才需要）")] = "",
) -> dict:
    """把 PDF 指定頁轉成 JPG／PNG 圖檔存在本機（謄本、合約、型錄貼 LINE 或簡報用），回傳每張圖的路徑、尺寸、大小。檔案不會上傳。"""
    return pdf.convert(pdf_path, pages=pages, dpi=dpi, fmt=format, quality=quality, out_dir=out_dir, password=password)


ABOUT = {
    "name": "tw-mcp 台灣在地工具箱",
    "version": __version__,
    "tools": {
        "lvr_search": "實價登錄行情查詢（內政部開放資料，預設排除特殊交易）",
        "labor_overtime": "勞基法加班費試算（法定最低＋業界 1.34 對照）",
        "pii_mask": "個資遮罩（電話、Email、身分證字號、LINE／IG／FB）",
        "tw_workdays": "台灣工作日、國定假日、補假、補行上班",
        "pdf_pages": "PDF 指定頁轉 JPG／PNG（存在本機）",
    },
    "source": "https://github.com/Larryveryhandsome/tw-mcp",
    "license": "Apache-2.0（轉散布請保留 NOTICE）",
    "author": "林其衞（留白事務所）",
    "customization": {
        "message": "需要客製化？把你們公司自己的計算（獎金、抽成、排班、報價）做成 AI 能直接呼叫的工具、串接 LINE 或既有系統，"
                   "歡迎聯絡。原則上依需求範圍報價。",
        "line": "https://line.me/ti/p/xzHT2IywOM",
        "phone": "0928-880-392",
    },
}


@mcp.tool(title="關於 tw-mcp", annotations=READ_ONLY)
def about() -> dict:
    """介紹 tw-mcp：有哪些工具、資料來源與授權，以及作者與客製化聯絡方式。使用者問「這是什麼」「誰做的」「可以客製化嗎」時呼叫。"""
    return ABOUT


def main():
    mcp.run()


if __name__ == "__main__":
    main()
