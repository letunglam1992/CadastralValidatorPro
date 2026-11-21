# Báo cáo môi trường — Gate 0 (21/11/2026)

## 1. Môi trường phát triển (nơi viết mã và chạy test lần này)

| Hạng mục | Giá trị thực đo | Ghi chú |
|---|---|---|
| Hệ điều hành | Linux x86_64 (máy ảo đám mây) | **Không phải Windows** — mọi hạng mục COM đều NOT TESTED |
| Python | 3.13 | Mục tiêu triển khai Windows: Python 3.11 x64 (chưa kiểm thử trên 3.11) |
| shapely | 2.2.0 | |
| pyproj | 3.8.0 | Chưa dùng ở G1 (chưa chuyển đổi CRS) |
| PySide6 | 6.12.0 | GUI chạy offscreen, đã chụp màn hình |
| openpyxl / lxml / pyshp / olefile | 3.1.5 / 6.1.3 / 3.1.9 / 0.47 | |
| GDAL/OGR | **Không cài được** (`pip install gdal` thiếu libgdal) | Không ảnh hưởng: driver DGN của GDAL chỉ đọc DGN **V7**; dữ liệu mẫu là V8 |
| Playwright Chromium | có | Dùng để kiểm tra bản đồ HTML (không lỗi console) |

## 2. Máy người dùng (Windows + MicroStation V8i) — CHƯA KHẢO SÁT

| Năng lực | Trạng thái | Cách xác minh |
|---|---|---|
| Windows 10/11 x64, quyền thư mục | NOT TESTED | chạy `scripts\probe_microstation.py` |
| MicroStation V8i: bản/build, 32/64-bit | NOT TESTED | metadata DGN cho thấy tệp được tạo bởi MicroStation **v8.11.9.357** và **v8.11.9.832** (V8i SELECTseries 3 = 08.11.09.xxx) |
| ProgID `MicroStationDGN.Application` | NOT TESTED | `python -m cadastral_validator com` |
| COM out-of-process từ Python x64 sang ustation.exe 32-bit | NOT TESTED | probe script thử Dispatch + `OpenDesignFileForProgram` chỉ đọc |
| Macro VBA xuất JSON (`XuatPhanTu_CVP.bas`) | NOT TESTED | chạy trong MicroStation trên DC8.dgn (tệp nhỏ nhất) |

## 3. Bộ dữ liệu mẫu nhận được (thư mục `Liem`)

| Tệp | Kích thước | Định dạng | Ghi chú |
|---|---|---|---|
| DC1, DC2, DC8, DC9, DC10 `.dgn` | 110 KB – 943 KB | DGN V8 (OLE/CFB) | 1 model; DC2 có thêm luồng Dgn^C (cell library/định nghĩa) |
| seed1000.dgn | 75 KB | DGN V8 | seed tỷ lệ 1:1000 (theo tên tệp) |
| Bo quy tac.json | 7 KB | JSON | ngưỡng theo tỷ lệ, CRS KTT 104°, danh mục mã đất — đã đưa vào rule pack với trạng thái PENDING |
| Quy tac kiem tra topology.md | 10 KB | pseudocode | thuật toán (a)(b)(c) — đã hiện thực trong `domain/topology.py`, `application/validate_service.py` |

Chi tiết hash/metadata: `docs/gate0/data_profile.xlsx`. **Các tệp DGN thật không được đưa lên GitHub** (repo công khai; dữ liệu địa chính).

Thiếu so với Gate 0 (Master Prompt XIV): bảng Level chính thức, GML/SHP/XSD mẫu, CRS đã xác nhận cho từng tờ, mẫu khung/trích lục, danh mục mã đất có căn cứ, bộ lỗi do cán bộ gán nhãn.
