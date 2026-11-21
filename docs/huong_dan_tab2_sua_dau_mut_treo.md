# Tab 2 — Xử lý đầu mút treo có kiểm soát

Nguyên tắc (Master Prompt mục VII, mức B): chỉ ĐỀ XUẤT; người dùng duyệt từng đối tượng; mô phỏng tác động trước;
ghi vào BẢN SAO; có macro hoàn tác; không cắt/lấp thửa, không đổi diện tích pháp lý.

## Các kiểu sửa (chỉ dời 1 đỉnh đầu mút của Line/LineString)
| Kiểu | Khi nào | Rủi ro |
|---|---|---|
| Nối 2 đầu treo (JOIN) | hai đầu treo đối diện nhau trong ngưỡng | B |
| Cắt nét thừa (TRIM) | đoạn cuối cắt qua ranh khác rồi thò ra | B |
| Kéo dài nét hụt (EXTEND) | kéo theo đúng hướng đoạn cuối chạm ranh khác | B |
| Bắt điểm gần nhất (SNAP) | không kéo thẳng được | B+ (đổi hướng nét — xem kỹ) |

Không đề xuất: khoảng hở ≥ ngưỡng; nét rời ngắn treo cả hai đầu (nghi ký hiệu); nhiều phần tử chung đầu mút; phần tử đóng/phần tử con.

## Các bước
1. Tab 2 → chọn tệp `.dgn` (đã có `<tên>.dgn.cvp.json` cạnh) → Hồ sơ Level → Hệ tọa độ → Ngưỡng (mặc định 1 m) → **Tìm đề xuất**.
2. **Đánh giá từng đề xuất**: cột "Tác động" cho biết số đầu treo giảm và lỗi MỚI phát sinh (chữ đỏ) nếu áp dụng riêng đề xuất đó.
3. Duyệt: tích từng dòng, hoặc **Chọn không lỗi mới, trừ SNAP**.
4. **Mô phỏng**: tổng tác động trước/sau của các đề xuất đã duyệt.
5. **Xuất ChangeSet + bản sao** → thư mục `Documents\CadastralValidatorPro\output\ChangeSet\CS_<tờ>_<thời gian>\` gồm:
   `<tờ>_BANSAO_<thời gian>.dgn`, `CVP_ApDung.bas`, `CVP_HoanTac.bas`, `CS_….xlsx`, `changeset.json`.
6. Trong MicroStation: mở **tệp BANSAO** → VBA Project Manager → dự án CVP → Import `CVP_ApDung.bas` → chạy `ApDungChangeSet`.
   Macro từ chối chạy nếu tên tệp không chứa `_BANSAO`; trước khi dời mỗi đỉnh, kiểm tra tọa độ hiện tại khớp giá trị "trước" (≤ 1 mm).
7. Xuất lại bản sao bằng `XuatPhanTuJSON` → kiểm tra lại bản sao ở Tab 3 → đối chiếu với tác động đã mô phỏng.
8. Cần hoàn tác: Import `CVP_HoanTac.bas` → chạy `HoanTacChangeSet` trên bản sao.

Trạng thái: macro áp dụng/hoàn tác **NOT_TESTED** trên MicroStation thật (dùng `GetElementByID`, `AsVertexList.ModifyVertex`, `Rewrite`).
