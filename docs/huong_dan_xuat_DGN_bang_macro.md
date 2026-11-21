# Hướng dẫn xuất phần tử DGN bằng macro VBA (MicroStation V8i)

Mục đích: tạo tệp `<tên>.dgn.cvp.json` để CadastralValidatorPro kiểm tra. Macro **chỉ đọc**, không sửa bản vẽ.

## 1. Tải macro
1. Mở https://github.com/letunglam1992/CadastralValidatorPro/blob/main/scripts/microstation/XuatPhanTu_CVP.bas
2. Bấm nút **Download raw file** (biểu tượng mũi tên xuống, góc phải trên khung mã).
3. Lưu vào thư mục dễ nhớ, ví dụ `D:\CVP\XuatPhanTu_CVP.bas`. Không mở/sửa bằng Word.

## 2. Sao lưu tệp DGN
Chép `DC8.dgn` sang thư mục làm việc riêng, ví dụ `D:\CVP\test\DC8.dgn`, rồi mở bản sao này. (Macro không ghi vào DGN, nhưng làm trên bản sao là nguyên tắc an toàn.)

## 3. Mở DGN và tạo dự án VBA
1. Mở MicroStation V8i → mở `D:\CVP\test\DC8.dgn`.
2. Menu **Utilities → Macro → Project Manager** (hoặc gõ key-in `vba pm` rồi Enter).
3. Trong hộp **VBA Project Manager**: bấm **New**, đặt tên `CVP`, lưu `D:\CVP\CVP.mvba` → OK. Dự án `CVP` xuất hiện và được đánh dấu Loaded.
4. Chọn dòng `CVP`, bấm **Visual Basic Editor** (hoặc Alt+F11).

## 4. Nhập tệp .bas
1. Trong cửa sổ Microsoft Visual Basic, khung **Project** bên trái → chọn `CVP`.
2. Menu **File → Import File…** → chọn `D:\CVP\XuatPhanTu_CVP.bas` → Open.
3. Dưới `CVP` → **Modules** sẽ có `XuatPhanTu_CVP`. Nháy đúp để xem mã.
4. Menu **Debug → Compile CVP**. Không có thông báo nghĩa là biên dịch được. Nếu báo lỗi, chụp màn hình dòng bị tô vàng gửi lại.
5. **File → Save CVP** (Ctrl+S).

## 5. Chạy
Cách 1: trong VBA Editor, đặt con trỏ chuột trong `Public Sub XuatPhanTuJSON()` rồi nhấn **F5**.

Cách 2: về MicroStation, gõ key-in:
```
vba run [CVP]XuatPhanTu_CVP.XuatPhanTuJSON
```

Thanh trạng thái MicroStation hiện "CVP: dang xuat phan tu…". Khi xong có hộp thoại:
`CVP: da xuat N phan tu (bo qua M ...) -> D:\CVP\test\DC8.dgn.cvp.json` — **ghi lại N và M**.

## 5b. Xuất CẢ THƯ MỤC một lần (nhiều tờ)
1. Mở một tệp DGN bất kỳ trong thư mục (ví dụ DC1.dgn) — macro cần MicroStation đang mở một tệp.
2. Key-in: `vba run [CVP]XuatPhanTu_CVP.XuatThuMucJSON` (hoặc trong VBA Editor đặt con trỏ trong `Sub XuatThuMucJSON` rồi F5).
3. Hộp thoại hỏi thư mục → mặc định là thư mục của tệp đang mở → OK.
4. Macro mở lần lượt từng `.dgn` ở chế độ CHỈ ĐỌC (không hiện lên màn hình), ghi `<tên>.dgn.cvp.json` cạnh từng tệp, cuối cùng hiện bảng kết quả: số phần tử từng tệp, tệp nào lỗi.

## 6. Kiểm tra kết quả
- Thư mục chứa DGN có thêm `DC8.dgn.cvp.json`.
- Mở bằng Notepad: dòng đầu bắt đầu bằng `{"schema":"cvp.dgn_exchange/1"`; cuối tệp có `"stats":{"exported":...,"element_types":{...}}`.

## 7. Đối chiếu để nghiệm thu (ghi lại)
| Chỉ tiêu | Cách lấy trong MicroStation | Giá trị |
|---|---|---|
| Số phần tử Text ở Level 13 (số thửa) | Edit → Select By Attributes: Level 13, Type Text → Execute; đọc số phần tử đã chọn ở thanh trạng thái | |
| Số Text Level 4 (diện tích) | như trên, Level 4 | |
| Số Text Level 2 (loại đất) | như trên, Level 2 | |
| Có Cell NHANTHUA không? | Select By Attributes: Type Cell | |
| Có cung tròn (Arc) trên Level 10 không? | Select By Attributes: Level 10, Type Arc | |
| Working Units | Settings → Design File → Working Units: Master Unit là gì (m?) | |

## 8. Gửi lại
Đặt `DC8.dgn.cvp.json` vào thư mục `K:\My Drive\23. Claude\Liem` và nhắn kèm bảng mục 7. **Không đưa tệp này lên GitHub** (repo công khai).

## Lỗi thường gặp
| Hiện tượng | Xử lý |
|---|---|
| Menu Macro không có / VBA bị khóa | Phiên bản cài đặt thiếu VBA hoặc bị chính sách chặn — báo lại |
| `Compile error: User-defined type not defined` ở `Point3d`/`Element` | Dự án tạo ngoài MicroStation; hãy tạo dự án bằng Project Manager như bước 3 |
| `Sub or Function not defined` ở `DLongToString` | Báo lại tên hàm bị tô vàng (khác biệt giữa các bản V8i) |
| `ActiveX component can't create object` | Máy chặn ADODB.Stream — báo lại để chuyển sang cách ghi tệp khác |
| Lỗi khi nhập .bas (dòng dính nhau) | Tải lại bằng nút Download raw file, không copy-paste từ trình duyệt |
