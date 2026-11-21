# Ma trận pháp lý và tiêu chuẩn kỹ thuật

> **Trạng thái chung: CHƯA XÁC MINH trong lần phát triển này.** Cột "Trạng thái theo Master Prompt" chép nguyên từ Phụ lục V2.1/V2.2 do người dùng cung cấp; phần mềm chưa tự đối chiếu văn bản gốc. Không rule nào trong `son_la_draft.json` được gắn `LEGAL_REQUIREMENT`. Ngày lập: 21/11/2026.

| Mã | Văn bản | Ngày | Điều/khoản/phụ lục liên quan | Phân hệ | Trạng thái theo Master Prompt | Trạng thái trong phần mềm | Nguồn |
|---|---|---|---|---|---|---|---|
| LUAT_DD_2024 | Luật Đất đai 31/2024/QH15; Luật 43/2024/QH15 sửa đổi | 18/01/2024; 29/06/2024 | CẦN BỔ SUNG | 2,3,5,6 | Phải rà soát bản hiện hành | PENDING_VERIFICATION | — |
| LUAT_DDBD | Luật Đo đạc và bản đồ 27/2018/QH14 | 14/06/2018 | CẦN BỔ SUNG | tất cả | Phải rà soát sửa đổi | PENDING_VERIFICATION | — |
| ND101_2024 | NĐ 101/2024/NĐ-CP (hồ sơ địa chính, CSDL) | 29/07/2024 | CẦN BỔ SUNG | 3,6 | Có sửa đổi bởi NĐ 226/2025 | PENDING_VERIFICATION | — |
| ND226_2025 | NĐ 226/2025/NĐ-CP | 15/08/2025 | CẦN BỔ SUNG | 2,5,6 | Đã xác minh khái quát | PENDING_VERIFICATION | vanban.chinhphu.vn docid=214955 |
| TT26_2024 | TT 26/2024/TT-BTNMT kỹ thuật đo đạc lập BĐĐC (hiệu lực 15/01/2025), sửa đổi bởi TT 23/2025/TT-BNNMT; VBHN 34/VBHN-BNNMT | 26/11/2024 | **Điều 8 khoản 5 + Phụ lục số 04** (giới hạn sai diện tích) — đã đọc từ bản .docx người dùng cung cấp 21/11/2026; các điều/phụ lục khác CẦN BỔ SUNG | 1–6 (nguồn cốt lõi) | Có sửa đổi bởi TT 23/2025 | AREA-001: VERIFIED_PARTIAL (chưa đối chiếu sửa đổi TT 23/2025 với Phụ lục 04); còn lại PENDING | bản .docx người dùng; vanban.chinhphu.vn docid=212227 |
| TT10_2024 | TT 10/2024/TT-BTNMT hồ sơ địa chính, GCN | 31/07/2024 | mẫu trích lục — CẦN BỔ SUNG | 6 | Đã xác minh nguồn gốc | PENDING_VERIFICATION | vanban.chinhphu.vn docid=210905 |
| TT25_2024 | TT 25/2024/TT-BTNMT quy trình CSDL đất đai | 26/11/2024 | CẦN BỔ SUNG | 1,3 | Cần kiểm tra văn bản gốc | PENDING_VERIFICATION | vanban.chinhphu.vn docid=212226 |
| TT24_2018 / TT19_2024 | Kiểm tra, thẩm định, nghiệm thu sản phẩm đo đạc | 15/11/2018; 31/10/2024 | CẦN BỔ SUNG | báo cáo | Rà soát sửa đổi | PENDING_VERIFICATION | — |
| QD108_2025_SL | QĐ 108/2025/QĐ-UBND Sơn La (quản lý hoạt động đo đạc) | 18/10/2025 | Điều 7–9; khoản 1 Điều 3 bị bãi bỏ bởi QĐ 2947/QĐ-UBND (19/11/2025) | báo cáo bàn giao | Hết hiệu lực một phần | PENDING_VERIFICATION | vbpl.vn ItemID=183446 |
| QD44_2025_SL | QĐ 44/2025/QĐ-UBND Sơn La (định mức KTKT) | 01/05/2025 | — | không dùng cho kiểm tra | Chưa xác minh độc lập (V2.2) | KHÔNG DÙNG | — |

## Điểm cần người dùng xác nhận

1. **Mâu thuẫn nguồn:** Master Prompt nêu QĐ 44/2025/QĐ-UBND là định mức KTKT đo đạc của Sơn La, trong khi bộ tài liệu pháp lý nội bộ của người dùng nhắc QĐ 47/2025/QĐ-UBND (kiểm tra – nghiệm thu) và QĐ 109/2025/QĐ-UBND (định mức KTKT đo đạc địa chính, hồ sơ địa chính, CSDL đất đai). Phần mềm chưa dùng văn bản nào trong số này; cần xác định đúng số hiệu trước khi đưa vào `legal_registry`.
2. Số điều/phụ lục TT 26/2024 (đã sửa đổi) cho: bảng phân lớp Level, hạn sai diện tích theo tỷ lệ, quy cách khung, ký hiệu.
3. Danh mục mã loại đất áp dụng tại thời điểm hồ sơ.

## Quy tắc phần mềm (đã cài đặt)

- `domain/rules.py` từ chối nạp rule `LEGAL_REQUIREMENT` thiếu `legal_refs` hoặc chưa `VERIFIED_CURRENT`; từ chối bật auto-fix cho rule chưa xác minh.
- Mỗi báo cáo ghi `rule_pack_version`, `config_hash`, SHA-256 nguồn, thời điểm chạy và tuyên bố "không phải kết quả kiểm định/chứng nhận LANDINFO hay cơ quan nhà nước".

## Ghi chú áp dụng Phụ lục 04 TT 26/2024 (21/11/2026)

- Khoản 5 Điều 8 quy định giới hạn sai giữa diện tích trên bản đồ số và diện tích **đo trực tiếp tại thực địa**. Phần mềm vận dụng cho so sánh *diện tích nhãn — diện tích tính từ tọa độ* theo quyết định của người dùng; báo cáo ghi rõ căn cứ.
- Chú thích (*) Phụ lục 04: nội suy đến 01 m² ⇒ diện tích lấy đến 1 m² (làm tròn xuống) trước khi tính.
- **Điểm không thống nhất trong văn bản:** tỷ lệ 1:5.000 và 1:10.000, dòng "50 < S ≤ 300" ghi "so với hạn sai của thửa đất **40 m²**" trong khi dòng trên là "S ≤ **50** … ≤ 0,5 m²". Phần mềm lấy mốc 50 m² — chờ người dùng xác nhận.
- Diện tích nhãn DC8 theo **mặt đất thực** (người dùng xác nhận). Phần mềm quy đổi: lưới → ellipsoid (chiếu ngược TM, KTT 104°, k0 0,9999) → mặt đất × (1 + h/R)², h = độ cao trung bình do người dùng nhập.
