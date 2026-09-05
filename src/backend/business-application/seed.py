"""Seed a complete local test dataset for the business-application database.

Usage:
    cd src/backend/business-application
    uv run python seed.py

The command truncates every table registered by the current ORM schema before
inserting deterministic demo data. Run it only against a disposable database.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

import src.models  # noqa: F401 - registers every table before TRUNCATE
from src.db import Base, async_session_maker
from src.helpers.pwd_hash import password_hash
from src.models.audit_log_model import AuditLogModel
from src.models.base_model import (
    AccountStatus,
    AuditAction,
    CourseStatus,
    Currency,
    InterviewLevel,
    InterviewMessageSender,
    InterviewStatus,
    LessonContentType,
    NotificationType,
    PaymentStatus,
    PayoutStatus,
    ProblemDifficulty,
    ProblemSubmissionStatus,
    QuizAttemptStatus,
    Role,
    TeacherRegisterStatus,
)
from src.models.comment_model import CommentModel
from src.models.course_favorite_model import CourseFavoriteModel
from src.models.course_moderation_review_model import CourseModerationReviewModel
from src.models.course_model import CourseModel
from src.models.course_review_model import CourseReviewModel
from src.models.enrollment_model import EnrollmentModel
from src.modules.student_course_directory.course_dto import EnrollStatus
from src.models.interview_message_model import InterviewMessageModel
from src.models.interview_report_model import InterviewReportModel
from src.models.interview_session_model import InterviewSessionModel
from src.models.language_model import LanguageModel
from src.models.lesson_content_model import LessonContentModel
from src.models.lesson_content_progress_model import LessonContentProgressModel
from src.models.lesson_model import LessonModel
from src.models.notification_model import NotificationModel
from src.models.problem_config_model import ProblemConfigModel
from src.models.problem_model import ProblemModel
from src.models.problem_tag_mapping_model import ProblemTagMappingModel
from src.models.problem_tag_model import ProblemTagModel
from src.models.quiz_enrollment_model import QuizEnrollmentModel
from src.models.quiz_attempt_model import QuizAttemptModel
from src.models.quiz_model import QuizModel
from src.models.quiz_option_model import QuizOptionModel
from src.models.quiz_question_model import QuizQuestionModel
from src.models.quiz_submission_model import QuizSubmissionModel
from src.models.reading_content_model import ReadingContentModel
from src.models.role_model import UserRoleModel
from src.models.section_model import SectionModel
from src.models.student_daily_activity_model import StudentDailyActivityModel
from src.models.student_profile_model import StudentProfileModel
from src.models.submission_model import SubmissionModel
from src.models.submission_result_detail_model import SubmissionResultDetailModel
from src.models.teacher_profile_model import TeacherProfileModel
from src.models.teacher_register_history_model import TeacherRegisterHistoryModel
from src.models.teacher_register_model import TeacherRegisterModel
from src.models.testcase_model import TestcaseModel
from src.models.transaction_model import TransactionModel
from src.models.user_model import UserModel
from src.models.user_identity_model import UserIdentityModel
from src.models.wallet_model import PayoutRequestModel, WalletLedgerModel, WalletModel


@dataclass(frozen=True)
class SeedAccount:
    key: str
    full_name: str
    email: str
    password: str
    role: Role
    address: str


# Keep these credentials stable: they are used for local debug and testing.
SEED_ACCOUNTS: tuple[SeedAccount, ...] = (
    SeedAccount("student", "Cloudian Student", "student@gmail.com", "student123", Role.STUDENT, "Cloudian Campus"),
    SeedAccount("teacher", "Cloudian Teacher", "teacher@gmail.com", "teacher123", Role.TEACHER, "Cloudian School"),
    SeedAccount("admin", "Cloudian Admin", "cloudian@gmail.com", "admin123", Role.ADMIN, "Cloudian HQ"),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


async def reset_business_database(session: Any) -> None:
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


async def seed_users(session: Any, seed_time: datetime) -> dict[str, UserModel]:
    users: dict[str, UserModel] = {}

    for account in SEED_ACCOUNTS:
        user = UserModel(
            full_name=account.full_name,
            email=account.email,
            password=password_hash.hash(account.password),
            address=account.address,
            avatar_url=None,
            refresh_token=None,
            account_status=AccountStatus.ACTIVE,
            created_at=seed_time,
            updated_at=seed_time,
        )
        session.add(user)
        await session.flush()
        session.add(UserRoleModel(user_id=user.id, role=account.role))
        users[account.key] = user

    teacher = users["teacher"]
    student = users["student"]
    session.add_all(
        [
            TeacherProfileModel(
                user_id=teacher.id,
                avatar_url="https://example.com/avatars/teacher.png",
                headline="Backend engineer and Python instructor",
                expertise_tags='["Python", "FastAPI", "PostgreSQL"]',
                years_of_experience=6,
                education_entries='[{"school": "Cloudian University", "degree": "BSc Computer Science"}]',
                experience_entries='[{"company": "Cloudian", "role": "Senior Backend Engineer"}]',
                github_url="https://github.com/cloudian-teacher",
                linkedin_url="https://linkedin.com/in/cloudian-teacher",
                website_url="https://teacher.example.com",
                email="teacher.contact@example.com",
                phone="+84900000001",
                created_at=seed_time - timedelta(days=90),
                updated_at=seed_time - timedelta(days=2),
            ),
            TeacherProfileModel(
                user_id=student.id,
                avatar_url="https://example.com/avatars/student-teacher.png",
                headline="Aspiring programming tutor",
                expertise_tags='["Python", "Algorithms"]',
                years_of_experience=1,
                education_entries='[{"school": "Cloudian Campus", "degree": "BSc Computer Science"}]',
                experience_entries='[]',
                github_url="https://github.com/cloudian-student",
                linkedin_url=None,
                website_url=None,
                email="student.contact@example.com",
                phone="+84900000002",
                created_at=seed_time - timedelta(days=10),
                updated_at=seed_time - timedelta(days=1),
            ),
            StudentProfileModel(
                user_id=student.id,
                bio="Seeded student account for course, quiz, and coding-practice tests.",
                learning_preferences='{"pace": "self-paced", "topics": ["Python", "algorithms"]}',
                social_links='{"github": "https://github.com/cloudian-student"}',
            ),
        ]
    )
    await session.flush()
    session.add(
        UserIdentityModel(
            user_id=student.id,
            provider="GOOGLE",
            provider_id="google-seed-student-001",
            created_at=seed_time,
            updated_at=seed_time,
        )
    )
    return users


async def seed_teacher_registers(
    session: Any, users: dict[str, UserModel], seed_time: datetime
) -> dict[str, TeacherRegisterModel]:
    admin = users["admin"]
    teacher = users["teacher"]
    student = users["student"]
    approved = TeacherRegisterModel(
        teacher_profile_id=teacher.id,
        bio="I teach practical backend development and algorithm design.",
        education_evidence_urls='["https://example.com/evidence/teacher-degree.pdf"]',
        legal_full_name="Cloudian Teacher",
        date_of_birth=date(1992, 5, 20),
        identity_number="012345678901",
        identity_front_url="https://example.com/identity/teacher-front.png",
        identity_back_url="https://example.com/identity/teacher-back.png",
        selfie_with_id_url="https://example.com/identity/teacher-selfie.png",
        cv_url="https://example.com/cv/teacher.pdf",
        motivation="I want to publish high-quality backend courses.",
        status=TeacherRegisterStatus.APPROVED,
        created_at=seed_time - timedelta(days=80),
        updated_at=seed_time - timedelta(days=75),
    )
    pending = TeacherRegisterModel(
        teacher_profile_id=student.id,
        bio="I would like to help beginner students learn Python.",
        education_evidence_urls='["https://example.com/evidence/student-transcript.pdf"]',
        legal_full_name="Cloudian Student",
        date_of_birth=date(2003, 8, 14),
        identity_number="012345678902",
        identity_front_url="https://example.com/identity/student-front.png",
        identity_back_url="https://example.com/identity/student-back.png",
        selfie_with_id_url="https://example.com/identity/student-selfie.png",
        cv_url="https://example.com/cv/student.pdf",
        motivation="I enjoy mentoring peers in coding clubs.",
        status=TeacherRegisterStatus.PENDING,
        created_at=seed_time - timedelta(days=2),
        updated_at=seed_time - timedelta(days=1),
    )
    session.add_all([approved, pending])
    await session.flush()
    session.add_all(
        [
            TeacherRegisterHistoryModel(
                teacher_register_id=approved.id,
                status=TeacherRegisterStatus.PENDING,
                reviewed_note="Application submitted.",
                submitted_at=seed_time - timedelta(days=80),
                acted_by=teacher.id,
            ),
            TeacherRegisterHistoryModel(
                teacher_register_id=approved.id,
                status=TeacherRegisterStatus.APPROVED,
                reviewed_note="Approved for seed data.",
                submitted_at=seed_time - timedelta(days=75),
                approved_at=seed_time - timedelta(days=75),
                acted_by=admin.id,
            ),
            TeacherRegisterHistoryModel(
                teacher_register_id=pending.id,
                status=TeacherRegisterStatus.PENDING,
                reviewed_note=None,
                submitted_at=seed_time - timedelta(days=1),
                acted_by=student.id,
            ),
        ]
    )
    return {"approved": approved, "pending": pending}


async def seed_reference_data(session: Any) -> dict[str, Any]:
    languages = {
        "python": LanguageModel(name="Python", default_time_limit=1000, default_memory_limit=256, is_active=True),
        "cpp": LanguageModel(name="C++", default_time_limit=1000, default_memory_limit=256, is_active=True),
        "javascript": LanguageModel(name="JavaScript", default_time_limit=1500, default_memory_limit=256, is_active=True),
    }
    tags = {
        "arrays": ProblemTagModel(tag_name="Arrays"),
        "hash_map": ProblemTagModel(tag_name="Hash Map"),
        "strings": ProblemTagModel(tag_name="Strings"),
    }
    session.add_all([*languages.values(), *tags.values()])
    await session.flush()
    return {"languages": languages, "tags": tags}


async def seed_quiz(session: Any, seed_time: datetime) -> QuizModel:
    quiz = QuizModel(
        title="Python Fundamentals Checkpoint",
        passing_score=Decimal("80"),
        start_date=seed_time - timedelta(days=1),
        end_date=seed_time + timedelta(days=30),
        attempts=3,
    )
    session.add(quiz)
    await session.flush()
    variables_question = QuizQuestionModel(
        quiz_id=quiz.id,
        title="Variables",
        content="Which keyword is used to define a constant in Python?",
        question_type="single_choice",
        points=Decimal("5"),
    )
    length_question = QuizQuestionModel(
        quiz_id=quiz.id,
        title="Lists",
        content="What is the output of len([1, 2, 3, 4])?",
        question_type="single_choice",
        points=Decimal("5"),
    )
    session.add_all([variables_question, length_question])
    await session.flush()
    session.add_all(
        [
            QuizOptionModel(question_id=variables_question.id, content="const", is_correct=False),
            QuizOptionModel(question_id=variables_question.id, content="There is no constant keyword", is_correct=True),
            QuizOptionModel(question_id=length_question.id, content="3", is_correct=False),
            QuizOptionModel(question_id=length_question.id, content="4", is_correct=True),
        ]
    )
    return quiz


async def seed_problem(session: Any, refs: dict[str, Any], teacher: UserModel, student: UserModel, seed_time: datetime) -> dict[str, Any]:
    problem = ProblemModel(
        teacher_id=teacher.id,
        title="Two Sum",
        slug="two-sum-seed",
        statement="Return the indices of two numbers whose sum equals the target.",
        input_description="The first line contains n and target; the second line contains n integers.",
        output_description="Print the zero-based indices.",
        constraints="1 <= n <= 1000",
        sample_input="4 9\n2 7 11 15",
        sample_output="0 1",
        explanation="A hash map tracks complements in linear time.",
        difficulty=ProblemDifficulty.EASY,
        passing_score=Decimal("100"),
        public=True,
        created_at=seed_time - timedelta(days=12),
    )
    session.add(problem)
    await session.flush()
    session.add_all(
        [
            ProblemTagMappingModel(problem_id=problem.id, tag_id=refs["tags"]["arrays"].id),
            ProblemTagMappingModel(problem_id=problem.id, tag_id=refs["tags"]["hash_map"].id),
            ProblemConfigModel(problem_id=problem.id, language_id=refs["languages"]["python"].id, time_limit_ms=1000, memory_limit_mb=256),
            ProblemConfigModel(problem_id=problem.id, language_id=refs["languages"]["cpp"].id, time_limit_ms=1000, memory_limit_mb=256),
        ]
    )
    visible_testcase = TestcaseModel(problem_id=problem.id, input_file="two-sum-visible.in", output_file="two-sum-visible.out", score=Decimal("50"), is_hidden=False)
    hidden_testcase = TestcaseModel(problem_id=problem.id, input_file="two-sum-hidden.in", output_file="two-sum-hidden.out", score=Decimal("50"), is_hidden=True)
    session.add_all([visible_testcase, hidden_testcase])
    await session.flush()
    submission = SubmissionModel(
        problem_id=problem.id,
        student_id=student.id,
        language_id=refs["languages"]["python"].id,
        source_code="def two_sum(numbers, target):\n    seen = {}\n    for index, value in enumerate(numbers):\n        if target - value in seen:\n            return [seen[target - value], index]\n        seen[value] = index\n",
        status=ProblemSubmissionStatus.ACCEPTED,
        score=Decimal("100"),
        runtime_ms=Decimal("12.5"),
        memory_kb=Decimal("512"),
        submitted_at=seed_time - timedelta(days=3),
    )
    session.add(submission)
    await session.flush()
    session.add_all(
        [
            SubmissionResultDetailModel(submission_id=submission.id, testcase_id=visible_testcase.id, status=ProblemSubmissionStatus.ACCEPTED, runtime_ms=Decimal("11.8"), memory_kb=Decimal("500")),
            SubmissionResultDetailModel(submission_id=submission.id, testcase_id=hidden_testcase.id, status=ProblemSubmissionStatus.ACCEPTED, runtime_ms=Decimal("12.5"), memory_kb=Decimal("512")),
        ]
    )
    return {"problem": problem, "submission": submission}


async def seed_courses_and_curriculum(session: Any, teacher: UserModel, quiz: QuizModel, problem: ProblemModel, seed_time: datetime) -> dict[str, Any]:
    free_course = CourseModel(
        title="Python Fundamentals", teacher_id=teacher.id, slug="python-fundamentals", field="Programming", tags="python,basics",
        description="A practical starter course for new Python learners.", thumbnail_url="https://example.com/courses/python-fundamentals.png",
        price=Decimal("0.00"), status=CourseStatus.APPROVED, created_at=seed_time - timedelta(days=12), updated_at=seed_time - timedelta(days=2),
    )
    paid_course = CourseModel(
        title="Advanced Algorithms", teacher_id=teacher.id, slug="advanced-algorithms", field="Computer Science", tags="algorithms,data-structures",
        description="A paid course for deeper algorithm practice.", thumbnail_url="https://example.com/courses/advanced-algorithms.png",
        price=Decimal("29.90"), status=CourseStatus.APPROVED, created_at=seed_time - timedelta(days=8), updated_at=seed_time - timedelta(days=1),
    )
    draft_course = CourseModel(
        title="AI Interview Lab", teacher_id=teacher.id, slug="ai-interview-lab", field="Career", tags="interview,ai",
        description="A draft course for interview preparation.", thumbnail_url="https://example.com/courses/ai-interview-lab.png",
        price=Decimal("19.90"), status=CourseStatus.DRAFT, created_at=seed_time - timedelta(days=3), updated_at=seed_time - timedelta(days=3),
    )
    session.add_all([free_course, paid_course, draft_course])
    await session.flush()
    session.add(CourseModerationReviewModel(course_id=free_course.id, reviewed_note="Approved for publication.", approved_at=seed_time - timedelta(days=10), submitted_at=seed_time - timedelta(days=11)))
    intro_section = SectionModel(course_id=free_course.id, title="Getting Started", position=0)
    practice_section = SectionModel(course_id=free_course.id, title="Practice", position=1)
    paid_section = SectionModel(course_id=paid_course.id, title="Core Concepts", position=0)
    session.add_all([intro_section, practice_section, paid_section])
    await session.flush()
    intro_lesson = LessonModel(section_id=intro_section.id, title="Welcome to Python", summary="Course introduction and setup.", score=Decimal("10"), position=0, created_at=seed_time - timedelta(days=11), updated_at=seed_time - timedelta(days=11))
    quiz_lesson = LessonModel(section_id=intro_section.id, title="Python Basics Quiz", summary="Check foundational knowledge.", score=Decimal("20"), position=1, created_at=seed_time - timedelta(days=10), updated_at=seed_time - timedelta(days=10))
    problem_lesson = LessonModel(section_id=practice_section.id, title="Two Sum Practice", summary="Solve a classic array problem.", score=Decimal("30"), position=0, created_at=seed_time - timedelta(days=9), updated_at=seed_time - timedelta(days=9))
    paid_lesson = LessonModel(section_id=paid_section.id, title="Algorithm Thinking", summary="A reading lesson for the paid course.", score=Decimal("15"), position=0, created_at=seed_time - timedelta(days=7), updated_at=seed_time - timedelta(days=7))
    session.add_all([intro_lesson, quiz_lesson, problem_lesson, paid_lesson])
    await session.flush()
    intro_reading = ReadingContentModel(title="Why Python is a good starter language", content="Python is readable, has a large ecosystem, and is great for automation.", created_at=seed_time - timedelta(days=11), updated_at=seed_time - timedelta(days=11))
    paid_reading = ReadingContentModel(title="Algorithm basics", content="Look for patterns, reduce the problem, and test edge cases.", created_at=seed_time - timedelta(days=7), updated_at=seed_time - timedelta(days=7))
    session.add_all([intro_reading, paid_reading])
    await session.flush()
    contents = {
        "intro": LessonContentModel(lesson_id=intro_lesson.id, content_type=LessonContentType.READING, content_id=intro_reading.id, position=0, created_at=seed_time - timedelta(days=11)),
        "quiz": LessonContentModel(lesson_id=quiz_lesson.id, content_type=LessonContentType.QUIZ, content_id=quiz.id, position=0, created_at=seed_time - timedelta(days=10)),
        "problem": LessonContentModel(lesson_id=problem_lesson.id, content_type=LessonContentType.PROBLEM, content_id=problem.id, position=0, created_at=seed_time - timedelta(days=9)),
        "paid": LessonContentModel(lesson_id=paid_lesson.id, content_type=LessonContentType.READING, content_id=paid_reading.id, position=0, created_at=seed_time - timedelta(days=7)),
    }
    session.add_all(contents.values())
    await session.flush()
    return {"free_course": free_course, "paid_course": paid_course, "contents": contents}


async def seed_learning_and_commerce(
    session: Any,
    users: dict[str, UserModel],
    quiz: QuizModel,
    graph: dict[str, Any],
    seed_time: datetime,
) -> dict[str, Any]:
    teacher = users["teacher"]
    student = users["student"]
    free_enrollment = EnrollmentModel(student_id=student.id, course_id=graph["free_course"].id, status=EnrollStatus.ENROLLED.value, enrolled_at=seed_time - timedelta(days=5))
    paid_enrollment = EnrollmentModel(student_id=student.id, course_id=graph["paid_course"].id, status=EnrollStatus.ENROLLED.value, enrolled_at=seed_time - timedelta(days=2))
    session.add_all([free_enrollment, paid_enrollment])
    await session.flush()
    session.add_all(
        [
            LessonContentProgressModel(enrollment_id=free_enrollment.id, lesson_content_id=graph["contents"]["intro"].id, completed=True, completed_at=seed_time - timedelta(days=5)),
            LessonContentProgressModel(enrollment_id=free_enrollment.id, lesson_content_id=graph["contents"]["quiz"].id, completed=True, completed_at=seed_time - timedelta(days=4)),
            LessonContentProgressModel(enrollment_id=free_enrollment.id, lesson_content_id=graph["contents"]["problem"].id, completed=True, completed_at=seed_time - timedelta(days=3)),
            LessonContentProgressModel(enrollment_id=paid_enrollment.id, lesson_content_id=graph["contents"]["paid"].id, completed=False),
            QuizEnrollmentModel(quiz_id=quiz.id, student_id=student.id, enrolled_at=seed_time - timedelta(days=4)),
            CourseFavoriteModel(student_id=student.id, course_id=graph["free_course"].id, created_at=seed_time - timedelta(days=5)),
            CourseReviewModel(course_id=graph["free_course"].id, student_id=student.id, rating=Decimal("5"), content="Clear explanations and useful practice.", created_at=seed_time - timedelta(days=2), updated_at=seed_time - timedelta(days=1)),
        ]
    )
    quiz_attempt = QuizAttemptModel(
        quiz_id=quiz.id,
        student_id=student.id,
        attempt_no=1,
        status=QuizAttemptStatus.SUBMITTED,
        started_at=seed_time - timedelta(days=4, minutes=20),
        submitted_at=seed_time - timedelta(days=4),
    )
    session.add(quiz_attempt)
    await session.flush()
    session.add(
        QuizSubmissionModel(
            quiz_attempt_id=quiz_attempt.id,
            score=Decimal("100"),
            answers='{"variables": "no_constant_keyword", "list_length": "4"}',
            submitted_at=seed_time - timedelta(days=4),
        )
    )
    root_comment = CommentModel(
        lesson_content_id=graph["contents"]["intro"].id,
        user_id=student.id,
        content="Could you explain why Python is a good first language?",
        created_at=seed_time - timedelta(days=4),
        updated_at=seed_time - timedelta(days=4),
    )
    session.add(root_comment)
    await session.flush()
    session.add(
        CommentModel(
            lesson_content_id=graph["contents"]["intro"].id,
            user_id=teacher.id,
            parent_id=root_comment.id,
            content="Its readable syntax lets beginners focus on problem solving.",
            created_at=seed_time - timedelta(days=3),
            updated_at=seed_time - timedelta(days=3),
        )
    )
    transaction = TransactionModel(
        student_id=student.id, course_id=graph["paid_course"].id, amount=Decimal("29.90"), status=PaymentStatus.COMPLETED,
        transaction_code="TRX-SEED-0001", payos_code="PAYOS-SEED-0001", payos_link="https://payos.example.com/checkout/TRX-SEED-0001",
        idempotency_key="seed-paid-course-checkout-0001", signature_verified=True, expires_at=seed_time - timedelta(days=2),
        completed_at=seed_time - timedelta(days=2), created_at=seed_time - timedelta(days=2), updated_at=seed_time - timedelta(days=2),
    )
    wallet = WalletModel(teacher_id=teacher.id, available_balance=Decimal("24.90"), pending_balance=Decimal("5.00"), currency=Currency.USD, created_at=seed_time - timedelta(days=2), updated_at=seed_time - timedelta(days=1))
    session.add_all([transaction, wallet])
    await session.flush()
    payout = PayoutRequestModel(wallet_id=wallet.id, teacher_id=teacher.id, amount=Decimal("5.00"), currency=Currency.USD, status=PayoutStatus.PENDING, created_at=seed_time - timedelta(hours=4), updated_at=seed_time - timedelta(hours=4))
    session.add(payout)
    await session.flush()
    session.add_all(
        [
            WalletLedgerModel(wallet_id=wallet.id, transaction_id=transaction.id, entry_type="revenue", amount=Decimal("29.90"), currency=Currency.USD, created_at=seed_time - timedelta(days=2)),
            WalletLedgerModel(wallet_id=wallet.id, payout_request_id=payout.id, entry_type="reserve", amount=Decimal("5.00"), currency=Currency.USD, created_at=seed_time - timedelta(hours=4)),
        ]
    )
    return {"transaction": transaction, "wallet": wallet, "payout": payout}


async def seed_activity_and_communication(
    session: Any,
    users: dict[str, UserModel],
    submission: SubmissionModel,
    transaction: TransactionModel,
    approved_register: TeacherRegisterModel,
    seed_time: datetime,
) -> None:
    admin = users["admin"]
    teacher = users["teacher"]
    student = users["student"]
    interview = InterviewSessionModel(
        student_id=student.id, topic="Python Backend Developer", level=InterviewLevel.JUNIOR, status=InterviewStatus.COMPLETED,
        max_questions=12, question_count=3, started_at=seed_time - timedelta(days=1), ended_at=seed_time - timedelta(days=1) + timedelta(minutes=25), report_generated_at=seed_time - timedelta(days=1) + timedelta(minutes=26),
    )
    session.add(interview)
    await session.flush()
    session.add_all(
        [
            InterviewMessageModel(session_id=interview.id, sender=InterviewMessageSender.AI, content="Tell me about a backend project you built.", created_at=seed_time - timedelta(days=1)),
            InterviewMessageModel(session_id=interview.id, sender=InterviewMessageSender.STUDENT, content="I built a FastAPI service with async PostgreSQL access.", created_at=seed_time - timedelta(days=1) + timedelta(minutes=2)),
            InterviewMessageModel(session_id=interview.id, sender=InterviewMessageSender.SYSTEM, content="Interview completed; generating report.", created_at=seed_time - timedelta(days=1) + timedelta(minutes=25)),
            InterviewReportModel(session_id=interview.id, overall_score=Decimal("8.5"), strengths="Clear backend thinking and practical testing instincts.", weaknesses="Could be more specific about scaling trade-offs.", suggestions="Practice system-design answers with concrete metrics.", generated_at=seed_time - timedelta(days=1) + timedelta(minutes=26)),
            NotificationModel(sender_id=admin.id, user_id=teacher.id, type=NotificationType.TEACHER_APPLICATION_APPROVED, target_type="teacher_register", target_id=approved_register.id, content="Your teacher application was approved.", is_read=True, created_at=seed_time - timedelta(days=75)),
            NotificationModel(sender_id=None, user_id=student.id, type=NotificationType.PAYMENT_SUCCESS, target_type="transaction", target_id=transaction.id, content="Your Advanced Algorithms payment completed successfully.", is_read=False, created_at=seed_time - timedelta(days=2)),
            NotificationModel(sender_id=teacher.id, user_id=student.id, type=NotificationType.JUDGE_RESULT, target_type="submission", target_id=submission.id, content="Your Two Sum submission was accepted.", is_read=True, created_at=seed_time - timedelta(days=3)),
            AuditLogModel(user_id=admin.id, action=AuditAction.ACCOUNT_STATUS_UPDATE, target_type="user", target_id=student.id, note="Seed student account activated.", correlation_id="seed-account-status-001", do_at=seed_time - timedelta(days=10)),
            AuditLogModel(user_id=admin.id, action=AuditAction.TEACHER_APPLICATION_REVIEW, target_type="teacher_register", target_id=approved_register.id, note="Seed teacher application approved.", correlation_id="seed-teacher-review-001", do_at=seed_time - timedelta(days=75)),
            StudentDailyActivityModel(student_id=student.id, activity_date=(seed_time - timedelta(days=3)).date(), contribution_count=2, study_seconds=3600, solved_problem_count=1, created_at=seed_time - timedelta(days=3), updated_at=seed_time - timedelta(days=3)),
            StudentDailyActivityModel(student_id=student.id, activity_date=(seed_time - timedelta(days=2)).date(), contribution_count=1, study_seconds=1800, solved_problem_count=0, created_at=seed_time - timedelta(days=2), updated_at=seed_time - timedelta(days=2)),
        ]
    )


async def seed_database() -> None:
    async with async_session_maker() as session:
        async with session.begin():
            await reset_business_database(session)
            seed_time = utc_now()
            users = await seed_users(session, seed_time)
            teacher_registers = await seed_teacher_registers(session, users, seed_time)
            refs = await seed_reference_data(session)
            quiz = await seed_quiz(session, seed_time)
            problem_data = await seed_problem(session, refs, users["teacher"], users["student"], seed_time)
            graph = await seed_courses_and_curriculum(session, users["teacher"], quiz, problem_data["problem"], seed_time)
            commerce_data = await seed_learning_and_commerce(session, users, quiz, graph, seed_time)
            await seed_activity_and_communication(
                session,
                users,
                problem_data["submission"],
                commerce_data["transaction"],
                teacher_registers["approved"],
                seed_time,
            )

    print("Seed completed successfully.")
    print("Created debug accounts:")
    for account in SEED_ACCOUNTS:
        print(f"- {account.email} / {account.password}")
    print("Seeded data covers all current schema tables and core test flows.")


def main() -> None:
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
