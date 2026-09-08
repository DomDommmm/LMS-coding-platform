# API Specification - LMS Coding Platform

## 1. Mục đích và nguồn sự thật

Tài liệu này là **target API contract cho MVP**, dùng để FE và BE triển khai thống nhất theo:

- Nghiệp vụ: [`prd.md`](../prd-documents/prd.md).
- Khoảng cách hiện trạng: [`gap-analysis.md`](../prd-documents/gap-analysis.md).
- Schema đề xuất: [`DATABASE.txt`](../DATABASE.txt).
- Kế hoạch triển khai: [`overall-plan.md`](../plans/overall-plan.md).

Route xuất hiện trong các bảng bên dưới là contract mục tiêu, không mặc nhiên có nghĩa route đã được implement. Trạng thái triển khai được theo dõi trong [`overall-plan.md`](../plans/overall-plan.md) và source tương ứng.

Các ký hiệu:

- `GATED`: contract hoặc payload chưa được phép triển khai cho tới khi quyết định nghiệp vụ tương ứng được duyệt và cập nhật vào các tài liệu nguồn.
- `GATED-SCHEMA`: nghiệp vụ có trong PRD nhưng canonical database proposal chưa có bảng/cột cần thiết; phải sửa và duyệt `DATABASE.txt` trước khi implement contract.
- `LEGACY`: route hiện có trong source nhưng không phải contract cuối; chỉ giữ tạm thời khi cần migration client.
- Không có nhãn: target contract đã đủ rõ để triển khai theo thứ tự trong `overall-plan.md`.

| Thành phần | Base URL local | Trách nhiệm |
|---|---|---|
| Auth Provider | `http://localhost:4001/api/auth` | Registration, identity, session, token, OTP và password recovery |
| Business Application | `http://localhost:4000/api` | Toàn bộ nghiệp vụ LMS, commerce, learning, Judge orchestration và Interview |

## 2. Quy ước chung

### 2.1. Request và định dạng dữ liệu

- Request mặc định dùng `application/json`; login form và file upload là ngoại lệ được ghi rõ ở từng route.
- Access token gửi bằng `Authorization: Bearer <access_token>`.
- Refresh token dùng cơ chế cookie bảo mật hoặc body theo quyết định Auth; FE không được phụ thuộc đồng thời vào cả hai.
- Timestamp dùng ISO 8601 UTC.
- Tiền dùng decimal string, ví dụ `"199000.00"`, luôn đi cùng `currency`; không dùng JSON float làm nguồn persistence.
- Tên field dùng `snake_case`.
- Mutation idempotent nhận `Idempotency-Key` ở header khi route yêu cầu.
- Upload chỉ lưu URL/object key trong database; API phải kiểm tra MIME type, kích thước và ownership.

### 2.2. Response envelope

| Loại | Cấu trúc |
|---|---|
| Một resource | `{ "data": { ... } }` |
| Danh sách | `{ "data": [...], "pagination": { "page": 1, "size": 20, "total": 42 } }` |
| Mutation | `{ "data": { ... }, "message": "..." }` |
| Không có body nghiệp vụ | `{ "message": "..." }` |
| Lỗi | `{ "message": "...", "error_code": "...", "details": [] }` |

Ví dụ lỗi:

```json
{
  "message": "Course đã được enrollment",
  "error_code": "ALREADY_ENROLLED",
  "details": [
    { "field": "course_id", "reason": "duplicate enrollment" }
  ]
}
```

Các error code tối thiểu:

| HTTP | Error code | Ý nghĩa |
|---|---|---|
| 400 | `INVALID_REQUEST` | Payload hoặc thao tác không hợp lệ ngoài validation field |
| 401 | `UNAUTHENTICATED` | Thiếu/sai/hết hạn token |
| 403 | `FORBIDDEN` | Không đủ role, capability hoặc ownership |
| 404 | `NOT_FOUND` | Resource không tồn tại hoặc được ẩn theo access policy |
| 409 | `DUPLICATE_RESOURCE` | Vi phạm unique/idempotency ngoài trường hợp trả lại kết quả cũ |
| 409 | `INVALID_STATE` | State transition không hợp lệ |
| 410 | `PAYMENT_EXPIRED` | Payment đã hết hạn |
| 422 | `VALIDATION_ERROR` | Field không hợp lệ |
| 429 | `RATE_LIMITED` | Vượt giới hạn request |

Không trả raw exception, stack trace, JWT, OTP/reset code, CCCD đầy đủ, secret hoặc raw payment payload.

### 2.3. Quy tắc ánh xạ API với database

Mọi field trong request/response của tài liệu này phải thuộc một trong bốn nhóm sau:

- **Stored field:** tên field trùng cột trong `DATABASE.txt`, trừ alias được ghi rõ.
- **Command field:** không phải cột; dùng để yêu cầu service thực hiện transition hoặc tạo nhiều bản ghi. Ví dụ `decision`, `tag_ids`, `Idempotency-Key`.
- **Projection field:** chỉ đọc, được tính từ bảng nguồn hoặc provider và không được ghi ngược vào một cột cùng tên. Ví dụ `capabilities`, `passed`, `locked`, `can_answer`, `checkout_url`.
- **Transient/transport field:** chỉ tồn tại trong giao thức hoặc hạ tầng tạm thời, không phải dữ liệu nghiệp vụ cần lưu trong các bảng canonical. Ví dụ access token, OTP/authorization code, pagination, acknowledgement, provider QR và kết quả `run` không chấm điểm.

Quy tắc bắt buộc:

- Primary key, foreign key theo current user, status do state machine quản lý và timestamp do server tạo không được nhận từ client, trừ route Admin/import được nêu rõ.
- Field soft-delete, reviewer, audit, idempotency, signature verification và balance không được client tự đặt.
- Alias API duy nhất đang được chấp nhận cho field database là `checkout_url` -> `transaction.payos_link`.
- Nếu API cần lưu một field chưa có trong `DATABASE.txt`, route phải mang nhãn `GATED-SCHEMA`; không được mô tả field đó như dữ liệu đã persist.
- Projection phải liệt kê rõ bảng nguồn. FE không gửi projection field trong mutation request.
- Transient/transport field không được thêm ngầm vào ORM model. Nếu Product quyết định cần persist field này, phải cập nhật `DATABASE.txt` và migration contract trước.

Các field Auth như `otp`, authorization `code`, reset token, access token, `expires_in`, `token_type`, `retry_after_seconds`, JWK/PEM và `key_id` là command hoặc transient/transport field của Auth Provider. Chúng không phải cột của bảng `user`. Auth Provider phải dùng kho bí mật có TTL hoặc cơ chế ký/xác minh phù hợp; nếu chọn lưu chúng trong relational database thì schema tương ứng phải được bổ sung vào `DATABASE.txt` trước khi triển khai.

### 2.4. Canonical DTO và field mapping

Các mô tả rút gọn trong bảng route như `CourseView`, `PaymentTransactionView` hoặc “course cards” phải tuân theo field set dưới đây. Implementation không được tự thêm stored field ngoài mapping này.

#### Identity và profile

| DTO | Bảng nguồn | Request fields được phép | Stored fields trong response | Field không trả hoặc projection |
|---|---|---|---|---|
| `UserIdentityMe`  | `user` | Give Jwt Token in header | `roles,email,account_status` | `id, email, password. more personal information` |
| `RegisterRequest` / `UserView` | `user` | `full_name`, `address`, `email`, `password` | `id`, `full_name`, `address`, `email`, `avatar_url`, `active`, `account_status`, `created_at`, `updated_at` | Hash `password` trước khi ghi; không trả `password`, `refresh_token`; `status` là legacy và không dùng làm account contract |
| `UserRoleView` | `user_role` | Admin command nhận `roles[]`; service tạo/xóa row | `id`, `user_id`, `role` | `capabilities` là projection từ role + application |
| `UserIdentityInternal` | `user_identity` | Google callback nhận transient `credential_code`; provider identity do server lấy từ token đã xác minh | `id`, `user_id`, `provider`, `provider_id`, `created_at`, `updated_at` | Chỉ dùng nội bộ Auth Provider; không trả `provider_id` trong token response và không lưu provider access/ID token |
| `StudentProfileWrite/View` | `student_profile` | `bio`, `learning_preferences`, `social_links` | `user_id`, các field request | `full_name` và `avatar_url` là projection từ `user` |
| `TeacherProfileWrite/View` | `teacher_profile` | `avatar_url`, `bio`, `headline`, `expertise_tags`, `years_of_experience`, `education_entries`, `experience_entries`, `github_url`, `linkedin_url`, `website_url`, `email`, `phone` | `user_id`, các field request, `approved_at`, `is_active`, `created_at`, `updated_at` | JSON fields giữ nguyên cấu trúc đã validate; profile không tự cấp `can_teach` |
| `TeacherApplicationWrite/View` | `teacher_register` | `bio`, `education_evidence_urls`, `legal_full_name`, `date_of_birth`, `identity_number`, `identity_front_url`, `identity_back_url`, `selfie_with_id_url`, `cv_url`, `motivation` | `id`, `teacher_profile_id`, role-filtered non-sensitive fields, masked identity/document projections, `status`, `reviewed_note`, `reviewed_by`, `reviewed_at`, `submitted_at`, `created_at`, `updated_at` | `teacher_profile_id` lấy từ current profile; không nhận status/reviewer/timestamp; không trả raw identity number/document URL cho actor không được phép |
| `TeacherApplicationHistoryView` | `teacher_register_history` | Không nhận trực tiếp | `id`, `teacher_register_id`, `status`, `note`, `acted_by`, `acted_at` | Row được service tạo khi transition |

#### Course, curriculum và learning

| DTO | Bảng nguồn | Request fields được phép | Stored fields trong response | Field không trả hoặc projection |
|---|---|---|---|---|
| `CourseWrite/View` | `courses` | `title`, `field`, `tags` dạng string, `description`, `thumbnail_url`, `price` | `id`, `title`, `teacher_id`, `slug`, `rating`, `field`, `tags`, `description`, `thumbnail_url`, `price`, `currency`, `status`, `submitted_at`, `reviewed_by`, `reviewed_note`, `reviewed_at`, `created_at`, `updated_at` | `currency` luôn `USD` do server đặt; không nhận `teacher_id`, `slug`, `rating`, status/review fields; public view ẩn moderation metadata; `is_favorited`, `is_enrolled`, review summary là projection |
| `CourseModerationView` | `course_moderation_review` | Command nhận `decision`, `note` | `id`, `course_id`, `status`, `note`, `reviewed_by`, `reviewed_at` | `decision` được map sang `status`; reviewer/time lấy từ server |
| `SectionWrite/View` | `sections` | `title`, `position` | `id`, `course_id`, `title`, `position` | `course_id` lấy từ path |
| `LessonWrite/View` | `lesson` | `title`, `summary`, `score`, `position` | `id`, `section_id`, `title`, `summary`, `score`, `position`, `created_at`, `updated_at` | `section_id` lấy từ path |
| `LessonContentBind/View` | `lesson_content` | `content_type`, `content_id`, `media_url`, `position` | `id`, `lesson_id`, `content_type`, `content_id`, `media_url`, `position`, `created_at` | Không có `completion_policy` trong schema hiện tại; `locked` là projection |
| `LessonContentProgressView` | `lesson_content_progress` | Reading complete không có body | `id`, `enrollment_id`, `lesson_content_id`, `completed`, `completed_at` | Quiz/Problem completion do service cập nhật; progress percent là projection |
| `ReadingContentWrite/View` | `reading_content` | `title`, `content` | `id`, `title`, `content`, `created_at`, `updated_at` | Ownership suy ra qua LessonContent binding |
| `CourseFavoriteView` | `course_favorite` | Không có body; course lấy từ path | `id`, `student_id`, `course_id`, `created_at` | `student_id` lấy từ current user; `is_favorited` là projection |
| `CourseReviewWrite/View` | `course_review` | `rating`, `content` | `id`, `course_id`, `student_id`, `rating`, `content`, `created_at`, `updated_at` | Course/student lấy từ path/current user; unique `(course_id, student_id)` và yêu cầu enrollment |

#### Quiz và Online Judge

| DTO | Bảng nguồn | Request fields được phép | Stored fields trong response | Field không trả hoặc projection |
|---|---|---|---|---|
| `QuizWrite/View` | `quizzes` | `title`, `passing_score`, `start_date`, `end_date`, `attempts` | `id` và các field request | Không trả `deleted_at`; ownership suy ra qua binding |
| `QuizQuestionWrite/View` | `quiz_questions` | `title`, `content`, `question_type`, `points` | `id`, `quiz_id` và các field request | `quiz_id` lấy từ path |
| `QuizOptionAuthorWrite/View` | `quiz_options` | `content`, `is_correct` | `id`, `question_id`, `content`, `is_correct` | Learner view chỉ có `id`, `question_id`, `content`; không trả `is_correct` |
| `QuizEnrollmentView` | `quiz_enrollment` | Không nhận trực tiếp | `id`, `quiz_id`, `student_id`, `enrolled_at` | Service tạo theo course/enrollment policy |
| `QuizAttemptView` | `quiz_attempt`, `quiz_submission` | Start không có body; submit nhận final structured `answers` | Attempt: `id`, `quiz_id`, `student_id`, `attempt_no`, `status`, `started_at`, `submitted_at`; terminal submission: `id`, `quiz_attempt_id`, `score`, parsed `answers`, `submitted_at` | Không save/resume; `passed`, `attempts_left`, `expires_at` là projection; learner không nhận answer key |
| `ProblemWrite/View` | `problem` | `title`, `slug`, `statement`, `input_description`, `output_description`, `constraints`, `sample_input`, `sample_output`, `explanation`, `difficulty`, `passing_score`, `public` | `id`, `teacher_id`, các field request, `created_at` | `teacher_id` từ current Teacher; `passing_score` là completion threshold; `tags`, supported languages, solved state và acceptance rate là relations/projection |
| `ProblemTagView` | `problem_tag`, `problem_tag_mapping` | Command nhận `tag_ids[]`; tag management nhận `tag_name` | Tag: `id`, `tag_name`; mapping: `id`, `problem_id`, `tag_id` | `tag_ids` không phải cột của `problem` |
| `ProblemConfigWrite/View` | `problem_config` | `language_id`, `time_limit_ms`, `memory_limit_mb` | `id`, `problem_id` và các field request | `problem_id` lấy từ path/problem command |
| `LanguageView` | `language` | Admin config nếu được mở rộng | `id`, `name`, `default_time_limit`, `default_memory_limit`, `is_active` | Learner chỉ nhận active languages |
| `TestcaseWrite/View` | `testcase` | Multipart nhận hai file input/output cùng `score`, `is_hidden`; service lưu object key vào `input_file`, `output_file` | `id`, `problem_id`, `input_file`, `output_file`, `score`, `is_hidden` cho owner/Admin | Client không được tự gửi storage path; learner không nhận file path/raw hidden data |
| `SubmissionWrite/View` | `submission` | `source_code`, `language_id`; problem lấy từ path | `id`, `problem_id`, `student_id`, `language_id`, `source_code`, `status`, `score`, `runtime_ms`, `memory_kb`, `submitted_at` | Source chỉ trả owner/authorized Teacher/Admin; testcase summary là projection |
| `SubmissionResultView` | `submission_result_detail` | Không nhận từ client | `id`, `submission_id`, `testcase_id`, `status`, `runtime_ms`, `memory_kb` | Learner hidden result không trả `testcase_id` nếu có thể suy ra dữ liệu ẩn |

#### Commerce và Teacher Finance

| DTO | Bảng nguồn | Request fields được phép | Stored fields trong response | Field không trả hoặc projection |
|---|---|---|---|---|
| `EnrollmentView` | `enrollment` | Free-enroll không có body | `id`, `student_id`, `course_id`, `status`, `enrolled_at`, `completed_at` | Student/course lấy từ current user/path/payment |
| `PaymentTransactionView` | `transaction` | Checkout command chỉ lấy course từ path và `Idempotency-Key`; client không gửi amount/status/provider fields | `id`, `student_id`, `course_id`, `payment_method`, `amount`, `currency`, `status`, `transaction_code`, `checkout_url`, `expires_at`, `completed_at`, `created_at`, `updated_at` | `currency` luôn `USD`; `checkout_url` là alias của `payos_link`; không trả `idempotency_key`; `payos_code`, `signature_verified` chỉ Admin/internal; QR có thể là transient provider data |
| `WalletView` | `wallet` | Không có client write | `id`, `teacher_id`, `available_balance`, `pending_balance`, `currency`, `created_at`, `updated_at` | Balance do ledger projection/service quản lý |
| `WalletLedgerView` | `wallet_ledger` | Không có client write trực tiếp | `id`, `wallet_id`, `transaction_id`, `payout_request_id`, `entry_type`, `amount`, `currency`, `created_at` | Immutable; corrections tạo row mới |
| `PayoutRequestWrite/View` | `payout_request` | Teacher chỉ gửi `amount`; currency do server cố định `USD`; Admin command gửi decision/settlement fields theo route | `id`, `wallet_id`, `teacher_id`, `amount`, `currency`, `status`, `reviewed_by`, `reviewed_at`, `settlement_reference`, `failure_reason`, `created_at`, `updated_at` | Review `note` ghi vào `audit_log.note`, không phải payout field; payout destination/settlement mechanism vẫn chưa có canonical source |

#### Interview, communication và dashboard

| DTO | Bảng nguồn | Request fields được phép | Stored fields trong response | Field không trả hoặc projection |
|---|---|---|---|---|
| `InterviewSessionWrite/View` | `interview_session` | `topic`, `level` | `id`, `student_id`, `topic`, `level`, `status`, `max_questions`, `question_count`, `started_at`, `ended_at`, `report_generated_at` | `can_answer` là projection `status == ACTIVE`; Student không gửi count/status/timestamps |
| `InterviewMessageWrite/View` | `interview_message` | Answer command nhận `answer_text`, được map sang `content` | `id`, `session_id`, `sender`, `content`, `created_at` | `sender` do server xác định; `answer_text` là text từ speech-to-text hoặc typed fallback, không phải media payload |
| `InterviewReportView` | `interview_reports` | Không nhận từ client | `id`, `session_id`, `overall_score`, `strengths`, `weaknesses`, `suggestions`, `generated_at` | Một aggregate report/session; không có skill score hoặc feedback theo từng câu |
| `CommentWrite/View` | `comment` | `content`, `parent_id?` | `id`, `lesson_content_id`, `user_id`, `parent_id`, `content`, `created_at`, `updated_at` | LessonContent/user lấy từ path/current user; `deleted_at` không trả; `is_deleted` là projection từ `deleted_at`; comment đã soft-delete chỉ trả tombstone, không trả nội dung cũ |
| `NotificationView` | `notification` | Mark-read không có body | `id`, `sender_id`, `user_id`, `type`, `target_type`, `target_id`, `content`, `is_read`, `created_at` | Recipient/type/target do service tạo |
| `AuditLogView` | `audit_log` | Không có client write trực tiếp | `id`, `user_id`, `action`, `target_type`, `target_id`, `note`, `correlation_id`, `do_at` | `user_id` là actor; payload phải được redact |
| `StudentDailyActivityView` | `student_daily_activity` | Không có client write trực tiếp | `id`, `student_id`, `activity_date`, `contribution_count`, `study_seconds`, `solved_problem_count`, `created_at`, `updated_at` | Streak/KPI/heatmap buckets là projection |

`user_history.problem_count` là aggregate legacy và không được dùng làm DTO nguồn cho contribution, streak hoặc study time.

#### Lesson Comment

`DATABASE.txt` đã có bảng canonical `comment` cho comment và reply theo LessonContent:

- Request chỉ nhận `content` và `parent_id?`; `lesson_content_id` lấy từ path và `user_id` lấy từ current user.
- `parent_id` luôn là comment được reply trực tiếp. Database có thể tạo chuỗi reply, nhưng API chỉ biểu diễn hai cấp trên giao diện: root và toàn bộ descendant cùng cấp reply.
- Reply phải trỏ tới parent chưa bị xóa và thuộc cùng `lesson_content_id`.
- Xóa root comment là hard-delete toàn bộ reply tree; xóa non-root có reply là soft-delete để giữ cấu trúc và list không trả nội dung cũ.
- List theo `lesson_content_id` phân trang ổn định theo root comment (`created_at`, `id`) và trả đầy đủ descendant của các root trong trang để FE không bị thiếu reply target; không được bỏ qua kiểm tra course access.

#### External identity và role audit

- `user_identity` lưu liên kết `(provider, provider_id)` đã được provider xác minh và không lưu provider token.
- `UNIQUE(provider, provider_id)` ngăn một external identity liên kết với nhiều user; `UNIQUE(user_id, provider)` giới hạn một identity cho mỗi provider của một user.
- `AuditAction.ROLE_UPDATE` là action canonical cho mọi thay đổi role của Admin.

## 3. Auth Provider

Các route trong mục này dùng base URL `http://localhost:4001/api/auth`.

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `POST` | `/register` | Public | `RegisterRequest` | `UserView` với `account_status: "UNVERIFIED"`, transient `verification_required`, `message` | Tạo local Student; response dùng `id`, không đổi tên thành `user_id`; gửi OTP qua kênh đã cấu hình; không trả OTP trong production |
| `GET` | `/verify?otp={otp}` | Public | Query `otp` | `account_status: "ACTIVE"`, `message` | OTP một lần, có expiry; phải redact query khỏi application log |
| `POST` | `/resend-otp` | Public | `email` | `message`, `retry_after_seconds` | Không tiết lộ email có tồn tại; rate limit |
| `POST` | `/login` | Public | Form: `email`, `password`, `redirect_uri` | `code`, `redirect_uri` | Chỉ account `ACTIVE`; account `UNVERIFIED/BANNED` bị từ chối bằng error code phù hợp |
| `POST` | `/code` | Public | `code` | `access_token`, `refresh_token`, `expires_in`, `token_type` | Authorization code một lần, có expiry và redirect/client binding |
| `POST` | `/refresh` | Session owner | `refresh_token` hoặc secure cookie | `access_token`, `expires_in`, `token_type` | Rotate/revoke theo token policy; kiểm tra account status hiện tại |
| `POST` | `/google` | Public | Command `credential_code` | Token response, `UserView` | Verify signature, issuer, audience, expiry, nonce và provider subject; lookup bằng `(provider, provider_id)`; tạo user + identity atomically khi hợp lệ; nếu email đã thuộc tài khoản khác thì không tự liên kết, yêu cầu authenticated linking/re-authentication theo policy |
| `POST` | `/logout` | User đăng nhập | Refresh session/cookie | `message` | Revoke refresh session; idempotent |
| `POST` | `/forgot-password` | Public | `email` | `message` | Gửi reset instruction; không trả reset code và không tiết lộ email tồn tại |
| `POST` | `/reset-password` | Public | `code`, `new_password` | `message` | Code một lần, có expiry; revoke session cũ theo policy |
| `POST` | `/change-email` | User đăng nhập | `new_email`, `password` | `message`, `verification_required` | Email mới chưa được dùng; xác minh lại trước khi thay đổi |
| `GET` | `/verify-reset-email?token={token}` | User xác minh | Query `token` | `email`, `message` | Token một lần; phải redact khỏi log |
| `GET` | `/public-key` | Service/Public theo policy | - | JWK hoặc PEM public key, `key_id` | Chỉ public material; hỗ trợ rotation/cache |

## 4. Current User, Profile và Admin User Management

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/users/me` | User đăng nhập | - | `UserIdentityMe` | Chỉ trả về một số thông tin cơ bản của user, sử dụng cho việc xác thực |
| `GET` | `/users/me/profile` | User profile | - | `StudentProfileView` | Trả về thông tin tài khoản student |
| `PUT` | `/users/me/profile` | User đăng nhập | `StudentProfileWrite` | `StudentProfileView` | Không sửa role/account status/user khác |
| `PUT` | `/users/me/teacher-profile` | User đăng nhập | `TeacherProfileWrite` | `TeacherProfileView` | `PENDING` khóa profile; `DRAFT`/`REJECTED`/`APPROVED` được sửa các field profile đã liệt kê. `APPROVED` không mở khóa các identity/document field của application; profile không tự cấp Teacher capability |
| `GET` | `/admin/users` | Admin | `q`, `role`, `account_status`, `page`, `size` | `UserView[]`, `UserRoleView[]` và capability projections | Không trả password/token/CCCD |
| `PUT` | `/admin/users/{user_id}/status` | Admin | `account_status: "ACTIVE" \| "BANNED"` | `UserView` đã cập nhật | Ghi audit; response dùng `id` theo bảng `user`; ban phải vô hiệu hóa refresh session theo policy |
| `PUT` | `/admin/users/{user_id}/roles` | Admin | `roles: ["ADMIN", "TEACHER", "STUDENT"]` | `user_id`, `UserRoleView[]`, `capabilities` | Thay thế role atomically, ghi audit `ROLE_UPDATE`; role `TEACHER` không được bypass application approval |

## 5. Teacher Application

Lifecycle chuẩn:

```text
DRAFT -> PENDING -> APPROVED | REJECTED
REJECTED --edit/submit--> PENDING
```

Giá trị legacy `AGREE/REJECT` không phải input hợp lệ của API.

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `POST` | `/teacher-applications` | Student | `TeacherApplicationWrite` | `TeacherApplicationView` với `status: "DRAFT"` | Tạo application duy nhất cho current `teacher_profile`; profile phải tồn tại; không log identity number/document URL |
| `GET` | `/teacher-applications/me` | Student | - | `TeacherApplicationView`, `TeacherProfileView`, `TeacherApplicationHistoryView[]`, `can_edit`, `can_submit` | Owner only; sensitive fields mask theo DTO policy |
| `PUT` | `/teacher-applications/me` | Application owner | Field mutable của `TeacherApplicationWrite` | Các view đã cập nhật | `DRAFT/REJECTED` cho sửa toàn bộ field được phép; `PENDING` từ chối; `APPROVED` chỉ whitelist bio/date_of_birth/motivation và field không nhạy cảm được duyệt |
| `POST` | `/teacher-applications/me/submit` | Application owner | - | `id`, `status: "PENDING"`, `submitted_at` | Chỉ application editable; dùng cho submit đầu và submit lại sau reject; validate đủ field |
| `GET` | `/admin/teacher-applications` | Admin | `status`, `q`, `page`, `size` | Redacted `TeacherApplicationView[]` | Không trả CCCD đầy đủ trong list |
| `GET` | `/admin/teacher-applications/{application_id}` | Admin | - | Authorized `TeacherApplicationView`, `TeacherProfileView`, `TeacherApplicationHistoryView[]` | Access phải được audit nếu chứa PII nhạy cảm |
| `POST` | `/admin/teacher-applications/{application_id}/review` | Admin | Command `decision: "APPROVED" \| "REJECTED"`, `note` | `TeacherApplicationView`, `TeacherApplicationHistoryView` | `decision` map sang status; `note` map vào application/history; chỉ `PENDING`; atomic capability effect + notification + audit |

`POST /teacher-applications/me/resubmit` không phải route canonical. FE dùng cùng `/submit` sau khi application `REJECTED` đã được sửa.

## 6. Catalog, Favorite, Course Review và Course Moderation

Course `APPROVED` là course public/bán được duy nhất. `PUBLISHED` chỉ là legacy migration value; `ARCHIVED` ẩn khỏi catalog mới nhưng Student đã enrollment vẫn truy cập được.

### 6.1. Catalog, Instructor, Favorite và Course Review

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/courses` | Public | `q`, `field`, `tag`, `price_type`, `page`, `size` | `CourseView[]` dạng card cùng currency/config projection | Chỉ course public/eligible; filter và pagination ổn định |
| `GET` | `/courses/{slug}` | Public/User | - | `CourseView`, instructor `TeacherProfileView`, `SectionView[]` overview và các projection favorite/review/enrollment | Không trả private lesson content hoặc bank fields |
| `GET` | `/instructors` | Public | `q`, `field`, `page`, `size` | Approved instructor cards | Dữ liệu từ profile/application projection, không hard-code từ course |
| `GET` | `/instructors/{user_id}` | Public | - | Instructor profile và public courses | Chỉ profile Teacher có capability hợp lệ |
| `GET` | `/favorites` | Student | `page`, `size` | `CourseFavoriteView[]` kèm `CourseView` projection | Owner only |
| `PUT` | `/courses/{course_id}/favorite` | Student | - | `CourseFavoriteView`, `is_favorited: true` | Idempotent; unique Student/course |
| `DELETE` | `/courses/{course_id}/favorite` | Student | - | `course_id`, `is_favorited: false` | Owner only; idempotent |
| `GET` | `/courses/{course_id}/reviews` | Public | `rating`, `page`, `size` | `CourseReviewView[]` và rating summary projection | Course review khác lesson comment |
| `POST` | `/courses/{course_id}/reviews` | Enrolled Student | `CourseReviewWrite` | `CourseReviewView` | Một review duy nhất cho mỗi Student/course; `409 DUPLICATE_RESOURCE` nếu đã có review; luôn yêu cầu enrollment |
| `PATCH` | `/courses/{course_id}/reviews/{review_id}` | Review owner | Partial `CourseReviewWrite` | `CourseReviewView` | Review phải thuộc owner và course; vẫn yêu cầu enrollment |

### 6.2. Teacher Course và Admin Moderation

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/teacher/courses` | Approved Teacher | `status`, `page`, `size` | Current Teacher `CourseView[]` | Owner scoped |
| `POST` | `/teacher/courses` | Approved Teacher | `CourseWrite` | `CourseView` với status `DRAFT`, `currency: "USD"` | Server đặt `currency` `USD`; client không gửi currency hoặc moderation/public status |
| `GET` | `/teacher/courses/{course_id}` | Course owner | - | `CourseView` và curriculum/moderation projections | Ownership bắt buộc |
| `PUT` | `/teacher/courses/{course_id}` | Course owner | Partial `CourseWrite` | `CourseView` | Chỉ state editable; không tự approve |
| `POST` | `/teacher/courses/{course_id}/submit-review` | Course owner | - | `CourseView` với `status: "PENDING_REVIEW"`, `submitted_at` đã cập nhật | Dùng cho submit/resubmit từ `DRAFT` hoặc `REJECTED`; validate curriculum tối thiểu |
| `GET` | `/teacher/courses/{course_id}/moderation-history` | Course owner | `page`, `size` | `CourseModerationView[]` | Owner only |
| `GET` | `/admin/courses` | Admin | `status`, `q`, `page`, `size` | `CourseView[]` moderation projection | Admin only |
| `GET` | `/admin/courses/{course_id}` | Admin | - | `CourseView`, `CourseModerationView[]`, curriculum review projections | Không trả secrets/testcase hidden raw data |
| `POST` | `/admin/courses/{course_id}/review` | Admin | Command `decision`, `note` | `CourseView`, `CourseModerationView` | Chỉ course chờ review; atomic history + notification + audit |
| `POST` | `/admin/courses/{course_id}/archive` | Admin | Command `note` | `CourseView` | Ghi `note` vào moderation/audit; learner đã mua áp dụng archive access policy |

Không có route `/resubmit` riêng: Teacher dùng lại `/submit-review` sau khi sửa course ở state cho phép.

## 7. Course Builder và Learning

`LessonContentType` chỉ nhận `READING`, `QUIZ`, `PROBLEM`. `content_id` là polymorphic reference, vì vậy service phải kiểm tra tồn tại, đúng loại, đúng course và ownership trước khi bind.

### 7.1. Teacher Curriculum Builder

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `POST` | `/teacher/courses/{course_id}/sections` | Course owner | `SectionWrite` | `SectionView` | Course editable; position unique trong course |
| `PUT` | `/teacher/sections/{section_id}` | Course owner | Partial `SectionWrite` | `SectionView` | Ownership toàn chuỗi |
| `DELETE` | `/teacher/sections/{section_id}` | Course owner | - | `message` | Cascade/content policy phải được duyệt |
| `POST` | `/teacher/sections/{section_id}/lessons` | Course owner | `LessonWrite` | `LessonView` | Position unique trong section |
| `PUT` | `/teacher/lessons/{lesson_id}` | Course owner | Partial `LessonWrite` | `LessonView` | Ownership toàn chuỗi |
| `DELETE` | `/teacher/lessons/{lesson_id}` | Course owner | - | `message` | Chỉ state editable |
| `POST` | `/teacher/lessons/{lesson_id}/readings` | Course owner | `ReadingContentWrite` và command `position` | `ReadingContentView`, `LessonContentView` | Tạo content + binding atomically vì `reading_content` không có owner trực tiếp |
| `PUT` | `/teacher/lesson-contents/{lesson_content_id}/reading` | Course owner | Partial `ReadingContentWrite` | `ReadingContentView` | Binding phải có type `READING`; ownership suy ra qua Lesson -> Section -> Course |
| `POST` | `/teacher/lessons/{lesson_id}/contents` | Course owner | `LessonContentBind` | `LessonContentView` | Reject type ngoài canonical; schema hiện không có completion-policy field |
| `PUT` | `/teacher/lesson-contents/{lesson_content_id}` | Course owner | Partial `LessonContentBind` không gồm `content_type` nếu policy cấm đổi loại | `LessonContentView` | Re-validate polymorphic reference |
| `DELETE` | `/teacher/lesson-contents/{lesson_content_id}` | Course owner | - | `message` | Chỉ state editable |
| `PUT` | `/teacher/courses/{course_id}/curriculum/reorder` | Course owner | Command `items: [{item_type, id, parent_id, position}]` | `SectionView[]`, `LessonView[]`, `LessonContentView[]` đã cập nhật | `item_type` chọn bảng; `parent_id` map vào FK phù hợp; atomic; item phải thuộc course; position không trùng |

### 7.2. Student Learning và Progress

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/student/courses` | Student | `page`, `size`, `status?` | `EnrollmentView[]`, `CourseView[]` và progress projection | Chỉ enrollment current user |
| `GET` | `/student/courses/{slug}/study` | Enrolled Student | - | `CourseView`, `SectionView[]`, `LessonView[]`, `LessonContentView[]`, content views và progress/`locked` projection | Enrollment/access bắt buộc; archived course theo policy |
| `POST` | `/student/progress/lesson-contents/{lesson_content_id}/complete` | Enrolled Student | - | `LessonContentProgressView` và course progress projection | Chỉ Reading; idempotent; Quiz/Problem không nhận completion từ client |
| `GET` | `/student/progress` | Student | `course_id?`, `page`, `size` | `LessonContentProgressView[]` theo enrollment/course | Current user only |

## 8. Quiz và Online Judge

### 8.1. Quiz Authoring và Attempt

Quiz attempt dùng `IN_PROGRESS`, `SUBMITTED`, `ABANDONED`. Mỗi lần bắt đầu tạo một row `quiz_attempt` mới; khi nộp, service tạo đúng một `quiz_submission` terminal cho attempt đó. Không có save/resume: learner gửi toàn bộ đáp án trong request submit.

Khi Student bắt đầu lại, attempt `IN_PROGRESS` trước đó của cùng Student/Quiz được chuyển thành `ABANDONED` trước khi cấp `attempt_no` mới. Attempt còn `IN_PROGRESS` khi Quiz hết `end_date` cũng được chuyển thành `ABANDONED`; hai trường hợp này không tạo `quiz_submission`.

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `POST` | `/teacher/lessons/{lesson_id}/quizzes` | Course owner | `QuizWrite` và command `position` | `QuizView`, `LessonContentView` | Tạo quiz + binding atomically vì Quiz không có owner trực tiếp trong proposal |
| `PUT` | `/teacher/quizzes/{quiz_id}` | Course owner qua binding | Partial `QuizWrite` | `QuizView` | Ownership suy ra qua LessonContent; không làm hỏng attempt đã bắt đầu ngoài policy |
| `PUT` | `/teacher/quizzes/{quiz_id}/questions` | Quiz owner | `{ questions: [{ QuizQuestionWrite, options: QuizOptionAuthorWrite[] }] }` | Author views gồm question/option | Validate points/options; answer key không vào learner projection |
| `POST` | `/student/quizzes/{quiz_id}/attempts` | Enrolled Student | - | `QuizAttemptView`, learner question/option views, computed `expires_at?` | Trong transaction: abandon attempt cũ nếu có, kiểm tra giới hạn, cấp `attempt_no` mới; không trả attempt cũ để resume và không trả `is_correct` |
| `GET` | `/student/quizzes/{quiz_id}/attempts/{attempt_id}` | Attempt owner | - | `QuizAttemptView`, learner question/option views | Owner + enrollment; không trả answer key |
| `POST` | `/student/quizzes/{quiz_id}/attempts/{attempt_id}/submit` | Attempt owner | Structured final `answers` | `QuizAttemptView`, computed `passed`, `LessonContentProgressView?` | Chỉ `IN_PROGRESS`; validate option/question/quiz, tạo `quiz_submission`, cập nhật attempt thành `SUBMITTED` và ghi `submitted_at` atomically; repeat cùng attempt trả terminal result cũ, không chấm lại |
| `GET` | `/student/quizzes/{quiz_id}/attempts` | Enrolled Student | `page`, `size` | Current Student `QuizAttemptView[]` | Owner only; không lộ answer key |

### 8.2. Problem Management và Judge

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/problems` | Public/User | `tag`, `difficulty`, `page`, `size` | `ProblemView[]`, tags và solved-state projection | Chỉ public/accessible problems |
| `GET` | `/problems/{slug}` | Public/User | - | `ProblemView`, `ProblemTagView[]`, `LanguageView[]`, configs được phép | Không trả testcase file/raw hidden data |
| `POST` | `/problems/{slug}/run` | Student | Transient `source_code`, `language_id`, `stdin?` | Transient run status/stdout/stderr/runtime/memory | Không tạo `submission` hay `submission_result_detail`; sandbox, rate limit; custom input không tạo completion |
| `POST` | `/problems/{slug}/submit` | Student | `SubmissionWrite` không gồm problem/student/status/result fields | `SubmissionView` với `status: "PENDING"` | Access + language validation; enqueue idempotent job; Judge trả progress theo từng testcase |
| `GET` | `/submissions/{submission_id}` | Submission owner/Problem owner/Admin | - | Role-filtered `SubmissionView`, `SubmissionResultView[]` hoặc hidden summary projection | Hidden testcase chỉ trả aggregate được phép |
| `GET` | `/problems/{slug}/submissions` | Student | `page`, `size` | Current Student `SubmissionView[]` | Owner only |
| `POST` | `/teacher/problems` | Approved Teacher | `ProblemWrite` gồm `passing_score`, command `tag_ids[]`, `configs: ProblemConfigWrite[]` | `ProblemView`, tags, configs | `passing_score` là ngưỡng hoàn thành lesson; phải là số không âm; service chỉ cập nhật completion khi submission `ACCEPTED` đạt ngưỡng |
| `PUT` | `/teacher/problems/{problem_id}` | Problem owner | Partial `ProblemWrite`, `tag_ids[]?`, `configs?` | `ProblemView`, tags, configs | Ownership + config validation |
| `POST` | `/teacher/problems/{problem_id}/testcases/upload` | Problem owner | Multipart input/output files, `score`, `is_hidden` | Transient `uploaded_count`, `message`; authorized `TestcaseView[]` | Server tạo object key cho `input_file`/`output_file`; validate file; hidden data không vào learner API |
| `GET` | `/teacher/courses/{course_id}/submissions` | Course owner | `problem_id?`, `student_id?`, `status?`, `page`, `size` | Authorized `SubmissionView[]` và result summary projections | Chỉ submission thuộc course/problem của Teacher |

Judge result phải dùng các status: `PENDING`, `RUNNING`, `ACCEPTED`, `WRONG_ANSWER`, `TIME_LIMIT_EXCEEDED`, `MEMORY_LIMIT_EXCEEDED`, `RUNTIME_ERROR`, `COMPILE_ERROR`.

Judge so khớp output testcase tuyệt đối theo byte UTF-8, bao gồm whitespace và newline cuối. Luồng Submit chạy testcase tuần tự và phát event progress theo đúng thứ tự (`RUNNING` → từng testcase đã chạy → kết quả terminal), với `sequence` tăng dần. Worker dừng ở testcase lỗi đầu tiên; chỉ khi toàn bộ testcase pass mới trả `ACCEPTED`. Event/projection gửi cho Student không được lộ raw input/output hoặc identifier của hidden testcase.

## 9. Checkout trực tiếp, PayOS và Enrollment

Mỗi checkout chỉ nhắm một course; MVP không có Cart hoặc Order. Giá là snapshot USD do server lấy từ course. Giao diện chỉ mở trang thanh toán giả, hiển thị kết quả/poll transaction; không có API client nào được phép đánh dấu thanh toán thành công.

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `POST` | `/courses/{course_id}/checkout` | Student | Không body; header `Idempotency-Key` | `PaymentTransactionView`, transient provider QR/redirect data | Course phải `APPROVED`, Student chưa enrollment; server snapshot `amount`/`currency: USD`; cùng key trả transaction cũ; khi đã có `PENDING` chưa hết hạn cho Student/course thì trả/reuse transaction đó, không tạo thêm active pending |
| `POST` | `/courses/{slug}/enroll` | Student | - | `EnrollmentView` | Chỉ free course; idempotent; paid course phải qua checkout |
| `GET` | `/payments/transactions/{transaction_code}` | Transaction owner/Admin | - | Role-filtered `PaymentTransactionView`, `EnrollmentView?` | Owner/Admin only; FE dùng để poll kết quả giả lập |
| `POST` | `/payments/payos/webhook` | PayOS mock/internal | Transient provider payload + signed test signature | Transient acknowledgement `accepted: true` | Verify signature/reference/amount/currency USD; endpoint không nhận user JWT để complete payment; event idempotent |
| `GET` | `/admin/payments` | Admin | `status`, `transaction_code?`, `student_id?`, `course_id?`, `page`, `size` | Admin-filtered `PaymentTransactionView[]` | Mask provider-sensitive data theo DTO policy |
| `GET` | `/admin/enrollments` | Admin | `student_id?`, `course_id?`, `page`, `size` | `EnrollmentView[]` | Admin only |

Webhook mock hợp lệ chuyển payment `PENDING` sang `COMPLETED` hoặc `FAILED`; expiry worker chuyển `PENDING` quá hạn sang `EXPIRED`. Chỉ transition `COMPLETED` tạo enrollment, revenue ledger, notification và audit đúng một lần; `FAILED/EXPIRED` không tạo enrollment hoặc revenue. Service phải serialise theo `(student_id, course_id)` để bảo đảm có nhiều lịch sử transaction nhưng tối đa một `PENDING` chưa hết hạn tại một thời điểm, và một enrollment duy nhất.

## 10. Wallet và Payout

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/teacher/wallet` | Approved Teacher | - | `WalletView` | Current Teacher only; balance phải reconcile được từ ledger |
| `GET` | `/teacher/wallet/ledger` | Approved Teacher | `entry_type?`, `from?`, `to?`, `page`, `size` | `WalletLedgerView[]` | Owner only |
| `POST` | `/teacher/payout-requests` | Approved Teacher | `PayoutRequestWrite` (`amount`) | `PayoutRequestView` với status `PENDING`, `currency: "USD"` | Validate minimum `0.00 USD`/available; server đặt currency; reserve ledger atomic. Payout destination/settlement mechanism chưa được chốt |
| `GET` | `/teacher/payout-requests` | Approved Teacher | `status?`, `page`, `size` | Current Teacher `PayoutRequestView[]` | Owner only |
| `GET` | `/admin/payout-requests` | Admin | `status`, `teacher_id?`, `page`, `size` | `PayoutRequestView[]` | Admin only |
| `POST` | `/admin/payout-requests/{payout_id}/review` | Admin | Command `decision: "APPROVED" \| "REJECTED"`, `note` | `PayoutRequestView` | `decision` map sang status; `note` ghi `audit_log.note`; chỉ `PENDING`; reviewer/time do server ghi; reject tạo compensating/release entry nếu đã reserve |
| `POST` | `/admin/payout-requests/{payout_id}/processing` | Admin/System | Command `settlement_reference?` | `PayoutRequestView` với status `PROCESSING` | Chỉ `APPROVED`; idempotent |
| `POST` | `/admin/payout-requests/{payout_id}/settle` | Admin/System | Command `result: "COMPLETED" \| "FAILED"`, `settlement_reference?`, `failure_reason?` | `PayoutRequestView` terminal | Chỉ `PROCESSING`; failure tạo compensating entry đúng một lần |

Ledger là immutable. Mọi sửa sai/reserve release/refund phải dùng entry bù trừ, không update hoặc delete entry cũ.

## 11. AI Interview

UI ưu tiên microphone: client speech-to-text thành text để learner xem/sửa trước khi gửi. Typed fallback là cùng một flow; camera chỉ preview tùy chọn. API chỉ nhận/lưu text và final aggregate report, không nhận/lưu/đánh giá audio, video hoặc ảnh và không biểu diễn trải nghiệm này như chatbot.

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/interviews/sessions` | Student | `status?`, `page`, `size` | Current Student `InterviewSessionView[]` | Owner only |
| `POST` | `/interviews/sessions` | Student | `InterviewSessionWrite` (`topic`, `level`) | `InterviewSessionView`, first `InterviewMessageView` | Validate active-session policy; count/status/timestamps do server ghi |
| `GET` | `/interviews/sessions/{session_id}` | Session owner | - | `InterviewSessionView`, `InterviewMessageView[]`, computed `can_answer` | Owner only; không tạo hoặc resume attempt từ GET |
| `POST` | `/interviews/sessions/{session_id}/answers` | Session owner | `InterviewMessageWrite` với `answer_text` | AI `InterviewMessageView`, `InterviewSessionView` | Backend chỉ nhận text STT/typed; sender/count/status do server ghi; chỉ `ACTIVE`; tối đa 12 câu; rate limit; reject media fields |
| `POST` | `/interviews/sessions/{session_id}/end` | Session owner | - | `InterviewSessionView` với status `REPORT_GENERATING` | Kết thúc hợp lệ và tạo report; idempotent; cho phép AI kết thúc sớm theo policy |
| `POST` | `/interviews/sessions/{session_id}/abort` | Session owner | Command `reason?` chỉ ghi audit note nếu policy yêu cầu | `InterviewSessionView` với status `ABORTED` | `interview_session` không có reason column; bỏ phiên không tạo final report ngoài policy |
| `GET` | `/interviews/sessions/{session_id}/report` | Session owner | - | `InterviewSessionView`, `InterviewReportView?` | Một report/session; không trigger generation khi GET |

Report worker phải idempotent và dùng unique `session_id`. Thành công chuyển `REPORT_GENERATING -> COMPLETED`; lỗi cuối chuyển `FAILED`; tạo `AI_REPORT_READY` đúng một lần. Report chỉ có điểm/tóm tắt tổng hợp (`overall_score`, strengths, weaknesses, suggestions), không có phản hồi từng câu hoặc chấm điểm theo skill.

## 12. Comment, Notification, Audit và Dashboard

### 12.1. Lesson Comment và Notification

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/lesson-contents/{lesson_content_id}/comments` | User có course access | `page`, `size` | `CommentView[]` | Chỉ user có quyền học/quản lý course; `page`/`size` tính theo root comment và mỗi root trả trọn thread dạng flat để FE hiển thị tối đa hai cấp; comment đã xóa trả tombstone |
| `POST` | `/lesson-contents/{lesson_content_id}/comments` | User có course access | `CommentWrite` (`content`, `parent_id?`) | `CommentView` | Trim/sanitize và giới hạn content; parent phải tồn tại, chưa bị xóa và cùng LessonContent; user/path fields do server đặt |
| `DELETE` | `/comments/{comment_id}` | Comment owner/Moderator | - | `message` | Idempotent; root comment hard-delete cả reply tree; non-root có reply soft-delete thành tombstone; non-root không có reply được hard-delete; chỉ owner hoặc moderator đúng policy |
| `GET` | `/notifications` | User đăng nhập | `unread_only?`, `type?`, `page`, `size` | `NotificationView[]` | Recipient only |
| `PUT` | `/notifications/{notification_id}/read` | Notification recipient | - | `NotificationView` với `is_read: true` | Owner only; idempotent |

Notification event tối thiểu: payment success/failure, teacher application approve/reject, course approve/reject, Judge result, AI report ready và payout approve/reject.

### 12.2. Dashboard và operational queries

| Method | Route | Actor | Request | Response chính | Quy tắc |
|---|---|---|---|---|---|
| `GET` | `/student/dashboard` | Student | - | `UserView`, profile/capability projection, KPIs, `StudentDailyActivityView[]`, continue-learning, interview và recommendation projections | Current user only; nguồn gồm `enrollment`, `lesson_content_progress`, `submission`, `interview_session`, `student_daily_activity` và problem tags; aggregate không phải cột mới |
| `GET` | `/teacher/dashboard/summary` | Approved Teacher | - | `WalletView`, course/enrollment/revenue aggregate projections | Nguồn gồm `courses`, `enrollment`, `transaction`, `wallet`, `wallet_ledger`; chỉ data của current Teacher |
| `GET` | `/teacher/courses/{course_id}/students` | Course owner | `q`, `page`, `size` | `EnrollmentView[]`, `UserView[]`, progress projections | Course owner only |
| `GET` | `/teacher/courses/{course_id}/students/{student_id}/progress` | Course owner | - | `EnrollmentView`, `LessonContentProgressView[]`, authorized `SubmissionView[]` summary | Student phải enrollment course đó |
| `GET` | `/teacher/courses/{course_id}/comments` | Course owner | `unanswered_only?`, `page`, `size` | `CommentView[]` kèm LessonContent/User projections tối thiểu | Chỉ owner của course; `unanswered_only` lọc root comment chưa có reply hợp lệ từ course owner; không trả nội dung đã soft-delete |
| `GET` | `/admin/audit-logs` | Admin | `user_id?`, `action?`, `target_type?`, `target_id?`, `correlation_id?`, `from?`, `to?`, `page`, `size` | Redacted `AuditLogView[]` | `user_id` là actor theo DB; dùng action `PAYMENT_WEBHOOK` để theo dõi webhook |


## Transaction, idempotency và authorization invariants

| Luồng | Invariant bắt buộc |
|---|---|
| Teacher profile/application | Một `teacher_register` cho mỗi `teacher_profile`; `PENDING` khóa cả profile/application, `REJECTED` mới được sửa/resubmit; `APPROVED` chỉ whitelist field không nhạy cảm |
| Teacher application review | Chỉ `PENDING`; history + capability effect + notification + audit nhất quán |
| Course moderation | Chỉ `PENDING_REVIEW`; history + notification + audit nhất quán |
| Payment webhook | Chỉ PayOS mock signed webhook được complete; verify signature/reference/amount/currency USD; event lặp không nhân side effect |
| Direct checkout | Nhiều transaction lịch sử được phép, nhưng lock/service invariant bảo đảm tối đa một `PENDING` chưa hết hạn cho mỗi `(student_id, course_id)` |
| Enrollment | Tối đa một `(student_id, course_id)`; chỉ payment completed/free-enroll tạo enrollment; failed/expired payment không tạo enrollment |
| Revenue ledger | Payment completed tạo revenue entries đúng một lần; ledger immutable |
| Quiz submit | Một attempt chỉ có một kết quả submit terminal; không có saved answer/resume; answer key không lộ |
| External identity | Chỉ liên kết provider subject đã xác minh; không auto-link theo email collision; provider token không được persist |
| Lesson Comment | Parent cùng LessonContent và course access bắt buộc; xóa root cascade toàn cây, còn non-root có reply giữ thread bằng tombstone và không lộ nội dung cũ |
| Judge result | Duplicate worker result không tạo detail/progress/activity trùng; progress chỉ khi `ACCEPTED` đạt `problem.passing_score` |
| Interview report | Một final aggregate report/session; GET report không trigger job; media không được gửi/lưu/xử lý |
| Payout | Reserve/release/settlement idempotent; failure dùng compensating ledger entry |
| Notification/Audit | Ghi qua foundation dùng chung; recipient/actor/target đúng và dữ liệu nhạy cảm đã redact |

Mọi mutation phải kiểm tra account status, role/capability và resource ownership ở server. Dashboard, notification, progress, payment transaction, enrollment, submission và interview mặc định chỉ trả dữ liệu current user, trừ route Teacher/Admin được nêu rõ.

## Điều kiện nghiệm thu API contract

- Pydantic schema và generated OpenAPI tại `/docs` khớp route, payload, enum và error contract trong tài liệu này.
- Mỗi field được persist trong request/response phải tồn tại trong bảng nguồn của `DATABASE.txt` hoặc dùng một trong hai alias đã công bố; mọi field còn lại phải được ghi rõ là command, projection hoặc transient/transport.
- Contract test xác nhận route target đã implement không lệch method/path/response envelope.
- Route `GATED` chỉ được mở sau khi quyết định liên quan đã được cập nhật đồng bộ; route `GATED-SCHEMA` chỉ được mở sau khi `DATABASE.txt` và migration contract có bảng/cột tương ứng.
- Authorization test có case current owner, user khác, role thiếu, Teacher chưa approved, profile/application `PENDING` bị khóa và Admin.
- Idempotency/concurrency test có cho direct payment active-pending, signed webhook, enrollment, revenue ledger, quiz submit, Judge result, report và payout.
- Không có target route trả secret, OTP/reset code, CCCD đầy đủ, raw hidden testcase, raw payment payload hoặc media interview sai đối tượng.
