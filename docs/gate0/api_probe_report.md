# Báo cáo khảo sát API/định dạng — Gate 0

## 1. DGN V8 đọc độc lập (không MicroStation)

Thực nghiệm trên 6 tệp thật (`scripts/gate0_profile.py`, test `test_real_dgn_probe_is_v8_and_reader_blocked_without_com`):

- Cả 6 tệp bắt đầu bằng chữ ký OLE/CFB `D0 CF 11 E0 A1 B1 1A E1` ⇒ **DGN V8**.
- Cấu trúc OLE: `Dgn~H`, `Dgn~S`, `Dgn~Mf`, `DgnTk`, `Dgn^Ix/Dgn~Mix`, `Dgn^Nm/$1`, `Dgn-Md/#000000/Dgn~Mh`, `Dgn-Md/#000000/Dgn^G/$1` (luồng phần tử đồ họa).
- Luồng `Dgn^G/$n`: 16 byte đầu là header, phần sau **nén zlib** (giải nén thử thành công cả 6 tệp; DC8: 81.858 byte → 350.280 byte).
- Tìm chuỗi mã loại đất (`LUC`, `ONT`, `BHK`, `CLN`, `NHANTHUA`) dạng ASCII và UTF-16LE trong dữ liệu đã giải nén: **0 kết quả** ⇒ văn bản được mã hóa theo cấu trúc phần tử/font riêng.
- Định dạng phần tử V8 là độc quyền Bentley, không có đặc tả công khai.

**Kết luận:** `BLOCKED` cho việc tự đọc phần tử DGN V8 bằng Python. Không viết bộ giải mã dựa trên suy đoán (Master Prompt I.2). GDAL/OGR driver `DGN` chỉ đọc V7; driver `DGNV8` cần ODA Teigha SDK (thương mại). ⇒ đường đọc chính thức: **MicroStation COM** hoặc **macro VBA** trong MicroStation.

## 2. MicroStation COM

| Hạng mục | Thiết kế | Trạng thái |
|---|---|---|
| ProgID | `MicroStationDGN.Application` | NOT TESTED |
| Mở tệp | `Application.OpenDesignFileForProgram(path, True)` (chỉ đọc, không hiện bản vẽ) | NOT TESTED |
| Duyệt phần tử | `DefaultModelReference.Scan()` → `ElementEnumerator.MoveNext/Current` | NOT TESTED |
| Hình học | `Element.Type`, `Level.Number`, `AsVertexList.GetVertices()` (Line/LineString/Shape), `AsComplexElement.GetSubElements()` | NOT TESTED |
| Nhãn | `AsTextElement.Text/Origin`, `AsTextNodeElement.GetSubElements()`, `AsCellElement.Name/GetSubElements()` | NOT TESTED |
| ID phần tử | `Application.DLongToString(Element.ID)` | NOT TESTED |
| Cung tròn, ellipse, B-spline | chưa rời rạc hóa — chỉ đếm, báo `unsupported_geometry` | PARTIAL (thiết kế) |
| Kiểu `Point3d` qua pywin32 | cần kiểm tra trả về record có `.X/.Y` | NOT TESTED |
| Bitness | V8i thường 32-bit; COM out-of-process thường gọi được từ x64 nhưng phải thử | NOT TESTED |

Phương án dự phòng (ADR-0002): macro `scripts/microstation/XuatPhanTu_CVP.bas` chạy trong MicroStation, xuất cùng định dạng JSON `cvp.dgn_exchange/1`; văn bản Unicode được escape `\uXXXX` nên không phụ thuộc mã trang.

## 3. Ghi DGN V8

`BLOCKED` ở G1: không có writer đã xác minh. Tab 1/Tab 2/Tab 4/Tab 6 (xuất DGN) bị khóa, GUI ghi rõ lý do.

## 4. Việc người dùng cần làm để mở khóa G1 trên dữ liệu thật

1. Trên máy có MicroStation: `python scripts\probe_microstation.py "K:\...\file DGN\DC8.dgn"` → gửi lại tệp `probe_result.json`.
2. Hoặc mở DC8.dgn trong MicroStation, nạp `XuatPhanTu_CVP.bas`, chạy `XuatPhanTuJSON` → được `DC8.dgn.cvp.json` → chạy `python -m cadastral_validator check DC8.dgn.cvp.json`.
3. Đối chiếu số lượng phần tử/nhãn với MicroStation (Level Manager / Element Selection) để nghiệm thu bộ trích xuất.
