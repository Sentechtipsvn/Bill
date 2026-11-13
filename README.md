# Bill & Phiếu Giao Hàng · © Sentechtipsvn

Bill **3.4.1** và Phiếu Giao Hàng **4.1.2** dùng chung giao diện JSON, sổ đơn và ảnh trong iCloud. Giữ Bill đang dùng; bản này sửa luồng lập danh sách của Phiếu Giao Hàng.

## Menu trống sau khi Bill đã lưu đơn · 4.1.2

Bản 4.1.2 đã ký qua Shortcuty. Chữ ký AEA, chữ ký chuỗi chứng chỉ và việc giữ nguyên toàn bộ 3.705 tác vụ đã được đối chiếu với bản dựng; kết quả ở `verification/signatures-v4.1.2.json`. Chưa chạy trên iPhone thật. Bill 3.4.1 giữ nguyên tệp đã bàn giao.

- Thay vòng lặp đếm động và biến hệ thống `Repeat Index 2/3` bằng Repeat with Each native, mỗi vòng có danh sách chụp riêng và bộ đếm mang tên riêng. Việc đọc kho, chuyển sổ, dựng menu và kiểm tra trước khi lưu dùng chung cách duyệt này.
- Đọc lại chỉ mục tên ảnh và đối chiếu metadata một lần để phục hồi các lượt chuyển sổ cũ đã được đánh dấu hoàn tất nhưng có thể chưa duyệt đủ. Không mở/nạp toàn bộ ảnh; không đặt lại khoản thu, công, ngày ký hay đường dẫn ảnh cũ.
- Nếu tác vụ sắp xếp trả danh sách rỗng trong khi chỉ mục chữ còn dữ liệu, dùng chỉ mục ban đầu để tiếp tục hiển thị đơn.
- Lần mở sau dùng JSON và không quét lại thư mục. Mục đọc lại tên ảnh thủ công tiếp tục hoạt động.

Ảnh chụp báo lỗi xác nhận Bill đã ghi đơn vào `DonHang.json`, nhưng chưa đủ để kết luận chính xác hành vi runtime nào trên iOS gây mất các dòng menu. Đây là bản sửa có kiểm tra mô phỏng và kiểm tra cấu trúc native; chưa chạy trực tiếp trên iPhone. Không coi các kiểm tra máy chủ là xác nhận đã khắc phục trên thiết bị.

Đã đạt **86 kiểm tra**, gồm ca metadata mới nhưng chưa có hồ sơ tài chính, cờ chuyển kho cũ còn sót, nhiều đơn có khoản thu/ngày ký/công cần giữ, vòng lặp lồng nhau và sắp xếp trả rỗng. Cài Phiếu Giao Hàng 4.1.2 rồi mở lại; đơn đã có trong `DonHang.json` không cần chia sẻ lại vào Bill.

## Bản sửa 13/11/2026

- Bill: sửa giá trị của Set Dictionary Value bị iOS hiển thị thành ô trống; kiểm tra ID trước khi ghi; khôi phục metadata khi ảnh cùng ID đã lưu từ lần lỗi trước.
- Cả hai: giữ giá trị khởi tạo rỗng và hằng số luồng bằng Text native; lấy trường từ điển bằng tác vụ Get Dictionary Value có đầu vào rõ ràng, bỏ bước gộp biến cũ.
- Phiếu Giao Hàng: Giới hạn hiển thị luôn mở ô nhập, giữ số đã đặt làm mặc định; nhận 0–500 và lưu qua lần chạy sau.
- Kho cũ: tự đọc tên các ảnh trong thư mục dùng chung một lần, bóc tên/tiền mà không đọc dữ liệu ảnh. Giữ nguyên các hồ sơ tài chính đã có, không suy ngày ký hoặc tự tính công cho ảnh cũ. Nếu thêm ảnh cũ sau đó: Tuỳ chỉnh → Dữ liệu / công cụ → Đọc lại tên ảnh trong kho.

## Cài và chuyển dữ liệu

1. Giữ **Bill v3.4.1**, cài **Phiếu Giao Hàng v4.1.2** và chạy một lần để đối chiếu lại kho cũ; lần đầu cần mạng nếu chưa có bản giao diện đã lưu.
2. Chia sẻ ảnh vào **Bill v3.4.1**, kiểm tra tên/tiền rồi lưu. Đơn đã gặp lỗi ở 3.4.0 cần chia sẻ lại ảnh vào bản này để hoàn tất sổ.
3. Chạy **Phiếu Giao Hàng v4.1.2** để chọn đơn. Đổi ô Trung tâm điều khiển sang phím tắt mới nếu đang dùng ô trỏ bản cũ.

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

Lần chuyển kho đầu tiên chỉ liệt kê tên tệp và thông tin ngày tạo. Các lần mở sau đọc JSON, không liệt kê lại thư mục ảnh. Chưa đo thời gian bản sửa trên iPhone 11.

## Thu tiền và QR

Thu tiền mặt điền sẵn tổng cần thu bằng tiền mặt sau khi trừ CK đã ghi. Bấm OK lưu tổng đó; sửa ô nếu khách chỉ trả một phần. Mở lại không cộng lặp.

**Tuỳ chỉnh → Thiết lập QR** nhập tên chủ tài khoản, số tài khoản và chọn ngân hàng. QR gốc không có số tiền; QR trong đơn dùng phần còn phải thu. Hiện QR không tự ghi nhận đã nhận tiền.

Nhánh QR mới giữ phản hồi SVG/PNG/JPEG ở dạng nhị phân rồi nhúng vào trang xem ảnh cục bộ. Không ép ảnh SVG thành văn bản để tìm XML. QR gốc không gửi tham số số tiền trống. Có bản ảnh và trang xem trong thư mục `QR`; mã đã lưu xem được khi mất mạng.

## Công và báo cáo

Công mặc định 5.000₫ tính theo ngày Sếp xác nhận ký nhận việc, kể cả giao thất bại. Đơn cũ chưa rõ ngày ký không tự suy từ ngày giao. Tiền mặt, CK khách báo và đối soát tiền vào công ty tách riêng.

Báo cáo vẫn có phiếu nội bộ, chứng từ CK/ảnh giấy khách ký theo loại; chỉ chia sẻ khi Sếp chọn và chỉ đánh dấu đã gửi sau xác nhận. Sổ có bản chờ, bản sao lưu và kiểm tra hash trước khi ghi. Không chạy nhiều phiên cùng lúc.

Bill 3.4.1 và Phiếu Giao Hàng 4.1.2 dùng chung định dạng dữ liệu. **Sweep 0.2.1 chưa có bộ nhập định dạng DonHang.json mới**; dự án này chưa thay đổi ứng dụng Sweep.

## Phát triển và kiểm tra

```bash
python -m pip install -r requirements.txt
python check.py
```

`project/bill_builder.py` giữ luồng OCR đã đối chiếu từ Bill 3.3.0, thêm `SĐT:` và sổ năm trường. `project/workflow.py` dựng Phiếu Giao Hàng; `shared.py` chứa cache/JSON và compiler giao diện; `synchronization.py` chuyển sổ cũ. Tệp build sinh ở `build/`.

Đã đạt **86 kiểm tra trên máy chủ**, gồm kiểm tra envelope native độc lập và các ca tái hiện lỗi Sếp báo: lưu đơn, giá trị mặc định/giới hạn, kho ảnh cũ không có sổ, giữ khoản thu và công, mở đúng một ảnh, hoàn tất ảnh còn lại sau lần lưu lỗi. Bộ mô phỏng trước đã bỏ sót lỗi cấu trúc native; kiểm tra mô phỏng không thay thế chạy thật trên iOS. Chữ ký và việc giữ nguyên action graph sau ký được kiểm tra riêng. Chưa chạy bản sửa trên iPhone thật.

Thư mục `verification/` chứa kết quả kiểm tra, dùng tài khoản ví dụ công khai của VietQR, không dùng tài khoản khách hoặc tài khoản của Sếp.
