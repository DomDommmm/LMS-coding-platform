from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.bases.constants.submission_queues import SUBMISSION_EXECUTION_RESULT_QUEUE
from src.cores.settings import RABBITMQ_URL
from src.grpc.client import AuthGrpcClient
from src.jwk_service import PublicKeyService
from src.modules.health.health_router import router as health_router
from src.modules.lesson_comment.lesson_comment_router import (
    router as lesson_comment_router,
)
from src.modules.student_course_directory.course_router import router as course_router
from src.modules.student_course_directory.student_router import router as student_router
from src.modules.student_course_directory.favorite_router import router as favorite_router
from src.modules.student_course_directory.course_review_router import router as course_review_router
from src.modules.user.user_router import admin_router, router as user_router
from src.modules.submission.submission_route import router as submission_router
from src.modules.teacher import router as teacher_router
from src.services.rabbitmq.rabbitmq_manager import RabbitMQManager
from src.services.rabbitmq.submission_execution_result_consumer import (
    handle_submission_execution_result,
)
from src.services.sse.sse_manager import SSEManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executed once when the application starts.
    Download and cache the JWT public key from the auth provider.
    Create RabbitMQ connection
    sse instance
    """
    client = AuthGrpcClient("localhost:50051")
    await PublicKeyService.load(client)

    # sse manager
    sse_manager = SSEManager()
    app.state.sse_manager = sse_manager

    # rabbit_mq manager
    rabbitmq_manager = RabbitMQManager(url=RABBITMQ_URL)
    # rabbit_mq consumer connect
    await rabbitmq_manager.connect()

    # consumer register
    async def handle_submission_result(job):
        await handle_submission_execution_result(job, sse_manager)

    await rabbitmq_manager.consume(
        SUBMISSION_EXECUTION_RESULT_QUEUE, handle_submission_result
    )
    # register to the application
    app.state.rabbitmq_manager = rabbitmq_manager

    yield
    await rabbitmq_manager.close()
    print("Rabbit MQ stopped")
    await client.close()
    print("Grpc client stopped")
    app.state.sse_manager = None
    print("SSE connection stopped")
    # Cleanup if needed when the application shuts down.
    # Nguyen tac quan trong: Ai tao ra resource thi nguoi do phai dong resource


# CORS origins
origins = ["http://localhost:5173", "http://localhost:50051", "http://localhost:4001"]
app = FastAPI(lifespan=lifespan )
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
v1_router = APIRouter(prefix="/api")

v1_router.include_router(health_router)
v1_router.include_router(course_router)
v1_router.include_router(student_router)
v1_router.include_router(favorite_router)
v1_router.include_router(course_review_router)
v1_router.include_router(submission_router)
v1_router.include_router(lesson_comment_router)
v1_router.include_router(teacher_router)
v1_router.include_router(user_router)
v1_router.include_router(admin_router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    errors = []

    for err in exc.errors():
        errors.append(
            {
                "field": err["loc"][-1],
                "message": err["msg"],
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "message": "Cloudian Notification Request",
            "errors": errors,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": "Cloudian Notification",
            "code": exc.status_code,
            "detail": str(exc.detail),
            # Them thoi gian dien ra loi:
            # "timestamp":
            "timestamp": datetime.now(UTC).isoformat(),
            "path": request.url.path,
        },
    )


app.include_router(v1_router)
