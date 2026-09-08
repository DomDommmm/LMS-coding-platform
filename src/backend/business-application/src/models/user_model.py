from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base
from src.models.base_model import AccountStatus, TimestampMixin

if TYPE_CHECKING:
    from src.models.audit_log_model import AuditLogModel
    from src.models.comment_model import CommentModel
    from src.models.course_favorite_model import CourseFavoriteModel
    from src.models.course_model import CourseModel
    from src.models.course_review_model import CourseReviewModel
    from src.models.enrollment_model import EnrollmentModel
    from src.models.interview_session_model import InterviewSessionModel
    from src.models.notification_model import NotificationModel
    from src.models.problem_model import ProblemModel
    from src.models.quiz_attempt_model import QuizAttemptModel
    from src.models.role_model import UserRoleModel
    from src.models.student_daily_activity_model import StudentDailyActivityModel
    from src.models.student_profile_model import StudentProfileModel
    from src.models.submission_model import SubmissionModel
    from src.models.teacher_profile_model import TeacherProfileModel
    from src.models.teacher_register_history_model import TeacherRegisterHistoryModel
    from src.models.transaction_model import TransactionModel
    from src.models.user_identity_model import UserIdentityModel
    from src.models.wallet_model import PayoutRequestModel, WalletModel


class UserModel(TimestampMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str | None] = mapped_column(nullable=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str | None] = mapped_column(nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(nullable=True)
    account_status: Mapped[AccountStatus] = mapped_column(
        SQLEnum(AccountStatus), default=AccountStatus.UNVERIFIED, nullable=False
    )

    roles: Mapped[list["UserRoleModel"]] = relationship(back_populates="user")
    identities: Mapped[list["UserIdentityModel"]] = relationship(
        back_populates="user"
    )
    student_profile: Mapped["StudentProfileModel | None"] = relationship(back_populates="user", uselist=False)
    teacher_profile: Mapped["TeacherProfileModel | None"] = relationship(back_populates="user", uselist=False)
    teaching_courses: Mapped[list["CourseModel"]] = relationship(back_populates="teacher")
    authored_problems: Mapped[list["ProblemModel"]] = relationship(back_populates="teacher")
    enrollments: Mapped[list["EnrollmentModel"]] = relationship(back_populates="student")
    quiz_attempts: Mapped[list["QuizAttemptModel"]] = relationship(
        back_populates="student"
    )
    problem_submissions: Mapped[list["SubmissionModel"]] = relationship(back_populates="student")
    transactions: Mapped[list["TransactionModel"]] = relationship(back_populates="student")
    course_favorites: Mapped[list["CourseFavoriteModel"]] = relationship(back_populates="student")
    course_reviews: Mapped[list["CourseReviewModel"]] = relationship(back_populates="student")
    wallet: Mapped["WalletModel | None"] = relationship(back_populates="teacher", uselist=False)
    payout_requests: Mapped[list["PayoutRequestModel"]] = relationship(back_populates="teacher", foreign_keys="[PayoutRequestModel.teacher_id]")
    reviewed_payout_requests: Mapped[list["PayoutRequestModel"]] = relationship(back_populates="reviewer", foreign_keys="[PayoutRequestModel.reviewed_by]")
    interview_sessions: Mapped[list["InterviewSessionModel"]] = relationship(back_populates="student")
    notifications_sent: Mapped[list["NotificationModel"]] = relationship(back_populates="sender", foreign_keys="[NotificationModel.sender_id]")
    notifications_received: Mapped[list["NotificationModel"]] = relationship(back_populates="recipient", foreign_keys="[NotificationModel.user_id]")
    audit_logs: Mapped[list["AuditLogModel"]] = relationship(back_populates="user")
    teacher_register_history_actions: Mapped[list["TeacherRegisterHistoryModel"]] = relationship(back_populates="actor")
    daily_activities: Mapped[list["StudentDailyActivityModel"]] = relationship(back_populates="student")
    comments: Mapped[list["CommentModel"]] = relationship(back_populates="user")
