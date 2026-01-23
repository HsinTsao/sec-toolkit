"""哈希工具模块"""
import hashlib
import hmac


def calculate_hash(text: str, algorithm: str = "md5") -> str:
    """计算哈希值"""
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha224": hashlib.sha224,
        "sha256": hashlib.sha256,
        "sha384": hashlib.sha384,
        "sha512": hashlib.sha512,
        "sha3_224": hashlib.sha3_224,
        "sha3_256": hashlib.sha3_256,
        "sha3_384": hashlib.sha3_384,
        "sha3_512": hashlib.sha3_512,
    }
    
    algorithm = algorithm.lower().replace("-", "_")
    
    if algorithm not in algorithms:
        return f"错误: 不支持的算法 {algorithm}"
    
    try:
        hash_func = algorithms[algorithm]
        return hash_func(text.encode('utf-8')).hexdigest()
    except Exception as e:
        return f"错误: {str(e)}"


def calculate_all_hashes(text: str) -> dict:
    """计算所有常用哈希值"""
    algorithms = ["md5", "sha1", "sha256", "sha384", "sha512"]
    result = {}
    
    for algo in algorithms:
        result[algo] = calculate_hash(text, algo)
    
    return result


def calculate_hmac(text: str, key: str, algorithm: str = "sha256") -> str:
    """计算 HMAC"""
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    
    algorithm = algorithm.lower()
    
    if algorithm not in algorithms:
        return f"错误: 不支持的算法 {algorithm}"
    
    try:
        return hmac.new(
            key.encode('utf-8'),
            text.encode('utf-8'),
            algorithms[algorithm]
        ).hexdigest()
    except Exception as e:
        return f"错误: {str(e)}"


def hash_file_content(content: bytes, algorithm: str = "sha256") -> str:
    """计算文件内容的哈希值"""
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    
    algorithm = algorithm.lower()
    
    if algorithm not in algorithms:
        return f"错误: 不支持的算法 {algorithm}"
    
    try:
        return algorithms[algorithm](content).hexdigest()
    except Exception as e:
        return f"错误: {str(e)}"


def compare_hash(text: str, expected_hash: str, algorithm: str = "auto") -> dict:
    """比较哈希值"""
    # 自动检测算法
    if algorithm == "auto":
        hash_length = len(expected_hash)
        if hash_length == 32:
            algorithm = "md5"
        elif hash_length == 40:
            algorithm = "sha1"
        elif hash_length == 64:
            algorithm = "sha256"
        elif hash_length == 128:
            algorithm = "sha512"
        else:
            return {"match": False, "error": "无法自动检测哈希算法"}
    
    calculated = calculate_hash(text, algorithm)
    
    return {
        "match": calculated.lower() == expected_hash.lower(),
        "algorithm": algorithm,
        "calculated": calculated,
        "expected": expected_hash
    }

