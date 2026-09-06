from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base

if TYPE_CHECKING:
    from src.models.quiz_attempt_model import QuizAttemptModel
    from src.models.quiz_question_model import QuizQuestionModel


class QuizModel(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    passing_score: Mapped[float] = mapped_column(Numeric, default=0, nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list["QuizQuestionModel"]] = relationship(back_populates="quiz")
    attempts_history: Mapped[list["QuizAttemptModel"]] = relationship(
        back_populates="quiz"
    )
