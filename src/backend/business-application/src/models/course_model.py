from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base
from src.models.base_model import CourseStatus, TimestampMixin

if TYPE_CHECKING:
    from src.models.course_favorite_model import CourseFavoriteModel
    from src.models.course_moderation_review_model import CourseModerationReviewModel
    from src.models.course_review_model import CourseReviewModel
    from src.models.enrollment_model import EnrollmentModel
    from src.models.section_model import SectionModel
    from src.models.transaction_model import TransactionModel
    from src.models.user_model import UserModel


class CourseModel(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    slug: Mapped[str] = mapped_column(unique=True, nullable=False)
    field: Mapped[str | None] = mapped_column(nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    status: Mapped[CourseStatus] = mapped_column(
        SQLEnum(CourseStatus), default=CourseStatus.DRAFT, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #Thuc hien denormalize. Them rating vao ben trong course_model de co the de dang tinht oan 
    teacher: Mapped["UserModel"] = relationship(back_populates="teaching_courses")
    sections: Mapped[list["SectionModel"]] = relationship(back_populates="course")
    enrollments: Mapped[list["EnrollmentModel"]] = relationship(back_populates="course")
    transactions: Mapped[list["TransactionModel"]] = relationship(back_populates="course")
    favorites: Mapped[list["CourseFavoriteModel"]] = relationship(back_populates="course")
    reviews: Mapped[list["CourseReviewModel"]] = relationship(back_populates="course")
    moderation_reviews: Mapped[list["CourseModerationReviewModel"]] = relationship(back_populates="course")
