from __future__ import annotations

import os
import re
import sys
import ast
import html
from datetime import timezone as _tz, timedelta
import time
from pathlib import Path

import streamlit as st
import json
from datetime import datetime
from subprocess import Popen, PIPE, STDOUT
import subprocess
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "report.html"
CHECKLIST_PATH = PROJECT_ROOT / "REGRESSION_CHECKLIST.md"
TESTS_DIR = PROJECT_ROOT / "tests"

RUN_HISTORY = REPORTS_DIR / "run_history.json"
SCREENSHOT_DIR = REPORTS_DIR / "screenshots"

MARKER_ORDER = ["smoke", "regression", "slow", "security", "destructive", "framework", "parametrize", "test"]
SAFE_MARKER_EXPR = "not destructive and not security and not framework"
BUSINESS_MARKER_EXPR = "not framework"


def _ordered_markers(markers: list[str]) -> list[str]:
    unique = []
    for marker in markers:
        if marker and marker not in unique:
            unique.append(marker)
    return sorted(unique, key=lambda marker: (MARKER_ORDER.index(marker) if marker in MARKER_ORDER else 99, marker))


def _test_business_description(name: str, doc: str, markers: list[str]) -> dict[str, str]:
    """Build dashboard-friendly test descriptions from test names and docstrings."""
    base_name = name.split("[", 1)[0]
    catalog = {
        "test_filter_apple_brand": {
            "goal": "Verify Apple brand filter on the laptop catalog.",
            "expected": "URL contains `brands=apple` and at least 3 visible products match Apple/MacBook.",
            "risk": "Prevents false pass where URL changes but product data is not actually filtered.",
        },
        "test_sort_price_low_to_high": {
            "goal": "Verify ascending price sort on the laptop catalog.",
            "expected": "Sort state is applied and visible prices are ordered from low to high.",
            "risk": "Prevents false pass where the sort button is clicked but the listing order is wrong.",
        },
        "test_search_logitech": {
            "goal": "Verify search with keyword Logitech.",
            "expected": "Top visible product names are relevant to Logitech.",
            "risk": "Prevents false pass from reading suggestions/header instead of real search results.",
        },
        "test_filter_all_products_match_brand": {
            "goal": "Verify every visible product after filtering matches the selected brand.",
            "expected": "The list updates and no visible product violates the selected brand rule.",
            "risk": "Stronger than checking only one random product.",
        },
        "test_unfilter_restores_list": {
            "goal": "Verify removing a filter restores a broader product list.",
            "expected": "Filter parameter is removed and products outside the previous brand can appear again.",
            "risk": "Catches sticky filter state after unchecking.",
        },
        "test_filter_combination_no_results": {
            "goal": "Verify filter plus impossible keyword shows a valid empty-result state.",
            "expected": "The page shows a no-result state instead of stale or unrelated products.",
            "risk": "Catches weak no-result UX and stale result rendering.",
        },
        "test_missing_selector_raises": {
            "goal": "Framework/internal: verify helper error handling for a missing selector.",
            "expected": "`first_visible` raises instead of silently passing.",
            "risk": "Not a direct Search/Filter/Sort business case; keep it out of the main business highlight.",
        },
        "test_slow_page_timeout": {
            "goal": "Framework/internal: verify explicit wait timeout behavior.",
            "expected": "The wait ends with the expected exception.",
            "risk": "Tests Selenium utility behavior, not user-facing Phong Vu behavior.",
        },
        "test_search_variants_returns_relevant_results": {
            "goal": "Verify search keyword variants: case, surrounding spaces, and special characters.",
            "expected": "Each valid variant returns results related to the normalized keyword.",
            "risk": "Catches weak input normalization.",
        },
        "test_search_not_found_shows_no_results": {
            "goal": "Verify a guaranteed non-existent keyword.",
            "expected": "The page shows a clear no-result message.",
            "risk": "Catches empty-state defects and unrelated fallback results.",
        },
        "test_sort_price_orders": {
            "goal": "Verify both ascending and descending price sort on the monitor catalog.",
            "expected": "Prices are ascending after asc sort and descending after desc sort.",
            "risk": "Catches one-direction sort bugs.",
        },
        "test_sort_changes_order_for_non_price_options": {
            "goal": "Verify non-price sort options such as best promotion, best selling, and newest.",
            "expected": "The option is applied and visible product order changes.",
            "risk": "This is a weaker oracle than price sort because business ranking is not directly observable.",
        },
        "test_filter_multiple_conditions": {
            "goal": "Verify applying multiple filter conditions together.",
            "expected": "Product list changes, remains non-empty, and does not grow unexpectedly.",
            "risk": "Catches broken combined-filter behavior.",
        },
        "test_preserve_sort_state_on_reload_and_navigation": {
            "goal": "Verify sort state survives reload and return navigation.",
            "expected": "Prices remain sorted after reload and after leaving/returning to the sorted URL.",
            "risk": "Catches lost query/state on reload or navigation.",
        },
        "test_search_vietnamese_accent_and_no_accent": {
            "goal": "Verify Vietnamese accented and unaccented search keywords.",
            "expected": "Both accented and unaccented terms return valid product results.",
            "risk": "Catches Vietnamese normalization defects.",
        },
        "test_search_empty_query": {
            "goal": "Verify blank/space-only search input.",
            "expected": "The path does not change incorrectly and the page remains usable.",
            "risk": "Catches blank-search redirect or layout breakage.",
        },
        "test_search_very_long_query": {
            "goal": "Verify the website handles an extremely long search keyword safely.",
            "expected": "PASS only when the page does not freeze, does not go blank, remains interactive, and shows results or a valid no-result state.",
            "risk": "FAIL when the page freezes, goes blank, stops rendering, cannot be interacted with, or lacks a valid no-result state. Destructive: run only with `--run-destructive`.",
        },
        "test_search_xss_payload_is_sanitized": {
            "goal": "Verify script-like search payloads are handled safely as plain user input.",
            "expected": "No browser alert/script execution, no blank page, and the result area ends in either valid products or a valid no-result state.",
            "risk": "Security payload test. Keep disabled on third-party live sites unless the target is authorized or a demo/mock environment.",
        },
        "test_search_sql_payload_is_handled_safely": {
            "goal": "Verify SQL-like search payloads are handled as plain text input.",
            "expected": "Boolean-based, union-based, and comment-style SQL payloads do not blank the page, leak database errors, or break the result/no-result state.",
            "risk": "Security payload test. Keep disabled on third-party live sites unless the target is authorized or a demo/mock environment.",
        },
        "test_search_change_keyword_updates_results": {
            "goal": "Verify changing from one search keyword to another refreshes the listing.",
            "expected": "Samsung results replace Logitech results and visible products are relevant to the new keyword.",
            "risk": "Catches stale search result state after users edit the keyword.",
        },
        "test_filter_state_persists_after_reload": {
            "goal": "Verify a selected brand filter survives page reload.",
            "expected": "Filtered URL/state remains after reload and visible products still match the selected brand.",
            "risk": "Catches lost filter state or unchecked UI state after refresh.",
        },
        "test_search_then_sort_price_keeps_relevant_sorted_results": {
            "goal": "Verify search results remain relevant after applying ascending price sort.",
            "expected": "Results still match the search keyword and visible prices are ascending.",
            "risk": "Catches sort resetting or corrupting search result scope.",
        },
        "test_filter_then_sort_price_keeps_filtered_sorted_results": {
            "goal": "Verify filtered listings remain filtered after applying ascending price sort.",
            "expected": "Visible products still match the selected brand and prices are ascending.",
            "risk": "Catches sort losing filter state or mixing unrelated products into the listing.",
        },
        "test_sort_combined_with_filter_and_search": {
            "goal": "Verify sort after filtering and on search-result pages.",
            "expected": "Prices remain correctly ascending in both filter + sort and search + sort flows.",
            "risk": "Catches sort logic that only works in isolation.",
        },
        "test_search_results_are_scoped_to_main_results_container": {
            "goal": "Verify product extraction is scoped to the main listing area.",
            "expected": "Products are found in the main results container and not confused with global/header elements.",
            "risk": "Reduces false pass from suggestions, header text, or unrelated page content.",
        },
    }

    result = catalog.get(base_name, {})
    if result:
        return result

    scope = " / ".join(_ordered_markers(markers)) or "test"
    first_line = doc.strip().splitlines()[0] if doc.strip() else "No detailed description."
    return {
        "goal": first_line,
        "expected": "See the test docstring for the exact pass condition.",
        "risk": f"Marker scope: {scope}.",
    }

def _render_test_discovery_card(meta: dict) -> None:
    markers_html = "".join(
        f'<span class="badge-marker {html.escape(m)}">{html.escape(m)}</span>'
        for m in meta["markers"]
    )
    desc = meta.get("description", {})
    goal = html.escape(desc.get("goal", "No goal description."))
    expected = html.escape(desc.get("expected", "No pass-condition description."))
    risk = html.escape(desc.get("risk", "No risk note."))
    raw_doc = html.escape(meta.get("doc", "No docstring."))
    source = html.escape(f"tests/{meta['file']}::{meta['name']}")
    st.markdown(f"""
        <div class="test-item-card">
            <div class="test-item-header">
                <span class="test-item-name"><code>{html.escape(meta['name'])}</code></span>
                <div class="test-item-badges">{markers_html}</div>
            </div>
            <div class="test-item-file">File: {source}</div>
            <div class="test-item-purpose-grid">
                <div class="test-purpose-box">
                    <div class="test-purpose-label">Goal</div>
                    <div class="test-purpose-text">{goal}</div>
                </div>
                <div class="test-purpose-box">
                    <div class="test-purpose-label">Expected Pass</div>
                    <div class="test-purpose-text">{expected}</div>
                </div>
                <div class="test-purpose-box">
                    <div class="test-purpose-label">Risk / Defect Signal</div>
                    <div class="test-purpose-text">{risk}</div>
                </div>
            </div>
            <div class="test-item-doc">Original docstring: {raw_doc}</div>
        </div>
    """, unsafe_allow_html=True)


def _load_history() -> list[dict]:
    try:
        if RUN_HISTORY.exists():
            return json.loads(RUN_HISTORY.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _append_history(entry: dict) -> None:
    history = _load_history()
    history.insert(0, entry)
    try:
        RUN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        RUN_HISTORY.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# Múi giờ Việt Nam UTC+7
def _sorted_pngs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(path.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)


def _failed_pngs(path: Path) -> list[Path]:
    return [
        p for p in _sorted_pngs(path)
        if "_failed_" in p.name or p.name.endswith("_failed.png")
    ]


def _artifact_screenshot_dirs() -> list[Path]:
    artifacts_root = REPORTS_DIR / "artifacts"
    dirs: list[Path] = []
    if artifacts_root.exists():
        for run_dir in artifacts_root.iterdir():
            screenshot_dir = run_dir / "screenshots"
            if run_dir.is_dir() and screenshot_dir.exists():
                dirs.append(screenshot_dir)
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs


def _latest_screenshot_dir(prefer_failed: bool = False) -> Path:
    artifacts_root = REPORTS_DIR / "artifacts"
    screenshots_path = SCREENSHOT_DIR

    run_history = _load_history()
    latest_run_id = run_history[0].get("run_id") if run_history else None
    if latest_run_id and latest_run_id != "-":
        candidate = artifacts_root / latest_run_id / "screenshots"
        if candidate.exists():
            if not prefer_failed or _failed_pngs(candidate):
                return candidate
            screenshots_path = candidate

    for candidate in _artifact_screenshot_dirs():
        if prefer_failed:
            if _failed_pngs(candidate):
                return candidate
        elif _sorted_pngs(candidate):
            return candidate

    return screenshots_path


VN_TZ = _tz(timedelta(hours=7))


def _format_time_vn(iso_str: str) -> str:
    """Chuyển đổi chuỗi ISO UTC sang giờ Việt Nam để hiển thị."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_vn = dt.astimezone(VN_TZ)
        return dt_vn.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return iso_str[:19].replace("T", " ")


def _run_with_streaming(command: list[str], cwd: Path, placeholder) -> dict:
    started = datetime.now(_tz.utc).isoformat().replace("+00:00", "Z")
    proc = Popen(command, cwd=str(cwd), stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace")
    out_lines = []
    try:
        for line in proc.stdout:
            out_lines.append(line)
            # keep last 500 lines to avoid huge memory
            placeholder.text(''.join(out_lines[-500:]))
    except Exception:
        pass
    proc.wait()
    ended = datetime.now(_tz.utc).isoformat().replace("+00:00", "Z")
    return {"returncode": proc.returncode, "stdout": ''.join(out_lines), "started": started, "ended": ended}


def _extract_parametrize_values(dec_node) -> list[str]:
    """Trích xuất danh sách tham số từ decorator @pytest.mark.parametrize."""
    params = []
    if not isinstance(dec_node, ast.Call):
        return params
    func = dec_node.func
    # Match: pytest.mark.parametrize(...)
    if not (isinstance(func, ast.Attribute) and func.attr == "parametrize"):
        return params
    if len(dec_node.args) < 2:
        return params
    values_node = dec_node.args[1]
    # values_node should be a list
    if isinstance(values_node, ast.List):
        for elt in values_node.elts:
            if isinstance(elt, ast.Constant):
                params.append(str(elt.value))
            elif isinstance(elt, (ast.List, ast.Tuple)):
                # parametrize with multiple args, use first element as label
                if elt.elts and isinstance(elt.elts[0], ast.Constant):
                    params.append(str(elt.elts[0].value))
                else:
                    params.append(f"param{len(params)}")
            else:
                params.append(f"param{len(params)}")
    return params


def discover_tests_metadata() -> dict[str, dict]:
    """Phát hiện toàn bộ test case sử dụng AST để trích xuất docstrings và markers.
    
    Tự động mở rộng các test được tham số hóa (@pytest.mark.parametrize) thành
    các mục riêng biệt, đảm bảo số lượng hiển thị khớp với số lượng pytest thực tế.
    """
    metadata = {}
    if not TESTS_DIR.exists():
        return metadata

    for file_path in sorted(TESTS_DIR.rglob("test_*.py")):
        try:
            rel_file = file_path.relative_to(TESTS_DIR).as_posix()
            content = file_path.read_text(encoding="utf-8").lstrip("\ufeff")
            tree = ast.parse(content, filename=file_path.name)
            
            # Module level markers (e.g. pytestmark = pytest.mark.smoke)
            module_markers = []
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "pytestmark":
                            val = node.value
                            if isinstance(val, ast.Attribute) and val.attr:
                                module_markers.append(val.attr)
                            elif isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute):
                                module_markers.append(val.func.attr)
                            elif isinstance(val, ast.List):
                                for elt in val.elts:
                                    if isinstance(elt, ast.Attribute):
                                        module_markers.append(elt.attr)
                                    elif isinstance(elt, ast.Call) and isinstance(elt.func, ast.Attribute):
                                        module_markers.append(elt.func.attr)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    doc = ast.get_docstring(node) or "Chưa có mô tả chi tiết."
                    
                    # Local function-level markers
                    local_markers = []
                    parametrize_values = []
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Attribute):
                            local_markers.append(dec.attr)
                        elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                            local_markers.append(dec.func.attr)
                            # Detect parametrize decorator and extract values
                            if dec.func.attr == "parametrize":
                                vals = _extract_parametrize_values(dec)
                                if vals:
                                    parametrize_values = vals
                    
                    all_markers = _ordered_markers(module_markers + local_markers)
                    if not all_markers:
                        if "smoke" in file_path.name:
                            all_markers.append("smoke")
                        elif "regression" in file_path.name:
                            all_markers.append("regression")
                        else:
                            all_markers.append("test")
                    all_markers = _ordered_markers(all_markers)

                    if parametrize_values:
                        # Tạo entry riêng cho từng biến thể tham số
                        for idx, param_val in enumerate(parametrize_values):
                            # Giữ nguyên giá trị param (kể cả khoảng trắng) để tránh trùng key
                            # Pytest sẽ dùng repr cho param có whitespace, ví dụ: "  Logitech  " -> "  Logitech  "
                            raw_param = str(param_val)
                            # Dùng index làm tie-breaker nếu 2 params giống nhau sau khi hiển thị
                            test_id = f"tests/{rel_file}::{node.name}[{raw_param}]"
                            if test_id in metadata:
                                test_id = f"tests/{rel_file}::{node.name}[{raw_param}-{idx}]"
                            description = _test_business_description(f"{node.name}[{raw_param}]", doc.strip(), all_markers + ["parametrize"])
                            metadata[test_id] = {
                                "doc": doc.strip(),
                                "description": description,
                                "file": rel_file,
                                "name": f"{node.name}[{raw_param}]",
                                "markers": _ordered_markers(all_markers + ["parametrize"]),
                            }
                    else:
                        test_id = f"tests/{rel_file}::{node.name}"
                        description = _test_business_description(node.name, doc.strip(), all_markers)
                        metadata[test_id] = {
                            "doc": doc.strip(),
                            "description": description,
                            "file": rel_file,
                            "name": node.name,
                            "markers": all_markers
                        }
        except Exception:
            pass
    return metadata



def discover_tests() -> list[str]:
    return list(discover_tests_metadata().keys())


@st.cache_data(ttl=20)
def collect_pytest_nodeids() -> list[str]:
    """Return pytest's real collected node ids, including parametrized cases."""
    try:
        cmd = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "tests",
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        lines = []
        for line in (proc.stdout or "").splitlines():
            text = line.strip()
            if text.startswith("tests/") and "::" in text:
                lines.append(text)
        return lines
    except Exception:
        return []


def _metadata_for_nodeid(nodeid: str, metadata: dict[str, dict]) -> dict:
    """Best-effort map from real pytest nodeid to AST metadata for labels."""
    normalized = nodeid.replace("\\", "/")
    if normalized in metadata:
        return metadata[normalized]
    base = normalized.split("[", 1)[0]
    for key, meta in metadata.items():
        key_norm = key.replace("\\", "/")
        if key_norm == normalized or key_norm.split("[", 1)[0] == base:
            return meta
    return {}


def _is_framework_nodeid(nodeid: str, metadata: dict[str, dict]) -> bool:
    return "framework" in _metadata_for_nodeid(nodeid, metadata).get("markers", [])


def _business_nodeids(nodeids: list[str], metadata: dict[str, dict]) -> list[str]:
    return [nodeid for nodeid in nodeids if not _is_framework_nodeid(nodeid, metadata)]


def _business_metadata_items(metadata: dict[str, dict]) -> list[tuple[str, dict]]:
    return [
        (test_id, meta)
        for test_id, meta in metadata.items()
        if "framework" not in meta.get("markers", [])
    ]


def _is_framework_result_case(test_case: dict, metadata: dict[str, dict]) -> bool:
    nodeid = f"tests/{test_case.get('classname', '')}.py::{test_case.get('name', '')}"
    return _is_framework_nodeid(nodeid, metadata)


def read_checklist_summary() -> dict[str, int]:
    summary = {"PASS": 0, "TODO": 0, "TONG": 0}
    try:
        content = CHECKLIST_PATH.read_text(encoding="utf-8")
    except Exception:
        return summary

    summary["PASS"] = len(re.findall(r"Status\s*:\s*✅\s*PASS", content))
    summary["TODO"] = len(re.findall(r"Status\s*:\s*⏳\s*TODO", content))
    summary["TONG"] = summary["PASS"] + summary["TODO"]
    return summary


def parse_junit_xml(xml_path: Path) -> list[dict]:
    import xml.etree.ElementTree as ET
    results = []
    if not xml_path.exists():
        return results
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        testcases = root.findall(".//testcase")
        for tc in testcases:
            classname = tc.get("classname", "")
            short_classname = classname.split(".")[-1]
            name = tc.get("name", "")
            duration = float(tc.get("time", "0.0"))
            
            status = "PASS"
            message = ""
            traceback = ""
            
            failure = tc.find("failure")
            error = tc.find("error")
            skipped = tc.find("skipped")
            
            if failure is not None:
                status = "FAIL"
                message = failure.get("message", "")
                traceback = failure.text or ""
            elif error is not None:
                status = "ERROR"
                message = error.get("message", "")
                traceback = error.text or ""
            elif skipped is not None:
                status = "SKIP"
                message = skipped.get("message", "")
                traceback = skipped.text or ""
                
            results.append({
                "classname": short_classname,
                "name": name,
                "duration": round(duration, 2),
                "status": status,
                "message": message,
                "traceback": traceback
            })
    except Exception as e:
        st.error(f"Lỗi phân tích kết quả XML: {e}")
    return results


def find_screenshot_for_test(test_name: str) -> Path | None:
    try:
        if not SCREENSHOT_DIR.exists():
            return None
        clean_name = re.sub(r"\[.*\]", "", test_name).strip()
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean_name).strip("_")
        
        for img_path in SCREENSHOT_DIR.glob("*.png"):
            if safe_name in img_path.name:
                return img_path
    except Exception:
        pass
    return None


def _target_args(custom_target: str | list[str]) -> list[str]:
    if isinstance(custom_target, list):
        return [target for target in custom_target if target]
    return custom_target.split() if custom_target else []


def _target_text(custom_target: str | list[str]) -> str:
    if isinstance(custom_target, list):
        return " ".join(custom_target)
    return custom_target or ""


def build_command(mode: str, custom_target: str | list[str], workers: int = 1, reruns: int = 2) -> list[str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    xml_report = REPORTS_DIR / "results.xml"
    custom_target_text = _target_text(custom_target)
    destructive_mode = mode in ("Destructive", "All including destructive/security") or "destructive" in custom_target_text.lower()
    if destructive_mode:
        reruns = 0

    command = [
        sys.executable, 
        "-m", 
        "pytest", 
        "--html=reports/report.html", 
        "--self-contained-html",
        f"--junitxml={xml_report}"
    ]
    
    # Ghi đè cấu hình mặc định trong pytest.ini nếu cần thiết
    command.extend(["-o", "addopts="])
    
    # Chạy song song dùng pytest-xdist nếu có cài đặt
    if workers > 1:
        try:
            import xdist
            command.extend(["-n", str(workers)])
        except ImportError:
            pass
        
    # Thử lại khi lỗi dùng pytest-rerunfailures nếu có cài đặt
    if reruns > 0:
        try:
            import pytest_rerunfailures
            command.extend(["--reruns", str(reruns), "--reruns-delay", "1"])
        except ImportError:
            pass
        
    command.extend(["-q"])

    # Chọn target test
    if mode == "Smoke nhanh":
        if custom_target:
            command.extend(_target_args(custom_target))
            command.extend(["-m", f"smoke and {SAFE_MARKER_EXPR}"])
        else:
            command.extend(["tests", "-m", f"smoke and {SAFE_MARKER_EXPR}"])
    elif mode == "Regression ưu tiên":
        if custom_target:
            command.extend(_target_args(custom_target))
            command.extend(["-m", f"regression and {SAFE_MARKER_EXPR}"])
        else:
            command.extend(["tests", "-m", f"regression and {SAFE_MARKER_EXPR}"])
    elif mode == "Full suite":
        if custom_target:
            command.extend(_target_args(custom_target))
            command.extend(["-m", SAFE_MARKER_EXPR])
        else:
            command.extend(["tests", "-m", SAFE_MARKER_EXPR])
    elif mode == "Security payload":
        if custom_target:
            command.extend(_target_args(custom_target))
            if "security" not in custom_target_text:
                command.extend(["-m", "security and not destructive and not framework"])
        else:
            command.extend(["tests", "-m", "security and not destructive and not framework"])
        command.extend(["--run-security"])
    elif mode == "Destructive":
        if custom_target:
            command.extend(_target_args(custom_target))
            if "destructive" not in custom_target_text:
                command.extend(["-m", "destructive and not security and not framework"])
        else:
            command.extend(["tests", "-m", "destructive and not security and not framework"])
        command.extend(["--run-destructive"])
    elif mode == "All including destructive/security":
        if custom_target:
            command.extend(_target_args(custom_target))
        else:
            command.extend(["tests"])
        command.extend(["-m", BUSINESS_MARKER_EXPR])
        command.extend(["--run-destructive", "--run-security"])
    elif mode == "Tùy chỉnh":
        targets = _target_args(custom_target)
        command.extend(targets or ["tests"])
        command.extend(["-m", BUSINESS_MARKER_EXPR])
    else:
        command.extend(["tests"])

    target_text = " ".join(command)
    marker_expr = ""
    for idx, part in enumerate(command[:-1]):
        if part == "-m":
            marker_expr = command[idx + 1]
    if (
        ("destructive" in marker_expr and "not destructive" not in marker_expr)
        or "test_search_very_long_query" in target_text
    ) and "--run-destructive" not in command:
        command.append("--run-destructive")
    if (
        ("security" in marker_expr and "not security" not in marker_expr)
        or "test_search_xss_payload_is_sanitized" in target_text
        or "test_search_sql_payload_is_handled_safely" in target_text
    ) and "--run-security" not in command:
        command.append("--run-security")
    return command


def style_app() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap');

        /* Set base styling */
        html, body, [class*="css"], .stMarkdown {
            font-family: 'Inter', sans-serif;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
        }

        /* Hero block style */
        .hero {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%);
            color: #ffffff;
            padding: 2.5rem;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }
        .hero::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 65%);
            pointer-events: none;
        }
        .hero h1 {
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            color: #ffffff !important;
            font-size: 2.6rem;
            margin: 0.5rem 0;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
            letter-spacing: -0.02em;
        }
        .hero p {
            font-family: 'Inter', sans-serif;
            color: #94a3b8 !important;
            font-size: 1.05rem;
            max-width: 850px;
            line-height: 1.6;
            margin: 0;
        }

        /* Pills inside hero */
        .pill-selenium {
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.85rem;
            margin-right: 0.5rem;
            border-radius: 99px;
            background: linear-gradient(135deg, #43B02A 0%, #368d21 100%);
            color: #ffffff !important;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            box-shadow: 0 4px 10px rgba(67, 176, 42, 0.3);
        }
        .pill-blue {
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.85rem;
            margin-right: 0.5rem;
            border-radius: 99px;
            background: rgba(255, 255, 255, 0.1);
            color: #cbd5e1 !important;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: 1px solid rgba(255, 255, 255, 0.12);
        }

        /* Premium Metric Cards */
        .metric-card {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.12);
            border-radius: 16px;
            padding: 1.25rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            margin-bottom: 1rem;
        }
        .metric-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.12);
            border-color: rgba(128, 128, 128, 0.25);
        }
        .metric-card.total { border-left: 5px solid #6366f1; }
        .metric-card.pass { border-left: 5px solid #10b981; }
        .metric-card.todo { border-left: 5px solid #f59e0b; }
        .metric-card.discovered { border-left: 5px solid #06b6d4; }

        .metric-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 0.4rem;
        }
        .metric-icon {
            font-size: 1.3rem;
        }
        .metric-label {
            font-size: 0.8rem;
            color: var(--text-color);
            opacity: 0.7;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .metric-value {
            font-size: 2.2rem;
            font-weight: 800;
            color: var(--text-color);
            line-height: 1.1;
            margin-bottom: 0.25rem;
            font-family: 'Outfit', sans-serif;
        }
        .metric-footer {
            font-size: 0.7rem;
            color: var(--text-color);
            opacity: 0.5;
        }

        /* Test item discovered cards */
        .test-item-card {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.12);
            border-radius: 12px;
            padding: 0.85rem 1.1rem;
            margin-bottom: 0.75rem;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .test-item-card:hover {
            border-color: rgba(128, 128, 128, 0.25);
            transform: translateX(4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        .test-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 0.3rem;
        }
        .test-item-name {
            font-weight: 600;
            color: var(--text-color);
            font-size: 0.95rem;
        }
        .test-item-file {
            font-size: 0.75rem;
            color: var(--text-color);
            opacity: 0.5;
            margin-bottom: 0.3rem;
        }
        .test-item-doc {
            font-size: 0.85rem;
            color: var(--text-color);
            opacity: 0.8;
            border-left: 2px solid rgba(128, 128, 128, 0.2);
            padding-left: 8px;
            margin-top: 0.3rem;
        }
        .test-item-purpose-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin-top: 0.65rem;
        }
        .test-purpose-box {
            background: rgba(128, 128, 128, 0.06);
            border: 1px solid rgba(128, 128, 128, 0.10);
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
            min-height: 74px;
        }
        .test-purpose-label {
            color: #38bdf8;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }
        .test-purpose-text {
            color: var(--text-color);
            font-size: 0.82rem;
            line-height: 1.45;
            opacity: 0.88;
        }
        @media (max-width: 900px) {
            .test-item-purpose-grid {
                grid-template-columns: 1fr;
            }
        }
        .badge-marker {
            display: inline-block;
            padding: 0.15rem 0.45rem;
            font-size: 0.65rem;
            font-weight: 700;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-left: 4px;
        }
        .badge-marker.smoke {
            background-color: rgba(16, 185, 129, 0.12);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.25);
        }
        .badge-marker.regression {
            background-color: rgba(99, 102, 241, 0.12);
            color: #6366f1;
            border: 1px solid rgba(99, 102, 241, 0.25);
        }
        .badge-marker.test {
            background-color: rgba(6, 182, 212, 0.12);
            color: #06b6d4;
            border: 1px solid rgba(6, 182, 212, 0.25);
        }
        .badge-marker.framework {
            background-color: rgba(148, 163, 184, 0.12);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.25);
        }
        .badge-marker.security {
            background-color: rgba(245, 158, 11, 0.14);
            color: #d97706;
            border: 1px solid rgba(245, 158, 11, 0.32);
        }
        .badge-marker.destructive {
            background-color: rgba(239, 68, 68, 0.12);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.25);
        }

        /* Custom Progress Bar for run results */
        .progress-bar-container {
            display: flex;
            height: 16px;
            width: 100%;
            background-color: rgba(128, 128, 128, 0.1);
            border-radius: 99px;
            overflow: hidden;
            margin: 1.25rem 0 0.75rem 0;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }
        .progress-segment {
            height: 100%;
            transition: width 0.5s ease;
        }
        .progress-segment.pass {
            background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        }
        .progress-segment.fail {
            background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
        }
        .progress-segment.skip {
            background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
        }
        .progress-legend {
            display: flex;
            gap: 16px;
            margin-bottom: 1.5rem;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }
        .legend-dot.pass { background-color: #10b981; }
        .legend-dot.fail { background-color: #ef4444; }
        .legend-dot.skip { background-color: #f59e0b; }

        /* Monospace terminal style for logs */
        div[data-baseweb="textarea"] textarea {
            font-family: 'Fira Code', 'Consolas', monospace !important;
            background-color: #0b0f19 !important;
            color: #38bdf8 !important;
            border: 1px solid rgba(56, 189, 248, 0.15) !important;
            box-shadow: inset 0 4px 12px rgba(0,0,0,0.6) !important;
            line-height: 1.6 !important;
            padding: 1.25rem !important;
            border-radius: 12px !important;
        }

        /* Streamlit Expander design */
        div[data-styled-state="closed"] > div, div[data-styled-state="open"] > div {
            border-radius: 12px !important;
        }

        /* Glassmorphic Radio / selectbox tweaks */
        div[data-baseweb="radio"] label {
            padding: 8px 12px !important;
            border-radius: 8px !important;
            transition: background 0.2s ease;
        }
        div[data-baseweb="radio"] label:hover {
            background: rgba(128,128,128,0.08) !important;
        }

        /* Run button customizing */
        div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #43B02A 0%, #368F21 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 0.8rem 1.8rem !important;
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.03em !important;
            box-shadow: 0 4px 15px rgba(67, 176, 42, 0.35) !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            width: 100%;
        }
        div.stButton > button[kind="primary"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(67, 176, 42, 0.55) !important;
            background: linear-gradient(135deg, #368F21 0%, #2b721a 100%) !important;
        }
        div.stButton > button[kind="primary"]:active {
            transform: translateY(0px) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Selenium Test Studio", page_icon="🧪", layout="wide")
    style_app()

    checklist = read_checklist_summary()
    discovered_metadata = discover_tests_metadata()
    business_metadata = dict(_business_metadata_items(discovered_metadata))
    discovered_tests = list(business_metadata.keys())
    collected_tests = collect_pytest_nodeids()
    business_collected_tests = _business_nodeids(collected_tests, discovered_metadata)
    source_test_count = len(business_collected_tests) if business_collected_tests else len(discovered_tests)

    st.markdown(
        """
        <div class="hero">
            <div class="pill-selenium">Selenium</div>
            <div class="pill-blue">Pytest</div>
            <div class="pill-blue">Chrome Headless</div>
            <h1 style="margin: 0.35rem 0 0.5rem 0;">Selenium Test Studio 🧪</h1>
            <p style="margin: 0;">
                Hệ thống kiểm thử tự động Selenium hoàn chỉnh cho Phong Vũ. Hỗ trợ chạy song song đa luồng, theo dõi trực quan kết quả thực thi và tự động chụp ảnh màn hình khi phát hiện lỗi.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Project học tập/kiểm thử độc lập, không phải hệ thống chính thức của Phong Vũ. Các chế độ an toàn không chạy destructive/security payload mặc định.")
    
    st.write("")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
            <div class="metric-card total">
                <div class="metric-header">
                    <span class="metric-icon">📋</span>
                    <span class="metric-label">Tổng Checklist</span>
                </div>
                <div class="metric-value">{checklist["TONG"]}</div>
                <div class="metric-footer">Mục tiêu kiểm thử</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class="metric-card pass">
                <div class="metric-header">
                    <span class="metric-icon">✅</span>
                    <span class="metric-label">PASS Checklist</span>
                </div>
                <div class="metric-value">{checklist["PASS"]}</div>
                <div class="metric-footer">Đã hoàn thành</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div class="metric-card todo">
                <div class="metric-header">
                    <span class="metric-icon">⏳</span>
                    <span class="metric-label">TODO Checklist</span>
                </div>
                <div class="metric-value">{checklist["TODO"]}</div>
                <div class="metric-footer">Cần kiểm thử lại</div>
            </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
            <div class="metric-card discovered">
                <div class="metric-header">
                    <span class="metric-icon">🔍</span>
                    <span class="metric-label">Mã nguồn Tests</span>
                </div>
                <div class="metric-value">{source_test_count}</div>
                <div class="metric-footer">Test cases tìm thấy</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    left, right = st.columns([0.45, 0.55], gap="large")

    with left:
        st.subheader("⚙️ Điều khiển chạy Test")
        
        mode_display = st.radio(
            "Chọn phạm vi kiểm thử ưu tiên:", 
            [
                "Smoke nhanh (Khuyên dùng)",
                "Regression đầy đủ",
                "Full suite an toàn (không destructive/security)",
                "Destructive only",
                "Security payload only",
                "Tất cả bao gồm destructive/security",
                "Tùy chỉnh",
            ], 
            index=2
        )
        
        mode_mapping = {
            "Smoke nhanh (Khuyên dùng)": "Smoke nhanh",
            "Regression đầy đủ": "Regression ưu tiên",
            "Full suite an toàn (không destructive/security)": "Full suite",
            "Destructive only": "Destructive",
            "Security payload only": "Security payload",
            "Tất cả bao gồm destructive/security": "All including destructive/security",
            "Tùy chỉnh": "Tùy chỉnh"
        }
        actual_mode = mode_mapping[mode_display]

        if actual_mode == "Smoke nhanh":
            st.info("💡 **Gợi ý:** Chạy 'Smoke nhanh' để kiểm tra các luồng chính yếu (như tìm kiếm, lọc Apple, sort giá) trước khi tích hợp code.")
        elif actual_mode == "Full suite":
            st.info("💡 **Gợi ý:** Full suite an toàn chạy toàn bộ test thường và loại cả `destructive` lẫn `security`, nên long-query và payload bảo mật sẽ không xuất hiện trong kết quả.")
        elif actual_mode == "Security payload":
            st.warning("⚠️ Chế độ này chỉ dành cho môi trường được ủy quyền/demo/mock. Không chạy security payload trên website bên thứ ba nếu chưa có phép.")
        elif actual_mode == "Destructive":
            st.warning("⚠️ Chế độ này chỉ chạy test destructive như long-query. Chrome có thể nặng hoặc treo nếu defect được tái hiện.")
        elif actual_mode == "All including destructive/security":
            st.warning("⚠️ Chế độ này chạy cả test thường, destructive và security payload. Chỉ dùng trên target được ủy quyền hoặc môi trường demo/mock.")

        custom_target = ""
        selected_tests = []
        description = st.text_input("Mô tả lần chạy (tuỳ chọn)", value="", help="Ghi chú ngắn để mô tả mục đích lần chạy này")
        
        if actual_mode == "Tùy chỉnh":
            with st.expander("🎯 Chọn Test Case cụ thể", expanded=True):
                selectable_tests = business_collected_tests or discovered_tests
                if selectable_tests:
                    selected_tests = st.multiselect(
                        "Click chọn một hoặc nhiều test để chạy:",
                        selectable_tests,
                        format_func=lambda x: (
                            f"{x.split('::')[-1]} - "
                            f"{_metadata_for_nodeid(x, discovered_metadata).get('doc', 'Không có mô tả')}"
                        ),
                        max_selections=50
                    )
                custom_target = st.text_input("Hoặc nhập target Pytest thủ công (ví dụ: tests/test_cases.py):")

        with st.expander("🛠 Cấu hình nâng cao (Hiệu năng & Trình duyệt)", expanded=False):
            browser_mode = st.radio(
                "Chế độ trình duyệt",
                [
                    "Headless - chạy ẩn, nhanh nhất",
                    "Headful - hiện Chrome để quan sát",
                ],
                index=0,
                help="Chọn Headful nếu muốn thấy Chrome mở lên và trang web chạy như khi gõ pytest bằng dòng lệnh.",
            )
            headless = browser_mode.startswith("Headless")
            if not headless:
                st.info("Chế độ Headful sẽ hiện Chrome trên màn hình và tự ép Workers = 1 để dễ quan sát, tránh mở nhiều tab/cửa sổ.")
            col_opts1, col_opts2 = st.columns(2)
            workers = col_opts1.number_input("Số luồng song song (Workers)", min_value=1, max_value=8, value=3, help="Khuyên dùng 3 luồng để cân bằng tốc độ và độ ổn định. Quá nhiều luồng có thể gây nghẽn CPU/RAM hoặc khiến website tải chậm!")
            timeout = col_opts2.number_input("Timeout chờ (s)", min_value=3, max_value=120, value=10, help="Thời gian chờ tìm phần tử DOM. KHÔNG nên đặt dưới 5s!")
            reruns = st.number_input("Thử lại khi lỗi (Flaky Retries)", min_value=0, max_value=5, value=2, help="Tự động thử lại để khắc phục lỗi mạng hoặc tải trang chậm ngẫu nhiên.")
            
            if timeout < 5:
                st.warning("⚠️ **Timeout quá thấp!** Trang web thực tế cần ít nhất 5-10s để load hoàn tất. Timeout quá thấp dễ gây lỗi giả.")
            if workers > 5:
                st.warning("⚠️ **Nhiều luồng quá!** Nhiều luồng chạy cùng lúc có thể khiến server Phong Vũ hạn chế IP hoặc nghẽn tài nguyên. Khuyên dùng tối đa 4 luồng.")

            # Điều khiển tải ảnh để giúp debug giao diện: Headless ưu tiên tốc độ, Headful ưu tiên quan sát thật.
            load_images = st.checkbox(
                "Tải ảnh (hiển thị hình ảnh trên trang)",
                value=not headless,
                key=f"load_images_{'headless' if headless else 'headful'}",
                help="Bật để trình duyệt tải ảnh; tắt để tăng tốc.",
            )
            save_on_pass = st.checkbox("Lưu screenshot khi PASS (traceability)", value=False, help="Lưu screenshot và page source khi test PASS để chứng minh hành vi.")

        st.write("")
        run_clicked = st.button("🚀 CHẠY KIỂM THỬ NGAY", type="primary", use_container_width=True)

    with right:
        st.subheader("ℹ️ Thông tin hệ thống")
        tab_history, tab_screens, tab_artifacts, tab_discovered = st.tabs(["📜 Lịch sử chạy", "📸 Ảnh chụp lỗi gần đây", "📂 Ảnh artifacts", "🔍 Test phát hiện"])

        with tab_history:
            history = _load_history()
            if history:
                for i, h in enumerate(history[:8]):
                    when_raw = h.get('time', '')
                    when = _format_time_vn(when_raw)
                    mode_h = h.get('mode', '')
                    rc = h.get('returncode', '')
                    dur = h.get('duration', '')
                    
                    st.markdown(f"**[{when}]** — **{mode_h}**")
                    col_a, col_b = st.columns([1, 4])
                    if rc == 0:
                        col_a.success("PASS")
                    else:
                        col_a.error(f"FAIL")
                    # Show target, duration and description if present
                    desc = h.get('description', '')
                    gitc = h.get('git_commit', h.get('git', '-'))
                    runid = h.get('run_id', '-')
                    caption_lines = [f"⏱️ {dur}s | 🎯 Target: {h.get('target', 'All')}"]
                    if desc:
                        caption_lines.append(f"📝 {desc}")
                    caption_lines.append(f"🔖 commit: {gitc} | id: {runid}")
                    col_b.caption(' | '.join(caption_lines))
                    st.divider()
            else:
                st.info('Chưa có lịch sử chạy')
                
        # Tab: show only FAILED screenshots from latest run
        with tab_screens:
            try:
                screenshots_path = _latest_screenshot_dir(prefer_failed=True)
                failed_imgs = _failed_pngs(screenshots_path)

                if failed_imgs:
                    st.markdown(f"**Hiển thị ảnh FAILED từ:** {str(screenshots_path.relative_to(PROJECT_ROOT))}")
                    cols = st.columns(2)
                    for idx, img in enumerate(failed_imgs[:12]):
                        with cols[idx % 2]:
                            st.image(str(img), caption=img.name, use_container_width=True)
                            # Show page/console links if exist
                            try:
                                run_dir = screenshots_path.parent
                                pages_dir = run_dir / "pages"
                                console_dir = run_dir / "console"
                                base_key = img.name.rsplit('.', 1)[0]
                                page_candidates = list(pages_dir.glob(f"{base_key}*.html")) if pages_dir.exists() else []
                                console_candidates = list(console_dir.glob(f"{base_key}*_console.json")) if console_dir.exists() else []
                                links = []
                                if page_candidates:
                                    links.append(f"[Page HTML]({page_candidates[0].as_posix()})")
                                if console_candidates:
                                    links.append(f"[Console log]({console_candidates[0].as_posix()})")
                                if links:
                                    st.markdown(" | ".join(links))
                            except Exception:
                                pass
                else:
                    st.success('Không có ảnh FAILED trong lần chạy gần nhất.')
            except Exception:
                st.info('Không thể đọc thư mục screenshots')
            
        # Tab: show ALL artifacts (passed + failed) for latest run
        with tab_artifacts:
            try:
                screenshots_path = _latest_screenshot_dir(prefer_failed=False)
                run_dir = screenshots_path.parent
                pages_dir = run_dir / "pages"
                console_dir = run_dir / "console"

                imgs = _sorted_pngs(screenshots_path)

                if imgs:
                    st.markdown(f"**Hiển thị tất cả ảnh artifacts từ:** {str(screenshots_path.relative_to(PROJECT_ROOT))}")
                    cols = st.columns(2)
                    for idx, img in enumerate(imgs[:48]):
                        with cols[idx % 2]:
                            fname = img.name
                            status = "PASS" if ("_passed_" in fname or fname.endswith("_passed.png")) else ("FAIL" if ("_failed_" in fname or fname.endswith("_failed.png")) else "UNK")
                            st.image(str(img), caption=f"{fname} — {status}", use_container_width=True)
                            try:
                                base_key = fname.rsplit('.', 1)[0]
                                page_candidates = list(pages_dir.glob(f"{base_key}*.html")) if pages_dir.exists() else []
                                console_candidates = list(console_dir.glob(f"{base_key}*_console.json")) if console_dir.exists() else []
                                links = []
                                if page_candidates:
                                    links.append(f"[Page HTML]({page_candidates[0].as_posix()})")
                                if console_candidates:
                                    links.append(f"[Console log]({console_candidates[0].as_posix()})")
                                if links:
                                    st.markdown(" | ".join(links))
                            except Exception:
                                pass
                else:
                    st.info('Không có artifacts cho lần chạy gần nhất.')
            except Exception:
                st.info('Không thể đọc artifacts')

        with tab_discovered:
            if business_metadata:
                st.markdown(f"Phát hiện **{source_test_count}** test cases từ mã nguồn:")
                if business_collected_tests and len(business_metadata) != source_test_count:
                    st.caption(
                        f"Đếm theo pytest collect thực tế: {source_test_count}. "
                        f"Metadata mô tả từ AST: {len(business_metadata)} mục."
                    )
                st.markdown("#### Kiểm thử chức năng website: Search / Filter / Sort")
                for test_id, meta in [
                    (k, v)
                    for k, v in business_metadata.items()
                    if "framework" not in v.get("markers", [])
                    and "security" not in v.get("markers", [])
                    and "destructive" not in v.get("markers", [])
                ]:
                    markers_html = "".join(
                        f'<span class="badge-marker {html.escape(m)}">{html.escape(m)}</span>'
                        for m in meta["markers"]
                    )
                    desc = meta.get("description", {})
                    goal = html.escape(desc.get("goal", "Chưa có mô tả mục tiêu."))
                    expected = html.escape(desc.get("expected", "Chưa có mô tả điều kiện pass."))
                    risk = html.escape(desc.get("risk", "Chưa có ghi chú rủi ro."))
                    raw_doc = html.escape(meta.get("doc", "Chưa có docstring."))
                    source = html.escape(f"tests/{meta['file']}::{meta['name']}")
                    st.markdown(f"""
                        <div class="test-item-card">
                            <div class="test-item-header">
                                <span class="test-item-name"><code>{html.escape(meta['name'])}</code></span>
                                <div class="test-item-badges">{markers_html}</div>
                            </div>
                            <div class="test-item-file">📁 {source}</div>
                            <div class="test-item-purpose-grid">
                                <div class="test-purpose-box">
                                    <div class="test-purpose-label">Mục tiêu</div>
                                    <div class="test-purpose-text">{goal}</div>
                                </div>
                                <div class="test-purpose-box">
                                    <div class="test-purpose-label">Kỳ vọng pass</div>
                                    <div class="test-purpose-text">{expected}</div>
                                </div>
                                <div class="test-purpose-box">
                                    <div class="test-purpose-label">Rủi ro bắt lỗi</div>
                                    <div class="test-purpose-text">{risk}</div>
                                </div>
                            </div>
                            <div class="test-item-doc">Docstring gốc: {raw_doc}</div>
                        </div>
                    """, unsafe_allow_html=True)

                risky_items = [
                    meta
                    for meta in business_metadata.values()
                    if "security" in meta.get("markers", []) or "destructive" in meta.get("markers", [])
                ]
                if risky_items:
                    st.markdown("#### Security/destructive payload tests")
                    st.caption("Cac test nay khong chay mac dinh tren website ben thu ba; chi chay khi co phep hoac tren moi truong demo/mock.")
                    for meta in risky_items:
                        _render_test_discovery_card(meta)
            else:
                st.warning("Chưa phát hiện test nào trong thư mục tests/.")

    st.markdown("---")
    
    if run_clicked:
        if selected_tests:
            target = selected_tests
        else:
            target = custom_target if actual_mode == "Tùy chỉnh" else ""
        target_text = _target_text(target)
            
        # Generate run id and try to get git commit for traceability
        run_id = str(uuid.uuid4())
        os.environ["RUN_ID"] = run_id
        git_commit = "-"
        try:
            git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(PROJECT_ROOT), text=True).strip()
        except Exception:
            git_commit = os.environ.get("GIT_COMMIT", "-")
        os.environ["GIT_COMMIT"] = git_commit

        if headless:
            os.environ["SELENIUM_HEADLESS"] = "1"
        else:
            os.environ.pop("SELENIUM_HEADLESS", None)

        # Kiểm soát chặn ảnh: SELENIUM_BLOCK_IMAGES (0 = allow, 1 = block)
        if load_images:
            os.environ["SELENIUM_BLOCK_IMAGES"] = "0"
        else:
            os.environ["SELENIUM_BLOCK_IMAGES"] = "1"

        # Save screenshot on pass flag
        if save_on_pass:
            os.environ["SELENIUM_SAVE_PASS"] = "1"
        else:
            os.environ.pop("SELENIUM_SAVE_PASS", None)

        # Export description so pytest run (CLI) can record it too
        if description:
            os.environ["SELENIUM_RUN_DESCRIPTION"] = description
        else:
            os.environ.pop("SELENIUM_RUN_DESCRIPTION", None)

        # If running headful (visible), force single worker so browsers appear in GUI
        if not headless and int(workers) != 1:
            st.info("Chế độ hiển thị yêu cầu 'Workers = 1' để cửa sổ trình duyệt hiển thị. Hệ thống đã đặt Workers = 1 cho lần chạy này.")
            workers = 1

        has_destructive = (
            actual_mode in ("Destructive", "All including destructive/security")
            or "destructive" in target_text.lower()
            or "test_search_very_long_query" in target_text
        )
        if has_destructive:
            if int(reruns) != 0:
                st.info("Chế độ có destructive test được ép Retries = 0. Dashboard sẽ mở Chrome riêng cho từng test và kill ngay sau test để tránh treo RAM.")
            reruns = 0
            os.environ["SELENIUM_ISOLATE_EACH_TEST"] = "1"
            os.environ.pop("SELENIUM_WORKER_BROWSER", None)
        else:
            os.environ["SELENIUM_ISOLATE_EACH_TEST"] = "1"
            os.environ.pop("SELENIUM_WORKER_BROWSER", None)

        os.environ["SELENIUM_TIMEOUT"] = str(int(timeout))
        if actual_mode == "Destructive" or (
            actual_mode != "All including destructive/security"
            and ("destructive" in target_text.lower() or "test_search_very_long_query" in target_text)
        ):
            os.environ["SELENIUM_COMMAND_TIMEOUT"] = "4"
            os.environ["DESTRUCTIVE_SCRIPT_TIMEOUT"] = "2"
            os.environ["DESTRUCTIVE_MAX_RESPONSE_SECONDS"] = "8"
            os.environ["VERY_LONG_COMMAND_TIMEOUT"] = "4"
            os.environ["VERY_LONG_QUERY_CHUNK_SIZE"] = "2000000"
            os.environ["VERY_LONG_QUERY_ITERATIONS"] = "20"
            os.environ["VERY_LONG_SAVE_PROGRESS_EVERY"] = "2"
            os.environ["SELENIUM_CAPTURE_DESTRUCTIVE_ARTIFACTS"] = "1"
            os.environ["SELENIUM_CAPTURE_DESTRUCTIVE_SCREENSHOT"] = "1"
        elif actual_mode == "All including destructive/security":
            os.environ["SELENIUM_COMMAND_TIMEOUT"] = "30"
            os.environ["DESTRUCTIVE_SCRIPT_TIMEOUT"] = "2"
            os.environ["DESTRUCTIVE_MAX_RESPONSE_SECONDS"] = "8"
            os.environ["VERY_LONG_COMMAND_TIMEOUT"] = "8"
            os.environ["VERY_LONG_QUERY_CHUNK_SIZE"] = "2000000"
            os.environ["VERY_LONG_QUERY_ITERATIONS"] = "20"
            os.environ["VERY_LONG_SAVE_PROGRESS_EVERY"] = "2"
            os.environ["SELENIUM_CAPTURE_DESTRUCTIVE_ARTIFACTS"] = "1"
            os.environ["SELENIUM_CAPTURE_DESTRUCTIVE_SCREENSHOT"] = "1"
        else:
            os.environ["SELENIUM_COMMAND_TIMEOUT"] = "30"
            os.environ.pop("DESTRUCTIVE_SCRIPT_TIMEOUT", None)
            os.environ.pop("DESTRUCTIVE_MAX_RESPONSE_SECONDS", None)
            os.environ.pop("VERY_LONG_COMMAND_TIMEOUT", None)
            os.environ.pop("VERY_LONG_QUERY_CHUNK_SIZE", None)
            os.environ.pop("VERY_LONG_QUERY_ITERATIONS", None)
            os.environ.pop("VERY_LONG_SAVE_PROGRESS_EVERY", None)
            os.environ.pop("SELENIUM_CAPTURE_DESTRUCTIVE_ARTIFACTS", None)
            os.environ.pop("SELENIUM_CAPTURE_DESTRUCTIVE_SCREENSHOT", None)
        os.environ["STREAMLIT_DASHBOARD_RUN"] = "1"

        cmd = build_command(actual_mode, target, int(workers), int(reruns))
        # Attach run metadata to command string for logs (not required by pytest)
        
        st.markdown("### ⏳ Đang thực thi kiểm thử...")
        placeholder = st.empty()
        
        start = time.perf_counter()
        run_res = _run_with_streaming(cmd, PROJECT_ROOT, placeholder)
        duration = round(time.perf_counter() - start, 2)

        result_obj = {
            "returncode": run_res.get("returncode", 1),
            "duration": duration,
            "stdout": run_res.get("stdout", ""),
            "stderr": run_res.get("stderr", ""),
            "command": " ".join(cmd),
        }
        st.session_state["last_result"] = result_obj

        hist_entry = {
            "time": datetime.now(_tz.utc).isoformat().replace("+00:00", "Z"),
            "run_id": os.environ.get("RUN_ID", "-"),
            "git_commit": os.environ.get("GIT_COMMIT", "-"),
            "mode": f"{actual_mode}",
            "target": target_text if target_text else "tests (all)",
            "description": description if description else "",
            "workers": int(workers),
            "headless": bool(headless),
            "returncode": result_obj["returncode"],
            "duration": result_obj["duration"],
        }
        _append_history(hist_entry)

        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()

    result = st.session_state.get("last_result")
    if result:
        st.markdown("### 📊 Kết quả lần chạy gần nhất")
        status_col, time_col, code_col = st.columns(3)
        if result["returncode"] == 0:
            status_col.success("🎉 Trạng thái: PASS (Thành công)")
        elif result["returncode"] == 5:
            status_col.warning("⚠️ Trạng thái: KHÔNG CÓ TEST NÀO ĐƯỢC CHẠY")
        else:
            status_col.error("❌ Trạng thái: FAIL (Có lỗi xảy ra)")
            
        time_col.metric("⏱️ Thời gian thực thi", f"{result['duration']}s")
        code_col.metric("💻 Exit code", result["returncode"])

        st.write("")
        tab1, tab2, tab3 = st.tabs(["📑 Chi tiết Test Cases", "📝 Logs hệ thống (stdout)", "⚠️ Logs lỗi (stderr)"])
        
        with tab1:
            xml_report = REPORTS_DIR / "results.xml"
            if xml_report.exists():
                test_cases = parse_junit_xml(xml_report)
                test_cases = [
                    tc for tc in test_cases
                    if not _is_framework_result_case(tc, discovered_metadata)
                ]
                if test_cases:
                    col_f1, col_f2 = st.columns([2, 1])
                    search_query = col_f1.text_input("🔍 Tìm kiếm Test Case (Tên hoặc File):", "")
                    status_filter = col_f2.selectbox(
                        "Lọc theo trạng thái:", 
                        ["Tất cả", "Thành công (PASS)", "Lỗi (FAIL/ERROR)", "Bỏ qua (SKIP)"]
                    )
                    
                    filtered_cases = []
                    for tc in test_cases:
                        full_name = f"{tc['classname']}::{tc['name']}"
                        if search_query.lower() not in full_name.lower():
                            continue
                        if status_filter == "Thành công (PASS)" and tc["status"] != "PASS":
                            continue
                        if status_filter == "Lỗi (FAIL/ERROR)" and tc["status"] not in ("FAIL", "ERROR"):
                            continue
                        if status_filter == "Bỏ qua (SKIP)" and tc["status"] != "SKIP":
                            continue
                        filtered_cases.append(tc)
                    
                    from collections import defaultdict
                    grouped_cases = defaultdict(list)
                    for tc in filtered_cases:
                        grouped_cases[tc["classname"]].append(tc)
                    
                    total_all = len(test_cases)
                    passed_filtered = sum(1 for tc in filtered_cases if tc["status"] == "PASS")
                    failed_filtered = sum(1 for tc in filtered_cases if tc["status"] in ("FAIL", "ERROR"))
                    skipped_filtered = sum(1 for tc in filtered_cases if tc["status"] == "SKIP")
                    total_filtered = len(filtered_cases)
                    
                    # Custom progress bar
                    if total_filtered > 0:
                        pass_pct = (passed_filtered / total_filtered) * 100
                        fail_pct = (failed_filtered / total_filtered) * 100
                        skip_pct = (skipped_filtered / total_filtered) * 100
                        
                        st.markdown(f"""
                            <div class="progress-bar-container">
                                <div class="progress-segment pass" style="width: {pass_pct}%" title="PASS: {passed_filtered}"></div>
                                <div class="progress-segment fail" style="width: {fail_pct}%" title="FAIL/ERROR: {failed_filtered}"></div>
                                <div class="progress-segment skip" style="width: {skip_pct}%" title="SKIP: {skipped_filtered}"></div>
                            </div>
                            <div class="progress-legend">
                                <span class="legend-item"><span class="legend-dot pass"></span> PASS: {passed_filtered} ({pass_pct:.1f}%)</span>
                                <span class="legend-item"><span class="legend-dot fail"></span> FAIL: {failed_filtered} ({fail_pct:.1f}%)</span>
                                <span class="legend-item"><span class="legend-dot skip"></span> SKIP: {skipped_filtered} ({skip_pct:.1f}%)</span>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown(
                        f"Hiển thị **{total_filtered}** / {total_all} test cases "
                        f"(🟢 **{passed_filtered}** PASS | 🔴 **{failed_filtered}** FAIL | 🟡 **{skipped_filtered}** SKIP)"
                    )
                    st.write("")
                    
                    if not filtered_cases:
                        st.info("Không tìm thấy test case nào khớp với bộ lọc.")
                    
                    for classname, cases in grouped_cases.items():
                        st.markdown(f"📂 **Thành phần:** `{classname}.py`")
                        for tc in cases:
                            if tc["status"] == "PASS":
                                icon = "🟢"
                                status_color = "green"
                                badge = "PASS"
                            elif tc["status"] in ("FAIL", "ERROR"):
                                icon = "🔴"
                                status_color = "red"
                                badge = tc["status"]
                            else:
                                icon = "🟡"
                                status_color = "orange"
                                badge = "SKIP"
                            
                            label = f"{icon} {tc['name']} ({tc['duration']}s)"
                            
                            with st.expander(label):
                                test_id = f"tests/{tc['classname']}.py::{tc['name']}"
                                docstring = discovered_metadata.get(test_id, {}).get("doc", "Chưa có mô tả chi tiết.")
                                
                                st.markdown(f"**Mô tả:** *{docstring}*")
                                st.markdown(f"**Đường dẫn:** `{tc['classname']}::{tc['name']}`")
                                st.markdown(f"**Thời gian chạy:** `{tc['duration']} giây`")
                                st.markdown(f"**Trạng thái:** :{status_color}[{badge}]")
                                
                                if tc["status"] in ("FAIL", "ERROR"):
                                    st.error(f"**Chi tiết lỗi:** {tc['message']}")
                                    if tc["traceback"]:
                                        st.code(tc["traceback"], language="python")
                                    
                                    screenshot_path = find_screenshot_for_test(tc["name"])
                                    if screenshot_path and screenshot_path.exists():
                                        st.image(str(screenshot_path), caption=f"Ảnh chụp màn hình lỗi: {screenshot_path.name}")
                                    else:
                                        st.info("Không tìm thấy ảnh chụp màn hình lỗi của case này.")
                                        
                                elif tc["status"] == "SKIP":
                                    st.warning(f"**Lý do bỏ qua:** {tc['message'] or 'Không rõ'}")
                else:
                    st.info("Không có dữ liệu test cases trong file XML.")
            else:
                st.info("Chưa có kết quả test cases. Hãy chạy kiểm thử bằng nút bấm phía trên để xem chi tiết.")
                
        with tab2:
            st.text_area("Đầu ra hệ thống:", value=str(result["stdout"]).strip() or "(Không có output)", height=400)
            
        with tab3:
            st.text_area("Lỗi hệ thống:", value=str(result["stderr"]).strip() or "(Không có lỗi)", height=400)


if __name__ == "__main__":
    main()
