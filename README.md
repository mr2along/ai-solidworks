---
title: AI CAD Generator
emoji: 🧩
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AI CAD Generator — FreeCAD headless MVP

Nhập mô tả cơ khí bằng tiếng Việt để tạo gói file CAD ngay trên Hugging Face Docker Space.

## Định dạng đầu ra

- `.FCStd`: tài liệu FreeCAD có thể mở và chỉnh sửa; executor hiện lưu một `Part::Feature` cùng thuộc tính kích thước, chưa phải Feature Tree tham số đầy đủ.
- `.step`: trao đổi mô hình 3D.
- `.stl`: mô hình lưới cho in 3D.
- `.pdf`: bản vẽ kích thước 2D sơ bộ (không phải bản vẽ chứng nhận sản xuất).

## Phạm vi hiện tại

Bản đầu chỉ hỗ trợ **tấm chữ nhật với 4 lỗ xuyên**, mô tả đủ chiều dài, chiều rộng, chiều dày, đường kính lỗ và khoảng cách tâm lỗ đến mép. Ví dụ:

`Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm`

Bộ phân tích hiện là parser theo quy tắc, chưa phải mô hình AI tổng quát. Mô hình được tạo bằng FreeCAD headless trong container Linux; không cần cài SOLIDWORKS trên máy người dùng. File `.SLDPRT` gốc không được tạo.

## Chạy local bằng Docker

```bash
docker build -t ai-cad-generator .
docker run --rm -p 7860:7860 ai-cad-generator
```

Mở `http://localhost:7860`.

## API

- `GET /health`: kiểm tra ứng dụng.
- `GET /api/health/cad`: chạy import probe trong FreeCAD runtime (`FreeCAD`, `Part`, `Mesh`, `Sketcher`) và trả trạng thái 503 nếu module không tải được.
- `POST /api/plan`: kiểm tra mô tả và trả về CAD plan JSON.
- `POST /api/generate`: dựng mô hình và tải ZIP chứa FCStd, STEP, STL, PDF.

Ví dụ body:

```json
{
  "description": "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
  "part_name": "mounting_plate"
}
```

## Giới hạn và an toàn

- Chỉ chạy các thao tác CAD cố định đã định nghĩa; không thực thi mã Python do người dùng nhập.
- Mỗi job chạy trong thư mục tạm riêng, có giới hạn thời gian và trả file ZIP qua HTTP.
- Docker runtime dùng Python Debian cùng bộ FreeCAD Debian; image build chạy import smoke test dưới tài khoản ứng dụng trước khi đóng gói.
- Dữ liệu ghi trong filesystem của Space có thể mất khi Space khởi động lại; file tạo ra cần được tải xuống.
- Chưa xác nhận thành công trên runtime Hugging Face thực tế. Cần theo dõi build log của Space để xác minh gói FreeCAD Debian và tên executable trên image.
