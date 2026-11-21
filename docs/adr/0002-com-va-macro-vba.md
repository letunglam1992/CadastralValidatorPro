# ADR-0002: Hai đường trích xuất MicroStation — COM Python và macro VBA

- Trạng thái: Đề xuất, chờ thử nghiệm.
- Bối cảnh: V8i thường 32-bit; ứng dụng chính Python x64. Chưa biết COM out-of-process có hoạt động ổn định và pywin32 trả `Point3d` thế nào.
- Quyết định: (1) `adapters/microstation_com.py` dùng `OpenDesignFileForProgram` chỉ đọc, không kill `ustation.exe`; (2) dự phòng `scripts/microstation/XuatPhanTu_CVP.bas` chạy trong MicroStation. Chỉ xây helper 32-bit + IPC nếu cả hai thất bại (Master Prompt III).
- Hệ quả: cần `scripts/probe_microstation.py` trên máy thật để chọn đường chính.
