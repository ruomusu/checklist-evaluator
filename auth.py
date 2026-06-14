"""
JWT 认证模块
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from storage import verify_user, get_user

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时

# Bearer Token
security = HTTPBearer()


def create_access_token(data: dict) -> str:
    """
    创建 JWT Token

    Args:
        data: 要包含在 Token 中的数据

    Returns:
        str: JWT Token 字符串
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    验证 Token 并返回载荷

    Args:
        token: JWT Token 字符串

    Returns:
        dict: Token 载荷

    Raises:
        HTTPException: Token 无效或过期
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 Token",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期或无效",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    获取当前登录用户

    Args:
        credentials: HTTP Bearer 凭证

    Returns:
        dict: 用户信息

    Raises:
        HTTPException: Token 无效或用户不存在
    """
    token = credentials.credentials
    payload = verify_token(token)
    username = payload.get("sub")

    user = get_user(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[dict]:
    """
    可选的获取当前用户（未登录也返回 None）

    Args:
        credentials: HTTP Bearer 凭证

    Returns:
        dict: 用户信息，未登录返回 None
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None