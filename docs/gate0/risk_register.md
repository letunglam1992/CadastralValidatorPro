# Sổ rủi ro (risk register)

| ID | Rủi ro | Khả năng | Ảnh hưởng | Biện pháp | Trạng thái |
|---|---|---|---|---|---|
| R01 | Không đọc được DGN V8 ngoài MicroStation | Đã xảy ra | Cao | Đọc qua COM/VBA → JSON trao đổi; lõi kiểm tra độc lập | Mở — chờ thử COM |
| R02 | Python x64 không điều khiển được MicroStation V8i 32-bit | Trung bình | Cao | Thử out-of-process; dự phòng macro VBA; nếu cần, helper 32-bit (ADR-0002) | Mở |
| R03 | Kiểu `Point3d`/`DLong` qua pywin32 không như VBA | Trung bình | Trung bình | probe script in ra kiểu thực; macro VBA không bị ảnh hưởng | Mở |
| R04 | Ngưỡng/Level/mã đất bị hiểu là quy định pháp luật | Trung bình | Cao | Rule pack gắn `classification` + `verification_status`; loader từ chối `LEGAL_REQUIREMENT` không có căn cứ; báo cáo có tuyên bố miễn trừ | Đã kiểm soát |
| R05 | CRS sai (KTT 104° vs 108°30' như video) làm sai diện tích | Trung bình | Cao | Bắt buộc chọn + xác nhận profile; cảnh báo CRS_CHUA_XAC_NHAN; kiểm tra khoảng tọa độ | Đã kiểm soát ở G1 |
| R06 | Master unit của tệp không phải mét | Thấp–TB | Cao | Exchange JSON khai báo `units.master`; loader từ chối khác `m` | Đã kiểm soát |
| R07 | Nhãn TCVN3/VNI làm sai so khớp | Trung bình | Trung bình | Lưu chuỗi gốc; chuẩn hóa NFC; bảng chuyển mã TCVN3 để G2 | Mở |
| R08 | Cell NHANTHUA không phân rã được qua COM | Trung bình | Trung bình | Báo số Cell chưa phân rã trong tiền kiểm; không đoán | Mở |
| R09 | Cung tròn trên ranh thửa chưa rời rạc hóa → báo treo giả | Trung bình | Trung bình | Đếm `unsupported_geometry`; G1.1 rời rạc hóa theo dung sai | Mở |
| R10 | Đẩy dữ liệu địa chính thật lên repo công khai | Thấp | Rất cao | `.gitignore` chặn `*.dgn`, `*.cvp.json`, `output/`; test dùng fixture tổng hợp | Đã kiểm soát |
| R11 | Hiệu năng với hàng nghìn thửa | Thấp | Trung bình | STRtree, snap theo lân cận; chưa benchmark dữ liệu thật — không cam kết thời gian | Mở |
| R12 | Báo cáo khác số lượng giữa Excel/CSV/JSON | Thấp | Trung bình | Một issue store; test tích hợp đối chiếu số lượng | Đã kiểm soát |
