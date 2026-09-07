import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import uvicorn

print("Generating temporary RSA key pair for demo...")
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = private_key.public_key()

pem_priv = private_key.private_bytes(
    encoding=serialization.Encoding.PEM, 
    format=serialization.PrivateFormat.PKCS8, 
    encryption_algorithm=serialization.NoEncryption()
)
pem_pub = public_key.public_bytes(
    encoding=serialization.Encoding.PEM, 
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Tạo JWT token
stu_payload = {'sub': '1', 'email': 'student@example.com', 'roles': ['STUDENT']}
tea_payload = {'sub': '2', 'email': 'teacher@example.com', 'roles': ['TEACHER']}

stu_token = jwt.encode(stu_payload, pem_priv, algorithm='RS256')
tea_token = jwt.encode(tea_payload, pem_priv, algorithm='RS256')

print("\n" + "="*50)
print("🔑 COPY CÁC TOKEN NÀY ĐỂ DÙNG TRONG SWAGGER UI 🔑")
print("="*50)
print("\n[HỌC VIÊN - STUDENT TOKEN]")
print(stu_token)
print("\n[GIẢNG VIÊN - TEACHER TOKEN]")
print(tea_token)
print("\n" + "="*50)
print("Khởi động server với Public Key tạm thời (không sửa code thật)...\n")

# Chèn Public Key vào bộ nhớ (Monkey-patch)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.jwk_service import PublicKeyService
PublicKeyService._FALLBACK_KEY = pem_pub.decode()

# Khởi chạy FastAPI
if __name__ == "__main__":
    uvicorn.run("src.app:app", host="0.0.0.0", port=4000, reload=False)
