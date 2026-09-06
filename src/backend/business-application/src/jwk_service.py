import logging
from src.grpc.client import AuthGrpcClient
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
)

class PublicKeyService:
    _public_key: str | None = None

    _FALLBACK_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAgIbaK/750rUs0CVcPswK
mJTVu6i3gHeUNQrpTSBlSRayGt9teX9CQuzaTRNfUzmlJkhn7SzOEORjDCP+4qqr
IbKy/Ded9Ch8VboEfeXp9+yz5Sp/8LvWhhmisyax9DRGIRIsm9va7aBptQqFGlsa
oNEsKmAPc17elPP2/tr5Ni9wjiuPmPoo/0m+FFsG0JAeVhwAH8ep860dVtOViFMK
wa9kdITJEi8L+5tZE/eqjlXVY0jyQsd5A9QEigad4WKezlUDrZfYcXHw59CUQmiU
0Ny4LKg/7ovARgqyoTpaKP4H3SdiCCqP+UbT0hS9E0j5mhbdZ5ZouC9fDZSfG3XV
kwIDAQAB
-----END PUBLIC KEY-----"""

    @classmethod
    async def load(cls , client : AuthGrpcClient):
        try: 
            response = await client.public_key() 
            cls._public_key = response 
            logger.info("Public key has been loaded successfully %s" , response)

        except Exception:
            logger.warning("Failed to load public key. Using fallback.")
            cls._public_key = cls._FALLBACK_KEY
    @classmethod
    def get(cls) -> str:
        if cls._public_key is None:
            raise RuntimeError("JWT public key has not been loaded.")

        return cls._public_key