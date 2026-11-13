# Bill & Phiếu Giao Hàng · © Sentechtipsvn

Bill **3.4.0** và Phiếu Giao Hàng **4.1.0** dùng chung giao diện JSON, sổ đơn và ảnh trong iCloud.

## Cài và chuyển dữ liệu

1. Cài cả hai bản mới. Chạy **Phiếu Giao Hàng v4.1.0 trước một lần** để chuyển sổ cũ; lần đầu cần mạng để tải giao diện.
2. Chia sẻ ảnh vào **Bill v3.4.0**, kiểm tra tên/tiền rồi lưu.
3. Chạy **Phiếu Giao Hàng v4.1.0** để chọn đơn. Nếu dùng Trung tâm điều khiển, đổi ô cũ đang trỏ v4.0 sang bản v4.1.

Dữ liệu vẫn ở `iCloud Drive/Shortcuts/SenTechTips_AnhDonHang`. Không cần tạo lại thư mục hoặc di chuyển ảnh cũ. Khoản thu, công và lịch sử cũ được giữ; ảnh cũ tiếp tục đọc theo đường dẫn đã lưu.

## Năm trường dữ liệu

`DonHang.json` là sổ metadata dùng chung, có cấu trúc:

```json
{
  "3856": {
    "Name": "TIỆM MẪU",
    "Money": "2165000",
    "ID": "3856",
    "DC": "12 Đường Mẫu",
    "Number": "0900000000"
  }
}
```

Đây là ví dụ giả, không phải đơn hàng thực tế. Ảnh mới lưu thành `Ảnh Đơn Hàng/3856.png`. ID lấy từ `Số:`; khi không đọc được thì tự cấp bốn số, không bắt nhập. Nếu mã bị trùng, ảnh được đối chiếu trước khi dùng lại ID; ảnh khác được cấp ID riêng, tránh ghi đè.

Sổ tài chính `orders.json` giữ schema `sen-orders-v3` và các khoản thu cũ. `DonHang.json` dùng cho tên/tiền/ID/địa chỉ/SĐT; sổ tài chính giữ thu tiền, ngày ký, công, báo cáo và đường dẫn ảnh cũ. Bill không ghi lại các khoản thu trong sổ tài chính.

## Giao diện và tốc độ

- `data/ui-v4.1.json` chứa các tiêu đề/nội dung giao diện và danh sách ngân hàng cho cả hai phím tắt. Sổ đơn, số tài khoản nhận tiền và ảnh lưu riêng trong iCloud.
- Lần đầu tải JSON; sau đó dùng `ui-v4.1.json` đã lưu. Muốn làm mới: **Tuỳ chỉnh → Dữ liệu / công cụ → Cập nhật giao diện**.
- Danh sách chính chỉ là **Tên tiệm — Tiền**. Tiêu đề dạng **Phiếu Giao Hàng 11-2026**; bỏ hướng dẫn thừa trong menu.
- Chỉ lấy ảnh của đơn được chọn. Sau khi chuyển sổ cũ, không liệt kê lại thư mục ảnh hoặc thư mục metadata cũ khi mở.
- Các hằng số xử lý, đường dẫn và mã luồng vẫn nằm trong phím tắt; sửa chữ trong JSON không làm đổi các mã xử lý này. Nhãn nhánh menu native là các nhãn điều hướng cố định.

Bộ mô phỏng cùng 150 đơn cho thấy số tác vụ thực thi giảm **25%** so với bản 4.0.0; không đọc ảnh, không kê thư mục và không gọi mạng ở lần mở sau. Đây là đếm tác vụ trên mô hình native, **không phải đo thời gian trên iPhone 11**.

## Thu tiền và QR

Thu tiền mặt điền sẵn tổng cần thu bằng tiền mặt sau khi trừ CK đã ghi. Bấm OK lưu tổng đó; sửa ô nếu khách chỉ trả một phần. Mở lại không cộng lặp.

**Tuỳ chỉnh → Thiết lập QR** nhập tên chủ tài khoản, số tài khoản và chọn ngân hàng. QR gốc không có số tiền; QR trong đơn dùng phần còn phải thu. Hiện QR không tự ghi nhận đã nhận tiền.

Nhánh QR mới giữ phản hồi SVG/PNG/JPEG ở dạng nhị phân rồi nhúng vào trang xem ảnh cục bộ. Không ép ảnh SVG thành văn bản để tìm XML. QR gốc không gửi tham số số tiền trống. Có bản ảnh và trang xem trong thư mục `QR`; mã đã lưu xem được khi mất mạng.

## Công và báo cáo

Công mặc định 5.000₫ tính theo ngày Sếp xác nhận ký nhận việc, kể cả giao thất bại. Đơn cũ chưa rõ ngày ký không tự suy từ ngày giao. Tiền mặt, CK khách báo và đối soát tiền vào công ty tách riêng.

Báo cáo vẫn có phiếu nội bộ, chứng từ CK/ảnh giấy khách ký theo loại; chỉ chia sẻ khi Sếp chọn và chỉ đánh dấu đã gửi sau xác nhận. Sổ có bản chờ, bản sao lưu và kiểm tra hash trước khi ghi. Không chạy nhiều phiên cùng lúc.

Bill 3.4.0 và Phiếu Giao Hàng 4.1.0 là một cặp cập nhật. **Sweep 0.2.1 chưa có bộ nhập định dạng DonHang.json mới**; dự án này chưa thay đổi ứng dụng Sweep.

## Phát triển và kiểm tra

```bash
python -m pip install -r requirements.txt
python check.py
```

`project/bill_builder.py` giữ luồng OCR đã đối chiếu từ Bill 3.3.0, thêm `SĐT:` và sổ năm trường. `project/workflow.py` dựng Phiếu Giao Hàng; `shared.py` chứa cache/JSON và compiler giao diện; `synchronization.py` chuyển sổ cũ. Tệp build sinh ở `build/`.

Đã đạt **70 kiểm tra** chạy trực tiếp action graph; đã lấy QR mẫu công khai thật của VietQR, dựng ảnh và giải mã xác nhận ngân hàng, tài khoản, số tiền/nội dung và CRC16. Cả nhánh thiết lập QR gốc cũng được đối chiếu. Chưa chạy các bản mới trên iPhone thật; Sếp cần thử một đơn mẫu và QR trên thiết bị.

Thư mục `verification/` chứa kết quả kiểm tra, dùng tài khoản ví dụ công khai của VietQR, không dùng tài khoản khách hoặc tài khoản của Sếp.
