# Quan sát video tham khảo (Gate 0)

- Nguồn: https://www.youtube.com/watch?v=ZG7MRxzzLTM — "Ứng dụng Chuẩn hóa bản đồ", kênh Trần Thanh Liêm, đăng 20/11/2026, dài 6:47.
- Cách xem: mở trong trình duyệt, chụp khung hình tại các mốc 0:20, 1:00, 1:40, 2:15, 2:55, 3:40, 6:20. Video **không có mô tả, không có phụ đề/transcript**. Độ phân giải 854×480 nên một số chữ nhỏ đọc không chắc chắn; chỗ nào không chắc đã ghi là "chưa xác minh".
- Ngày ghi nhận: 21/11/2026.

| Quan sát trực tiếp | Chưa xác minh | Đề xuất thiết kế cho CadastralValidatorPro |
|---|---|---|
| Tên phần mềm "GML2DGN 1.2 — GML/SHP → DGN V8 · MicroStation V8i"; có 6 tab: ① Đầu vào ② Xử lý chồng/hở ③ Kiểm tra Web ④ Vẽ khung ⑤ So sánh ⑥ Trích lục | Ngôn ngữ/framework của GUI | Giữ cấu trúc 6 phân hệ đúng thứ tự này (sidebar), tab nào chưa làm thì ghi rõ trạng thái |
| Tab 1 có nhập thư mục GML: "11 file · 3,079 đối tượng · 11 cột · VN-2000 KTT 108°30'" | Cách nó nhận diện KTT (từ tệp hay từ seed) | Không mã hóa cứng KTT; chọn profile CRS và bắt người dùng xác nhận (`crs_profiles.json`) |
| Seed `108030.dgn — KTT 108°30'`; chế độ "Phiên tự động (COM) — không đụng bản vẽ đang mở"; tách theo từng tờ ra `DGN_Tach\DC<số tờ>.dgn` | Phiên bản build MicroStation | Đọc/ghi DGN qua MicroStation COM; mở tệp chỉ đọc; tên tệp đầu ra theo mẫu cấu hình |
| Phân lớp: "Ranh Line gộp L10 · Số thửa L13 · Loại đất L2 · Diện tích L4 · Phân lớp DTL→L32, SON→L31, DGT→L23" | Nguồn căn cứ của sơ đồ Level này | `levels.json` ghi đúng sơ đồ này, gắn nhãn `LOCAL_CONFIG / PENDING_VERIFICATION` |
| Nhãn chữ: cỡ 1 m, phân số, Cell, tự co vừa thửa, Unicode Arial | Quy cách cỡ chữ theo tỷ lệ | Đọc nhãn cả dạng Text, TextNode, Cell; nhãn phân số tách có điều kiện |
| Tab 2: chế độ xử lý riêng từng tờ / tổng xã; chồng ≥ 70% thửa nhỏ; xử lý vùng hở, thửa thiếu số thửa; đoán loại đất, đổi mã theo thư viện; gộp thửa nhỏ < 20 m²; khoanh vùng đã xử lý ở Level 9; sao lưu DGN cũ vào Backup trước khi chạy | Thuật toán gộp/cắt cụ thể | Tab 2 (G3) chỉ đề xuất + ChangeSet + phê duyệt; KHÔNG tự cắt/gộp (Master Prompt VII mức C) |
| Tab 3 "Kiểm tra DGN theo luật web (Cadastral DGN Validator + gdla)": đọc DGN bằng MicroStation, chỉ đọc; dựng vùng khép kín từ đường level 10/23/31/32; nhãn level 13/2/4; khung level 54; dung sai diện tích 0,1 m²; nhãn sát ranh < 0,2 m; "nối đầu mút treo cách ranh ≤ 0,1 m"; khoanh vị trí lỗi bán kính 1,5 m; mã loại đất "danh mục tùy chỉnh: 57 mã"; tùy chọn tra loại đất theo GML gốc | Ý nghĩa chữ "gdla"; nội dung 57 mã | Tab 3 làm đúng các phép kiểm tra này; ngưỡng đưa vào rule pack dạng tham số; khoanh lỗi chỉ trên bản sao/overlay |
| Bảng kết quả Tab 3: cột File, Kết quả, Lỗi, Cần xem, Vùng, Nhãn số, Treo, Tổng DT vùng/nhãn; ví dụ DC15: SAI, 13 lỗi, 12 cần xem, 320 vùng, 319 nhãn, 3 treo | — | Bảng theo tờ có cùng nhóm cột |
| Nút sau kiểm tra: Xuất báo cáo lỗi (.csv), Quy tắc kiểm tra, Sửa mã loại đất, Xử lý thiếu loại đất, Xử lý số thửa trùng, "Tự động xử lý thửa đất ngoài khung" (thửa > 50% diện tích ngoài khung level 63) | Chi tiết thao tác sửa | G1 chỉ xuất báo cáo; các nút sửa thuộc G3 |
| Bản đồ HTML `DC15_BanDo.html` mở trong trình duyệt: nền tối, thửa lỗi tô đỏ thẫm, nhãn số thửa (cam), loại đất (xanh lá), diện tích (xanh dương); panel phải "Vị trí lỗi / cần đối chiếu" có mã DAU_MUT_TREO, VUNG_KHONG_NHAN, SO_THUA_KHONG_CO_VUNG, sai số lượng nhãn; nút "Mở DGN", "Toàn tờ"; chú giải dưới: Ranh thửa, Khung (54), Số thửa, Loại đất, Diện tích, Vùng lỗi, Bỏ qua tab 7, Đầu mút treo/ranh hở | Cơ chế nút "Mở DGN" | Đã làm bản đồ HTML cục bộ tương tự (không gọi mạng, CSP chặn tài nguyên ngoài); nút "Mở DGN trong MicroStation" để G1+ sau khi COM được xác minh |
| Màn hình khởi động MicroStation V8i SELECTseries 3 (Bentley 2012) | Bitness bản cài trên máy người dùng | Gate 0 phải chạy `scripts/probe_microstation.py` trên máy thật |

Kết luận: video thể hiện một công cụ đã chạy được với MicroStation qua COM. Định hướng CadastralValidatorPro giữ quy trình tương tự nhưng thêm: rule pack có trạng thái xác minh, ID lỗi ổn định, chỉ đọc, tách biệt kiểm tra với sửa.
