# ADR-0003: Mọi ngưỡng là tham số rule pack có trạng thái xác minh

- Trạng thái: Chấp nhận.
- Quyết định: Ngưỡng theo tỷ lệ lấy từ `Bo quy tac.json` (người dùng), ngưỡng chung từ Master Prompt/video; tất cả `SOFTWARE_HEURISTIC` hoặc `LOCAL_CONFIG`, `PENDING_VERIFICATION`, không auto-fix.
- Khe hở chỉ đánh giá khi có vùng bao phủ hợp lệ (nhánh polygon) — với nét DGN, khe hở xuất hiện dưới dạng "vùng không nhãn"/mảnh vụn. Vùng chỉ có nhãn loại đất DGT/DTL/SON/MNC không bị coi là thiếu số thửa (cấu hình `non_parcel_land_codes`, cần xác nhận).
- Snap chỉ áp dụng trên bản sao trong bộ nhớ để dựng vùng; độ dịch cực đại ghi vào thống kê.
