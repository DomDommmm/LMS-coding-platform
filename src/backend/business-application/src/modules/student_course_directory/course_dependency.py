from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import get_db_session
from src.modules.student_course_directory.course_service import CourseService

def get_course_service(db_session: AsyncSession = Depends(get_db_session)) -> CourseService:
    """Provide a CourseService instance for FastAPI Depends injection."""
    return CourseService(db_session=db_session)
