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

MINIO_URL = get_env_var('MINIO_URL')
MINIO_ACCESS_KEY = get_env_var('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = get_env_var('MINIO_SECRET_KEY')
MINIO_BUCKET_NAME = get_env_var('MINIO_BUCKET_NAME')
MINIO_PORT = get_env_var('MINIO_PORT')
