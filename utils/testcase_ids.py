import re
import zipfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTCASE_WORKBOOK = PROJECT_ROOT / "outputs" / "testcase_workbook" / "BANG_TESTCASE_THEO_CHUC_NANG_fixed.xlsx"

_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

_TESTCASE_ID_BY_FUNCTION = {
    "test_search_load_more_preserves_keyword": "TC_SEARCH_01",
    "test_search_deeplink_query_loads_correct_results": "TC_SEARCH_02",
    "test_search_autocomplete_suggestion_click_navigates_to_results": "TC_SEARCH_03",
    "test_search_enter_vs_click_icon_same_result": "TC_SEARCH_04",
    "test_search_vietnamese_accent_and_no_accent": "TC_SEARCH_05",
    "test_search_empty_query": "TC_SEARCH_06",
    "test_search_very_long_query": "TC_SEARCH_07",
    "test_search_results_are_scoped_to_main_results_container": "TC_SEARCH_08",
    "test_search_change_keyword_updates_results": "TC_SEARCH_09",
    "test_search_then_sort_price_keeps_relevant_sorted_results": "TC_SEARCH_10",
    "test_search_not_found_shows_no_results": "TC_SEARCH_20",
    "test_filter_all_products_match_brand": "TC_FILTER_01",
    "test_unfilter_restores_list": "TC_FILTER_02",
    "test_filter_combination_no_results": "TC_FILTER_03",
    "test_filter_multiple_conditions_then_remove_one_updates_results": "TC_FILTER_04",
    "test_filter_state_persists_after_reload": "TC_FILTER_05",
    "test_filter_then_sort_price_keeps_filtered_sorted_results": "TC_FILTER_06",
    "test_sort_price_orders": "TC_SORT_01",
    "test_sort_changes_order_for_non_price_options": "TC_SORT_02",
    "test_sort_switching_between_sort_types_keeps_results_visible": "TC_SORT_03",
    "test_preserve_sort_state_on_reload_and_navigation": "TC_SORT_04",
}

_SEARCH_VARIANT_IDS = {
    "logitech": "TC_SEARCH_11",
    "Logitech": "TC_SEARCH_12",
    "  Logitech  ": "TC_SEARCH_13",
    "Logitech!@#": "TC_SEARCH_14",
}

_SEARCH_TYPO_IDS = {
    "Logitec": "TC_SEARCH_15",
    "Logit ech": "TC_SEARCH_16",
    "Logitechk": "TC_SEARCH_17",
    "Logtech": "TC_SEARCH_18",
    "Logit3ch": "TC_SEARCH_19",
}

_XSS_PAYLOAD_IDS = {
    "<script>alert(1)</script>": "TC_SEARCH_21",
    '"<img src=x onerror=alert(1)>': "TC_SEARCH_22",
}

_SQL_PAYLOAD_IDS = {
    "' OR '1'='1": "TC_SEARCH_23",
    '" OR "1"="1': "TC_SEARCH_24",
    "' UNION SELECT NULL --": "TC_SEARCH_25",
    "' UNION SELECT username,password FROM users --": "TC_SEARCH_26",
    "') UNION SELECT NULL,NULL --": "TC_SEARCH_27",
    "'; DROP TABLE products; --": "TC_SEARCH_28",
    "admin' --": "TC_SEARCH_29",
}

_TESTCASE_PASS_CONCLUSIONS = {
    "TC_SEARCH_01": "Danh sách sản phẩm sau khi xem thêm vẫn giữ đúng ngữ cảnh từ khóa tìm kiếm.",
    "TC_SEARCH_02": "URL tìm kiếm trực tiếp tải được kết quả liên quan đến từ khóa.",
    "TC_SEARCH_03": "Click gợi ý autocomplete điều hướng đến trang kết quả hợp lệ.",
    "TC_SEARCH_04": "Tìm kiếm bằng Enter và click icon cho danh sách sản phẩm tương đương.",
    "TC_SEARCH_05": "Từ khóa tiếng Việt có dấu/không dấu vẫn được xử lý ổn định.",
    "TC_SEARCH_06": "Tìm kiếm rỗng không làm trang lỗi hoặc crash.",
    "TC_SEARCH_07": "Chuỗi rất dài vẫn không làm trình duyệt mất phản hồi.",
    "TC_SEARCH_08": "Danh sách sản phẩm được lấy đúng từ vùng kết quả chính.",
    "TC_SEARCH_09": "Đổi từ khóa làm danh sách sản phẩm cập nhật đúng.",
    "TC_SEARCH_10": "Tìm kiếm rồi sắp xếp theo giá vẫn giữ sản phẩm liên quan và thứ tự giá hợp lệ.",
    "TC_SEARCH_11": "Từ khóa viết thường vẫn trả về sản phẩm liên quan.",
    "TC_SEARCH_12": "Từ khóa chuẩn trả về danh sách sản phẩm liên quan.",
    "TC_SEARCH_13": "Từ khóa có khoảng trắng đầu/cuối vẫn được xử lý đúng.",
    "TC_SEARCH_14": "Từ khóa có ký tự đặc biệt không làm trang lỗi và vẫn được xử lý an toàn.",
    "TC_SEARCH_15": "Từ khóa sai chính tả nhẹ vẫn trả về sản phẩm liên quan.",
    "TC_SEARCH_16": "Từ khóa bị tách khoảng trắng vẫn trả về kết quả hợp lệ.",
    "TC_SEARCH_17": "Từ khóa thừa ký tự cuối vẫn được hệ thống xử lý đúng kỳ vọng.",
    "TC_SEARCH_18": "Từ khóa thiếu ký tự vẫn trả về kết quả hợp lệ.",
    "TC_SEARCH_19": "Từ khóa lẫn số được xử lý an toàn và không làm trang lỗi.",
    "TC_SEARCH_20": "Không tìm thấy sản phẩm nhưng trang hiển thị trạng thái no-result hợp lệ.",
    "TC_SEARCH_21": "Payload XSS script không được thực thi trên trình duyệt.",
    "TC_SEARCH_22": "Payload XSS qua thẻ ảnh/onerror không được thực thi.",
    "TC_SEARCH_23": "Payload SQL OR 1=1 dạng nháy đơn được xử lý an toàn.",
    "TC_SEARCH_24": "Payload SQL OR 1=1 dạng nháy kép được xử lý an toàn.",
    "TC_SEARCH_25": "Payload SQL UNION NULL không làm lộ dữ liệu hoặc lỗi hệ thống.",
    "TC_SEARCH_26": "Payload SQL dò username/password không làm lộ dữ liệu nhạy cảm.",
    "TC_SEARCH_27": "Payload SQL UNION đóng ngoặc được xử lý an toàn.",
    "TC_SEARCH_28": "Payload SQL DROP TABLE không gây tác động phá hoại.",
    "TC_SEARCH_29": "Payload SQL admin comment không bypass hoặc trả dữ liệu bất thường.",
    "TC_FILTER_01": "Tất cả sản phẩm sau lọc phù hợp với thương hiệu đã chọn.",
    "TC_FILTER_02": "Bỏ lọc khôi phục danh sách sản phẩm về trạng thái hợp lệ.",
    "TC_FILTER_03": "Tổ hợp filter và keyword không tồn tại hiển thị trạng thái không có sản phẩm hợp lệ.",
    "TC_FILTER_04": "Bỏ một điều kiện lọc làm danh sách cập nhật đúng.",
    "TC_FILTER_05": "Trạng thái lọc vẫn được giữ sau khi reload trang.",
    "TC_FILTER_06": "Lọc rồi sắp xếp theo giá vẫn giữ đúng điều kiện lọc và thứ tự giá.",
    "TC_SORT_01": "Giá sản phẩm được sắp xếp đúng theo chiều tăng/giảm.",
    "TC_SORT_02": "Các tùy chọn sắp xếp không theo giá vẫn giữ danh sách hiển thị hợp lệ.",
    "TC_SORT_03": "Chuyển qua lại giữa các kiểu sắp xếp không làm mất kết quả.",
    "TC_SORT_04": "Trạng thái sắp xếp được bảo toàn sau reload và điều hướng.",
}

_TESTCASE_FAIL_CONCLUSIONS = {
    "TC_SEARCH_07": "Phát hiện defect: dữ liệu rất dài làm trình duyệt chậm, treo hoặc không thể thao tác tiếp.",
    "TC_SEARCH_20": "Không tìm thấy trạng thái no-result hợp lệ hoặc trang phản hồi sai khi không có sản phẩm.",
    "TC_SORT_02": "Thứ tự sản phẩm không thay đổi đúng kỳ vọng sau khi chọn sắp xếp.",
}


def _cell_text(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value = cell.find("a:v", _NS)
        if value is None or value.text is None:
            return ""
        return shared_strings[int(value.text)]
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", _NS))
    value = cell.find("a:v", _NS)
    return "" if value is None or value.text is None else value.text


def _read_shared_strings(zip_file):
    try:
        root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(text_node.text or "" for text_node in item.findall(".//a:t", _NS))
        for item in root.findall("a:si", _NS)
    ]


def _sheet_paths(zip_file):
    workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
    rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    paths = {}
    for sheet in workbook.findall(".//a:sheet", _NS):
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_by_id.get(rel_id, "")
        if target:
            paths[sheet.attrib["name"]] = "xl/" + target.lstrip("/")
    return paths


@lru_cache(maxsize=1)
def workbook_testcase_titles():
    """Return {testcase_id: title} from the generated Excel testcase workbook."""
    if not TESTCASE_WORKBOOK.exists():
        return {}

    testcase_titles = {}
    try:
        with zipfile.ZipFile(TESTCASE_WORKBOOK) as zip_file:
            shared_strings = _read_shared_strings(zip_file)
            for sheet_name, sheet_path in _sheet_paths(zip_file).items():
                if sheet_name.lower() in {"tong hop", "summary"}:
                    continue
                sheet_root = ET.fromstring(zip_file.read(sheet_path))
                rows = sheet_root.findall(".//a:sheetData/a:row", _NS)
                for row in rows:
                    values = [_cell_text(cell, shared_strings) for cell in row.findall("a:c", _NS)]
                    if len(values) >= 2 and re.fullmatch(r"TC_[A-Z]+_\d{2}", values[0] or ""):
                        testcase_titles[values[0]] = values[1]
    except Exception:
        return {}

    return testcase_titles


def _param_value(nodeid):
    match = re.search(r"\[(.*)\]$", nodeid)
    return match.group(1) if match else ""


def testcase_id_for_nodeid(nodeid):
    base_name = nodeid.rsplit("::", 1)[-1]
    function_name = base_name.split("[", 1)[0]
    param = _param_value(nodeid)

    if function_name == "test_search_variants_returns_relevant_results":
        return _SEARCH_VARIANT_IDS.get(param)
    if function_name == "test_search_typo_tolerance_returns_relevant_results":
        return _SEARCH_TYPO_IDS.get(param)
    if function_name == "test_search_xss_payload_is_sanitized":
        return _XSS_PAYLOAD_IDS.get(param)
    if function_name == "test_search_sql_payload_is_handled_safely":
        return _SQL_PAYLOAD_IDS.get(param)

    return _TESTCASE_ID_BY_FUNCTION.get(function_name)


def testcase_meta_for_nodeid(nodeid):
    testcase_id = testcase_id_for_nodeid(nodeid)
    if not testcase_id:
        return None
    title = workbook_testcase_titles().get(testcase_id, "")
    return {"id": testcase_id, "title": title, "workbook": str(TESTCASE_WORKBOOK)}


def testcase_conclusion_for_nodeid(nodeid, status):
    testcase_id = testcase_id_for_nodeid(nodeid)
    if not testcase_id:
        return None

    normalized_status = (status or "").upper()
    if normalized_status == "PASS":
        detail = _TESTCASE_PASS_CONCLUSIONS.get(testcase_id, "Kết quả thực tế phù hợp với kết quả mong đợi.")
        return f"✅ PASS - {testcase_id}: {detail}"
    if normalized_status == "FAIL":
        detail = _TESTCASE_FAIL_CONCLUSIONS.get(testcase_id, "Kết quả thực tế không phù hợp với kết quả mong đợi.")
        return f"❌ FAIL - {testcase_id}: {detail}"
    if normalized_status == "SKIP":
        return f"⏭️ SKIP - {testcase_id}: Không đủ điều kiện dữ liệu/giao diện để thực thi test case này."
    return f"ℹ️ {normalized_status} - {testcase_id}: Đã ghi nhận trạng thái kiểm thử."
