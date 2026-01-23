"""用户路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ...database import get_db
from ...models import User
from ...schemas import UserResponse, UserUpdate
from ...api.deps import get_current_user
from ...utils.security import hash_password, verify_password

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    user_dict = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "avatar": current_user.avatar,
        "is_active": current_user.is_active,
        "settings": json.loads(current_user.settings) if current_user.settings else {},
        "created_at": current_user.created_at,
    }
    return UserResponse(**user_dict)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户信息"""
    if user_in.username is not None:
        current_user.username = user_in.username
    if user_in.avatar is not None:
        current_user.avatar = user_in.avatar
    if user_in.settings is not None:
        current_user.settings = json.dumps(user_in.settings)
    
    await db.flush()
    await db.refresh(current_user)
    
    user_dict = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "avatar": current_user.avatar,
        "is_active": current_user.is_active,
        "settings": json.loads(current_user.settings) if current_user.settings else {},
        "created_at": current_user.created_at,
    }
    return UserResponse(**user_dict)


@router.patch("/me/password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
    
    current_user.password_hash = hash_password(new_password)
    await db.flush()
    
    return {"message": "密码修改成功"}

