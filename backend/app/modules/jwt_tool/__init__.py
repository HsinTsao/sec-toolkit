"""JWT 工具模块"""
import base64
import json
from jose import jwt, JWTError
from datetime import datetime


def decode_jwt(token: str) -> dict:
    """解码 JWT (不验证签名)"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {"error": "无效的 JWT 格式"}
        
        # 解码 header
        header_data = parts[0]
        # 补全 padding
        header_data += '=' * (4 - len(header_data) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_data))
        
        # 解码 payload
        payload_data = parts[1]
        payload_data += '=' * (4 - len(payload_data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_data))
        
        # 检查过期时间
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


def encode_jwt(payload: dict, secret: str, algorithm: str = "HS256") -> str:
    """编码 JWT"""
    try:
        token = jwt.encode(payload, secret, algorithm=algorithm)
        return token
    except Exception as e:
        return f"错误: {str(e)}"


def verify_jwt(token: str, secret: str, algorithms: list = None) -> dict:
    """验证 JWT"""
    if algorithms is None:
        algorithms = ["HS256", "HS384", "HS512"]
    
    try:
        payload = jwt.decode(token, secret, algorithms=algorithms)
        return {
            "valid": True,
            "payload": payload
        }
    except JWTError as e:
        return {
            "valid": False,
            "error": str(e)
        }


def get_jwt_algorithms() -> list:
    """获取支持的 JWT 算法列表"""
    return [
        {"name": "HS256", "description": "HMAC using SHA-256"},
        {"name": "HS384", "description": "HMAC using SHA-384"},
        {"name": "HS512", "description": "HMAC using SHA-512"},
        {"name": "RS256", "description": "RSA using SHA-256"},
        {"name": "RS384", "description": "RSA using SHA-384"},
        {"name": "RS512", "description": "RSA using SHA-512"},
        {"name": "ES256", "description": "ECDSA using P-256 and SHA-256"},
        {"name": "ES384", "description": "ECDSA using P-384 and SHA-384"},
        {"name": "ES512", "description": "ECDSA using P-521 and SHA-512"},
    ]

