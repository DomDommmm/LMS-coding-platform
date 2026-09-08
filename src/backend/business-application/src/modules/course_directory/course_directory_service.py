from decimal import Decimal
from typing import cast

from fastapi import HTTPException
from sqlalchemy import ScalarSelect, Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.base_model import (
    AccountStatus,
    CourseStatus,
    Role,
    TeacherRegisterStatus,
)
from src.models.course_favorite_model import CourseFavoriteModel
from src.models.course_model import CourseModel
from src.models.course_review_model import CourseReviewModel
from src.models.enrollment_model import EnrollmentModel
from src.models.lesson_model import LessonModel
from src.models.role_model import UserRoleModel
from src.models.teacher_profile_model import TeacherProfileModel
from src.models.teacher_register_model import TeacherRegisterModel
from src.models.user_model import UserModel
from src.modules.course_directory.course_directory_dto import (
    CourseDetailView,
    CourseFavoriteView,
    CourseListResponse,
    CourseReviewPatch,
    CourseReviewView,
    CourseReviewWrite,
    CourseView,
    FavoriteListResponse,
    FavoriteRemovalView,
    InstructorDetailView,
    InstructorListResponse,
    Pagination,
    PriceType,
    ReviewListResponse,
    ReviewSummary,
    SectionOverviewView,
    TeacherProfileView,
)


ACTIVE_ENROLLMENT_STATUSES = ("enrolled", "active", "completed")


class CourseDirectoryService:
    def __init__(self, db: AsyncSession):
        self.db: AsyncSession = db

    @staticmethod
    def _course_stats() -> ScalarSelect[float]:
        rating = (
            select(func.coalesce(func.avg(CourseReviewModel.rating), 0))
            .where(CourseReviewModel.course_id == CourseModel.id)
            .scalar_subquery()
        )
        return rating

    @staticmethod
    def _eligible_course_statement() -> Select[tuple[CourseModel, float]]:
        rating = CourseDirectoryService._course_stats()
        return (
            select(CourseModel, rating)
            .join(TeacherProfileModel, TeacherProfileModel.user_id == CourseModel.teacher_id)
            .join(
                TeacherRegisterModel,
                TeacherRegisterModel.teacher_profile_id == TeacherProfileModel.user_id,
            )
            .join(
                UserRoleModel,
                (UserRoleModel.user_id == TeacherProfileModel.user_id)
                & (UserRoleModel.role == Role.TEACHER),
            )
            .join(UserModel, UserModel.id == TeacherProfileModel.user_id)
            .where(
                CourseModel.status == CourseStatus.APPROVED,
                CourseModel.deleted_at.is_(None),
                TeacherRegisterModel.status == TeacherRegisterStatus.APPROVED,
                TeacherRegisterModel.deleted_at.is_(None),
                UserModel.account_status == AccountStatus.ACTIVE,
            )
        )

    @staticmethod
    def _course_view(course: CourseModel, rating: float) -> CourseView:
        return CourseView(
            id=course.id,
            teacher_id=course.teacher_id,
            title=course.title,
            slug=course.slug,
            # rating=float(rating),
            field=course.field,
            tags=course.tags,
            description=course.description,
            thumbnail_url=course.thumbnail_url,
            price=Decimal(str(course.price)),
            
            status=course.status,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )

    @staticmethod
    def _instructor_view(
        user: UserModel,
        profile: TeacherProfileModel,
        registration: TeacherRegisterModel,
    ) -> TeacherProfileView:
        return TeacherProfileView(
            user_id=user.id,
            full_name=user.full_name,
            avatar_url=profile.avatar_url or user.avatar_url,
            headline=profile.headline,
            expertise_tags=profile.expertise_tags,
            years_of_experience=profile.years_of_experience,
            education_entries=profile.education_entries,
            experience_entries=profile.experience_entries,
            github_url=profile.github_url,
            linkedin_url=profile.linkedin_url,
            website_url=profile.website_url,
            email=profile.email,
            phone=profile.phone,
            bio=registration.bio,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    async def _approved_instructor(
        self, user_id: int
    ) -> tuple[UserModel, TeacherProfileModel, TeacherRegisterModel]:
        row = (await self.db.execute(
            select(UserModel, TeacherProfileModel, TeacherRegisterModel)
            .join(TeacherProfileModel, TeacherProfileModel.user_id == UserModel.id)
            .join(
                TeacherRegisterModel,
                TeacherRegisterModel.teacher_profile_id == TeacherProfileModel.user_id,
            )
            .join(
                UserRoleModel,
                (UserRoleModel.user_id == UserModel.id)
                & (UserRoleModel.role == Role.TEACHER),
            )
            .where(
                UserModel.id == user_id,
                UserModel.account_status == AccountStatus.ACTIVE,
                TeacherRegisterModel.status == TeacherRegisterStatus.APPROVED,
                TeacherRegisterModel.deleted_at.is_(None),
            )
        )).tuples().first()
        if row is None:
            raise HTTPException(404, "Instructor not found")
        return row

    async def _require_public_course(self, course_id: int) -> None:
        statement = self._eligible_course_statement().where(CourseModel.id == course_id)
        if (await self.db.execute(statement)).first() is None:
            raise HTTPException(404, "Course not found")
        
    async def _lock_student(self, student_id: int) -> None:
        _ = await self.db.execute(
            select(UserModel.id).where(UserModel.id == student_id).with_for_update()
        )

    async def _require_enrollment(self, course_id: int, student_id: int) -> None:
        enrollment_id = await self.db.scalar(select(EnrollmentModel.id).where(
            EnrollmentModel.course_id == course_id,
            EnrollmentModel.student_id == student_id,
            EnrollmentModel.status.in_(ACTIVE_ENROLLMENT_STATUSES),
        ))
        if enrollment_id is None:
            raise HTTPException(403, "Must be enrolled to review this course")

    async def list_courses(
        self,
        page: int,
        size: int,
        q: str | None,
        field: str | None,
        tag: str | None,
        price_type: PriceType | None,
    ) -> CourseListResponse:
        statement = self._eligible_course_statement()
        if q:
            statement = statement.where(or_(
                CourseModel.title.ilike(f"%{q}%"),
                CourseModel.description.ilike(f"%{q}%"),
            ))
        if field:
            statement = statement.where(CourseModel.field == field)
        if tag:
            normalized_tags = func.regexp_replace(func.trim(CourseModel.tags), r"\s*,\s*", ",", "g")
            statement = statement.where(
                func.concat(",", normalized_tags, ",").contains(f",{tag},", autoescape=True)
            )
        if price_type == PriceType.FREE:
            statement = statement.where(CourseModel.price == 0)
        elif price_type == PriceType.PAID:
            statement = statement.where(CourseModel.price > 0)

        total = await self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = (await self.db.execute(
            statement.order_by(CourseModel.id).offset((page - 1) * size).limit(size)
        )).tuples().all()
        return CourseListResponse(
            data=[self._course_view(*row) for row in rows],
            pagination=Pagination(page=page, size=size, total=total),
        )

    async def get_course(self, slug: str, current_user_id: int | None) -> CourseDetailView:
        statement = (
            self._eligible_course_statement()
            .where(CourseModel.slug == slug)
            .options(selectinload(CourseModel.sections))
        )
        row = (await self.db.execute(statement)).tuples().first()
        if row is None:
            raise HTTPException(404, "Course not found")
        course, rating = row
        user, profile, registration = await self._approved_instructor(course.teacher_id)

        section_ids = [section.id for section in course.sections]
        lesson_counts: dict[int, int] = {}
        if section_ids:
            counts = (await self.db.execute(
                select(LessonModel.section_id, func.count(LessonModel.id))
                .where(LessonModel.section_id.in_(section_ids))
                .group_by(LessonModel.section_id)
            )).tuples().all()
            lesson_counts = {section_id: count for section_id, count in counts}
        
        detail = {
            **self._course_view(course, rating).model_dump(),
            "instructor": self._instructor_view(user, profile, registration),
            "sections": [
                SectionOverviewView(
                    id=section.id,
                    course_id=section.course_id,
                    title=section.title,
                    position=section.position,
                    lesson_count=lesson_counts.get(section.id, 0),
                )
                for section in sorted(course.sections, key=lambda item: item.position)
            ],
        }
        if current_user_id is not None:
            is_favorited = bool(await self.db.scalar(select(CourseFavoriteModel.id).where(
                CourseFavoriteModel.student_id == current_user_id,
                CourseFavoriteModel.course_id == course.id,
            )))
            is_enrolled = bool(await self.db.scalar(select(EnrollmentModel.id).where(
                EnrollmentModel.student_id == current_user_id,
                EnrollmentModel.course_id == course.id,
                EnrollmentModel.status.in_(ACTIVE_ENROLLMENT_STATUSES),
            )))
            detail["is_favorited"] = is_favorited
            detail["is_enrolled"] = is_enrolled
        review_count = await self.db.scalar(select(func.count(CourseReviewModel.id)).where(
            CourseReviewModel.course_id == course.id
        )) or 0

        return CourseDetailView.model_validate(
            {
                **detail,
                "review_summary": ReviewSummary(
                    average_rating=float(rating), total_reviews=review_count
                ),
            }
        )

    async def list_instructors(
        self, page: int, size: int, q: str | None, field: str | None
    ) -> InstructorListResponse:
        statement = (
            select(UserModel, TeacherProfileModel, TeacherRegisterModel)
            .join(TeacherProfileModel, TeacherProfileModel.user_id == UserModel.id)
            .join(TeacherRegisterModel, TeacherRegisterModel.teacher_profile_id == UserModel.id)
            .join(
                UserRoleModel,
                (UserRoleModel.user_id == UserModel.id)
                & (UserRoleModel.role == Role.TEACHER),
            )
            .where(
                UserModel.account_status == AccountStatus.ACTIVE,
                TeacherRegisterModel.status == TeacherRegisterStatus.APPROVED,
                TeacherRegisterModel.deleted_at.is_(None),
            )
        )
        if q:
            statement = statement.where(or_(
                UserModel.full_name.ilike(f"%{q}%"),
                TeacherProfileModel.headline.ilike(f"%{q}%"),
                TeacherProfileModel.expertise_tags.ilike(f"%{q}%"),
            ))
        if field:
            statement = statement.where(TeacherProfileModel.expertise_tags.ilike(f"%{field}%"))

        total = await self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = (await self.db.execute(
            statement.order_by(UserModel.id).offset((page - 1) * size).limit(size)
        )).tuples().all()
        return InstructorListResponse(
            data=[self._instructor_view(*row) for row in rows],
            pagination=Pagination(page=page, size=size, total=total),
        )

    async def get_instructor(self, user_id: int) -> InstructorDetailView:
        user, profile, registration = await self._approved_instructor(user_id)
        rows = (await self.db.execute(
            self._eligible_course_statement()
            .where(CourseModel.teacher_id == user_id)
            .order_by(CourseModel.id)
        )).tuples().all()
        return InstructorDetailView.model_validate(
            {
                **self._instructor_view(user, profile, registration).model_dump(),
                "courses": [self._course_view(*row) for row in rows],
            }
        )

    async def list_favorites(
        self, student_id: int, page: int, size: int
    ) -> FavoriteListResponse:
        rating = self._course_stats()
        statement = (
            select(CourseFavoriteModel, CourseModel, rating)
            .join(CourseModel, CourseModel.id == CourseFavoriteModel.course_id)
            .join(TeacherProfileModel, TeacherProfileModel.user_id == CourseModel.teacher_id)
            .join(TeacherRegisterModel, TeacherRegisterModel.teacher_profile_id == CourseModel.teacher_id)
            .join(
                UserRoleModel,
                (UserRoleModel.user_id == CourseModel.teacher_id)
                & (UserRoleModel.role == Role.TEACHER),
            )
            .join(UserModel, UserModel.id == CourseModel.teacher_id)
            .where(
                CourseFavoriteModel.student_id == student_id,
                CourseModel.status == CourseStatus.APPROVED,
                CourseModel.deleted_at.is_(None),
                TeacherRegisterModel.status == TeacherRegisterStatus.APPROVED,
                TeacherRegisterModel.deleted_at.is_(None),
                UserModel.account_status == AccountStatus.ACTIVE,
            )
        )
        total = await self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = (await self.db.execute(
            statement.order_by(CourseFavoriteModel.created_at.desc(), CourseFavoriteModel.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )).tuples().all()
        return FavoriteListResponse(
            data=[
                CourseFavoriteView(
                    id=favorite.id,
                    student_id=favorite.student_id,
                    course_id=favorite.course_id,
                    created_at=favorite.created_at,
                    course=self._course_view(course, average),
                )
                for favorite, course, average in rows
            ],
            pagination=Pagination(page=page, size=size, total=total),
        )

    async def add_favorite(
        self,
        student_id: int,
        course_id: int,
    ) -> CourseFavoriteView:
        try:
            await self._lock_student(student_id)

            await self._require_public_course(course_id)
            course = (await self.db.execute(
                select(CourseModel).where(
                    CourseModel.id == course_id
                )
            )).scalar() 
            if course is None: 
                raise HTTPException(
                    404, "Course not found" 
                )
            favorite = await self.db.scalar(
                select(CourseFavoriteModel)
                .options(
                    selectinload(CourseFavoriteModel.course)
                )
                .where(
                    CourseFavoriteModel.student_id == student_id,
                    CourseFavoriteModel.course_id == course_id,
                )
            )
            if favorite is None:
                favorite = CourseFavoriteModel(
                    student_id=student_id,
                    course_id=course_id,
                )

                self.db.add(favorite)
                await self.db.flush()
                favorite.course = course
            result = CourseFavoriteView(
                student_id = student_id, 
                course_id=course_id, 
                course = CourseView(
                    id = course.id, 
                    teacher_id=course.teacher_id,
                    title=course.title,
                    slug=course.slug,
                    # rating=course.rating,
                    field=course.field,
                    tags=course.tags,
                    description=course.description,
                    thumbnail_url=course.thumbnail_url,
                    price=Decimal(str(course.price)),
                    status=course.status,
                    created_at=course.created_at,
                    updated_at=course.updated_at,
                ), 
                created_at = favorite.created_at, 
                id = favorite.id, 
            )
            await self.db.commit()
            return result

        except Exception as e:
            print("Adding favorite course error:", e)
            await self.db.rollback()
            raise

    async def remove_favorite(self, student_id: int, course_id: int) -> FavoriteRemovalView:
        await self._lock_student(student_id)
        _ = await self.db.execute(delete(CourseFavoriteModel).where(
            CourseFavoriteModel.student_id == student_id,
            CourseFavoriteModel.course_id == course_id,
        ))
        await self.db.commit()
        return FavoriteRemovalView(course_id=course_id)

    async def list_reviews(
        self, course_id: int, rating: int | None, page: int, size: int
    ) -> ReviewListResponse:
        await self._require_public_course(course_id)
        summary_row = cast(tuple[float, int], (await self.db.execute(select(
            func.coalesce(func.avg(CourseReviewModel.rating), 0),
            func.count(CourseReviewModel.id),
        ).where(CourseReviewModel.course_id == course_id))).tuples().one())
        distribution = {value: 0 for value in range(1, 6)}
        for value, count in (await self.db.execute(
            select(CourseReviewModel.rating, func.count(CourseReviewModel.id))
            .where(CourseReviewModel.course_id == course_id)
            .group_by(CourseReviewModel.rating)
        )).tuples().all():
            distribution[int(value)] = count

        statement = select(CourseReviewModel).where(CourseReviewModel.course_id == course_id)
        if rating is not None:
            statement = statement.where(CourseReviewModel.rating == rating)
        total = await self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        reviews = (await self.db.scalars(
            statement.order_by(CourseReviewModel.created_at.desc(), CourseReviewModel.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )).all()
        return ReviewListResponse(
            data=[CourseReviewView.model_validate(review) for review in reviews],
            pagination=Pagination(page=page, size=size, total=total),
            summary=ReviewSummary(
                average_rating=float(summary_row[0]),
                total_reviews=summary_row[1],
                rating_distribution=distribution,
            ),
        )

    async def add_review(
        self, course_id: int, student_id: int, payload: CourseReviewWrite
    ) -> CourseReviewView:
        await self._lock_student(student_id)
        await self._require_public_course(course_id)
        await self._require_enrollment(course_id, student_id)
        if await self.db.scalar(select(CourseReviewModel.id).where(
            CourseReviewModel.course_id == course_id,
            CourseReviewModel.student_id == student_id,
        )) is not None:
            raise HTTPException(409, {
                "message": "You have already reviewed this course",
                "error_code": "DUPLICATE_RESOURCE",
            })
        review = CourseReviewModel(
            course_id=course_id,
            student_id=student_id,
            rating=payload.rating,
            content=payload.content,
        )
        self.db.add(review)
        try:
            await self.db.commit()
            await self.db.refresh(review)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(409, {
                "message": "You have already reviewed this course",
                "error_code": "DUPLICATE_RESOURCE",
            })
        return CourseReviewView.model_validate(review)

    async def update_review(
        self,
        course_id: int,
        review_id: int,
        student_id: int,
        payload: CourseReviewPatch,
    ) -> CourseReviewView:
        await self._lock_student(student_id)
        await self._require_public_course(course_id)
        await self._require_enrollment(course_id, student_id)
        review = await self.db.scalar(select(CourseReviewModel).where(
            CourseReviewModel.id == review_id,
            CourseReviewModel.course_id == course_id,
            CourseReviewModel.student_id == student_id,
        ))
        if review is None:
            raise HTTPException(404, "Review not found")
        if payload.rating is not None:
            review.rating = payload.rating
        if "content" in payload.model_fields_set:
            review.content = payload.content
        await self.db.commit()
        await self.db.refresh(review)
        return CourseReviewView.model_validate(review)
