"""JWT 工具模块"""
import base64
import json
from jose import jwt, JWTError
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization


SYMMETRIC_ALGORITHMS = {"HS256", "HS384", "HS512"}
RSA_ALGORITHMS = {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512"}
EC_ALGORITHMS = {"ES256", "ES384", "ES512"}
ASYMMETRIC_ALGORITHMS = RSA_ALGORITHMS | EC_ALGORITHMS

EC_CURVE_MAP = {
    "ES256": ec.SECP256R1(),
    "ES384": ec.SECP384R1(),
    "ES512": ec.SECP521R1(),
}


def is_asymmetric(algorithm: str) -> bool:
    return algorithm in ASYMMETRIC_ALGORITHMS


def decode_jwt(token: str) -> dict:
    """解码 JWT (不验证签名)"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {"error": "无效的 JWT 格式"}
        
        header_data = parts[0]
        header_data += '=' * (4 - len(header_data) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_data))
        
        payload_data = parts[1]
        payload_data += '=' * (4 - len(payload_data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_data))
        
        exp = payload.get('exp')
        iat = payload.get('iat')
        nbf = payload.get('nbf')
        
        expiration_info = {}
        if exp:
            exp_time = datetime.fromtimestamp(exp)
            expiration_info['exp'] = exp_time.isoformat()
            expiration_info['expired'] = datetime.utcnow().timestamp() > exp
        
        if iat:
            expiration_info['iat'] = datetime.fromtimestamp(iat).isoformat()
        
        if nbf:
            expiration_info['nbf'] = datetime.fromtimestamp(nbf).isoformat()
        
        return {
            "header": header,
            "payload": payload,
            "signature": parts[2],
            "expiration": expiration_info
        }
    except Exception as e:
        return {"error": str(e)}


def encode_jwt(payload: dict, secret: str, algorithm: str = "HS256", header: dict = None) -> str:
    """编码 JWT，支持对称和非对称算法。非对称算法时 secret 应传入 PEM 格式私钥。"""
    try:
        # 将用户自定义 header 中除 alg/typ 外的字段作为额外 headers 传入
        extra_headers = None
        if header:
            extra_headers = {k: v for k, v in header.items() if k not in ("alg", "typ")}
            if not extra_headers:
                extra_headers = None
        token = jwt.encode(payload, secret, algorithm=algorithm, headers=extra_headers)
        return token
    except Exception as e:
        return f"错误: {str(e)}"


def verify_jwt(token: str, key: str, algorithm: str = "HS256") -> dict:
    """验证 JWT。对称算法传 secret，非对称算法传 PEM 格式公钥。"""
    try:
        payload = jwt.decode(token, key, algorithms=[algorithm])
        return {
            "valid": True,
            "payload": payload
        }
    except JWTError as e:
        return {
            "valid": False,
            "error": str(e)
        }


def generate_rsa_keypair(key_size: int = 2048) -> dict:
    """生成 RSA 密钥对，返回 PEM 格式"""
    try:
        if key_size not in (2048, 3072, 4096):
            return {"error": "密钥长度仅支持 2048、3072、4096"}
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode('utf-8')
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('utf-8')
        
        return {"private_key": private_pem, "public_key": public_pem}
    except Exception as e:
        return {"error": str(e)}


def generate_ec_keypair(algorithm: str = "ES256") -> dict:
    """根据算法生成对应的 EC 密钥对，返回 PEM 格式"""
    try:
        curve = EC_CURVE_MAP.get(algorithm)
        if not curve:
            return {"error": f"不支持的 EC 算法: {algorithm}"}
        
        private_key = ec.generate_private_key(curve)
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode('utf-8')
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('utf-8')
        
        return {"private_key": private_pem, "public_key": public_pem}
    except Exception as e:
        return {"error": str(e)}


def get_jwt_algorithms() -> list:
    """获取支持的 JWT 算法列表"""
    return [
        {"name": "HS256", "type": "symmetric", "description": "HMAC using SHA-256"},
        {"name": "HS384", "type": "symmetric", "description": "HMAC using SHA-384"},
        {"name": "HS512", "type": "symmetric", "description": "HMAC using SHA-512"},
        {"name": "RS256", "type": "RSA", "description": "RSA using SHA-256"},
        {"name": "RS384", "type": "RSA", "description": "RSA using SHA-384"},
        {"name": "RS512", "type": "RSA", "description": "RSA using SHA-512"},
        {"name": "PS256", "type": "RSA", "description": "RSA-PSS using SHA-256"},
        {"name": "PS384", "type": "RSA", "description": "RSA-PSS using SHA-384"},
        {"name": "PS512", "type": "RSA", "description": "RSA-PSS using SHA-512"},
        {"name": "ES256", "type": "EC", "description": "ECDSA using P-256 and SHA-256"},
        {"name": "ES384", "type": "EC", "description": "ECDSA using P-384 and SHA-384"},
        {"name": "ES512", "type": "EC", "description": "ECDSA using P-521 and SHA-512"},
    ]

