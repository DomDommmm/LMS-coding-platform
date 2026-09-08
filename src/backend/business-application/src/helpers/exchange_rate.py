import logging
import time
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Fallback in case the API is down
FALLBACK_USD_TO_VND = 25000.0

class ExchangeRateCache(BaseModel):
    rate: float
    updated_at: float

# Simple in-memory cache
_cache: ExchangeRateCache | None = None
CACHE_TTL_SECONDS = 6 * 3600  # 6 hours

async def get_usd_to_vnd_rate() -> float:
    """
    Lấy tỷ giá USD sang VND thực tế từ open.er-api.com.
    Có sử dụng in-memory cache 6 tiếng và cơ chế fallback.
    """
    global _cache
    now = time.time()
    
    # Return cached rate if still valid
    if _cache and (now - _cache.updated_at < CACHE_TTL_SECONDS):
        return _cache.rate

    url = "https://open.er-api.com/v6/latest/USD"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            vnd_rate = data.get("rates", {}).get("VND")
            if not vnd_rate:
                logger.error("Không tìm thấy tỷ giá VND trong response từ API")
                return FALLBACK_USD_TO_VND
            
            # Update cache
            _cache = ExchangeRateCache(rate=float(vnd_rate), updated_at=now)
            logger.info("Đã cập nhật tỷ giá USD sang VND mới: %s", vnd_rate)
            return _cache.rate
            
    except httpx.HTTPError as e:
        logger.error("Lỗi khi gọi API tỷ giá: %s", str(e))
        # Use existing cache even if expired, else fallback
        if _cache:
            return _cache.rate
        return FALLBACK_USD_TO_VND
    except Exception as e:
        logger.error("Lỗi không mong muốn khi lấy tỷ giá: %s", str(e))
        if _cache:
            return _cache.rate
        return FALLBACK_USD_TO_VND
