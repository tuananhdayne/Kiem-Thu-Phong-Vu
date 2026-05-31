# Hướng Dẫn Kiểm Thử Tự Động Phong Vũ — Selenium + Pytest 🧪

Tài liệu này hướng dẫn cách thiết lập, vận hành và quản lý bộ kiểm thử tự động (Automation Test Suite) sử dụng **Selenium** kết hợp **Pytest** và giao diện **Streamlit Dashboard** cho trang web thương mại điện tử Phong Vũ (`phongvu.vn`).

---

## 📋 Mục Lục
1. [Hướng Dẫn Cài Đặt & Khởi Chạy](#-hướng-dẫn-cài-đặt--khởi-chạy)
2. [Sử Dụng Giao Diện Streamlit Dashboard](#-sử-dụng-giao-diện-streamlit-dashboard)
3. [Cấu Trúc Thư Mục & Chức Năng](#-cấu-trúc-thư-mục--chức-năng)
4. [Chi Tiết Các Kịch Bản Kiểm Thử (Test Cases)](#-chi-tiết-các-kịch-bản-kiểm-thử-test-cases)
5. [Cơ Chế Báo Cáo & Ảnh Chụp Lỗi](#-cơ-chế-báo-cáo--ảnh-chụp-lỗi)
6. [Quản Lý & Tùy Biến Cấu Hình](#-quản-lý--tùy-biến-cấu-hình)

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Kích Hoạt Môi Trường Virtual Environment
Môi trường Python ảo (venv) đã được thiết lập sẵn trong thư mục dự án:
```powershell
# Di chuyển đến thư mục dự án
cd "d:\Kiem Thu"

# Kích hoạt venv trên Windows (PowerShell)
.venv\Scripts\activate
```

### 2. Cài Đặt Các Thư Viện Cần Thiết
Cập nhật thư viện từ file `requirements.txt` và (nếu muốn) cài thêm `webdriver-manager` để quản lý driver tự động:
```powershell
# Cài đặt thư viện Python
pip install -r requirements.txt

# (Tùy chọn) cài webdriver-manager để tự động tải driver
pip install webdriver-manager
```

Lưu ý: Selenium 4.10+ tích hợp Selenium Manager, có thể tự động tải WebDriver cho Chrome/Edge/Firefox. Nếu muốn kiểm soát driver thủ công, dùng `webdriver-manager` hoặc tải ChromeDriver tương ứng với phiên bản trình duyệt.

### 3. Chạy Kiểm Thử Từ Command Line (CLI)
Bạn có thể chạy các kịch bản kiểm thử trực tiếp bằng lệnh `pytest`:

* **Chạy toàn bộ test suite (tất cả tests trong `tests/`):**
  ```powershell
  pytest tests/ -o addopts="" -v --tb=short
  ```

* **Chạy các test case thuộc nhóm Smoke (Luồng chính quan trọng):**
  ```powershell
  pytest tests/ -m smoke -v
  ```

* **Chạy các test case thuộc nhóm Regression (Bộ kiểm thử hồi quy chi tiết):**
  ```powershell
  pytest tests/ -m regression -v
  ```

* **Chạy song song (Parallel) để tăng tốc (nếu pytest-xdist được cài):**
  ```powershell
  pytest tests/ -n 4 -v
  ```

---

## 🖥️ Sử Dụng Giao Diện Streamlit Dashboard

Streamlit Dashboard cung cấp một giao diện web trực quan giúp bạn chạy test, xem logs thời gian thực, xem lịch sử chạy và xem chi tiết lỗi kèm ảnh chụp màn hình.

### 1. Khởi Chạy Dashboard
```powershell
# Chạy dashboard chính (file dashboard.py nằm ở gốc repo)
streamlit run dashboard.py --server.port 8501

# Hoặc chạy trên cổng 8502 nếu cần
streamlit run dashboard.py --server.port 8502
```

*Sau khi chạy, dashboard sẽ mở trên `http://localhost:8501` hoặc `http://localhost:8502` tùy cổng bạn chọn.*

### 2. Các Tính Năng Trên Dashboard
* **Định cấu hình chạy nhanh:** Chọn chế độ chạy (Full suite, Smoke, Regression, hoặc chọn thủ công từng Test Case cụ thể).
* **Cấu hình nâng cao:** Tắt/mở giao diện trình duyệt (`Headless`), tùy chỉnh số luồng chạy song song (`Workers`), thời gian Timeout, và số lần thử lại khi lỗi (`Flaky Retries`).
* **Lịch sử chạy:** Xem kết quả các lần kiểm thử trước đó, thời gian thực thi, và tỷ lệ thành công.
* **Ảnh chụp màn hình lỗi:** Xem danh sách ảnh chụp màn hình của các lỗi xuất hiện trong quá trình kiểm thử gần nhất.
* **Chi tiết Test Cases:** Xem cây thư mục chứa các test cases, click vào từng case để xem chi tiết thông báo lỗi (Assertion Message) và Traceback nếu case đó bị fail.

---

## 📂 Cấu Trúc Thư Mục & Chức Năng

Bộ test Selenium được tổ chức quanh thư mục `tests/` và các tài nguyên hỗ trợ ở gốc repo:
```
d:\Kiem Thu\
├── config.json              # (Tùy chọn) Chứa thông tin cấu hình selector CSS/XPath, URLs và dữ liệu test
├── conftest.py              # Định nghĩa các fixtures dùng chung (WebDriver, session, logging)
├── dashboard.py             # Streamlit Dashboard để chạy & xem kết quả
├── pytest.ini               # Cấu hình mặc định của pytest (đăng ký các markers: smoke, regression, slow)
├── reports/                 # Thư mục chứa báo cáo và kết quả chạy test
│   ├── results.xml          # Kết quả chạy định dạng JUnit XML
│   ├── report.html          # Báo cáo HTML tự động tạo bởi pytest-html
│   └── screenshots/         # Nơi lưu ảnh chụp màn hình tự động khi có test case bị FAILED
└── tests/                   # Thư mục chứa các tệp kịch bản kiểm thử chính (Selenium)
  ├── filter/
  │   └── test_filter_advanced.py
  ├── search/
  │   ├── test_search_functional.py
  │   ├── test_search_regression.py
  │   ├── test_search_security.py
  │   └── test_search_variants.py
  ├── smoke/
  │   └── test_cases.py
  ├── sort/
  │   └── test_sort_verification.py
  ├── test_black_box_extended.py
  ├── test_negative_cases.py
  └── test_regression_filter_sort_search.py
```

---

## 📝 Chi Tiết Các Kịch Bản Kiểm Thử (Test Cases)

Bộ kiểm thử tập trung vào **3 chức năng cốt lõi**: **Lọc sản phẩm (Filter)**, **Sắp xếp sản phẩm (Sort)**, và **Tìm kiếm sản phẩm (Search)**.

(Phần mô tả chi tiết test case giữ nguyên, tương tự nội dung trước)

---

## 📸 Cơ Chế Báo Cáo & Ảnh Chụp Lỗi

1. **Báo cáo HTML:** Sau mỗi lượt chạy bằng Streamlit hoặc lệnh Pytest, một báo cáo HTML tự đóng gói (`reports/report.html`) sẽ được xuất ra. Báo cáo này hiển thị trực quan biểu đồ, thời gian chạy chi tiết của từng test case.
2. **Ảnh chụp màn hình lỗi:** Khi một test case bị **FAILED**, fixture trong `conftest.py` sẽ chụp màn hình trình duyệt bằng Selenium và lưu vào thư mục `reports/screenshots/`. Tên ảnh thường chứa tên test case để dễ tra cứu.
3. **Traceback chi tiết:** Bạn có thể xem log lỗi chi tiết (Traceback) trực tiếp ngay trên giao diện Streamlit Dashboard hoặc mở file báo cáo HTML.

---

## ⚙️ Quản Lý & Tùy Biến Cấu Hình

Tất cả các selectors CSS/XPath, đường dẫn trang web và dữ liệu kiểm thử nên được tập trung trong tệp cấu hình **`config.json`** ở gốc repo. Khi giao diện trang web Phong Vũ thay đổi, bạn chỉ cần cập nhật selector trong file JSON này mà không cần sửa đổi mã nguồn Python.

Ví dụ `config.json`:
```json
{
  "base_url": "https://phongvu.vn",
  "pages": {
    "laptop": "https://phongvu.vn/c/laptop",
    "monitor": "https://phongvu.vn/c/man-hinh-may-tinh"
  },
  "selectors": {
    "search_input": "input[type='search'], input[placeholder*='Tìm kiếm']",
    "product_card_title": "a h3, div.att-product-card-title",
    "product_price": "[class*='att-product-detail-latest-price'], [class*='price']"
  },
  "test_data": {
    "brand_to_filter": "Apple",
    "search_keyword": "Logitech"
  }
}
```

---

Chúc bạn thực hiện kiểm thử thành công và ổn định!
