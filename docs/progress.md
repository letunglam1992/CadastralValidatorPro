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
