from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from src.cores.settings import FRONTEND_CHECKOUT_URL

from src.models.base_model import CourseStatus, LessonContentType
from src.models.course_model import CourseModel
from src.models.enrollment_model import EnrollmentModel
from src.models.course_review_model import CourseReviewModel
from src.models.section_model import SectionModel
from src.models.lesson_model import LessonModel
from src.models.lesson_content_progress_model import LessonContentProgressModel
from src.models.lesson_content_model import LessonContentModel
from sqlalchemy.orm import selectinload
from sqlalchemy import select, or_, func, delete
from src.modules.student_course_directory.course_dto import (
    CourseCatalogResponse,
    CourseDetailResponse,
    CourseItemResponse,
    CompleteContentResponse,
    EnrolledCourseResponse,
    EnrollResponse,
    EnrollStatus,
    LessonContentStudyResponse,
    LessonStudyResponse,
    PriceType,
    QuizOptionResponse,
    QuizQuestionResponse,
    QuizResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    SectionOverviewResponse,
    SectionStudyResponse,
    StudentCoursesResponse,
    StudyResponse,
    UnenrollResponse,
    QuizAttemptView,
)
from src.models.quiz_model import QuizModel
from src.models.quiz_attempt_model import QuizAttemptModel
from src.models.quiz_submission_model import QuizSubmissionModel
from src.models.base_model import QuizAttemptStatus

# ---------------------------------------------------------------------------
# Static mock catalogue — realistic data, no placeholder strings
# ---------------------------------------------------------------------------

_MOCK_COURSES = [
    CourseItemResponse(
        id=1,
        slug="nhap-mon-lap-trinh-python",
        title="Nhập môn Lập trình Python",
        thumbnail_url="https://cdn.cloudian.dev/courses/python-intro.jpg",
        price=0.0,
        price_type=PriceType.FREE,
        field="Lập trình",
        tags=["python", "beginner", "programming"],
        enrolled_count=3120,
        rating=4.8,
    ),
    CourseItemResponse(
        id=2,
        slug="cau-truc-du-lieu-va-giai-thuat",
        title="Cấu trúc Dữ liệu và Giải thuật",
        thumbnail_url="https://cdn.cloudian.dev/courses/dsa.jpg",
        price=299000.0,
        price_type=PriceType.PAID,
        field="Khoa học Máy tính",
        tags=["dsa", "algorithms", "intermediate"],
        enrolled_count=1845,
        rating=4.9,
    ),
    CourseItemResponse(
        id=3,
        slug="lap-trinh-web-voi-fastapi",
        title="Lập trình Web với FastAPI",
        thumbnail_url="https://cdn.cloudian.dev/courses/fastapi.jpg",
        price=399000.0,
        price_type=PriceType.PAID,
        field="Web Development",
        tags=["fastapi", "python", "backend", "api"],
        enrolled_count=972,
        rating=4.7,
    ),
    CourseItemResponse(
        id=4,
        slug="co-so-du-lieu-sql",
        title="Cơ sở Dữ liệu và SQL",
        thumbnail_url="https://cdn.cloudian.dev/courses/sql.jpg",
        price=0.0,
        price_type=PriceType.FREE,
        field="Cơ sở Dữ liệu",
        tags=["sql", "database", "beginner"],
        enrolled_count=2500,
        rating=4.6,
    ),
]

# Map slug -> detail-level data (sections overview)
_MOCK_COURSE_SECTIONS = {
    "nhap-mon-lap-trinh-python": [
        SectionOverviewResponse(id=1, title="Giới thiệu Python", position=0, lesson_count=4),
        SectionOverviewResponse(id=2, title="Kiểu dữ liệu và Biến", position=1, lesson_count=5),
        SectionOverviewResponse(id=3, title="Cấu trúc điều kiện và vòng lặp", position=2, lesson_count=6),
    ],
    "cau-truc-du-lieu-va-giai-thuat": [
        SectionOverviewResponse(id=4, title="Mảng và Danh sách liên kết", position=0, lesson_count=5),
        SectionOverviewResponse(id=5, title="Stack và Queue", position=1, lesson_count=4),
        SectionOverviewResponse(id=6, title="Sắp xếp và Tìm kiếm", position=2, lesson_count=7),
    ],
    "lap-trinh-web-voi-fastapi": [
        SectionOverviewResponse(id=7, title="Cài đặt môi trường FastAPI", position=0, lesson_count=3),
        SectionOverviewResponse(id=8, title="Routing và Request Handling", position=1, lesson_count=5),
        SectionOverviewResponse(id=9, title="Pydantic và Validation", position=2, lesson_count=4),
    ],
    "co-so-du-lieu-sql": [
        SectionOverviewResponse(id=10, title="Giới thiệu cơ sở dữ liệu", position=0, lesson_count=3),
        SectionOverviewResponse(id=11, title="Câu lệnh SELECT nâng cao", position=1, lesson_count=5),
    ],
}

# Mock enrolled courses for seed student (user_id=1)
_MOCK_ENROLLED_COURSES = [
    EnrolledCourseResponse(
        id=1,
        slug="nhap-mon-lap-trinh-python",
        title="Nhập môn Lập trình Python",
        thumbnail_url="https://cdn.cloudian.dev/courses/python-intro.jpg",
        progress_percent=65.0,
    ),
    EnrolledCourseResponse(
        id=4,
        slug="co-so-du-lieu-sql",
        title="Cơ sở Dữ liệu và SQL",
        thumbnail_url="https://cdn.cloudian.dev/courses/sql.jpg",
        progress_percent=20.0,
    ),
]

# Study mode mock — slug -> full curriculum with locked/completed flags
# Rule (mock only): first 2 lessons locked=False, rest locked=True
_MOCK_STUDY_DATA = {
    "nhap-mon-lap-trinh-python": StudyResponse(
        course_slug="nhap-mon-lap-trinh-python",
        sections=[
            SectionStudyResponse(
                id=1,
                title="Giới thiệu Python",
                position=0,
                lessons=[
                    LessonStudyResponse(
                        id=1,
                        title="Python là gì? Tại sao nên học Python?",
                        position=0,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=1,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=True,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=2,
                        title="Cài đặt Python và môi trường lập trình",
                        position=1,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=2,
                                content_type=LessonContentType.READING,
                                media_url="https://cdn.cloudian.dev/videos/python-setup.mp4",
                                completed=True,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=3,
                        title="Chương trình Python đầu tiên",
                        position=2,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=3,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                            LessonContentStudyResponse(
                                id=4,
                                content_type=LessonContentType.QUIZ,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=4,
                        title="Bài tập thực hành: Hello World",
                        position=3,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=5,
                                content_type=LessonContentType.PROBLEM,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                ],
            ),
            SectionStudyResponse(
                id=2,
                title="Kiểu dữ liệu và Biến",
                position=1,
                lessons=[
                    LessonStudyResponse(
                        id=5,
                        title="Biến và kiểu dữ liệu cơ bản",
                        position=0,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=6,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=6,
                        title="Số nguyên, số thực và chuỗi ký tự",
                        position=1,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=23,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=7,
                        title="Kiểu boolean và toán tử",
                        position=2,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=24,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=8,
                        title="Ép kiểu dữ liệu",
                        position=3,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=25,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=9,
                        title="Bài tập thực hành: Kiểu dữ liệu",
                        position=4,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=26,
                                content_type=LessonContentType.PROBLEM,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                ],
            ),
            SectionStudyResponse(
                id=3,
                title="Cấu trúc điều kiện và vòng lặp",
                position=2,
                lessons=[
                    LessonStudyResponse(
                        id=10,
                        title="Câu lệnh if/elif/else",
                        position=0,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=30,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=11,
                        title="Vòng lặp for và range()",
                        position=1,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=31,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=12,
                        title="Vòng lặp while",
                        position=2,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=32,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=13,
                        title="break, continue và pass",
                        position=3,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=33,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=14,
                        title="Nested loop và list comprehension",
                        position=4,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=34,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=15,
                        title="Bài tập thực hành: Vòng lặp",
                        position=5,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=35,
                                content_type=LessonContentType.PROBLEM,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    ),
    "co-so-du-lieu-sql": StudyResponse(
        course_slug="co-so-du-lieu-sql",
        sections=[
            SectionStudyResponse(
                id=10,
                title="Giới thiệu cơ sở dữ liệu",
                position=0,
                lessons=[
                    LessonStudyResponse(
                        id=20,
                        title="Cơ sở dữ liệu là gì?",
                        position=0,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=20,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=True,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=21,
                        title="Các loại cơ sở dữ liệu phổ biến",
                        position=1,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=21,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=22,
                        title="Cài đặt PostgreSQL",
                        position=2,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=22,
                                content_type=LessonContentType.READING,
                                media_url="https://cdn.cloudian.dev/videos/postgres-setup.mp4",
                                completed=False,
                            ),
                        ],
                    ),
                ],
            ),
            SectionStudyResponse(
                id=11,
                title="Câu lệnh SELECT nâng cao",
                position=1,
                lessons=[
                    LessonStudyResponse(
                        id=30,
                        title="SELECT với WHERE và điều kiện lọc",
                        position=0,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=40,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=31,
                        title="ORDER BY và LIMIT",
                        position=1,
                        locked=False,
                        contents=[
                            LessonContentStudyResponse(
                                id=41,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=32,
                        title="GROUP BY và HAVING",
                        position=2,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=42,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=33,
                        title="JOIN các bảng",
                        position=3,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=43,
                                content_type=LessonContentType.READING,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                    LessonStudyResponse(
                        id=34,
                        title="Bài tập thực hành: SELECT nâng cao",
                        position=4,
                        locked=True,
                        contents=[
                            LessonContentStudyResponse(
                                id=44,
                                content_type=LessonContentType.PROBLEM,
                                media_url=None,
                                completed=False,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    ),
}

# Valid lesson content IDs for mock 404 check
_VALID_LESSON_CONTENT_IDS = {
    1, 2, 3, 4, 5, 6, 20, 21, 22,
    23, 24, 25, 26,
    30, 31, 32, 33, 34, 35,
    40, 41, 42, 43, 44
}

# Mock quiz data — is_correct stored internally, NEVER exposed in QuizResponse
_MOCK_QUIZ_ANSWER_KEY: dict[int, dict[int, int]] = {
    # quiz_id -> {question_id -> correct_option_id}
    1: {1: 2, 2: 3, 3: 1},
}

_MOCK_QUIZZES: dict[int, QuizResponse] = {
    1: QuizResponse(
        id=1,
        title="Kiểm tra kiến thức Python cơ bản",
        # passing_score mirrors quiz.passing_score configured by the teacher.
        # Real implementation reads this from the DB; mock uses the same field.
        passing_score=5.0,
        questions=[
            QuizQuestionResponse(
                id=1,
                question_text="Python là ngôn ngữ lập trình thuộc loại nào?",
                options=[
                    QuizOptionResponse(id=1, text="Ngôn ngữ biên dịch (Compiled)"),
                    QuizOptionResponse(id=2, text="Ngôn ngữ thông dịch (Interpreted)"),
                    QuizOptionResponse(id=3, text="Ngôn ngữ hợp ngữ (Assembly)"),
                    QuizOptionResponse(id=4, text="Ngôn ngữ máy (Machine code)"),
                ],
            ),
            QuizQuestionResponse(
                id=2,
                question_text="Hàm nào dùng để in ra màn hình trong Python?",
                options=[
                    QuizOptionResponse(id=1, text="echo()"),
                    QuizOptionResponse(id=2, text="console.log()"),
                    QuizOptionResponse(id=3, text="print()"),
                    QuizOptionResponse(id=4, text="write()"),
                ],
            ),
            QuizQuestionResponse(
                id=3,
                question_text="Kết quả của biểu thức 3 ** 2 trong Python là?",
                options=[
                    QuizOptionResponse(id=1, text="9"),
                    QuizOptionResponse(id=2, text="6"),
                    QuizOptionResponse(id=3, text="32"),
                    QuizOptionResponse(id=4, text="Lỗi cú pháp"),
                ],
            ),
        ],
    ),
}


from sqlalchemy.ext.asyncio import AsyncSession

class CourseService:
    """
    Service layer for Module 2: Student Course Directory & Study Mode.
    All methods use mock data — DB integration is deferred until API contract is stable.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    # ------------------------------------------------------------------
    # Endpoint 1 — GET /courses
    # ------------------------------------------------------------------

    async def get_course_catalog(
        self,
        page: int,
        size: int,
        q: str | None,
        price_type: PriceType | None,
    ) -> CourseCatalogResponse:
        
        enrolled_count_sq = (
            select(func.count(EnrollmentModel.id))
            .where(EnrollmentModel.course_id == CourseModel.id)
            .scalar_subquery()
            .label("enrolled_count")
        )
        
        rating_sq = (
            select(func.coalesce(func.avg(CourseReviewModel.rating), 0.0))
            .where(CourseReviewModel.course_id == CourseModel.id)
            .scalar_subquery()
            .label("rating")
        )

        stmt = select(CourseModel, enrolled_count_sq, rating_sq).where(
            CourseModel.status == CourseStatus.APPROVED,
            CourseModel.deleted_at.is_(None)
        )

        if q:
            stmt = stmt.where(CourseModel.title.ilike(f"%{q}%"))

        if price_type == PriceType.FREE:
            stmt = stmt.where(CourseModel.price == 0)
        elif price_type == PriceType.PAID:
            stmt = stmt.where(CourseModel.price > 0)

        # Count total items
        count_stmt = select(func.count(CourseModel.id)).where(
            CourseModel.status == CourseStatus.APPROVED,
            CourseModel.deleted_at.is_(None)
        )
        if q:
            count_stmt = count_stmt.where(CourseModel.title.ilike(f"%{q}%"))
        if price_type == PriceType.FREE:
            count_stmt = count_stmt.where(CourseModel.price == 0)
        elif price_type == PriceType.PAID:
            count_stmt = count_stmt.where(CourseModel.price > 0)

        total_items = await self.db_session.scalar(count_stmt)
        total_items = total_items or 0

        # Pagination
        start = (page - 1) * size
        stmt = stmt.offset(start).limit(size)
        
        rows = (await self.db_session.execute(stmt)).all()

        page_items = []
        for c, enrolled_count, rating in rows:
            c_price = float(c.price)
            c_price_type = PriceType.FREE if c_price == 0 else PriceType.PAID
            tags_list = [tag.strip() for tag in c.tags.split(",")] if c.tags else []

            page_items.append(
                CourseItemResponse(
                    id=c.id,
                    slug=c.slug,
                    title=c.title,
                    thumbnail_url=c.thumbnail_url or "",
                    price=c_price,
                    price_type=c_price_type,
                    field=c.field or "",
                    tags=tags_list,
                    enrolled_count=int(enrolled_count),
                    rating=float(rating),
                )
            )

        total_pages = max(1, (total_items + size - 1) // size)

        return CourseCatalogResponse(
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            items=page_items,
        )

    # ------------------------------------------------------------------
    # Endpoint 2 — GET /courses/{slug}
    # ------------------------------------------------------------------

    async def get_course_detail(self, slug: str) -> CourseDetailResponse:
        from src.models.section_model import SectionModel
        from src.models.lesson_model import LessonModel
        from sqlalchemy.orm import selectinload

        # Scalar subquery: total enrollments for this course.
        # Source: https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-orm-entities
        enrolled_count_sq = (
            select(func.count(EnrollmentModel.id))
            .where(EnrollmentModel.course_id == CourseModel.id)
            .scalar_subquery()
            .label("enrolled_count")
        )

        # Scalar subquery: average review rating, defaulting to 0.0 when no reviews exist.
        rating_sq = (
            select(func.coalesce(func.avg(CourseReviewModel.rating), 0.0))
            .where(CourseReviewModel.course_id == CourseModel.id)
            .scalar_subquery()
            .label("rating")
        )

        # Load the course together with its sections to avoid a second round-trip.
        # selectinload issues one extra SELECT per relationship, which is correct
        # for collections. Source: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#selectin-loading
        stmt = (
            select(CourseModel, enrolled_count_sq, rating_sq)
            .where(
                CourseModel.slug == slug,
                CourseModel.status == CourseStatus.APPROVED,
                CourseModel.deleted_at.is_(None),
            )
            .options(selectinload(CourseModel.sections))
        )

        row = (await self.db_session.execute(stmt)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Course not found")

        course, enrolled_count, rating = row

        # lesson_count per section: one scalar subquery per section is a separate DB call.
        # Since sections are already loaded in memory, build counts with a single
        # bulk query grouping by section_id to keep it to one extra round-trip.
        section_ids = [s.id for s in course.sections]
        lesson_count_map: dict[int, int] = {}
        if section_ids:
            count_rows = (
                await self.db_session.execute(
                    select(LessonModel.section_id, func.count(LessonModel.id).label("cnt"))
                    .where(LessonModel.section_id.in_(section_ids))
                    .group_by(LessonModel.section_id)
                )
            ).all()
            lesson_count_map = {row.section_id: row.cnt for row in count_rows}

        sections = [
            SectionOverviewResponse(
                id=s.id,
                title=s.title,
                position=s.position,
                lesson_count=lesson_count_map.get(s.id, 0),
            )
            for s in sorted(course.sections, key=lambda s: s.position)
        ]

        c_price = float(course.price)
        tags_list = [tag.strip() for tag in course.tags.split(",")] if course.tags else []

        return CourseDetailResponse(
            id=course.id,
            slug=course.slug,
            title=course.title,
            description=course.description or "",
            price=c_price,
            price_type=PriceType.FREE if c_price == 0 else PriceType.PAID,
            field=course.field or "",
            tags=tags_list,
            enrolled_count=int(enrolled_count),
            rating=float(rating),
            sections=sections,
        )

    # ------------------------------------------------------------------
    # Endpoint 3 — POST /courses/{slug}/enroll  → 201
    # ------------------------------------------------------------------

    async def enroll_course(self, slug: str, user_id: int) -> EnrollResponse | JSONResponse:
        from sqlalchemy import select
        from decimal import Decimal

        # Find course by slug
        stmt = select(CourseModel).where(
            CourseModel.slug == slug,
            CourseModel.status == CourseStatus.APPROVED,
            CourseModel.deleted_at.is_(None),
        )
        course = (await self.db_session.execute(stmt)).scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check existing enrollment
        enroll_stmt = select(EnrollmentModel).where(
            EnrollmentModel.student_id == user_id,
            EnrollmentModel.course_id == course.id,
        )
        existing = (await self.db_session.execute(enroll_stmt)).scalar_one_or_none()
        
        c_price = float(course.price)
        is_free = c_price == 0

        if existing:
            # According to api_spec.md, return 400 with ALREADY_ENROLLED error envelope
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Course enrollment",
                    "error_code": "ALREADY_ENROLLED",
                    "details": [
                        { "field": "course_id", "reason": "duplicate enrollment" }
                    ]
                }
            )

        # Insert real enrollment row
        enrollment = EnrollmentModel(
            student_id=user_id,
            course_id=course.id,
            status=EnrollStatus.ENROLLED.value if is_free else EnrollStatus.PENDING_PAYMENT.value
        )
        self.db_session.add(enrollment)
        await self.db_session.commit()

        if is_free:
            return EnrollResponse(status=EnrollStatus.ENROLLED, checkout_url=None)
        else:
            # TODO: integrate real PayOS payment gateway — currently returns a placeholder frontend checkout URL
            return EnrollResponse(
                status=EnrollStatus.PENDING_PAYMENT,
                checkout_url=f"{FRONTEND_CHECKOUT_URL}/{slug}",
            )

    # ------------------------------------------------------------------
    # Endpoint 4 — GET /student/courses
    # ------------------------------------------------------------------

    async def get_enrolled_courses(self, user_id: int) -> StudentCoursesResponse:
        # Compute total lesson contents per course
        total_contents_sq = (
            select(SectionModel.course_id, func.count(LessonContentModel.id).label("total"))
            .join(LessonModel, LessonModel.section_id == SectionModel.id)
            .join(LessonContentModel, LessonContentModel.lesson_id == LessonModel.id)
            .group_by(SectionModel.course_id)
        ).subquery()

        # Compute completed lesson contents per course for this user
        completed_contents_sq = (
            select(
                EnrollmentModel.course_id,
                func.count(LessonContentProgressModel.id).label("completed")
            )
            .join(LessonContentProgressModel, LessonContentProgressModel.enrollment_id == EnrollmentModel.id)
            .where(
                LessonContentProgressModel.completed == True,
                EnrollmentModel.student_id == user_id
            )
            .group_by(EnrollmentModel.course_id)
        ).subquery()

        # Fetch enrollments
        stmt = (
            select(
                EnrollmentModel,
                CourseModel,
                func.coalesce(total_contents_sq.c.total, 0).label("total"),
                func.coalesce(completed_contents_sq.c.completed, 0).label("completed")
            )
            .join(CourseModel, EnrollmentModel.course_id == CourseModel.id)
            .outerjoin(total_contents_sq, CourseModel.id == total_contents_sq.c.course_id)
            .outerjoin(completed_contents_sq, CourseModel.id == completed_contents_sq.c.course_id)
            .where(
                EnrollmentModel.student_id == user_id,
                EnrollmentModel.status == EnrollStatus.ENROLLED.value
            )
        )
        
        result = await self.db_session.execute(stmt)
        rows = result.all()
        
        items = []
        for enrollment, course, total_count, completed_count in rows:
            progress_percent = 0.0
            if total_count > 0:
                progress_percent = round((completed_count / total_count) * 100, 2)
                
            items.append(EnrolledCourseResponse(
                id=course.id,
                slug=course.slug,
                title=course.title,
                thumbnail_url=course.thumbnail_url or "",
                progress_percent=progress_percent
            ))
            
        return StudentCoursesResponse(items=items)

    # ------------------------------------------------------------------
    # Endpoint 5 — GET /student/courses/{slug}/study
    # ------------------------------------------------------------------

    async def get_study_content(self, slug: str, user_id: int) -> StudyResponse:
        # First, find the course and check enrollment
        stmt = (
            select(CourseModel, EnrollmentModel)
            .outerjoin(EnrollmentModel, (EnrollmentModel.course_id == CourseModel.id) & (EnrollmentModel.student_id == user_id))
            .where(CourseModel.slug == slug)
            .options(
                selectinload(CourseModel.sections).selectinload(SectionModel.lessons).selectinload(LessonModel.contents)
            )
        )
        
        result = await self.db_session.execute(stmt)
        row = result.first()
        
        if not row:
            # Course doesn't exist at all -> 404
            raise HTTPException(status_code=404, detail="Course not found")
            
        course, enrollment = row
        
        if not enrollment or enrollment.status != EnrollStatus.ENROLLED.value:
            # Course exists but user not enrolled -> 403
            raise HTTPException(status_code=403, detail="Not enrolled in this course")

        # Fetch progress for this enrollment
        progress_stmt = select(LessonContentProgressModel).where(
            LessonContentProgressModel.enrollment_id == enrollment.id
        )
        progress_result = await self.db_session.execute(progress_stmt)
        progress_map = {p.lesson_content_id: p.completed for p in progress_result.scalars().all()}

        # Build response
        sections_resp = []
        for section in course.sections:
            lessons_resp = []
            for lesson in section.lessons:
                contents_resp = []
                for content in sorted(lesson.contents, key=lambda x: x.position):
                    # Resolve specific content IDs based on content_type
                    reading_id = None
                    quiz_id = None
                    # problem_id = None  # Problem ID not currently in DTO
                    if content.content_type == LessonContentType.READING:
                        reading_id = content.content_id
                    elif content.content_type == LessonContentType.QUIZ:
                        quiz_id = content.content_id

                    contents_resp.append(LessonContentStudyResponse(
                        id=content.id,
                        content_type=content.content_type,
                        media_url=content.media_url,
                        completed=progress_map.get(content.id, False),
                        reading_content_id=reading_id,
                        quiz_id=quiz_id,
                    ))
                
                lessons_resp.append(LessonStudyResponse(
                    id=lesson.id,
                    title=lesson.title,
                    position=lesson.position,
                    locked=False, # No completion_policy in schema yet, default to False
                    contents=contents_resp
                ))
            
            # Sort lessons by position
            lessons_resp.sort(key=lambda x: x.position)
            
            sections_resp.append(SectionStudyResponse(
                id=section.id,
                title=section.title,
                position=section.position,
                lessons=lessons_resp
            ))
            
        # Sort sections by position
        sections_resp.sort(key=lambda x: x.position)
        
        return StudyResponse(
            course_slug=course.slug,
            sections=sections_resp
        )

    # ------------------------------------------------------------------
    # Endpoint 6 — POST /student/progress/lesson-content/{id}/complete
    # ------------------------------------------------------------------

    async def complete_lesson_content(
        self, lesson_content_id: int, user_id: int
    ) -> CompleteContentResponse:
        # Join content -> lesson -> section -> course to find course_id
        # Then join enrollment to verify the student is enrolled in that course
        stmt = (
            select(LessonContentModel, EnrollmentModel)
            .join(LessonModel, LessonContentModel.lesson_id == LessonModel.id)
            .join(SectionModel, LessonModel.section_id == SectionModel.id)
            .join(CourseModel, SectionModel.course_id == CourseModel.id)
            .outerjoin(
                EnrollmentModel, 
                (EnrollmentModel.course_id == CourseModel.id) & 
                (EnrollmentModel.student_id == user_id) & 
                (EnrollmentModel.status == EnrollStatus.ENROLLED.value)
            )
            .where(LessonContentModel.id == lesson_content_id)
        )
        
        result = await self.db_session.execute(stmt)
        row = result.first()
        
        if not row:
            # Content doesn't exist
            raise HTTPException(status_code=404, detail="Lesson content not found")
            
        content, enrollment = row
        
        if not enrollment:
            # Content exists, but user is not enrolled -> 403 to match get_study_content ownership logic
            raise HTTPException(status_code=403, detail="Not enrolled in this course")
            
        if content.content_type != LessonContentType.READING:
            # Block Quiz/Problem completion from client
            raise HTTPException(
                status_code=400, 
                detail="Only READING content can be marked as completed by client"
            )
            
        # Check existing progress (idempotency)
        progress_stmt = select(LessonContentProgressModel).where(
            LessonContentProgressModel.enrollment_id == enrollment.id,
            LessonContentProgressModel.lesson_content_id == lesson_content_id
        )
        progress_result = await self.db_session.execute(progress_stmt)
        progress = progress_result.scalar_one_or_none()
        
        now = datetime.now(timezone.utc)
        
        if progress:
            if not progress.completed:
                progress.completed = True
                progress.completed_at = now
        else:
            progress = LessonContentProgressModel(
                enrollment_id=enrollment.id,
                lesson_content_id=lesson_content_id,
                completed=True,
                completed_at=now
            )
            self.db_session.add(progress)
            
        await self.db_session.flush()
        
        return CompleteContentResponse(
            message="Lesson content marked as completed",
            completed_at=progress.completed_at or now,
        )

    async def _verify_quiz_enrollment(self, quiz_id: int, user_id: int):
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from src.models.lesson_content_model import LessonContentModel, LessonContentType
        from src.models.lesson_model import LessonModel
        from src.models.section_model import SectionModel
        from src.models.enrollment_model import EnrollmentModel
        from src.modules.student_course_directory.course_dto import EnrollStatus
        from fastapi import HTTPException
        
        stmt = (
            select(LessonContentModel)
            .options(
                selectinload(LessonContentModel.lesson).selectinload(LessonModel.section)
            )
            .where(
                LessonContentModel.content_type == LessonContentType.QUIZ,
                LessonContentModel.content_id == quiz_id
            )
        )
        lesson_contents = (await self.db_session.execute(stmt)).scalars().all()
        if not lesson_contents:
            raise HTTPException(status_code=404, detail="Quiz not found in any curriculum")
            
        course_ids = {lc.lesson.section.course_id for lc in lesson_contents}
        
        enroll_stmt = select(EnrollmentModel).where(
            EnrollmentModel.student_id == user_id,
            EnrollmentModel.course_id.in_(course_ids),
            EnrollmentModel.status == EnrollStatus.ENROLLED.value
        )
        enrollment = (await self.db_session.execute(enroll_stmt)).scalars().first()
        if not enrollment:
            raise HTTPException(status_code=403, detail="Not enrolled in the course containing this quiz")

    async def create_quiz_attempt(
        self, quiz_id: int, user_id: int
    ) -> QuizAttemptView:
        # 1. Verify course enrollment first
        await self._verify_quiz_enrollment(quiz_id, user_id)
        
        # 2. Fetch quiz
        quiz = await self.db_session.get(QuizModel, quiz_id)
        if not quiz or quiz.deleted_at:
            raise HTTPException(status_code=404, detail="Quiz not found")
            
        # 3. Handle existing IN_PROGRESS attempt
        in_progress_stmt = select(QuizAttemptModel).where(
            QuizAttemptModel.quiz_id == quiz_id,
            QuizAttemptModel.student_id == user_id,
            QuizAttemptModel.status == QuizAttemptStatus.IN_PROGRESS
        )
        in_progress_result = await self.db_session.execute(in_progress_stmt)
        in_progress = in_progress_result.scalar_one_or_none()
        
        if in_progress:
            in_progress.status = QuizAttemptStatus.ABANDONED
            
        # 4. Check limits (count SUBMITTED attempts)
        submitted_stmt = select(func.count(QuizAttemptModel.id)).where(
            QuizAttemptModel.quiz_id == quiz_id,
            QuizAttemptModel.student_id == user_id,
            QuizAttemptModel.status == QuizAttemptStatus.SUBMITTED
        )
        submitted_count = (await self.db_session.execute(submitted_stmt)).scalar_one()
        
        if quiz.attempts is not None and submitted_count >= quiz.attempts:
            raise HTTPException(status_code=400, detail="Maximum attempts reached")
            
        # 5. Determine new attempt_no
        max_attempt_stmt = select(func.max(QuizAttemptModel.attempt_no)).where(
            QuizAttemptModel.quiz_id == quiz_id,
            QuizAttemptModel.student_id == user_id
        )
        max_attempt = (await self.db_session.execute(max_attempt_stmt)).scalar_one() or 0
        new_attempt_no = max_attempt + 1
        
        # 6. Create new attempt
        new_attempt = QuizAttemptModel(
            quiz_id=quiz_id,
            student_id=user_id,
            attempt_no=new_attempt_no,
            status=QuizAttemptStatus.IN_PROGRESS,
        )
        self.db_session.add(new_attempt)
        await self.db_session.flush()
        
        attempts_left = quiz.attempts - submitted_count if quiz.attempts is not None else None
        
        return QuizAttemptView(
            id=new_attempt.id,
            quiz_id=quiz_id,
            student_id=user_id,
            attempt_no=new_attempt_no,
            status=new_attempt.status,
            started_at=new_attempt.started_at,
            submitted_at=new_attempt.submitted_at,
            passed=None,
            attempts_left=attempts_left,
            expires_at=quiz.end_date,
            questions=None,
            submission=None
        )

    async def get_quiz_attempt(
        self, quiz_id: int, attempt_id: int, user_id: int
    ) -> QuizAttemptView:
        await self._verify_quiz_enrollment(quiz_id, user_id)
        
        from sqlalchemy.orm import selectinload
        
        from src.models.quiz_question_model import QuizQuestionModel
        
        # 1. Fetch attempt and eager load submission + quiz + questions + options
        stmt = (
            select(QuizAttemptModel)
            .options(
                selectinload(QuizAttemptModel.quiz)
                .selectinload(QuizModel.questions)
                .selectinload(QuizQuestionModel.options),
                selectinload(QuizAttemptModel.submission)
            )
            .where(
                QuizAttemptModel.id == attempt_id,
                QuizAttemptModel.quiz_id == quiz_id,
                QuizAttemptModel.student_id == user_id
            )
        )
        result = await self.db_session.execute(stmt)
        attempt = result.scalar_one_or_none()
        
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
            
        quiz = attempt.quiz
        if quiz.deleted_at:
            raise HTTPException(status_code=404, detail="Quiz not found")
            
        # Calculate attempts left
        submitted_stmt = select(func.count(QuizAttemptModel.id)).where(
            QuizAttemptModel.quiz_id == quiz_id,
            QuizAttemptModel.student_id == user_id,
            QuizAttemptModel.status == QuizAttemptStatus.SUBMITTED
        )
        submitted_count = (await self.db_session.execute(submitted_stmt)).scalar_one()
        attempts_left = quiz.attempts - submitted_count if quiz.attempts is not None else None
        
        passed = None
        if attempt.submission:
            passed = attempt.submission.score >= quiz.passing_score
            
        return QuizAttemptView(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            student_id=attempt.student_id,
            attempt_no=attempt.attempt_no,
            status=attempt.status,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            passed=passed,
            attempts_left=attempts_left,
            expires_at=quiz.end_date,
            questions=quiz.questions,  # DTO auto maps QuizQuestionResponse, doesn't leak is_correct
            submission=attempt.submission
        )
    async def submit_quiz_attempt(
        self, quiz_id: int, attempt_id: int, payload: QuizSubmitRequest, user_id: int
    ) -> QuizAttemptView:
        await self._verify_quiz_enrollment(quiz_id, user_id)
        
        from sqlalchemy.orm import selectinload
        from src.models.quiz_question_model import QuizQuestionModel
        from src.models.quiz_option_model import QuizOptionModel
        from src.models.quiz_submission_model import QuizSubmissionModel
        
        # 1. Fetch attempt + quiz + questions + options
        stmt = (
            select(QuizAttemptModel)
            .options(
                selectinload(QuizAttemptModel.quiz).selectinload(QuizModel.questions).selectinload(QuizQuestionModel.options),
                selectinload(QuizAttemptModel.submission)
            )
            .where(
                QuizAttemptModel.id == attempt_id,
                QuizAttemptModel.quiz_id == quiz_id,
                QuizAttemptModel.student_id == user_id
            )
        )
        attempt = (await self.db_session.execute(stmt)).scalar_one_or_none()
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
            
        quiz = attempt.quiz
        if quiz.deleted_at:
            raise HTTPException(status_code=404, detail="Quiz not found")
            
        # 2. Check status (Idempotent for SUBMITTED, error for ABANDONED)
        if attempt.status == QuizAttemptStatus.SUBMITTED:
            return await self.get_quiz_attempt(quiz_id, attempt_id, user_id)
        if attempt.status == QuizAttemptStatus.ABANDONED:
            raise HTTPException(status_code=400, detail="Cannot submit an abandoned attempt")
            
        # 3. Calculate score with weights (points)
        earned_points = 0.0
        total_points = sum(float(q.points) for q in quiz.questions)
        
        # Build answer key dict
        answer_key = {}
        for q in quiz.questions:
            for opt in q.options:
                if opt.is_correct:
                    answer_key[q.id] = (opt.id, float(q.points))
                    break
                    
        # Score answers
        for q_id, opt_id in payload.answers.items():
            correct_opt_id, points = answer_key.get(q_id, (None, 0.0))
            if correct_opt_id == opt_id:
                earned_points += points
                
        # Calculate percentage based on weighted points
        score = (earned_points / total_points * 100) if total_points > 0 else 0.0
        passed = score >= float(quiz.passing_score)
        
        now = datetime.now(timezone.utc)
        
        # 4. Create submission
        import json
        submission = QuizSubmissionModel(
            quiz_attempt_id=attempt.id,
            score=score,
            answers=json.dumps(payload.answers),
            submitted_at=now
        )
        self.db_session.add(submission)
        
        # 5. Update attempt status
        attempt.status = QuizAttemptStatus.SUBMITTED
        attempt.submitted_at = now
        attempt.submission = submission
        await self.db_session.flush()
        
        # 6. Side effect: Mark LessonContent as completed if passed
        if passed:
            from src.models.lesson_content_model import LessonContentModel, LessonContentType
            from src.models.lesson_content_progress_model import LessonContentProgressModel
            
            # Find the lesson content ID for this quiz
            from sqlalchemy.orm import selectinload
            from src.models.lesson_model import LessonModel
            from src.models.section_model import SectionModel
            content_stmt = select(LessonContentModel).options(
                selectinload(LessonContentModel.lesson).selectinload(LessonModel.section)
            ).where(
                LessonContentModel.content_type == LessonContentType.QUIZ,
                LessonContentModel.content_id == quiz_id
            )
            lesson_content = (await self.db_session.execute(content_stmt)).scalar_one_or_none()
            
            if lesson_content:
                content_id = lesson_content.id
                course_id = lesson_content.lesson.section.course_id
                from src.models.enrollment_model import EnrollmentModel
                # Find enrollment_id first
                enroll_stmt = select(EnrollmentModel.id).where(
                    EnrollmentModel.course_id == course_id,
                    EnrollmentModel.student_id == user_id
                )
                enroll_id = (await self.db_session.execute(enroll_stmt)).scalar_one_or_none()
                
                if enroll_id:
                    progress_stmt = select(LessonContentProgressModel).where(
                        LessonContentProgressModel.lesson_content_id == content_id,
                        LessonContentProgressModel.enrollment_id == enroll_id
                    )
                    progress = (await self.db_session.execute(progress_stmt)).scalar_one_or_none()
                    if not progress:
                        progress = LessonContentProgressModel(
                            lesson_content_id=content_id,
                            enrollment_id=enroll_id,
                            completed=True,
                            completed_at=now
                        )
                        self.db_session.add(progress)
                    elif not progress.completed:
                        progress.completed = True
                        progress.completed_at = now
                    
                await self.db_session.flush()
                
        return await self.get_quiz_attempt(quiz_id, attempt_id, user_id)

    async def list_quiz_attempts(self, quiz_id: int, user_id: int, page: int = 1, size: int = 20):
        await self._verify_quiz_enrollment(quiz_id, user_id)
        from sqlalchemy.orm import selectinload
        from src.models.quiz_submission_model import QuizSubmissionModel
        from src.models.quiz_model import QuizModel
        from src.models.quiz_attempt_model import QuizAttemptModel
        from fastapi import HTTPException

            
        # Get attempts history
        offset = (page - 1) * size
        list_stmt = (
            select(QuizAttemptModel)
            .options(
                selectinload(QuizAttemptModel.quiz),
                selectinload(QuizAttemptModel.submission)
            )
            .where(
                QuizAttemptModel.quiz_id == quiz_id,
                QuizAttemptModel.student_id == user_id
            )
            .order_by(QuizAttemptModel.started_at.desc())
            .offset(offset)
            .limit(size)
        )
        
        attempts = (await self.db_session.execute(list_stmt)).scalars().all()
        
        # Compute passed
        result = []
        for attempt in attempts:
            passed = None
            if attempt.submission:
                passed = attempt.submission.score >= attempt.quiz.passing_score
                
            result.append(QuizAttemptView(
                id=attempt.id,
                quiz_id=attempt.quiz_id,
                student_id=attempt.student_id,
                attempt_no=attempt.attempt_no,
                status=attempt.status,
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
                passed=passed,
                attempts_left=None,
                expires_at=attempt.quiz.end_date,
                submission=attempt.submission,
                questions=None
            ))
            
        from src.modules.student_course_directory.course_dto import QuizAttemptListResponse
        return QuizAttemptListResponse(data=result)

    # ------------------------------------------------------------------
    # Endpoint 7 — GET /student/quizzes/{quizId}
    # NOTE: QuizResponse never exposes is_correct — answer key is kept in
    #       _MOCK_QUIZ_ANSWER_KEY (internal dict, never part of any response schema)
    # ------------------------------------------------------------------

    async def get_quiz(self, quiz_id: int) -> QuizResponse:
        quiz = _MOCK_QUIZZES.get(quiz_id)
        if quiz is None:
            raise HTTPException(status_code=404, detail="Quiz not found")
        return quiz

    # ------------------------------------------------------------------
    # Endpoint 8 — POST /student/quizzes/{quizId}/submit
    # ------------------------------------------------------------------

    async def submit_quiz(
        self, quiz_id: int, payload: QuizSubmitRequest, user_id: int
    ) -> QuizSubmitResponse:
        quiz = _MOCK_QUIZZES.get(quiz_id)
        if quiz is None:
            raise HTTPException(status_code=404, detail="Quiz not found")

        if not payload.answers:
            raise HTTPException(
                status_code=400, detail="At least one answer is required"
            )

        answer_key = _MOCK_QUIZ_ANSWER_KEY.get(quiz_id, {})
        total_count = len(quiz.questions)
        correct_count = sum(
            1
            for q_id, chosen_option_id in payload.answers.items()
            if answer_key.get(q_id) == chosen_option_id
        )
        score = round((correct_count / total_count) * 10, 2) if total_count else 0.0
        passed = score >= quiz.passing_score

        return QuizSubmitResponse(
            submission_id=1001,
            score=score,
            passed=passed,
            correct_count=correct_count,
            total_count=total_count,
        )

    # ------------------------------------------------------------------
    # Endpoint 9 — POST /courses/{slug}/unenroll
    # ------------------------------------------------------------------

    async def unenroll_course(self, slug: str, user_id: int) -> UnenrollResponse:
        # Check if course exists
        course_stmt = select(CourseModel).where(CourseModel.slug == slug)
        course = (await self.db_session.execute(course_stmt)).scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check if enrollment exists
        enroll_stmt = select(EnrollmentModel).where(
            EnrollmentModel.student_id == user_id,
            EnrollmentModel.course_id == course.id,
        )
        enrollment = (await self.db_session.execute(enroll_stmt)).scalar_one_or_none()
        
        if not enrollment:
            # Tra api_spec.md: Không có api_spec cho endpoint unenroll.
            # Trả về 404 vì resource (enrollment) không tồn tại cho student này.
            raise HTTPException(status_code=404, detail="Enrollment not found")

        # Hard delete: No "unenrolled" status in EnrollStatus.
        # TODO: confirm with product/leader whether unenroll should hard-delete progress data or preserve history - api_spec.md doesn't define this endpoint.
        # Must delete LessonContentProgressModel first to avoid foreign key violation.
        del_progress_stmt = delete(LessonContentProgressModel).where(
            LessonContentProgressModel.enrollment_id == enrollment.id
        )
        await self.db_session.execute(del_progress_stmt)
        
        del_enrollment_stmt = delete(EnrollmentModel).where(
            EnrollmentModel.id == enrollment.id
        )
        await self.db_session.execute(del_enrollment_stmt)
        await self.db_session.commit()

        return UnenrollResponse(message=f"Successfully unenrolled from course '{course.title}'")
