"""安全工具路由"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from pydantic import BaseModel

from ...database import get_db
from ...models import User, Favorite, ToolHistory
from ...schemas import FavoriteCreate, FavoriteResponse, ToolHistoryCreate, ToolHistoryResponse
from ...api.deps import get_current_user, get_optional_user
from ...modules import encoding, crypto, hash_tools, jwt_tool, network, format_tools

router = APIRouter()


# ==================== 收藏 ====================

@router.get("/favorites", response_model=List[FavoriteResponse])
async def get_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取收藏工具列表"""
    result = await db.execute(
        select(Favorite)
        .where(Favorite.user_id == current_user.id)
        .order_by(Favorite.sort_order)
    )
    return result.scalars().all()


@router.post("/favorites", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    favorite_in: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """收藏工具"""
    # 检查是否已收藏
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.tool_key == favorite_in.tool_key
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="已收藏该工具")
    
    favorite = Favorite(
        user_id=current_user.id,
        tool_key=favorite_in.tool_key,
        sort_order=favorite_in.sort_order
    )
    db.add(favorite)
    await db.flush()
    await db.refresh(favorite)
    return favorite


@router.delete("/favorites/{tool_key}")
async def remove_favorite(
    tool_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消收藏"""
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.tool_key == tool_key
        )
    )
    favorite = result.scalar_one_or_none()
    
    if not favorite:
        raise HTTPException(status_code=404, detail="未收藏该工具")
    
    await db.delete(favorite)
    return {"message": "取消收藏成功"}


# ==================== 历史记录 ====================

@router.get("/history", response_model=List[ToolHistoryResponse])
async def get_history(
    tool_key: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取工具使用历史"""
    query = select(ToolHistory).where(ToolHistory.user_id == current_user.id)
    
    if tool_key:
        query = query.where(ToolHistory.tool_key == tool_key)
    
    query = query.order_by(ToolHistory.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/history", response_model=ToolHistoryResponse, status_code=status.HTTP_201_CREATED)
async def add_history(
    history_in: ToolHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """添加工具使用历史"""
    import json
    
    history = ToolHistory(
        user_id=current_user.id,
        tool_key=history_in.tool_key,
        input_data=json.dumps(history_in.input_data) if history_in.input_data else None,
        output_data=json.dumps(history_in.output_data) if history_in.output_data else None
    )
    db.add(history)
    await db.flush()
    await db.refresh(history)
    return history


@router.delete("/history")
async def clear_history(
    tool_key: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清除历史记录"""
    query = delete(ToolHistory).where(ToolHistory.user_id == current_user.id)
    
    if tool_key:
        query = query.where(ToolHistory.tool_key == tool_key)
    
    await db.execute(query)
    return {"message": "清除成功"}


# ==================== 编码工具 ====================

class EncodeRequest(BaseModel):
    text: str
    encoding: str = "utf-8"


@router.post("/encoding/base64/encode")
async def base64_encode(req: EncodeRequest):
    """Base64 编码"""
    return {"result": encoding.base64_encode(req.text)}


@router.post("/encoding/base64/decode")
async def base64_decode(req: EncodeRequest):
    """Base64 解码"""
    return {"result": encoding.base64_decode(req.text)}


@router.post("/encoding/url/encode")
async def url_encode(req: EncodeRequest):
    """URL 编码"""
    return {"result": encoding.url_encode(req.text)}


@router.post("/encoding/url/decode")
async def url_decode(req: EncodeRequest):
    """URL 解码"""
    return {"result": encoding.url_decode(req.text)}


@router.post("/encoding/html/encode")
async def html_encode(req: EncodeRequest):
    """HTML 实体编码"""
    return {"result": encoding.html_encode(req.text)}


@router.post("/encoding/html/decode")
async def html_decode(req: EncodeRequest):
    """HTML 实体解码"""
    return {"result": encoding.html_decode(req.text)}


@router.post("/encoding/hex/encode")
async def hex_encode(req: EncodeRequest):
    """Hex 编码"""
    return {"result": encoding.hex_encode(req.text)}


@router.post("/encoding/hex/decode")
async def hex_decode(req: EncodeRequest):
    """Hex 解码"""
    return {"result": encoding.hex_decode(req.text)}


@router.post("/encoding/unicode/encode")
async def unicode_encode(req: EncodeRequest):
    """Unicode 编码"""
    return {"result": encoding.unicode_encode(req.text)}


@router.post("/encoding/unicode/decode")
async def unicode_decode(req: EncodeRequest):
    """Unicode 解码"""
    return {"result": encoding.unicode_decode(req.text)}


# ==================== 哈希工具 ====================

class HashRequest(BaseModel):
    text: str
    algorithm: str = "md5"


@router.post("/hash/calculate")
async def calculate_hash(req: HashRequest):
    """计算哈希值"""
    return {"result": hash_tools.calculate_hash(req.text, req.algorithm)}


@router.post("/hash/all")
async def calculate_all_hashes(req: HashRequest):
    """计算所有哈希值"""
    return {"result": hash_tools.calculate_all_hashes(req.text)}


# ==================== 加密工具 ====================

class CryptoRequest(BaseModel):
    text: str
    key: str
    iv: Optional[str] = None
    algorithm: str = "aes-256-cbc"


@router.post("/crypto/aes/encrypt")
async def aes_encrypt(req: CryptoRequest):
    """AES 加密"""
    return {"result": crypto.aes_encrypt(req.text, req.key, req.iv)}


@router.post("/crypto/aes/decrypt")
async def aes_decrypt(req: CryptoRequest):
    """AES 解密"""
    return {"result": crypto.aes_decrypt(req.text, req.key, req.iv)}


class RSAKeyGenRequest(BaseModel):
    key_size: int = 2048


@router.post("/crypto/rsa/generate")
async def rsa_generate_keys(req: RSAKeyGenRequest):
    """生成 RSA 密钥对"""
    return crypto.rsa_generate_keys(req.key_size)


class RSARequest(BaseModel):
    text: str
    key: str


@router.post("/crypto/rsa/encrypt")
async def rsa_encrypt(req: RSARequest):
    """RSA 加密"""
    return {"result": crypto.rsa_encrypt(req.text, req.key)}


@router.post("/crypto/rsa/decrypt")
async def rsa_decrypt(req: RSARequest):
    """RSA 解密"""
    return {"result": crypto.rsa_decrypt(req.text, req.key)}


# ==================== JWT 工具 ====================

class JWTDecodeRequest(BaseModel):
    token: str


class JWTEncodeRequest(BaseModel):
    payload: dict
    secret: str
    algorithm: str = "HS256"


@router.post("/jwt/decode")
async def jwt_decode(req: JWTDecodeRequest):
    """JWT 解码"""
    return jwt_tool.decode_jwt(req.token)


@router.post("/jwt/encode")
async def jwt_encode(req: JWTEncodeRequest):
    """JWT 编码"""
    return {"result": jwt_tool.encode_jwt(req.payload, req.secret, req.algorithm)}


@router.post("/jwt/verify")
async def jwt_verify(token: str, secret: str):
    """JWT 验证"""
    return jwt_tool.verify_jwt(token, secret)


# ==================== 密码工具 ====================

class PasswordGenRequest(BaseModel):
    length: int = 16
    uppercase: bool = True
    lowercase: bool = True
    digits: bool = True
    special: bool = True


@router.post("/password/generate")
async def generate_password(req: PasswordGenRequest):
    """生成随机密码"""
    return {"result": crypto.generate_password(
        req.length, req.uppercase, req.lowercase, req.digits, req.special
    )}


class PasswordStrengthRequest(BaseModel):
    password: str


@router.post("/password/strength")
async def check_password_strength(req: PasswordStrengthRequest):
    """检查密码强度"""
    return crypto.check_password_strength(req.password)


# ==================== 格式工具 ====================

class FormatRequest(BaseModel):
    text: str


@router.post("/format/json")
async def format_json(req: FormatRequest):
    """JSON 格式化"""
    return {"result": format_tools.format_json(req.text)}


@router.post("/format/xml")
async def format_xml(req: FormatRequest):
    """XML 格式化"""
    return {"result": format_tools.format_xml(req.text)}


class ConvertRequest(BaseModel):
    text: str
    from_format: str
    to_format: str


@router.post("/format/convert")
async def convert_format(req: ConvertRequest):
    """格式转换"""
    return {"result": format_tools.convert_format(req.text, req.from_format, req.to_format)}


class RegexRequest(BaseModel):
    pattern: str
    text: str
    flags: str = ""


@router.post("/format/regex/test")
async def test_regex(req: RegexRequest):
    """正则表达式测试"""
    return format_tools.test_regex(req.pattern, req.text, req.flags)


class DiffRequest(BaseModel):
    text1: str
    text2: str


@router.post("/format/diff")
async def text_diff(req: DiffRequest):
    """文本对比"""
    return {"result": format_tools.text_diff(req.text1, req.text2)}


# ==================== 网络工具 ====================

class DNSRequest(BaseModel):
    domain: str
    record_type: str = "A"


@router.post("/network/dns")
async def dns_lookup(req: DNSRequest):
    """DNS 查询"""
    return await network.dns_lookup(req.domain, req.record_type)


class WhoisRequest(BaseModel):
    domain: str


@router.post("/network/whois")
async def whois_lookup(req: WhoisRequest):
    """WHOIS 查询"""
    return await network.whois_lookup(req.domain)


class IPRequest(BaseModel):
    ip: str


@router.post("/network/ip/info")
async def ip_info(req: IPRequest):
    """IP 信息查询"""
    return await network.ip_info(req.ip)


class AnalyzeRequest(BaseModel):
    target: str


@router.post("/network/analyze")
async def analyze_target(req: AnalyzeRequest):
    """综合分析目标（支持 URL、域名、IP）"""
    return await network.analyze_target(req.target)


# ==================== 其他工具 ====================

class TimestampRequest(BaseModel):
    timestamp: Optional[int] = None
    datetime_str: Optional[str] = None
    format: str = "%Y-%m-%d %H:%M:%S"


@router.post("/misc/timestamp")
async def convert_timestamp(req: TimestampRequest):
    """时间戳转换"""
    return format_tools.convert_timestamp(req.timestamp, req.datetime_str, req.format)


class BaseConvertRequest(BaseModel):
    value: str
    from_base: int
    to_base: int


@router.post("/misc/base-convert")
async def base_convert(req: BaseConvertRequest):
    """进制转换"""
    return {"result": format_tools.base_convert(req.value, req.from_base, req.to_base)}


@router.post("/misc/uuid")
async def generate_uuid():
    """生成 UUID"""
    return format_tools.generate_uuid()

