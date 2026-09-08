
from fastapi import HTTPException
from sqlalchemy import delete, exc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.testcase_model import TestcaseModel
from src.services.minio.minio_handler import MinioHandler
from src.models.problem_config_model import ProblemConfigModel
from src.models.problem_model import ProblemModel
from src.models.problem_tag_mapping_model import ProblemTagMappingModel
from src.models.problem_tag_model import ProblemTagModel
from src.modules.teacher.teacher_problem.teacher_problem_dto import (
    ProblemTagView,
    ProblemView,
    ProblemWrite,
    TestcaseUploadResponse,
    TestcaseView,
)
from fastapi import UploadFile

class TeacherProblemService:
    def __init__(self, db: AsyncSession , minio_handler : MinioHandler):
        self.db = db
        self.minio_handler = minio_handler

    async def get_all_problem_tags(self) -> list[ProblemTagView]:
        stmt = select(ProblemTagModel).order_by(ProblemTagModel.tag_name)
        result = await self.db.execute(stmt)
        tags = result.scalars().all()
        return [ProblemTagView.model_validate(t) for t in tags]

    async def _validate_tag_ids(self, tag_ids: list[int]) -> None:
        if tag_ids:
            stmt = select(ProblemTagModel.id).where(ProblemTagModel.id.in_(tag_ids))
            result = await self.db.execute(stmt)
            existing_tag_ids = result.scalars().all()
            if len(existing_tag_ids) != len(set(tag_ids)):
                raise HTTPException(status_code=400, detail="One or more tag_ids are invalid")

    async def create_problem(self, teacher_id: int, data: ProblemWrite) -> ProblemView:
        await self._validate_tag_ids(data.tag_ids)
        problem = (await self.db.execute(
            select(ProblemModel).where(ProblemModel.slug == data.slug)
        )).scalar_one_or_none() 
        if problem is not None: 
            raise HTTPException(
                status_code = 409, 
                detail = "Problem slug has been existed"
            )
        new_problem = ProblemModel(
            teacher_id=teacher_id,
            title=data.title,
            slug=data.slug,
            statement=data.statement,
            sample_input=data.sample_input,
            sample_output=data.sample_output,
            explanation=data.explanation,
            difficulty=data.difficulty,
            passing_score=data.passing_score,
            public=data.public
        )
        self.db.add(new_problem)
        try:
            await self.db.flush()
        except exc.IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail="Slug already exists")

        for t_id in set(data.tag_ids):
            self.db.add(ProblemTagMappingModel(problem_id=new_problem.id, tag_id=t_id))
            
        for conf in data.configs:
            self.db.add(ProblemConfigModel(
                problem_id=new_problem.id,
                language_id=conf.language_id,
                time_limit_ms=conf.time_limit_ms,
                memory_limit_mb=conf.memory_limit_mb
            ))

        await self.db.commit()
        await self.db.refresh(new_problem)
        return ProblemView.model_validate(new_problem)
    # Tien hanh cap nhat lai, hien tai no choi update fullbatch. Cai nay thuc hien cap nhat sau 
    async def update_problem(self, teacher_id: int, problem_id: int, data: ProblemWrite) -> ProblemView:
        # Check problem existence and ownership
        stmt = select(ProblemModel).where(ProblemModel.id == problem_id)
        result = await self.db.execute(stmt)
        problem = result.scalar_one_or_none()
        
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")
        if problem.teacher_id != teacher_id:
            raise HTTPException(status_code=403, detail="You do not have permission to modify this problem")

        await self._validate_tag_ids(data.tag_ids)

        # Update problem fields
        problem.title = data.title
        problem.slug = data.slug
        problem.statement = data.statement
        problem.sample_input = data.sample_input
        problem.sample_output = data.sample_output
        problem.explanation = data.explanation
        problem.difficulty = data.difficulty
        problem.passing_score = data.passing_score
        problem.public = data.public

        try:
            await self.db.flush()
        except exc.IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail="Slug already exists")

                # Update tags: replace all mapping
        stmt_del_tags = delete(ProblemTagMappingModel).where(ProblemTagMappingModel.problem_id == problem.id)
        await self.db.execute(stmt_del_tags)
        
        for t_id in set(data.tag_ids):
            self.db.add(ProblemTagMappingModel(problem_id=problem.id, tag_id=t_id))

        # Update configs: upsert by language_id to preserve ID
        # Note: PUT full-replace semantics - client must send all existing configs. Any omitted languages will be deleted.
        stmt_get_configs = select(ProblemConfigModel).where(ProblemConfigModel.problem_id == problem.id)
        result_configs = await self.db.execute(stmt_get_configs)
        existing_configs = result_configs.scalars().all()
        
        existing_config_map = {c.language_id: c for c in existing_configs}
        new_config_map = {c.language_id: c for c in data.configs}
        
        for lang_id, new_conf in new_config_map.items():
            if lang_id in existing_config_map:
                existing_conf = existing_config_map[lang_id]
                existing_conf.time_limit_ms = new_conf.time_limit_ms
                existing_conf.memory_limit_mb = new_conf.memory_limit_mb
            else:
                self.db.add(ProblemConfigModel(
                    problem_id=problem.id,
                    language_id=lang_id,
                    time_limit_ms=new_conf.time_limit_ms,
                    memory_limit_mb=new_conf.memory_limit_mb
                ))
                
        for lang_id, existing_conf in existing_config_map.items():
            if lang_id not in new_config_map:
                await self.db.delete(existing_conf)

        await self.db.commit()
        await self.db.refresh(problem)
        return ProblemView.model_validate(problem)
    """
    async def upload_testcase(self, teacher_id: int, problem_id: int, input_file: str, output_file: str, score: float, is_hidden: bool) -> TestcaseUploadResponse:
        # Check problem existence and ownership
        stmt = select(ProblemModel).where(ProblemModel.id == problem_id)
        result = await self.db.execute(stmt)
        problem = result.scalar_one_or_none()
        
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")
        if problem.teacher_id != teacher_id:
            raise HTTPException(status_code=403, detail="You do not have permission to modify this problem")

        from src.models.testcase_model import TestcaseModel

        new_tc = TestcaseModel(
            problem_id=problem.id,
            input_file=input_file,
            output_file=output_file,
            score=score,
            is_hidden=is_hidden
        )
        self.db.add(new_tc)
        await self.db.commit()
        await self.db.refresh(new_tc)
        
        return TestcaseUploadResponse(
            uploaded_count=1,
            message="Testcase uploaded successfully",
            testcases=[TestcaseView.model_validate(new_tc)]
        )
    """
    # Note tien hanh tao them cac du lieu de gui chung voi cai nay, tam thoi chugn ta se mock 
    # cac gia tri problem_id, is_hidden, score, teacher_id .... 
    async def upload_testcase(self, teacher_id : int, problem_id : int, score: float, is_hidden: bool, input_file: UploadFile , output_file : UploadFile): 
        try: 
            # Check problem existence and ownership
            stmt = select(ProblemModel).where(ProblemModel.id == problem_id)
            result = await self.db.execute(stmt)
            problem = result.scalar_one_or_none()
            
            if not problem:
                raise HTTPException(status_code=404, detail="Problem not found")
            if problem.teacher_id != teacher_id:
                raise HTTPException(status_code=403, detail="You do not have permission to modify this problem")

            input_upload_result = self.minio_handler.put_object(
                file_data = input_file.file, 
                file_name = input_file.filename, 
                content_type = input_file.content_type
            )
            output_upload_result = self.minio_handler.put_object(
                file_data = output_file.file, 
                file_name = output_file.filename, 
                content_type=output_file.content_type
            )
            # luu tru du lieu vao ben trong database
            testcase = TestcaseModel(
                problem_id = problem_id, 
                input_file = input_upload_result.get('file_name'), 
                output_file = output_upload_result.get('file_name'), 
                score = score, 
                is_hidden = is_hidden
            )
            self.db.add(
                testcase 
            )

            await self.db.commit() 
            await self.db.refresh(testcase) 
            return TestcaseUploadResponse(
                uploaded_count =2, 
                message = "Uploaded successfully", 
                testcases = [
                    TestcaseView(
                        id = testcase.id, 
                        problem_id=  problem_id, 
                        input_file = input_upload_result.get('file_name', ''), 
                        output_file = output_upload_result.get('file_name', ''), 
                        score = score, 
                        is_hidden = is_hidden 
                    )
                ]
            )
        except Exception as e: 
            await self.db.rollback() 
            # neu da lo upload len minio thi tien hanh xoa cac object nay (se trien khai sau)
            print("Upload testcase error: ", e) 
            raise e
    # Bo sung them API de thuc hien xoa testcase 