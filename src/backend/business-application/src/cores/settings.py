import base64
import os 
from dotenv import load_dotenv 

load_dotenv() 

class _NoArg:
    """A sentinel value to indicate that a parameter was not given"""
    
NO_ARG = _NoArg()

def get_env_var(key:str , default : str | _NoArg = NO_ARG): 
    try: 
        return os.environ[key] 
    except KeyError: 
        if isinstance(default , _NoArg): 
            raise ValueError(f"Environment with key {key} is missing") 
    return default 

DATABASE_URL = get_env_var(
    "DATABASE_URL"
)
VERIFY_REGISTER_SECRET = get_env_var(
    "VERIFY_REGISTER_SECRET"
)
AUTH_PROVIDER_URL = get_env_var(
    "AUTH_PROVIDER_URL"
)
UPSTASH_REDIS_REST_URL = get_env_var('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_REST_TOKEN = get_env_var('UPSTASH_REDIS_REST_TOKEN')

RABBITMQ_URL = get_env_var('RABBITMQ_URL')
MAX_TESTCASE_FILE_SIZE_MB = int(get_env_var('MAX_TESTCASE_FILE_SIZE_MB', '5'))
FRONTEND_CHECKOUT_URL = get_env_var('FRONTEND_CHECKOUT_URL', 'http://localhost:5173/checkout')
FE_URL = get_env_var('FE_URL', 'http://localhost:5173')

MINIO_URL = get_env_var('MINIO_URL')
MINIO_ACCESS_KEY = get_env_var('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = get_env_var('MINIO_SECRET_KEY')
MINIO_BUCKET_NAME = get_env_var('MINIO_BUCKET_NAME')
MINIO_PORT = get_env_var('MINIO_PORT')

PAYOS_CLIENT_ID = get_env_var('PAYOS_CLIENT_ID', '')
PAYOS_API_KEY = get_env_var('PAYOS_API_KEY', '')
PAYOS_CHECKSUM_KEY = get_env_var('PAYOS_CHECKSUM_KEY', '')

_raw_jwt_public = get_env_var('JWT_ACCESS_PUBLIC', '')
if _raw_jwt_public:
    _stripped = _raw_jwt_public.strip()
    if _stripped.startswith("-----BEGIN"):
        JWT_ACCESS_PUBLIC = _stripped
    else:
        try:
            JWT_ACCESS_PUBLIC = base64.b64decode(_stripped).decode('utf-8')
        except Exception:
            JWT_ACCESS_PUBLIC = _stripped
else:
    JWT_ACCESS_PUBLIC = ""

