import hashlib
import hmac
import logging
logger = logging.getLogger(__name__)
from typing import Any
import httpx

PAYOS_API_URL = "https://api-merchant.payos.vn/v2/payment-requests"

from src.cores.settings import PAYOS_API_KEY, PAYOS_CHECKSUM_KEY, PAYOS_CLIENT_ID

class PayOSClient:
    def __init__(
        self, 
        client_id: str = PAYOS_CLIENT_ID,
        api_key: str = PAYOS_API_KEY,
        checksum_key: str = PAYOS_CHECKSUM_KEY
    ):
        self.client_id = client_id
        self.api_key = api_key
        self.checksum_key = checksum_key

    def _create_signature(self, data: dict[str, Any]) -> str:
        """Ký HMAC-SHA256 theo chuẩn PayOS: sắp xếp key alphabet: amount=...&cancelUrl=..."""
        sorted_keys = sorted(data.keys())
        query_string = "&".join(
            f"{k}={data[k]}"
            for k in sorted_keys
            if data[k] is not None
        )
        return hmac.new(
            self.checksum_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def create_payment_link(
        self,
        order_code: int,
        amount: int,
        description: str,
        return_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Gọi API PayOS tạo link thanh toán VietQR."""
        if not (self.client_id and self.api_key and self.checksum_key):
            raise RuntimeError("PayOS credentials are not configured (PAYOS_CLIENT_ID/PAYOS_API_KEY/PAYOS_CHECKSUM_KEY)")
        clean_desc = description[:25]  # PayOS giới hạn 25 ký tự
        payload_to_sign = {
            "amount": amount,
            "cancelUrl": cancel_url,
            "description": clean_desc,
            "orderCode": order_code,
            "returnUrl": return_url,
        }
        signature = self._create_signature(payload_to_sign)
        body = {
            **payload_to_sign,
            "signature": signature,
        }
        headers = {
            "x-client-id": self.client_id,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(PAYOS_API_URL, json=body, headers=headers)
                try:
                    data = response.json()
                except ValueError as exc:
                    logger.error("PayOS returned non-JSON response (status=%s)", response.status_code)
                    raise RuntimeError("PayOS returned an invalid (non-JSON) response") from exc
                if response.status_code != 200 or data.get("code") != "00":
                    logger.error("PayOS Error Response: %s", data)
                    raise RuntimeError(f"PayOS error: {data.get('desc', 'Unknown error')}")
                return data["data"]
            except httpx.RequestError as exc:
                logger.error("Failed to connect to PayOS: %s", exc)
                raise RuntimeError(f"Cannot connect to PayOS gateway: {exc}") from exc
                
    async def cancel_payment_link(
        self,
        order_code_or_id: int | str,
        cancellation_reason: str = "Khách hàng hủy đơn",
    ) -> dict[str, Any]:
        """Gọi API PayOS hủy link thanh toán."""
        if not (self.client_id and self.api_key and self.checksum_key):
            raise RuntimeError("PayOS credentials are not configured (PAYOS_CLIENT_ID/PAYOS_API_KEY/PAYOS_CHECKSUM_KEY)")
        url = f"https://api-merchant.payos.vn/v2/payment-requests/{order_code_or_id}/cancel"
        headers = {
            "x-client-id": self.client_id,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        body = {
            "cancellationReason": cancellation_reason,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=body, headers=headers)
                try:
                    data = response.json()
                except ValueError:
                    logger.warning("PayOS Cancel returned non-JSON response (status=%s)", response.status_code)
                    return {}
                if response.status_code != 200 or data.get("code") != "00":
                    logger.warning("PayOS Cancel Response: %s", data)
                return data.get("data", {})
            except httpx.RequestError as exc:
                logger.error("Failed to cancel payment link on PayOS: %s", exc)
                return {}

    def verify_webhook_signature(self, webhook_data: dict[str, Any], signature: str) -> bool:
        """Xác thực chữ ký số webhook HMAC-SHA256 gửi từ PayOS."""
        if not self.checksum_key:
            logger.error("PAYOS_CHECKSUM_KEY is not configured")
            return False
        sorted_keys = sorted(webhook_data.keys())
        parts = []
        for key in sorted_keys:
            val = webhook_data[key]
            if val is None:
                val_str = ""
            elif isinstance(val, (int, float, bool)):
                val_str = str(val)
            elif isinstance(val, str):
                val_str = val
            else:
                continue  # bỏ qua nested list/dict
            parts.append(f"{key}={val_str}")
        query_string = "&".join(parts)
        expected_signature = hmac.new(
            self.checksum_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)


payos_client = PayOSClient()

