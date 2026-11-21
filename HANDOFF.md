# HANDOFF

**Trạng thái:** G0 PARTIAL, G1 PARTIAL (21/11/2026). Mọi kết quả kiểm tra hiện chỉ được chứng minh trên dữ liệu tổng hợp.

**Khởi động:**
```bat
pip install -r requirements.lock
python -m pytest -q          REM kỳ vọng 49 passed
python main.py
```

**Chặn chính:** đọc phần tử DGN V8 cần MicroStation (COM hoặc macro VBA). Chưa thử trên máy thật.

**Bước tiếp theo theo thứ tự:**
1. Người dùng chạy `scripts/probe_microstation.py DC8.dgn` hoặc macro `XuatPhanTu_CVP.bas` trên DC8.dgn, gửi kết quả.
2. Sửa bộ trích xuất theo kết quả; thêm test tích hợp với `DC8.dgn.cvp.json` (giữ ngoài repo công khai).
3. Rời rạc hóa cung tròn; đối chiếu số lượng nhãn/vùng với MicroStation; lập golden dataset 3–5 tờ.
4. Xác nhận Level/ngưỡng/mã đất/CRS → nâng trạng thái rule từ PENDING.
5. G2: writer DGN qua COM, Tab 1 round-trip.
