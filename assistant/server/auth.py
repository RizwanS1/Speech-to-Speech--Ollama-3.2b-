from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from assistant.server.config import get_settings
from assistant.server.db import get_db
from assistant.server.models import User
from assistant.server.rate_limit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
password_hash = PasswordHash.recommended()
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


class UserRegistration(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=1024)


class UserResponse(BaseModel):
    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _create_access_token(user_id: int) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_user_id(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise InvalidTokenError("Token subject is missing.")
        return int(subject)
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise credentials_exception from exc


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> User:
    user_id = _decode_user_id(token)
    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    request.state.user_id = user.id
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    registration: UserRegistration,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    hashed_password = await run_in_threadpool(password_hash.hash, registration.password)
    user = User(
        username=registration.username,
        hashed_password=hashed_password,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already registered.",
        ) from exc
    await db.refresh(user)
    return UserResponse(id=user.id, username=user.username)


@router.post(
    "/token",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(max_requests=1, window_seconds=10, per_user=False))],
)
async def issue_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    verified = await run_in_threadpool(password_hash.verify, form.password, user.hashed_password)
    if not verified:
        raise credentials_exception
    return TokenResponse(access_token=_create_access_token(user.id))
