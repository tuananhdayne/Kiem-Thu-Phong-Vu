# Bảng Test Case Theo Chức Năng

Nguồn dữ liệu: kết quả `pytest --collect-only` hiện tại trong thư mục `tests`.

Tổng số test case phát hiện trong phạm vi 3 chức năng: **39**.

Ghi chú:
- Báo cáo này chỉ liệt kê test case thuộc 3 chức năng chính: **Tìm kiếm**, **Lọc**, **Sắp xếp**.
- Hai testcase kiểm tra helper/framework nội bộ không được đưa vào bảng vì không thuộc phạm vi chức năng người dùng.
- Các test có tính phá hủy/bảo mật vẫn được liệt kê trong nhóm Tìm kiếm để báo cáo đầy đủ, nhưng chỉ nên chạy khi có chủ đích.

## 1. Chức năng Tìm Kiếm (Search)

| Mã TC | Tên Test Case | Mục tiêu | Dữ liệu đầu vào (Input) | Các bước thực hiện | Kết quả mong đợi | Mức độ |
|---|---|---|---|---|---|---|
| TC_SEARCH_01 | Tìm kiếm và xem thêm giữ nguyên từ khóa | Kiểm tra nút xem thêm không làm mất từ khóa tìm kiếm | `Logitech` | Vào trang chủ; nhập từ khóa; thực hiện tìm kiếm; nhấn xem thêm sản phẩm | Danh sách sản phẩm tăng thêm và từ khóa tìm kiếm ban đầu vẫn được giữ | High |
| TC_SEARCH_02 | Truy cập deeplink tìm kiếm | Kiểm tra URL tìm kiếm trực tiếp hiển thị đúng kết quả | URL tìm kiếm với `Logitech` | Mở trực tiếp URL có query tìm kiếm; chờ kết quả tải | Trang hiển thị sản phẩm liên quan đến từ khóa | High |
| TC_SEARCH_03 | Gợi ý autocomplete điều hướng đến kết quả | Kiểm tra click gợi ý tìm kiếm chuyển đến trang kết quả | Từ khóa gợi ý | Nhập từ khóa; chờ autocomplete; click một gợi ý | Trình duyệt điều hướng sang trang kết quả phù hợp | Medium |
| TC_SEARCH_04 | So sánh Enter và click icon tìm kiếm | Kiểm tra hai cách submit tìm kiếm cho kết quả tương đương | `Logitech` | Tìm kiếm bằng phím Enter; lưu kết quả; tìm kiếm lại bằng icon; so sánh | Hai cách thao tác đều hiển thị kết quả liên quan, không rỗng | High |
| TC_SEARCH_05 | Tìm kiếm tiếng Việt có dấu và không dấu | Kiểm tra khả năng xử lý từ khóa tiếng Việt | Từ khóa có dấu/không dấu | Nhập từng biến thể từ khóa; thực hiện tìm kiếm; đọc danh sách sản phẩm | Kết quả liên quan vẫn hiển thị ổn định | Medium |
| TC_SEARCH_06 | Tìm kiếm rỗng | Kiểm tra hệ thống không lỗi khi submit ô tìm kiếm rỗng | Chuỗi rỗng | Vào trang chủ; để trống ô tìm kiếm; submit | Trang không crash, không hiển thị lỗi giao diện nghiêm trọng | Medium |
| TC_SEARCH_07 | Tìm kiếm chuỗi rất dài | Kiểm tra khả năng chịu tải input cực dài và phát hiện treo | Chuỗi rất dài, thao tác paste lặp | Nhập/paste chuỗi lớn vào ô tìm kiếm; tiếp tục paste đến khi không thêm được; thử click sản phẩm | Test ghi nhận số lần paste, độ dài input và trạng thái click sau khi quá tải | Critical |
| TC_SEARCH_08 | Kết quả tìm kiếm nằm đúng vùng kết quả chính | Kiểm tra parser không lấy nhầm text ngoài danh sách sản phẩm | `Logitech` | Tìm kiếm; xác định vùng kết quả chính; trích tên sản phẩm trong vùng đó | Danh sách lấy được nằm trong container kết quả chính | High |
| TC_SEARCH_09 | Đổi từ khóa cập nhật kết quả | Kiểm tra thay đổi keyword làm mới danh sách sản phẩm | Hai từ khóa tìm kiếm khác nhau | Tìm keyword thứ nhất; lưu kết quả; đổi keyword; tìm lại | Kết quả sau khi đổi từ khóa được cập nhật, không giữ danh sách cũ | High |
| TC_SEARCH_10 | Tìm kiếm rồi sắp xếp theo giá | Kiểm tra kết quả tìm kiếm vẫn liên quan sau khi sort | `Logitech`, sort giá | Tìm kiếm keyword; chọn sắp xếp theo giá; đọc tên và giá sản phẩm | Sản phẩm vẫn liên quan keyword và giá được sắp đúng | High |
| TC_SEARCH_11 | Từ khóa viết thường | Kiểm tra tìm kiếm không phân biệt chữ hoa/thường | `logitech` | Nhập từ khóa; submit; đọc sản phẩm | Kết quả có sản phẩm liên quan Logitech | Medium |
| TC_SEARCH_12 | Từ khóa viết chuẩn | Kiểm tra tìm kiếm keyword chuẩn | `Logitech` | Nhập từ khóa; submit; đọc sản phẩm | Kết quả có sản phẩm liên quan Logitech | Medium |
| TC_SEARCH_13 | Từ khóa có khoảng trắng đầu/cuối | Kiểm tra hệ thống xử lý trim khoảng trắng | `  Logitech  ` | Nhập từ khóa có khoảng trắng; submit | Kết quả vẫn liên quan Logitech | Medium |
| TC_SEARCH_14 | Từ khóa có ký tự đặc biệt | Kiểm tra xử lý ký tự đặc biệt trong keyword | `Logitech!@#` | Nhập từ khóa; submit; đọc kết quả | Trang không lỗi, kết quả vẫn liên quan hoặc xử lý an toàn | Medium |
| TC_SEARCH_15 | Tìm kiếm typo Logitec | Kiểm tra khả năng chịu sai chính tả nhẹ | `Logitec` | Nhập keyword typo; submit; đọc kết quả | Kết quả vẫn trả về sản phẩm liên quan Logitech | Medium |
| TC_SEARCH_16 | Tìm kiếm typo có khoảng trắng giữa từ | Kiểm tra keyword bị tách ký tự vẫn có kết quả liên quan | `Logit ech` | Nhập keyword typo; submit; đọc kết quả | Kết quả vẫn liên quan Logitech | Medium |
| TC_SEARCH_17 | Tìm kiếm typo Logitechk | Kiểm tra sai chính tả có thêm ký tự cuối | `Logitechk` | Nhập keyword typo; submit; đọc kết quả | Kết quả trả về sản phẩm liên quan Logitech | Medium |
| TC_SEARCH_18 | Tìm kiếm typo Logtech | Kiểm tra thiếu ký tự trong keyword | `Logtech` | Nhập keyword typo; submit; đọc kết quả | Kết quả trả về sản phẩm liên quan Logitech | Medium |
| TC_SEARCH_19 | Tìm kiếm typo có số | Kiểm tra keyword lẫn số vẫn xử lý an toàn | `Logit3ch` | Nhập keyword typo; submit; đọc kết quả | Kết quả liên quan hoặc trang hiển thị trạng thái hợp lệ | Medium |
| TC_SEARCH_20 | Tìm kiếm không có kết quả | Kiểm tra trạng thái no-result | `nonexistentsku12345` | Nhập keyword không tồn tại; submit | Trang hiển thị trạng thái không có kết quả, không crash | High |
| TC_SEARCH_21 | Payload XSS script | Kiểm tra payload script không được thực thi trên UI | `<script>alert(1)</script>` | Nhập payload vào ô tìm kiếm; submit; kiểm tra alert và nội dung trang | Không xuất hiện alert độc hại, trang xử lý an toàn | Critical |
| TC_SEARCH_22 | Payload XSS img onerror | Kiểm tra payload HTML event không được thực thi | `"<img src=x onerror=alert(1)>` | Nhập payload; submit; kiểm tra alert/script | Không có alert hoặc thực thi script ngoài ý muốn | Critical |
| TC_SEARCH_23 | Payload SQL OR 1=1 dạng nháy đơn | Kiểm tra input SQL-like được xử lý an toàn | `' OR '1'='1` | Nhập payload; submit; quan sát phản hồi | Trang không lỗi và không trả về dữ liệu bất thường | Critical |
| TC_SEARCH_24 | Payload SQL OR 1=1 dạng nháy kép | Kiểm tra biến thể SQL-like với dấu nháy kép | `" OR "1"="1` | Nhập payload; submit | Trang xử lý an toàn, không crash | Critical |
| TC_SEARCH_25 | Payload SQL UNION NULL | Kiểm tra payload UNION đơn giản | `' UNION SELECT NULL --` | Nhập payload; submit | Không có lỗi hệ thống hoặc dữ liệu bất thường | Critical |
| TC_SEARCH_26 | Payload SQL UNION username/password | Kiểm tra payload dò dữ liệu nhạy cảm | `' UNION SELECT username,password FROM users --` | Nhập payload; submit | Trang không lộ dữ liệu, không lỗi truy vấn | Critical |
| TC_SEARCH_27 | Payload SQL UNION đóng ngoặc | Kiểm tra biến thể payload có dấu ngoặc | `') UNION SELECT NULL,NULL --` | Nhập payload; submit | Trang xử lý an toàn | Critical |
| TC_SEARCH_28 | Payload SQL DROP TABLE | Kiểm tra payload phá hoại dạng SQL-like | `'; DROP TABLE products; --` | Nhập payload; submit | Không có tác động phá hoại, không lỗi hệ thống | Critical |
| TC_SEARCH_29 | Payload SQL admin comment | Kiểm tra payload bypass đơn giản | `admin' --` | Nhập payload; submit | Trang không bypass hoặc trả dữ liệu bất thường | Critical |

## 2. Chức năng Lọc (Filter)

| Mã TC | Tên Test Case | Mục tiêu | Dữ liệu đầu vào (Input) | Các bước thực hiện | Kết quả mong đợi | Mức độ |
|---|---|---|---|---|---|---|
| TC_FILTER_01 | Lọc sản phẩm theo thương hiệu | Kiểm tra tất cả sản phẩm sau lọc đúng thương hiệu | Brand `Apple` | Vào trang laptop; chọn checkbox Apple; chờ danh sách cập nhật; đọc tên sản phẩm | Các sản phẩm hiển thị liên quan Apple/MacBook | High |
| TC_FILTER_02 | Bỏ lọc khôi phục danh sách | Kiểm tra bỏ filter đưa danh sách về trạng thái không lọc | Brand `Apple` | Chọn checkbox Apple; xác nhận URL/danh sách lọc; bỏ chọn checkbox; đọc lại danh sách | Danh sách được khôi phục và URL/trạng thái filter được bỏ | High |
| TC_FILTER_03 | Kết hợp filter với tìm kiếm không có kết quả | Kiểm tra hệ thống xử lý tổ hợp điều kiện không có sản phẩm | Brand `Apple`, keyword không tồn tại | Chọn filter; nhập keyword không tồn tại; submit | Trang hiển thị trạng thái không có kết quả hợp lệ | Medium |
| TC_FILTER_04 | Nhiều điều kiện rồi bỏ một điều kiện | Kiểm tra danh sách cập nhật đúng khi giảm bớt điều kiện lọc | Các điều kiện lọc có sẵn trên trang | Chọn nhiều filter; ghi nhận danh sách; bỏ một filter; chờ cập nhật | Danh sách thay đổi phù hợp, không giữ sai điều kiện cũ | High |
| TC_FILTER_05 | Giữ trạng thái filter sau reload | Kiểm tra filter vẫn tồn tại sau khi tải lại trang | Brand `Apple` | Chọn filter; reload trang; đọc URL và danh sách | Trạng thái filter vẫn được giữ, sản phẩm vẫn phù hợp | High |
| TC_FILTER_06 | Lọc rồi sắp xếp theo giá | Kiểm tra sort không phá điều kiện filter | Brand `Apple`, sort giá | Chọn filter Apple; chọn sort giá; đọc sản phẩm và giá | Sản phẩm vẫn đúng brand và giá được sắp xếp | High |

## 3. Chức năng Sắp Xếp (Sort)

| Mã TC | Tên Test Case | Mục tiêu | Dữ liệu đầu vào (Input) | Các bước thực hiện | Kết quả mong đợi | Mức độ |
|---|---|---|---|---|---|---|
| TC_SORT_01 | Sắp xếp theo giá tăng/giảm | Kiểm tra thứ tự giá đúng theo tùy chọn | Giá tăng dần, giá giảm dần | Vào trang laptop; chọn sort giá tăng; đọc giá; chọn sort giá giảm; đọc giá | Giá được sắp đúng thứ tự tăng dần và giảm dần | Critical |
| TC_SORT_02 | Đổi thứ tự với các sort không phải giá | Kiểm tra sort khác giá làm thay đổi thứ tự sản phẩm hợp lệ | Khuyến mãi tốt nhất, bán chạy, mới nhất | Chọn từng tùy chọn sort; đọc danh sách sản phẩm | Danh sách vẫn hiển thị và thứ tự có thay đổi phù hợp | Medium |
| TC_SORT_03 | Chuyển qua lại giữa các kiểu sort | Kiểm tra đổi sort liên tục không làm mất kết quả | Nhiều tùy chọn sort | Chọn nhiều kiểu sort liên tiếp; đọc giá/tên sản phẩm sau mỗi lần | Danh sách vẫn hiển thị, không rỗng, không crash | High |
| TC_SORT_04 | Giữ trạng thái sort sau reload và điều hướng | Kiểm tra sort đã chọn được bảo toàn khi reload/điều hướng | Một tùy chọn sort hợp lệ | Chọn sort; reload; điều hướng; kiểm tra lại trạng thái và danh sách | Sort không bị mất và danh sách vẫn phù hợp | High |

## Tổng Hợp Số Lượng Theo Bảng

| Phân hệ (Module) | Tổng số TC |
|---|---:|
| Tìm kiếm (Search) | 29 |
| Lọc (Filter) | 6 |
| Sắp xếp (Sort) | 4 |
| **Tổng cộng trong phạm vi 3 chức năng** | **39** |
