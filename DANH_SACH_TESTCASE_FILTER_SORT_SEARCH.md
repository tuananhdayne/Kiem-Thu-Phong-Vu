# Danh Sách Testcase Theo 3 Chức Năng Chính

Tài liệu này liệt kê các testcase hiện có trong dự án theo 3 chức năng chính: `filter`, `sort`, `search`.

Lưu ý:
- Một số testcase là testcase giao thoa giữa `filter` và `sort`, nên được ghi ở cả hai nhóm liên quan.
- Các testcase parameterized được tách thành từng case riêng nếu pytest collect ra nhiều item.

## 1. Filter

### Nhóm filter thuần
- `tests/filter/test_filter_advanced.py::test_filter_all_products_match_brand`
- `tests/filter/test_filter_advanced.py::test_unfilter_restores_list`
- `tests/filter/test_filter_advanced.py::test_filter_combination_no_results`
- `tests/test_regression_filter_sort_search.py::test_filter_multiple_conditions`

### Nhóm filter liên quan sort
- `tests/test_black_box_extended.py::test_filter_state_persists_after_reload`
- `tests/test_black_box_extended.py::test_filter_then_sort_price_keeps_filtered_sorted_results`
- `tests/test_regression_filter_sort_search.py::test_preserve_sort_state_on_reload_and_navigation`
- `tests/test_regression_filter_sort_search.py::test_sort_combined_with_filter_and_search`

## 2. Sort

### Nhóm sort thuần
- `tests/sort/test_sort_verification.py::test_sort_price_orders`
- `tests/sort/test_sort_verification.py::test_sort_changes_order_for_non_price_options`

### Nhóm sort liên quan filter/search
- `tests/test_black_box_extended.py::test_filter_then_sort_price_keeps_filtered_sorted_results`
- `tests/test_black_box_extended.py::test_search_then_sort_price_keeps_relevant_sorted_results`
- `tests/test_regression_filter_sort_search.py::test_preserve_sort_state_on_reload_and_navigation`
- `tests/test_regression_filter_sort_search.py::test_sort_combined_with_filter_and_search`

## 3. Search

### Search variants
- `tests/search/test_search_variants.py::test_search_variants_returns_relevant_results[logitech]`
- `tests/search/test_search_variants.py::test_search_variants_returns_relevant_results[Logitech]`
- `tests/search/test_search_variants.py::test_search_variants_returns_relevant_results[  Logitech  ]`
- `tests/search/test_search_variants.py::test_search_variants_returns_relevant_results[Logitech!@#]`
- `tests/search/test_search_variants.py::test_search_typo_tolerance_returns_relevant_results[Logitec]`
- `tests/search/test_search_variants.py::test_search_typo_tolerance_returns_relevant_results[Logit ech]`
- `tests/search/test_search_variants.py::test_search_typo_tolerance_returns_relevant_results[Logitechk]`
- `tests/search/test_search_variants.py::test_search_typo_tolerance_returns_relevant_results[Logtech]`
- `tests/search/test_search_variants.py::test_search_typo_tolerance_returns_relevant_results[Logit3ch]`
- `tests/search/test_search_variants.py::test_search_not_found_shows_no_results`

### Search functional
- `tests/search/test_search_functional.py::test_search_load_more_preserves_keyword`
- `tests/search/test_search_functional.py::test_search_deeplink_query_loads_correct_results`
- `tests/search/test_search_functional.py::test_search_autocomplete_suggestion_click_navigates_to_results`
- `tests/search/test_search_functional.py::test_search_enter_vs_click_icon_same_result`

### Search regression
- `tests/search/test_search_regression.py::test_search_vietnamese_accent_and_no_accent`
- `tests/search/test_search_regression.py::test_search_empty_query`
- `tests/search/test_search_regression.py::test_search_very_long_query`
- `tests/search/test_search_regression.py::test_search_repeated_long_input_does_not_blank_or_lag`
- `tests/search/test_search_regression.py::test_search_results_are_scoped_to_main_results_container`
- `tests/search/test_search_regression.py::test_search_change_keyword_updates_results`
- `tests/search/test_search_regression.py::test_search_then_sort_price_keeps_relevant_sorted_results`

### Search security
- `tests/search/test_search_security.py::test_search_xss_payload_is_sanitized[<script>alert(1)</script>]`
- `tests/search/test_search_security.py::test_search_xss_payload_is_sanitized["<img src=x onerror=alert(1)>]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely[' OR '1'='1]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely[" OR "1"="1]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely[' UNION SELECT NULL --]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely[' UNION SELECT username,password FROM users --]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely[') UNION SELECT NULL,NULL --]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely['; DROP TABLE products; --]`
- `tests/search/test_search_security.py::test_search_sql_payload_is_handled_safely[admin' --]`

## Tổng Kết Nhanh

- `filter`: 8 testcase
- `sort`: 6 testcase
- `search`: 30 testcase
- `tổng pytest collect`: 45 testcase

Nếu bạn muốn, tôi có thể tiếp tục tạo thêm một file dạng bảng gồm `Tên testcase | File | Mục tiêu | Kết quả mong đợi` để dễ review hơn.