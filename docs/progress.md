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

## Lượt 5 — 21/11/2026: hạn sai diện tích TT 26/2024
- Người dùng: tỷ lệ DC8 = 1:5000; diện tích nhãn theo mặt đất thực; ngưỡng theo TT 26/2024 (cung cấp .docx); mã đất cũ chỉ báo, người dùng tự nhập mã mới.
- Thêm `domain/area_tolerance.py` (Phụ lục 04, 6 tỷ lệ), `domain/area_reference.py` (grid/ellipsoid/ground), tùy chọn `--area-ref`, `--mean-height`; Excel thêm cột "Mã loại đất mới (người dùng nhập)".
- Sửa lỗi: vùng có 2 nhãn diện tích từng bị so diện tích với nhãn đầu tiên (DC8 thửa 9, 26) → nay chỉ báo TRUNG_NHAN.
- DC8 (mặt đất, chưa có h): 1 lỗi diện tích — thửa 45 lệch 44,16 m² > hạn sai 8,57 m². Sai khác hệ thống ~0,02% của các thửa khác nằm trong hạn sai. 66 test PASS.

## Lượt 6 — 21/11/2026: TT 23/2025 và hồ sơ tờ DC8
- Người dùng: mốc 50 m² (1:5000/1:10000); đồng ý vận dụng khoản 5 Điều 8; h = 904 m; cung cấp TT 23/2025.
- TT 23/2025 không sửa khoản 5 Điều 8 / Phụ lục 04 TT 26/2024; Phụ lục 01 (đã sửa) xác nhận KTT Sơn La 104°00' → CRS VERIFIED_CURRENT.
- Hồ sơ Level DC8 mang thêm thuộc tính tờ: scale 1:5000, area_reference ground, mean_height_m 904 → CLI/GUI không cần nhập lại.
- DC8: 1 lỗi diện tích (thửa 45, lệch 44,61 m² > 8,58 m²).

## Lượt 7 — 21/11/2026: bộ cài Windows v0.2.0
- PyInstaller (onedir) + Inno Setup, build trên GitHub Actions windows-latest, Python 3.12 (pyproj 3.8 yêu cầu ≥ 3.12). Workflow: cài thư viện → pytest (66 passed, 1 skipped) → đóng gói → mở EXE 15 giây không lỗi → ISCC → Release.
- Release v0.2.0: CadastralValidatorPro_Setup_0.2.0.exe (53,6 MB). Chưa ký số. Chưa thử cài trên máy người dùng.
- Đường dẫn khi chạy EXE: cấu hình trong gói (_MEIPASS), báo cáo/log tại Documents\CadastralValidatorPro.

## Lượt 8 — 21/11/2026: kiểm tra 5 tờ DC1, DC2, DC8, DC9, DC10
- Macro: OpenDesignFileForProgram gây "Level Error 32768" (không đọc được Level của phần tử tệp mở ngầm) → đổi sang mở lần lượt từng tệp (chỉ đọc). Sửa lỗi ghi '\' (JSON hỏng DC1) do tôi gây ra ở lần sửa trước; loader tự sửa tệp đã xuất lỗi.
- Chọn thẳng .dgn: dùng <tên>.dgn.cvp.json nếu mới hơn DGN → thử COM → báo hướng dẫn. GUI hiện toàn văn lỗi đọc.
- DC2, DC10 vẽ ranh ở Level THUA (không phải L) → hồ sơ chung `son_la_ten_level_chung` v2: ranh = L hoặc THUA; tỷ lệ 1:5000; độ cao = auto:DO-CAO (trung vị từng tờ).
- Heuristic bảng thống kê siết lại (cụm ≤ 100 m, ≥ 3×3, ≤ 20 cm giấy, không phải dải hẹp) — bản cũ gộp nhầm 513 nhãn DC2 thành "bảng". Bảng DC2 (nhiều cột giãn rộng) chỉ nhận một phần → nên khai báo exclusion_boxes.
- Thêm Level G (đường) vào ranh không cải thiện → không dùng.
- Kết quả: DC1 296 lỗi, DC2 1.493, DC8 106, DC9 691, DC10 1.032. Sai diện tích: DC2 thửa 487; DC8 thửa 45; DC10 16 thửa.

## Lượt 9 — 21/11/2026: xác nhận của người dùng
- Đồng ý độ cao tự động theo DO-CAO; DC2 chỉ có ranh ở L, THUA; kết quả sai diện tích được xác nhận.
- Không có cung tròn (type 16) bị bỏ sót; phần bị bỏ: ellipse/đường tròn (15), dimension (33), phần tử không đồ họa.
- Đầu mút treo nay ghi khoảng hở tới nét gần nhất (hụt/thừa < 1 m; hở 1–5 m; ranh hở/đứt > 5 m). DC2: 33 điểm < 1 m, 205 điểm 1–5 m, 258 điểm > 5 m.

## Lượt 10 — 21/11/2026: Tab 2 (G3) — sửa đầu mút treo có kiểm soát
- `domain/fixes.py`: JOIN/TRIM/EXTEND/SNAP, bỏ qua nét rời ngắn treo 2 đầu (DC2: 8 nét ~0,7 m nghi ký hiệu); `application/fix_service.py`: analyze, evaluate_each, simulate, export (bản sao DGN kiểm hash, macro áp dụng/hoàn tác có chốt "_BANSAO" và kiểm tọa độ trước); `ui/fix_tab.py`.
- Lỗi phát hiện khi chạy dữ liệu thật và đã sửa: hai đầu treo đối diện bị đề xuất đổi chỗ cho nhau (DC2 28 đề xuất chỉ giảm 14 treo) → thêm JOIN.
- Dữ liệu thật, ngưỡng 1 m, chọn "không lỗi mới, trừ SNAP": DC2 7 sửa (treo 496→484, lỗi 1493→1475), DC10 8 sửa (217→204, 1032→1016), DC9 1, DC1/DC8 0. Phần lớn đầu treo > 1 m — không thuộc phạm vi tự sửa.
- G3: PARTIAL — macro áp dụng NOT_TESTED; chưa có sửa chồng/hở, mã đất, số thửa.
