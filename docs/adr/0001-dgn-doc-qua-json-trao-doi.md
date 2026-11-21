# ADR-0001: Tách đọc DGN khỏi lõi kiểm tra bằng định dạng trao đổi JSON

- Trạng thái: Chấp nhận (G1) — 21/11/2026
- Bối cảnh: DGN V8 mẫu là OLE + zlib, phần tử độc quyền; Python không đọc được nếu không có MicroStation/ODA. Môi trường phát triển không có Windows.
- Quyết định: Bộ trích xuất (COM Python hoặc macro VBA) ghi `cvp.dgn_exchange/1`; engine kiểm tra chỉ làm việc với mô hình chuẩn từ JSON/GML/SHP.
- Hệ quả: lõi kiểm thử được bằng fixture tổng hợp ở mọi máy; bộ trích xuất phải được nghiệm thu riêng trên máy có MicroStation. Kết quả kiểm tra DGN thật chưa được tuyên bố cho tới khi nghiệm thu.
