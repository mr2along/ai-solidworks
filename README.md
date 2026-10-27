---
title: AI CAD Agent
emoji: 🧩
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AI CAD Agent — FreeCAD headless MVP

Nhập mô tả cơ khí bằng tiếng Việt để tạo gói file CAD ngay trên Hugging Face Docker Space.

## Định dạng đầu ra

- `.FCStd`: tài liệu FreeCAD có thể mở và chỉnh sửa; executor hiện lưu một `Part::Feature` cùng thuộc tính kích thước, chưa phải Feature Tree tham số đầy đủ.
- `.step`: trao đổi mô hình 3D.
- `.stl`: mô hình lưới cho in 3D.
- `.pdf`: bản vẽ sơ bộ gồm hình trục đo 3D, hình chiếu vuông góc sáu mặt và hình chiếu trên có kích thước (không phải bản vẽ chứng nhận sản xuất).

## Phạm vi hiện tại

Bản đầu chỉ hỗ trợ **tấm chữ nhật với 4 lỗ xuyên**, mô tả đủ chiều dài, chiều rộng, chiều dày, đường kính lỗ và khoảng cách tâm lỗ đến mép. Parser hỗ trợ mẫu tiếng Việt và tiếng Anh đã kiểm thử, quy đổi mm, cm, m và inch sang mm. Ví dụ:

`Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm`

`Make a plate 10 cm long, 60 mm wide, 5 mm thick, with four through holes Ø6 mm, 10 mm from each edge`

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
- `POST /api/plan`: kiểm tra mô tả và trả về CAD plan JSON gồm feature, tham số, ràng buộc, giả định, cảnh báo và kết quả validation.
- `POST /api/generate`: nhận `{"plan": <plan>}` từ bước preview; server xác thực lại plan trước khi gọi FreeCAD. Gọi `/api/plan` trước, sau đó gửi trường `plan` trong response; request cũ chỉ có mô tả cần chuyển sang flow hai bước này.

Gọi `POST /api/plan` với mô tả:

```json
{
  "description": "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
  "part_name": "mounting_plate"
}
```

Response có thuộc tính `plan`; sau khi rà soát preview, gửi thuộc tính đó tới `POST /api/generate`:

```json
{
  "plan": {
    "schema_version": "1.0",
    "part_name": "mounting_plate",
    "units": "mm",
    "features": [
      {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
      {"id": "holes", "type": "through_holes", "diameter": 6, "positions": [
        {"x": 10, "y": 10}, {"x": 90, "y": 10}, {"x": 10, "y": 50}, {"x": 90, "y": 50}
      ]}
    ],
    "outputs": ["fcstd", "step", "stl", "pdf"],
    "assumptions": ["Khoảng cách mép được hiểu là từ tâm lỗ đến cạnh tấm."],
    "warnings": ["PDF đầu ra là bản vẽ minh họa, không phải bản vẽ sản xuất được chứng nhận."],
    "backend": "freecad"
  }
}
```

Giao diện gửi CAD plan đã hiển thị sau khi người dùng xác nhận. Nếu mô tả hoặc tên part đổi, preview cũ bị xóa; các kích thước chỉnh sửa được kiểm tra lại tại API. Gửi mô tả trực tiếp tới `/api/generate` không còn được chấp nhận; client cũ cần chuyển sang flow hai bước.

## Giới hạn và an toàn

- Chỉ chạy các thao tác CAD cố định đã định nghĩa; không thực thi mã Python do người dùng nhập.
- Mỗi job chạy trong thư mục tạm riêng, có giới hạn thời gian và trả file ZIP qua HTTP.
- Docker runtime dùng Python Debian cùng bộ FreeCAD Debian; image build chạy import smoke test dưới tài khoản ứng dụng trước khi đóng gói.
- Dữ liệu ghi trong filesystem của Space có thể mất khi Space khởi động lại; file tạo ra cần được tải xuống.
- FreeCAD 0.20.2 đã được xác nhận trên GitHub Docker smoke test và Hugging Face Space sau deploy; bài generation trên Space đã trả HTTP 200 và các file trong ZIP đã qua kiểm tra định dạng.
- Bộ parser xác định đã kiểm thử các mẫu mô tả tiếng Việt và tiếng Anh cho tấm chữ nhật 4 lỗ; các feature khác, job queue, xác thực người dùng và SOLIDWORKS Agent chưa được xác minh/triển khai.
