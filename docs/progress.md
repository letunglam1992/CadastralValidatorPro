# Tiến độ

## Lượt 1 — 21/11/2026

| Đã làm | File tạo/sửa | Lệnh đã chạy | Test | Chứng cứ | Vấn đề | Quyết định cần người dùng | Bước tiếp theo |
|---|---|---|---|---|---|---|---|
| Khảo sát 6 DGN thật | `adapters/dgn_probe.py`, `scripts/gate0_profile.py`, `docs/gate0/data_profile.xlsx` | `python scripts/gate0_profile.py <Liem> ...` | PASS | 6/6 V8, zlib OK | Không tự đọc được phần tử V8 | Chạy probe/macro trên máy có MicroStation | Nghiệm thu bộ trích xuất |
| Xem video tham khảo | `docs/gate0/video_observations.md` | trình duyệt, chụp 7 khung hình | — | bảng quan sát | Không có mô tả/phụ đề | — | — |
| Lõi kiểm tra Tab 3 | `domain/*`, `application/validate_service.py` | `pytest` | 49 PASS / 0 FAIL / 0 SKIP | log pytest | Chỉ trên fixture tổng hợp | Xác nhận Level, ngưỡng, danh mục mã đất | Chạy trên DC8 thật |
| Báo cáo Excel/CSV/GeoJSON/JSON/HTML | `adapters/reports.py`, `adapters/html_map.py` | Playwright mở HTML, nhấp lỗi | PASS | `docs/img/html_map_full.png` | — | — | — |
| GUI 6 tab | `ui/main_window.py` | offscreen | PASS | `docs/img/gui_tab3.png` | Chưa chạy trên Windows thật | — | Thử trên Windows, DPI 125–200% |
| Bộ trích xuất COM + macro VBA | `adapters/microstation_com.py`, `scripts/microstation/XuatPhanTu_CVP.bas`, `scripts/probe_microstation.py` | — | NOT TESTED | — | Không có Windows/MicroStation | Chạy thử | Sửa theo kết quả probe |
| Lỗi phát hiện trên dữ liệu thật | `dgn_probe.clean_ole_string` | probe DC2/DC8/seed | PASS (test hồi quy) | metadata OLE có rác sau NUL | — | — | — |

### Hạn chế đã biết
- Cung tròn/ellipse/B-spline trên ranh chưa rời rạc hóa (có thể gây đầu mút treo giả).
- Chưa đối chiếu GML gốc (Tab 3 Tầng B mục cuối), chưa có nút mở DGN/khoanh Level 63.
- Chưa có SQLite/GeoPackage issue store, chưa có resume theo job manifest.
- Chưa benchmark trên dữ liệu thật; không cam kết thời gian.

## Lượt 2 — 21/11/2026: chạy thử trên DC8 thật (macro VBA)

- Macro VBA chạy được trên máy người dùng: 2.142 phần tử, bỏ qua 18 (kiểu 5, 9, 15 ellipse, 56, 66, 96, 97). **Bộ trích xuất VBA: PARTIAL** (chạy được, chưa đối chiếu số lượng với MicroStation).
- Phát hiện: DC8 **không dùng Level 2/4/13**. `Level.Number` xuất ra 65–75. Sơ đồ suy luận (CHƯA XÁC NHẬN): ranh 67 (dựng 122 vùng), số thửa 71 (151 nhãn), diện tích 72 (123 nhãn), loại đất 65 (mã cũ N, M, 1L, Ao, Hg, GT, T), khung 66 (3.000 × 3.000 m → nghi tỷ lệ 1:5000). Cần biết 65–75 là "Number" hay ID nội bộ → macro đã thêm `level_name` và bảng `levels`.
- Chữ tiếng Việt dùng bảng mã font MicroStation (ví dụ "XA8 PHI3NG LU4NG" = XÃ PHIÊNG LUÔNG) — cần bảng chuyển mã đã kiểm thử.
- Bảng thống kê diện tích trong tờ chứa nhãn cùng Level với nhãn thửa → báo "nhãn ngoài vùng" giả. Cần cấu hình vùng loại trừ (G1.1).
- Lỗi phần mềm phát hiện nhờ dữ liệu thật và đã sửa (có test hồi quy): độ dịch snap tính sai (báo 1.403 m), đưa khung tờ vào dựng vùng (mặc định nay tắt), tên tệp đường dẫn Windows.

## Lượt 3 — 21/11/2026: hồ sơ Level theo TÊN cho DC8

- Người dùng xác nhận: ranh = `L`, số thửa = `TCT`, diện tích = `DIENTICH3`, loại đất = `C`. Thêm `config/level_profiles/dc8_phieng_luong.json`; khung `KG-5000` (chưa xác nhận). Số Level dự phòng 65–75 suy từ thứ tự Level Manager — dùng đến khi có tệp xuất bằng macro mới (có `level_name`).
- Thêm phân giải Level theo tên (`domain/level_resolve.py`), tùy chọn `--levels` (CLI) và "Hồ sơ Level" (GUI), `exclusion_boxes`.
- Thêm LAB-007 (heuristic): nhãn ngoài vùng xếp lưới hàng–cột → nghi Bảng thống kê, báo 1 dòng info.
- Kết quả DC8 (THĂM DÒ, CRS chưa xác nhận, tỷ lệ 1:5000 suy từ KG-5000): 122 vùng; 151 nhãn số thửa, 123 diện tích, 156 loại đất; 95 nhãn thuộc bảng thống kê; còn 48 nhãn ngoài vùng, 28 vùng không nhãn, 17 trùng nhãn, 11 đầu mút treo, 1 trùng số thửa (119), 81 mã đất hệ cũ (N, M, 1L, Ao, Hg, GT, T). 53 test PASS.

## Lượt 4 — 21/11/2026: DC8 xuất lại có tên Level; CRS xác nhận
- Macro mới xuất bảng `levels` + `level_name`: khớp hoàn toàn ánh xạ dự phòng (C=65 … 0=75). Phân giải Level nay lấy từ `element.level_name`.
- Người dùng xác nhận KTT Sơn La 104°00' → `VN2000_TM3_104` = VERIFIED_PARTIAL (chưa ghi số hiệu văn bản nguồn).
- Diện tích DC8 (64 thửa có đúng 1 số thửa + 1 diện tích): lệch tương đối trung vị 0,019%, nhãn luôn LỚN hơn hình học ~1,9×10⁻⁴ ⇒ **sai khác hệ thống** cỡ k² của phép chiếu (k0 = 0,9999 → k² ≈ 0,9998): nghi diện tích nhãn tính theo mặt ellipsoid/thực địa hoặc phép chiếu khác. Cần người dùng xác nhận quy ước; KHÔNG tự hiệu chỉnh. Ngoại lệ: thửa 45 lệch +44 m² (2,86%).
- 1:5000: rule pack chưa có ngưỡng hạn sai diện tích (Bo quy tac.json để trống) → AREA-001 không chạy.
