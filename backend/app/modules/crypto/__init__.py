"""加密/解密工具模块"""
import base64
import secrets
import string
import re
from Crypto.Cipher import AES, DES, DES3
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


def aes_encrypt(text: str, key: str, iv: str = None) -> str:
    """AES 加密 (CBC 模式)"""
    try:
        # 密钥处理 (补齐或截断到 16/24/32 字节)
        key_bytes = key.encode('utf-8')
        if len(key_bytes) <= 16:
            key_bytes = key_bytes.ljust(16, b'\0')
        elif len(key_bytes) <= 24:
            key_bytes = key_bytes.ljust(24, b'\0')
        else:
            key_bytes = key_bytes[:32].ljust(32, b'\0')
        
        # IV 处理
        if iv:
            iv_bytes = iv.encode('utf-8')[:16].ljust(16, b'\0')
        else:
            iv_bytes = get_random_bytes(16)
        
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        encrypted = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
        
        # 返回 Base64 编码的结果 (IV + 密文)
        result = base64.b64encode(iv_bytes + encrypted).decode('utf-8')
        return result
    except Exception as e:
        return f"错误: {str(e)}"


def aes_decrypt(ciphertext: str, key: str, iv: str = None) -> str:
    """AES 解密 (CBC 模式)"""
    try:
        # 密钥处理
        key_bytes = key.encode('utf-8')
        if len(key_bytes) <= 16:
            key_bytes = key_bytes.ljust(16, b'\0')
        elif len(key_bytes) <= 24:
            key_bytes = key_bytes.ljust(24, b'\0')
        else:
            key_bytes = key_bytes[:32].ljust(32, b'\0')
        
        # Base64 解码
        data = base64.b64decode(ciphertext)
        
        # 提取 IV 和密文
        if iv:
            iv_bytes = iv.encode('utf-8')[:16].ljust(16, b'\0')
            encrypted = data
        else:
            iv_bytes = data[:16]
            encrypted = data[16:]
        
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
        
        return decrypted.decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def des_encrypt(text: str, key: str) -> str:
    """DES 加密"""
    try:
        key_bytes = key.encode('utf-8')[:8].ljust(8, b'\0')
        iv = get_random_bytes(8)
        
        cipher = DES.new(key_bytes, DES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(text.encode('utf-8'), DES.block_size))
        
        return base64.b64encode(iv + encrypted).decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def des_decrypt(ciphertext: str, key: str) -> str:
    """DES 解密"""
    try:
        key_bytes = key.encode('utf-8')[:8].ljust(8, b'\0')
        data = base64.b64decode(ciphertext)
        
        iv = data[:8]
        encrypted = data[8:]
        
        cipher = DES.new(key_bytes, DES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(encrypted), DES.block_size)
        
        return decrypted.decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def rsa_generate_keys(key_size: int = 2048) -> dict:
    """生成 RSA 密钥对"""
    try:
        key = RSA.generate(key_size)
        private_key = key.export_key().decode('utf-8')
        public_key = key.publickey().export_key().decode('utf-8')
        
        return {
            "private_key": private_key,
            "public_key": public_key,
            "key_size": key_size
        }
    except Exception as e:
        return {"error": str(e)}


def rsa_encrypt(text: str, public_key: str) -> str:
    """RSA 加密"""
    try:
        key = RSA.import_key(public_key)
        cipher = PKCS1_OAEP.new(key)
        encrypted = cipher.encrypt(text.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def rsa_decrypt(ciphertext: str, private_key: str) -> str:
    """RSA 解密"""
    try:
        key = RSA.import_key(private_key)
        cipher = PKCS1_OAEP.new(key)
        decrypted = cipher.decrypt(base64.b64decode(ciphertext))
        return decrypted.decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def generate_password(
    length: int = 16,
    uppercase: bool = True,
    lowercase: bool = True,
    digits: bool = True,
    special: bool = True
) -> str:
    """生成随机密码，确保勾选的每种字符类型至少出现一次"""
    chars = ""
    required_chars = []  # 必须包含的字符（每种类型至少一个）
    
    if uppercase:
        chars += string.ascii_uppercase
        required_chars.append(secrets.choice(string.ascii_uppercase))
    if lowercase:
        chars += string.ascii_lowercase
        required_chars.append(secrets.choice(string.ascii_lowercase))
    if digits:
        chars += string.digits
        required_chars.append(secrets.choice(string.digits))
    if special:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        chars += special_chars
        required_chars.append(secrets.choice(special_chars))
    
    if not chars:
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    # 确保密码长度足够容纳所有必须的字符类型
    if length < len(required_chars):
        length = len(required_chars)
    
    # 剩余长度用随机字符填充
    remaining_length = length - len(required_chars)
    password_chars = required_chars + [secrets.choice(chars) for _ in range(remaining_length)]
    
    # 打乱顺序
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)


def check_password_strength(password: str) -> dict:
    """检查密码强度"""
    score = 0
    feedback = []
    
    # 长度检查
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("密码长度至少 8 位")
    
    if len(password) >= 12:
        score += 1
    
    if len(password) >= 16:
        score += 1
    
    # 大写字母
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        feedback.append("建议包含大写字母")
    
    # 小写字母
    if re.search(r'[a-z]', password):
        score += 1
    else:
        feedback.append("建议包含小写字母")
    
    # 数字
    if re.search(r'\d', password):
        score += 1
    else:
        feedback.append("建议包含数字")
    
    # 特殊字符
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        score += 1
    else:
        feedback.append("建议包含特殊字符")
    
    # 连续字符检查
    if re.search(r'(.)\1{2,}', password):
        score -= 1
        feedback.append("避免连续重复字符")
    
    # 常见弱密码检查
    weak_passwords = ['password', '123456', 'qwerty', 'admin', 'letmein']
    if password.lower() in weak_passwords:
        score = 0
        feedback.append("这是一个常见的弱密码")
    
    # 评级
    if score <= 2:
        strength = "弱"
        level = "weak"
    elif score <= 4:
        strength = "中等"
        level = "medium"
    elif score <= 6:
        strength = "强"
        level = "strong"
    else:
        strength = "非常强"
        level = "very_strong"
    
    return {
        "score": max(0, score),
        "max_score": 7,
        "strength": strength,
        "level": level,
        "feedback": feedback
    }

