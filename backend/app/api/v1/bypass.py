"""WAF/编码绕过 API"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal
from app.modules import bypass

router = APIRouter()


class UrlEncodeRequest(BaseModel):
    text: str
    level: int = 1
    encode_all: bool = False


class UrlDecodeRequest(BaseModel):
    text: str
    level: int = 1


class HtmlEntityRequest(BaseModel):
    text: str
    mode: Literal['decimal', 'hex', 'named'] = 'decimal'
    padding: int = 0


class JsEscapeRequest(BaseModel):
    text: str
    mode: Literal['octal', 'hex', 'unicode'] = 'hex'


class CaseTransformRequest(BaseModel):
    text: str
    mode: Literal['upper', 'lower', 'random', 'alternate'] = 'random'


class SqlBypassRequest(BaseModel):
    text: str
    technique: Literal['comment', 'hex', 'char'] = 'comment'
    db_type: Literal['mysql', 'mssql', 'oracle'] = 'mysql'


class SpaceBypassRequest(BaseModel):
    text: str
    mode: Literal['comment', 'tab', 'newline', 'plus', 'parenthesis'] = 'comment'


class GenerateAllRequest(BaseModel):
    text: str


# ==================== URL 编码 ====================
@router.post("/url/encode")
async def url_encode(req: UrlEncodeRequest):
    """URL 编码（支持多层）"""
    return {"result": bypass.url_encode(req.text, req.level, req.encode_all)}


@router.post("/url/decode")
async def url_decode(req: UrlDecodeRequest):
    """URL 解码（支持多层）"""
    return {"result": bypass.url_decode(req.text, req.level)}


# ==================== HTML 实体编码 ====================
@router.post("/html/encode")
async def html_entity_encode(req: HtmlEntityRequest):
    """HTML 实体编码"""
    return {"result": bypass.html_entity_encode(req.text, req.mode, req.padding)}


class TextRequest(BaseModel):
    text: str


@router.post("/html/decode")
async def html_decode(req: TextRequest):
    """HTML 实体解码"""
    return {"result": bypass.html_entity_decode(req.text)}


# ==================== JavaScript 编码 ====================
@router.post("/js/encode")
async def js_escape(req: JsEscapeRequest):
    """JavaScript 转义编码"""
    return {"result": bypass.js_escape(req.text, req.mode)}


@router.post("/js/decode")
async def js_unescape(req: TextRequest):
    """JavaScript 转义解码"""
    return {"result": bypass.js_unescape(req.text)}


# ==================== 大小写变形 ====================
@router.post("/case/transform")
async def case_transform(req: CaseTransformRequest):
    """大小写变形"""
    return {"result": bypass.case_transform(req.text, req.mode)}


# ==================== SQL 绕过 ====================
@router.post("/sql/bypass")
async def sql_bypass(req: SqlBypassRequest):
    """SQL 注入绕过"""
    if req.technique == 'comment':
        result = bypass.sql_comment_bypass(req.text)
    elif req.technique == 'hex':
        result = bypass.hex_encode_sql(req.text)
    elif req.technique == 'char':
        result = bypass.char_encode_sql(req.text, req.db_type)
    else:
        result = req.text
    return {"result": result}


# ==================== 空格绕过 ====================
@router.post("/space/bypass")
async def space_bypass(req: SpaceBypassRequest):
    """空格绕过"""
    return {"result": bypass.space_bypass(req.text, req.mode)}


# ==================== 一键生成所有编码 ====================
@router.post("/generate-all")
async def generate_all(req: GenerateAllRequest):
    """生成所有常用编码形式"""
    return {"results": bypass.generate_all_encodings(req.text)}


# ==================== Payload 模板 ====================
@router.get("/templates")
async def get_templates():
    """获取常用 Payload 模板"""
    return {"templates": bypass.PAYLOAD_TEMPLATES}


@router.post("/template/encode")
async def encode_template(template_name: str, encoding: str = 'url'):
    """对模板进行编码"""
    if template_name not in bypass.PAYLOAD_TEMPLATES:
        return {"error": "Template not found"}
    
    payload = bypass.PAYLOAD_TEMPLATES[template_name]
    
    encoding_map = {
        'url': lambda t: bypass.url_encode(t),
        'double_url': lambda t: bypass.url_encode(t, level=2),
        'html_decimal': lambda t: bypass.html_entity_encode(t, 'decimal'),
        'html_hex': lambda t: bypass.html_entity_encode(t, 'hex'),
        'js_hex': lambda t: bypass.js_escape(t, 'hex'),
        'js_unicode': lambda t: bypass.js_escape(t, 'unicode'),
    }
    
    encoder = encoding_map.get(encoding, encoding_map['url'])
    return {
        "original": payload,
        "encoded": encoder(payload)
    }

