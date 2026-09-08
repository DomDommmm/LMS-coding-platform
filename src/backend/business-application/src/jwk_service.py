import asyncio
import logging

from src.cores.settings import JWT_ACCESS_PUBLIC
from src.grpc.client import AuthGrpcClient

logger = logging.getLogger(__name__)


class PublicKeyService:
    _public_key: str | None = None

    @classmethod
    async def load(cls, client: AuthGrpcClient, retries: int = 3, delay: float = 1.0):
        # 1. Thử tải qua gRPC từ Auth Provider trước (nguồn chính)
        for attempt in range(1, retries + 1):
            try:
                response = await client.public_key()
                if response and "BEGIN PUBLIC KEY" in response:
                    cls._public_key = response
                    logger.info("Public key has been loaded successfully via gRPC.")
                    return
            except Exception as e:
                logger.warning(
                    "Attempt %s/%s: Failed to load public key via gRPC (%s)",
                    attempt,
                    retries,
                    e,
                )
                if attempt < retries:
                    await asyncio.sleep(delay)

        # 2. Nếu gRPC không thành công, fallback sang biến môi trường JWT_ACCESS_PUBLIC
        if JWT_ACCESS_PUBLIC and "BEGIN PUBLIC KEY" in JWT_ACCESS_PUBLIC:
            logger.warning(
                "Could not connect to Auth Provider via gRPC. Falling back to JWT_ACCESS_PUBLIC from environment."
            )
            cls._public_key = JWT_ACCESS_PUBLIC
            return

        # 3. Nếu cả gRPC lẫn biến môi trường đều không có -> Báo lỗi rõ ràng
        logger.error(
            "CRITICAL: Cannot load JWT public key (gRPC failed and no valid JWT_ACCESS_PUBLIC in environment)."
        )
        raise RuntimeError(
            "JWT public key could not be loaded via gRPC and no fallback key provided in environment (JWT_ACCESS_PUBLIC)."
        )

    @classmethod
    def get(cls) -> str:
        if cls._public_key is None:
            raise RuntimeError("JWT public key has not been loaded.")

        return cls._public_key