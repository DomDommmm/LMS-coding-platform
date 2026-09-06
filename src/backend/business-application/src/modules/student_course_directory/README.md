# Student Course Directory (Module 2)

Module này quản lý các tính năng liên quan đến học viên, danh mục khóa học, đăng ký, tiến độ học tập, bài tập trắc nghiệm, khóa học yêu thích (Favorite) và đánh giá khóa học (Course Review). 
Đây là một trong các module cốt lõi của hệ thống LMS, cung cấp các luồng nghiệp vụ quan trọng từ khi người dùng tìm kiếm khóa học cho đến khi hoàn thành.

## 🚀 Các tính năng chính (Endpoints)

### 1. Catalog & Khóa học
- `GET /api/courses`: Lấy danh sách khóa học public (Course Catalog), có hỗ trợ phân trang và tìm kiếm.
- `GET /api/courses/{slug}`: Xem chi tiết khóa học.

### 2. Enrollment & Tiến độ học tập
- `POST /api/courses/{slug}/enroll`: Đăng ký khóa học (yêu cầu Auth). Hỗ trợ khóa học miễn phí (đăng ký thành công ngay) và khóa học trả phí (trả về URL thanh toán PayOS).
  - *Lưu ý: Thanh toán khóa trả phí hiện dùng URL checkout tạm (FRONTEND_CHECKOUT_URL), việc tích hợp PayOS thật sẽ do thành viên khác đảm nhiệm.*
- `POST /api/courses/{slug}/unenroll`: Hủy đăng ký khóa học.
- `GET /api/courses/enrolled`: Xem danh sách các khóa học đã đăng ký.
- `GET /api/courses/{slug}/study-content`: Lấy nội dung học thuật để bắt đầu học.
- `POST /api/lessons/{lesson_content_id}/complete`: Đánh dấu hoàn thành một nội dung học tập.

### 3. Quiz & Thực hành
- `GET /api/quizzes/{quiz_id}`: Lấy thông tin bài tập trắc nghiệm (không lộ đáp án).
- `POST /api/quizzes/{quiz_id}/submit`: Nộp bài, tự động chấm điểm và trả về kết quả.

### 4. Yêu thích khóa học (Course Favorite)
- `GET /api/favorites`: Lấy danh sách khóa học yêu thích của học viên.
- `PUT /api/courses/{course_id}/favorite`: Thêm khóa học vào danh sách yêu thích. Xử lý an toàn (idempotent) không văng lỗi nếu đã thêm trước đó.
- `DELETE /api/courses/{course_id}/favorite`: Bỏ khóa học khỏi danh sách yêu thích. Xử lý an toàn (idempotent) không văng lỗi nếu chưa từng thêm.

### 5. Đánh giá khóa học (Course Review)
- `GET /api/courses/{course_id}/reviews`: Lấy danh sách đánh giá của một khóa học (Public), kèm theo Rating Summary (tổng số review, điểm trung bình, phân bổ sao). Computed thông qua subquery trực tiếp dưới DB.
- `POST /api/courses/{course_id}/reviews`: Đăng review khóa học (1 tài khoản chỉ được review 1 lần trên 1 khóa học đã đăng ký). Trả về lỗi `409 DUPLICATE_RESOURCE` nếu review trùng lặp. Yêu cầu enrollment.
- `PATCH /api/courses/{course_id}/reviews/{review_id}`: Sửa đánh giá khóa học (chỉ chủ sở hữu review mới có quyền).

### 6. Instructor (Teacher)
- Hỗ trợ các API cho giáo viên quản lý khóa học (`POST /api/teacher/courses`, `PUT`, `GET`, `POST /api/teacher/courses/{course_id}/sections`, `POST /api/teacher/courses/{course_id}/submit-review`, ...).

---

## 🛠 Cách chạy và kiểm thử

### 1. Chuẩn bị môi trường
- Đảm bảo **Docker Desktop** đang chạy.
- Khởi động cơ sở dữ liệu PostgreSQL từ thư mục gốc của project:
  ```bash
  docker compose up -d postgres
  ```
- Khởi chạy server FastAPI:
  ```bash
  cd src/backend/business-application
  uv run uvicorn src.app:app --reload
  ```

### 2. Kiểm thử thông qua Swagger UI (Tương tác trực tiếp qua `/docs`)
Truy cập Swagger UI tại: `http://localhost:4000/docs`.

**Cách lấy JWT Token để test các endpoint yêu cầu Auth:**
1. Module 2 yêu cầu quyền (`Role.STUDENT` cho thao tác học viên, `Role.TEACHER` cho giáo viên). JWT sinh ra phải chứa thông tin role.
2. Dùng file `scripts/demo_server.py` hoặc các công cụ mock token nội bộ để lấy JWT có chứa:
   - `sub`: ID của user (VD: 1 cho Student, 2 cho Teacher)
   - `roles`: `["STUDENT"]` (Phải viết in hoa theo chuẩn hệ thống).
3. Nhấp vào nút **Authorize** ở góc trên cùng bên phải màn hình Swagger UI và dán token vào.

### 3. Chạy Automated Tests
Toàn bộ các tính năng đã được test độ phủ 100% bằng `pytest`.
```bash
uv run pytest tests/module2/ -v
```

---

## 📝 Changelog (feat/module2-db-integration)

Các thay đổi quan trọng đã được thực hiện trong suốt chu kỳ phát triển trên nhánh này:

- **1. Catalog & Enrollment DB Integration**: 
  - Nối toàn bộ `GET /api/courses`, `GET /api/courses/{slug}` (Course Catalog) với Database PostgreSQL thay vì mock data.
  - Tích hợp DB thật cho tính năng Đăng ký (`POST /api/courses/{slug}/enroll`) và Hủy đăng ký (`POST /api/courses/{slug}/unenroll`), xử lý checkout PayOS.
- **2. Khắc phục lỗi TestClient rò rỉ DB Pool**: 
  - Thiết kế mock Database Session thông minh cho `TestClient`, fix thành công lỗi `InterfaceError: cannot perform operation: another operation is in progress`.
- **3. Instructor Test Coverage**: 
  - Hoàn thiện test coverage độ ưu tiên cao (risk-priority) cho các thao tác CRUD của Instructor bằng `httpx.AsyncClient` và `ASGITransport` để đảm bảo transaction rollback chính xác trong môi trường DB.
- **4. Course Favorite**: 
  - Bổ sung 3 endpoint yêu thích khóa học (`GET /favorites`, `PUT`, `DELETE`).
  - Xử lý idempotency tinh tế bằng cách catch `IntegrityError` và tối ưu query (sử dụng subquery để map với `CourseItemResponse`).
- **5. Course Review**: 
  - Thiết kế và cài đặt endpoint `GET /courses/{course_id}/reviews` kèm theo `CourseReviewSummary` (thống kê sao và đếm lượt đánh giá realtime).
  - Tích hợp logic ràng buộc ownership, bắt lỗi duplicated (`409`), ràng buộc khóa học đã enroll (chỉ Student đã enroll mới được đánh giá) cho `POST` và `PATCH`.
- **6. Sửa lỗi xung đột với nhánh `feat/oj-flow`**: 
  - Fix lỗi tích hợp MinIO/S3 gây vỡ upload (bổ sung `Depends()`).
  - Bỏ các giá trị hard-code teacher_id để logic lấy role/ownership động quay trở lại hoạt động bình thường.
- **7. Sửa lỗi permission tiềm ẩn (SEED_STUDENT)**: 
  - Phát hiện và sửa lỗi khai báo mock JWT roles cho user giả lập (`"student"` -> `"STUDENT"`) để phù hợp với quy tắc in hoa của Base Model (`Role.STUDENT`).
