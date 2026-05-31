# Regression Checklist — Bộ Kiểm Thử Phongvu.vn

**Ngày tạo**: 13-05-2026  
**Trạng thái Smoke Test**: ✅ Ổn định (82.66s, 3/3 PASS)  
**Mục tiêu**: Bộ kiểm tra regression đầy đủ theo quy trình tester chuyên nghiệp

---

## I. NHÓM FILTER (Lọc Sản Phẩm)

### ✓ 1.1 Lọc theo 1 điều kiện
- **Test Case**: `test_filter_apple_brand`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Vào trang Laptop
  2. Nhấp checkbox "Apple" trong bộ lọc Thương hiệu
  3. Chờ trang reload
- **Kỳ vọng**:
  - URL chứa `brands=apple`
  - Tất cả sản phẩm hiển thị chứa từ khóa "Apple" hoặc "MacBook"
  - Danh sách sản phẩm thay đổi so với lúc chưa lọc
- **Status**: ✅ PASS

### ☐ 1.2 Bỏ lọc
- **Test Case**: `test_unfilter_restores_list`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Áp dụng filter Apple (checkbox checked)
  2. Nhấp lại checkbox để bỏ filter
  3. Chờ trang reload
- **Kỳ vọng**:
  - Checkbox không được chọn (unchecked)
  - Danh sách sản phẩm trở lại trạng thái ban đầu
  - Có sản phẩm không phải Apple trong kết quả
- **Status**: ✅ PASS

### ☐ 1.3 Lọc nhiều điều kiện
- **Test Case**: `test_filter_combination_...`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Chọn filter Thương hiệu: Apple
  2. Chọn filter Dòng CPU: Apple M-series
  3. Chọn filter Giá: 10,000,000 - 50,000,000
- **Kỳ vọng**:
  - URL chứa multiple parameters: `brands=apple&cpu=...&price=...`
  - Tất cả sản phẩm thỏa mãn tất cả 3 điều kiện
  - Số lượng sản phẩm giảm đáng kể so với lọc 1 điều kiện
- **Status**: ⏳ TODO

### ☐ 1.4 Lọc không có kết quả
- **Test Case**: `test_filter_combination_no_results`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Chọn filter Thương hiệu: Apple
  2. Search từ khóa vô nghĩa: `noresults_xyz_98765`
- **Kỳ vọng**:
  - Kết quả rỗng hoặc thông báo "Không tìm thấy sản phẩm"
  - URL chứa cả filter và search keyword
- **Status**: ✅ PASS

### ☐ 1.5 Chuyển trang vẫn giữ filter
- **Test Case**: `test_filter_pagination_...`
- **URL**: `https://phongvu.vn/c/laptop?brands=apple`
- **Bước**:
  1. Áp dụng filter Apple
  2. Scroll xuống, nhấp nút trang tiếp theo (page 2)
- **Kỳ vọng**:
  - URL vẫn giữ `brands=apple`
  - Tất cả sản phẩm trang 2 vẫn là Apple
- **Status**: ⏳ TODO

---

## II. NHÓM SORT (Sắp Xếp Sản Phẩm)

### ✓ 2.1 Giá thấp → cao
- **Test Case**: `test_sort_price_low_to_high`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Vào trang Laptop
  2. Nhấp vào "Sắp xếp theo" → Chọn "Giá thấp đến cao"
  3. Chờ trang reload
- **Kỳ vọng**:
  - URL chứa `sort=SORT_BY_PRICE&order=ASC`
  - Danh sách giá sản phẩm được sắp xếp tăng dần: [a, b, c] với a ≤ b ≤ c
  - Ít nhất 2 sản phẩm để so sánh
- **Status**: ✅ PASS (23.30s)

### ☐ 2.2 Giá cao → thấp
- **Test Case**: `test_sort_price_high_to_low`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Vào trang Laptop
  2. Nhấp vào "Sắp xếp theo" → Chọn "Giá cao đến thấp"
- **Kỳ vọng**:
  - URL chứa `sort=SORT_BY_PRICE&order=DESC`
  - Danh sách giá giảm dần: [z, y, x] với z ≥ y ≥ x
- **Status**: ⏳ TODO

### ☐ 2.3 Bán chạy
- **Test Case**: `test_sort_best_selling`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Chọn "Bán chạy" từ dropdown Sắp xếp
- **Kỳ vọng**:
  - URL chứa `sort=BEST_SELLING` (hoặc tương tự)
  - Sản phẩm được sắp xếp theo lượng bán
- **Status**: ⏳ TODO

### ☐ 2.4 Mới nhất
- **Test Case**: `test_sort_newest`
- **URL**: `https://phongvu.vn/c/laptop`
- **Bước**:
  1. Chọn "Mới nhất" từ dropdown Sắp xếp
- **Kỳ vọng**:
  - URL chứa `sort=NEWEST` (hoặc tương tự)
  - Sản phẩm được sắp xếp theo ngày thêm mới
- **Status**: ⏳ TODO

### ☐ 2.5 Reload trang vẫn giữ sort
- **Test Case**: `test_sort_persistence_...`
- **URL**: `https://phongvu.vn/c/laptop?sort=SORT_BY_PRICE&order=ASC`
- **Bước**:
  1. Áp dụng sort Giá tăng dần
  2. Reload trang (F5 hoặc Ctrl+R)
- **Kỳ vọng**:
  - Trang vẫn hiển thị sort Giá tăng dần
  - URL vẫn giữ sort parameters
- **Status**: ⏳ TODO

---

## III. NHÓM SEARCH (Tìm Kiếm Sản Phẩm)

### ✓ 3.1 Search từ khóa hợp lệ
- **Test Case**: `test_search_logitech`
- **URL**: `https://phongvu.vn` (homepage)
- **Bước**:
  1. Vào trang chủ
  2. Nhấp vào ô tìm kiếm
  3. Gõ "Logitech" → Nhấp Enter hoặc nút Search
- **Kỳ vọng**:
  - URL chứa search parameter: `?q=logitech` (hoặc tương tự)
  - Kết quả chứa sản phẩm Logitech
  - Ít nhất 3-5 sản phẩm được trả về
- **Status**: ✅ PASS

### ☐ 3.2 Search chữ thường/chữ hoa
- **Test Case**: `test_search_case_insensitive`
- **URL**: `https://phongvu.vn`
- **Bước**:
  1. Search "logitech" (chữ thường)
  2. Search "LOGITECH" (chữ hoa)
  3. Search "Logitech" (hỗn hợp)
- **Kỳ vọng**:
  - Tất cả 3 tìm kiếm trả về kết quả giống nhau
  - Không phân biệt hoa/thường
- **Status**: ⏳ TODO

### ☐ 3.3 Search có khoảng trắng
- **Test Case**: `test_search_with_spaces`
- **URL**: `https://phongvu.vn`
- **Bước**:
  1. Search "  Logitech  " (có khoảng trắng đầu/cuối)
- **Kỳ vọng**:
  - Kết quả giống với "Logitech" (không có khoảng trắng)
  - Trim whitespace tự động
- **Status**: ⏳ TODO

### ☐ 3.4 Search ký tự đặc biệt
- **Test Case**: `test_search_special_chars`
- **URL**: `https://phongvu.vn`
- **Bước**:
  1. Search "Logitech!@#" (có ký tự đặc biệt)
- **Kỳ vọng**:
  - Hệ thống xử lý gracefully (không crash)
  - Trả về kết quả Logitech hoặc thông báo không tìm thấy
- **Status**: ⏳ TODO

### ☐ 3.5 Search không có kết quả
- **Test Case**: `test_search_no_results`
- **URL**: `https://phongvu.vn`
- **Bước**:
  1. Search "nonexistentsku12345" (từ khóa vô nghĩa)
- **Kỳ vọng**:
  - Kết quả rỗng
  - Hiển thị thông báo "Không tìm thấy sản phẩm"
  - URL chứa search keyword vô lý
- **Status**: ⏳ TODO

---

## IV. NHÓM UI/UX (Giao Diện Người Dùng)

### ☐ 4.1 Sản phẩm có tên
- **Verification**: Mỗi sản phẩm trong danh sách phải hiển thị tên rõ ràng
- **Selector**: `div.att-product-card-title` hoặc tương tự
- **Status**: ⏳ TODO

### ☐ 4.2 Sản phẩm có giá
- **Verification**: Mỗi sản phẩm phải hiển thị giá rõ ràng
- **Selector**: `[class*='att-product-detail-latest-price']` hoặc tương tự
- **Status**: ⏳ TODO

### ☐ 4.3 Sản phẩm có ảnh
- **Verification**: Mỗi sản phẩm phải có ảnh thumbnail
- **Selector**: `img[class*='product-image']` hoặc tương tự
- **Status**: ⏳ TODO

### ☐ 4.4 Có nút mua/xem chi tiết
- **Verification**: Mỗi sản phẩm có nút "Xem chi tiết", "Thêm giỏ hàng", hoặc tương tự
- **Selector**: `button[class*='add-to-cart']` hoặc `a[href*='/p/']`
- **Status**: ⏳ TODO

### ☐ 4.5 Có phản hồi khi loading
- **Verification**: Khi lọc/sort/search, hiển thị loading indicator
- **Selector**: `div[class*='spinner']` hoặc `div[class*='loading']`
- **Status**: ⏳ TODO

---

## V. TÓNG KẾT STATUS

| Nhóm | Tổng | PASS | TODO | Tỷ lệ |
|------|------|------|------|-------|
| **Filter** | 5 | 2 | 3 | 40% |
| **Sort** | 5 | 1 | 4 | 20% |
| **Search** | 5 | 1 | 4 | 20% |
| **UI/UX** | 5 | 0 | 5 | 0% |
| **TOTAL** | 20 | 4 | 16 | 20% |

---

## VI. KẾ HOẠCH TIẾP THEO

### Giai đoạn 3 — Mở Rộng Automation (Tuần sau)

**Nhóm 1: Search Regression** (3-4 tests)
```
- test_search_case_insensitive
- test_search_with_spaces
- test_search_special_chars
- test_search_no_results
```

**Nhóm 2: Filter Regression** (3-4 tests)
```
- test_filter_multi_criteria
- test_filter_pagination
- test_filter_no_results_ui
```

**Nhóm 3: Sort Regression** (2-3 tests)
```
- test_sort_price_desc
- test_sort_best_selling
- test_sort_persistence
```

**Nhóm 4: UI/UX Validation** (3-4 tests)
```
- test_product_elements_visibility (tên, giá, ảnh)
- test_loading_states
- test_responsive_layout (desktop/mobile)
```

---

## VII. GHI CHÚ KỸ THUẬT

### Timeout Hiện Tại
- **Smoke Test**: 3s (implicit wait)
- **Selector Lookup**: 3-10s (WebDriverWait)
- **Product Extraction**: 3s

### Browser Config
- Chrome headless (tùy chọn)
- Window size: 1920x1080
- Disable GPU, Sandbox

### Screenshot Policy
- ✅ Chỉ chụp khi **FAIL**
- ✅ Không chụp khi **PASS**
- ✅ Lưu vào: `reports/screenshots/`

---

**Cập nhật lần cuối**: 13-05-2026 00:28  
**Người tạo**: QA Automation Team
