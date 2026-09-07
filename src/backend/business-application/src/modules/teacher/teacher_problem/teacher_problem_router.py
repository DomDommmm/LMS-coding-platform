import time
import re 
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from src.helpers.validate_file import validate_file
from src.middlewares.role_middleware import require_role
from src.models.base_model import Role
from src.modules.teacher.teacher_problem.teacher_problem_dependency import (
    get_teacher_problem_service,
)
from src.modules.teacher.teacher_problem.teacher_problem_dto import (
    ProblemTagView,
    ProblemView,
    ProblemWrite,
    TestcaseUploadResponse,
    TestcaseView,
    UploadTestcase,
)
from src.modules.teacher.teacher_problem.teacher_problem_service import TeacherProblemService

router = APIRouter(tags=["Teacher Problem"])

def get_current_teacher_id(user: dict = Depends(require_role(Role.TEACHER))) -> int:
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return int(user_id)

@router.get("/problem-tags", response_model=list[ProblemTagView])
async def get_problem_tags(
    teacher_id: int = Depends(get_current_teacher_id),
    service: TeacherProblemService = Depends(get_teacher_problem_service)
):
    return await service.get_all_problem_tags()

@router.post("/problems", response_model=ProblemView, status_code=status.HTTP_201_CREATED)
async def create_problem(
    data: ProblemWrite,
    teacher_id: int = Depends(get_current_teacher_id),
    service: TeacherProblemService = Depends(get_teacher_problem_service)
):
    return await service.create_problem(teacher_id, data)

@router.put("/problems/{problem_id}", response_model=ProblemView)
async def update_problem(
    problem_id: int,
    data: ProblemWrite,
    teacher_id: int = Depends(get_current_teacher_id),
    service: TeacherProblemService = Depends(get_teacher_problem_service)
):
    return await service.update_problem(teacher_id, problem_id, data)






@router.post("/problems/{problem_id}/testcases/upload" , response_model=TestcaseUploadResponse , status_code = status.HTTP_201_CREATED) 
async def upload_testcase(
    problem_id : int, 
    data : UploadTestcase = Depends(), 
    input: UploadFile = File(...),  
    output: UploadFile = File(...), 
    service : TeacherProblemService = Depends(get_teacher_problem_service),
    user = Depends(require_role(Role.TEACHER))
): 
    validate_file(input , r'inp\d{2}') 
    validate_file(output , r'out\d{2}')
    teacher_id = int(user.get('sub')) 
    result = await service.upload_testcase(teacher_id , int(problem_id) , data.score , data.is_hidden , input, output)
    return result 
    